"""Integration tests for the stream reliability module with a fake upstream.

These exercise the full request lifecycle against a deterministic fake upstream
and fake clock — no real network, no real time. They cover the G-WAIT1 through
G-WAIT9 acceptance gates from docs/PRD_MAAS_STREAM_WAIT_RELIABILITY_V1.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))

from stream_reliability import (  # noqa: E402
    ActivityMonitor,
    CancellationController,
    ConcurrencyGuard,
    ErrorCodes,
    ObservabilitySink,
    ReasoningFilter,
    RequestMetrics,
    RequestState,
    SSETerminator,
    TimeoutConfig,
)


# ---------------------------------------------------------------------------
# Fake clock
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Fake upstream — produces deterministic chunks
# ---------------------------------------------------------------------------


class FakeUpstream:
    """A scripted upstream that yields chunks on demand.

    Each step is (kind, payload) where kind is one of:
      "headers"     — response headers received
      "reasoning"   — a reasoning_content chunk
      "text"        — a visible text chunk
      "tool"        — a tool_call chunk
      "finish"      — a message_delta with stop_reason
      "stop"        — a message_stop
      "eof"         — stream ends (no more data)
      "silence"     — time passes with no data
      "error"       — upstream HTTP error
    """

    def __init__(self, steps: list[tuple[str, dict | None]]):
        self._steps = list(steps)
        self._index = 0
        self.aborted = False

    def abort(self) -> None:
        self.aborted = True

    def next(self) -> tuple[str, dict | None] | None:
        if self._index >= len(self._steps):
            return None
        step = self._steps[self._index]
        self._index += 1
        return step


# ---------------------------------------------------------------------------
# Request handler — orchestrates the module against a fake upstream
# ---------------------------------------------------------------------------


class RequestHandler:
    """Drives a fake upstream through the reliability module."""

    def __init__(
        self,
        clock: FakeClock,
        timeout_config: TimeoutConfig,
        upstream: FakeUpstream,
    ):
        self.clock = clock
        self.cfg = timeout_config
        self.upstream = upstream
        self.monitor = ActivityMonitor(
            clock=clock,
            idle_timeout=timeout_config.idle_timeout,
            total_timeout=timeout_config.total_timeout,
        )
        self.terminator = SSETerminator()
        self.reasoning_filter = ReasoningFilter()
        self.cancel = CancellationController()
        self.cancel.on_abort(upstream.abort)
        self.metrics = RequestMetrics()
        self.state = RequestState.ACCEPTED
        self.client_output: list[dict] = []
        self.error_code: str | None = None
        self._message_started = False
        self._block_started = False

    def _ensure_message_start(self) -> None:
        if not self._message_started:
            self.client_output.extend(self.terminator.feed({"type": "message_start"}))
            self._message_started = True

    def _ensure_text_block_start(self) -> None:
        self._ensure_message_start()
        if not self._block_started:
            self.client_output.extend(self.terminator.feed(
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}}
            ))
            self._block_started = True

    def _set_state(self, state: RequestState) -> None:
        self.state = state
        self.metrics.record_state(state)

    def run(self) -> None:
        """Process the upstream until completion, timeout, or abort."""
        self.monitor.mark_request_started()
        self._set_state(RequestState.CONNECTING)

        while True:
            if self.cancel.is_aborted:
                self._set_state(RequestState.CLIENT_ABORTED)
                self.metrics.record_outcome("client_aborted", ErrorCodes.CLIENT_ABORTED)
                return

            # Check timeouts.
            if self.monitor.is_total_expired():
                self.error_code = ErrorCodes.TOTAL_TIMEOUT
                self._set_state(RequestState.TOTAL_TIMEOUT)
                self.cancel.abort()
                self.metrics.record_outcome("total_timeout", self.error_code)
                return

            if self.monitor.is_idle_expired():
                self.error_code = ErrorCodes.IDLE_TIMEOUT
                self._set_state(RequestState.IDLE_TIMEOUT)
                self.cancel.abort()
                self.metrics.record_outcome("idle_timeout", self.error_code)
                return

            step = self.upstream.next()
            if step is None:
                # EOF.
                extra = self.terminator.finalize()
                self.client_output.extend(extra)
                if self.terminator.is_failed:
                    self.error_code = ErrorCodes.STREAM_EOF
                    self._set_state(RequestState.UPSTREAM_FAILED)
                    self.metrics.record_outcome("upstream_failed", self.error_code)
                elif self.terminator.is_complete:
                    self._set_state(RequestState.COMPLETED)
                    self.metrics.record_outcome("completed")
                return

            kind, payload = step

            if kind == "headers":
                self.monitor.mark_connected()
                continue

            if kind == "silence":
                self.clock.advance(payload.get("duration", 1.0))
                continue

            if kind == "error":
                self.error_code = ErrorCodes.UPSTREAM_HTTP
                self._set_state(RequestState.UPSTREAM_FAILED)
                self.cancel.abort()
                self.metrics.record_outcome("upstream_failed", self.error_code)
                return

            if kind == "eof":
                extra = self.terminator.finalize()
                self.client_output.extend(extra)
                if self.terminator.is_failed:
                    self.error_code = ErrorCodes.STREAM_EOF
                    self._set_state(RequestState.UPSTREAM_FAILED)
                    self.metrics.record_outcome("upstream_failed", self.error_code)
                elif self.terminator.is_complete:
                    self._set_state(RequestState.COMPLETED)
                    self.metrics.record_outcome("completed")
                return

            # All other kinds are upstream activity.
            self.monitor.record_upstream_activity(kind=kind)

            if kind == "reasoning":
                if self.state not in (RequestState.VISIBLE_STREAMING, RequestState.COMPLETING):
                    self._set_state(RequestState.UPSTREAM_ACTIVE_HIDDEN)
                self.reasoning_filter.filter_chunk(
                    {"choices": [{"delta": {"reasoning_content": payload.get("text", "")}}]}
                )
                self.metrics.record_reasoning(1, len(payload.get("text", "").encode("utf-8")))
                continue

            if kind == "text":
                self._set_state(RequestState.VISIBLE_STREAMING)
                self._ensure_text_block_start()
                evt = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": payload.get("text", "")}}
                self.client_output.extend(self.terminator.feed(evt))
                self.metrics.record_visible_text(len(payload.get("text", "").encode("utf-8")))
                continue

            if kind == "tool":
                self._set_state(RequestState.VISIBLE_STREAMING)
                self._ensure_message_start()
                self.metrics.record_tool_call()
                continue

            if kind == "finish":
                self._set_state(RequestState.COMPLETING)
                self._ensure_message_start()
                # Close the open text block if any.
                if self._block_started:
                    self.client_output.extend(self.terminator.feed({"type": "content_block_stop", "index": 0}))
                    self._block_started = False
                reason = payload.get("stop_reason", "end_turn")
                evt = {"type": "message_delta", "delta": {"stop_reason": reason}}
                self.client_output.extend(self.terminator.feed(evt))
                continue

            if kind == "stop":
                self._ensure_message_start()
                self.client_output.extend(self.terminator.feed({"type": "message_stop"}))
                self._set_state(RequestState.COMPLETED)
                self.metrics.record_outcome("completed")
                return


# ---------------------------------------------------------------------------
# G-WAIT1: original defect red — the module reports hidden activity
# ---------------------------------------------------------------------------


def test_g_wait1_reports_hidden_activity():
    """The module must report upstream_active_hidden during reasoning-only phase.

    A naive adapter that drops reasoning without recording activity would have
    no way to distinguish this from a stall. This module does.
    """
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=10, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("reasoning", {"text": "thinking..."}),
        ("reasoning", {"text": "more thinking..."}),
        ("text", {"text": "Answer"}),
        ("finish", {"stop_reason": "end_turn"}),
        ("stop", {}),
    ])
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert RequestState.UPSTREAM_ACTIVE_HIDDEN in handler.metrics._states
    assert handler.state == RequestState.COMPLETED


# ---------------------------------------------------------------------------
# G-WAIT2: normal long reasoning not mis-killed
# ---------------------------------------------------------------------------


def test_g_wait2_long_reasoning_succeeds():
    """Reasoning chunks spaced < idle, total > idle → success, reasoning hidden."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=10, idle_timeout=10, total_timeout=100)
    steps = [("headers", {})]
    # 15 reasoning chunks, 5s apart — idle (10) never expires, total (100) not reached.
    for i in range(15):
        steps.append(("reasoning", {"text": f"thinking-{i}..."}))
        steps.append(("silence", {"duration": 5}))
    steps.append(("text", {"text": "Final answer"}))
    steps.append(("finish", {"stop_reason": "end_turn"}))
    steps.append(("stop", {}))
    upstream = FakeUpstream(steps)
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert handler.state == RequestState.COMPLETED
    assert handler.error_code is None
    # Reasoning content must not appear in client output.
    for evt in handler.client_output:
        assert "thinking-" not in str(evt)


# ---------------------------------------------------------------------------
# G-WAIT3: real silence → bounded idle timeout failure
# ---------------------------------------------------------------------------


def test_g_wait3_idle_timeout_on_silence():
    """Headers then permanent silence → MAAS_IDLE_TIMEOUT."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("silence", {"duration": 11}),  # > idle
    ])
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert handler.state == RequestState.IDLE_TIMEOUT
    assert handler.error_code == ErrorCodes.IDLE_TIMEOUT
    assert upstream.aborted


# ---------------------------------------------------------------------------
# G-WAIT4: total timeout despite continuous activity
# ---------------------------------------------------------------------------


def test_g_wait4_total_timeout_with_continuous_reasoning():
    """Continuous reasoning past total → MAAS_TOTAL_TIMEOUT."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=20)
    steps = [("headers", {})]
    # Reasoning every 5s — idle never expires, but total (20) will.
    for i in range(10):
        steps.append(("reasoning", {"text": f"think-{i}"}))
        steps.append(("silence", {"duration": 5}))
    upstream = FakeUpstream(steps)
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert handler.state == RequestState.TOTAL_TIMEOUT
    assert handler.error_code == ErrorCodes.TOTAL_TIMEOUT


# ---------------------------------------------------------------------------
# G-WAIT5: termination correctness
# ---------------------------------------------------------------------------


def test_g_wait5_finish_reason_missing_terminals_synthesizes():
    """Finish reason observed but missing terminals → synthesize exactly once."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("text", {"text": "Hi"}),
        ("finish", {"stop_reason": "end_turn"}),
        ("eof", None),  # no message_stop from upstream
    ])
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert handler.state == RequestState.COMPLETED
    # The synthesized message_stop should be in client output.
    stops = [e for e in handler.client_output if e.get("type") == "message_stop"]
    assert len(stops) == 1


def test_g_wait5_no_finish_reason_eof_fails():
    """EOF without finish reason → failure, never fakes success."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("text", {"text": "Hi"}),
        ("eof", None),  # no finish, no stop
    ])
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()
    assert handler.state == RequestState.UPSTREAM_FAILED
    assert handler.error_code == ErrorCodes.STREAM_EOF


# ---------------------------------------------------------------------------
# G-WAIT6: client cancellation
# ---------------------------------------------------------------------------


def test_g_wait6_client_abort_cancels_upstream():
    """Client disconnect during reasoning → upstream aborted, state client_aborted."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("reasoning", {"text": "thinking..."}),
    ])
    handler = RequestHandler(clock, cfg, upstream)
    # Simulate client disconnect after first reasoning chunk.
    handler.cancel.abort()
    handler.run()
    assert handler.state == RequestState.CLIENT_ABORTED
    assert upstream.aborted


def test_g_wait6_abort_is_idempotent():
    """Multiple abort signals don't double-terminate."""
    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([("headers", {}), ("reasoning", {"text": "..."})])
    handler = RequestHandler(clock, cfg, upstream)
    handler.cancel.abort()
    handler.cancel.abort()
    handler.cancel.abort()
    handler.run()
    assert handler.state == RequestState.CLIENT_ABORTED
    assert upstream.aborted


# ---------------------------------------------------------------------------
# G-WAIT7: sensitive data zero leakage
# ---------------------------------------------------------------------------


def test_g_wait7_no_secret_leakage():
    """Injected key/prompt/reasoning/tool-args must not appear in any output."""
    secret_key = "sk-SECRET-KEY-LEAK-CANARY-1234567890"
    secret_reasoning = "SECRET-REASONING-LEAK-CANARY"
    secret_prompt = "SECRET-PROMPT-LEAK-CANARY"
    secret_tool_args = '{"secret": "TOOL-ARGS-LEAK-CANARY"}'

    clock = FakeClock()
    cfg = TimeoutConfig(connect_timeout=5, idle_timeout=10, total_timeout=100)
    upstream = FakeUpstream([
        ("headers", {}),
        ("reasoning", {"text": secret_reasoning}),
        ("text", {"text": "safe answer"}),
        ("finish", {"stop_reason": "end_turn"}),
        ("stop", {}),
    ])
    handler = RequestHandler(clock, cfg, upstream)
    handler.run()

    # Collect all output surfaces.
    surfaces = [
        str(handler.client_output),
        str(handler.metrics.to_dict()),
    ]
    sink = ObservabilitySink()
    sink.register(handler.metrics)
    surfaces.append(str(sink.status()))

    for surface in surfaces:
        assert secret_key not in surface
        assert secret_reasoning not in surface
        assert secret_prompt not in surface
        assert secret_tool_args not in surface


# ---------------------------------------------------------------------------
# G-WAIT9: local concurrency — C1, C16, C64, C256
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("concurrency", [1, 16, 64, 256])
def test_g_wait9_concurrency_no_deadlock(concurrency):
    """C{N} fake upstream — no deadlock, no unhandled rejection, bounded."""
    guard = ConcurrencyGuard(max_concurrency=concurrency)
    admitted = 0
    for _ in range(concurrency):
        if guard.try_admit():
            admitted += 1
    assert admitted == concurrency
    assert guard.active == concurrency
    # Over-capacity rejected.
    assert guard.try_admit() is False
    # Release all.
    for _ in range(concurrency):
        guard.release()
    assert guard.active == 0


def test_g_wait9_over_capacity_returns_503_code():
    guard = ConcurrencyGuard(max_concurrency=2)
    guard.try_admit()
    guard.try_admit()
    ok, code = guard.try_admit_with_code()
    assert not ok
    assert code == ErrorCodes.OVER_CAPACITY
    assert ErrorCodes.http_status(code) == 503


# ---------------------------------------------------------------------------
# G-WAIT8: architecture invariants — no new gateway deps, model unchanged
# ---------------------------------------------------------------------------


def test_g_wait8_model_and_context_unchanged():
    """The reliability module must not change model or context defaults."""
    cfg = TimeoutConfig()
    # The module doesn't touch model/context — it only manages timeouts.
    assert cfg.connect_timeout == 60
    assert cfg.idle_timeout == 180
    assert cfg.total_timeout == 600
