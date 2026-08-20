"""Unit tests for client/stream_reliability.py — the stream reliability deep module.

This module implements the request-level "stream activity and termination control"
from docs/PRD_MAAS_STREAM_WAIT_RELIABILITY_V1.md. Tests are deterministic: they
use a fake clock and fake upstream, never real time or network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make client/ importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))

from stream_reliability import (  # noqa: E402
    ErrorCodes,
    RequestState,
    TimeoutConfig,
)


# ===========================================================================
# Task 1: Error codes, TimeoutConfig, RequestState
# ===========================================================================


class TestErrorCodes:
    """G-WAIT: stable error codes with correct retryable flags (PRD §9)."""

    def test_all_codes_are_stable_strings(self):
        codes = [
            ErrorCodes.CONNECT_TIMEOUT,
            ErrorCodes.IDLE_TIMEOUT,
            ErrorCodes.TOTAL_TIMEOUT,
            ErrorCodes.UPSTREAM_HTTP,
            ErrorCodes.STREAM_EOF,
            ErrorCodes.STREAM_PROTOCOL,
            ErrorCodes.TOOL_ARGS_TOO_LARGE,
            ErrorCodes.CLIENT_ABORTED,
            ErrorCodes.OVER_CAPACITY,
        ]
        for code in codes:
            assert isinstance(code, str)
            assert code.startswith("MAAS_")

    def test_retryable_flags(self):
        assert ErrorCodes.is_retryable(ErrorCodes.CONNECT_TIMEOUT) is True
        assert ErrorCodes.is_retryable(ErrorCodes.IDLE_TIMEOUT) is True
        assert ErrorCodes.is_retryable(ErrorCodes.TOTAL_TIMEOUT) is True
        assert ErrorCodes.is_retryable(ErrorCodes.STREAM_EOF) is True
        assert ErrorCodes.is_retryable(ErrorCodes.OVER_CAPACITY) is True
        # Non-retryable.
        assert ErrorCodes.is_retryable(ErrorCodes.STREAM_PROTOCOL) is False
        assert ErrorCodes.is_retryable(ErrorCodes.TOOL_ARGS_TOO_LARGE) is False
        assert ErrorCodes.is_retryable(ErrorCodes.CLIENT_ABORTED) is False

    def test_http_status_mapping(self):
        assert ErrorCodes.http_status(ErrorCodes.CONNECT_TIMEOUT) == 504
        assert ErrorCodes.http_status(ErrorCodes.IDLE_TIMEOUT) == 504
        assert ErrorCodes.http_status(ErrorCodes.TOTAL_TIMEOUT) == 504
        assert ErrorCodes.http_status(ErrorCodes.STREAM_EOF) == 502
        assert ErrorCodes.http_status(ErrorCodes.STREAM_PROTOCOL) == 502
        assert ErrorCodes.http_status(ErrorCodes.TOOL_ARGS_TOO_LARGE) == 422
        assert ErrorCodes.http_status(ErrorCodes.OVER_CAPACITY) == 503


class TestRequestState:
    """The 11-state machine (PRD §core state machine)."""

    def test_all_states_exist(self):
        expected = {
            "accepted",
            "connecting",
            "upstream_active_hidden",
            "visible_streaming",
            "completing",
            "completed",
            "client_aborted",
            "connect_timeout",
            "idle_timeout",
            "total_timeout",
            "upstream_failed",
        }
        actual = {s.value for s in RequestState}
        assert actual == expected

    def test_terminal_states(self):
        terminals = RequestState.terminal_states()
        for s in (
            RequestState.COMPLETED,
            RequestState.CLIENT_ABORTED,
            RequestState.CONNECT_TIMEOUT,
            RequestState.IDLE_TIMEOUT,
            RequestState.TOTAL_TIMEOUT,
            RequestState.UPSTREAM_FAILED,
        ):
            assert s in terminals
        # Non-terminal.
        assert RequestState.CONNECTING not in terminals
        assert RequestState.UPSTREAM_ACTIVE_HIDDEN not in terminals


class TestTimeoutConfig:
    """Three-layer timeout with env override + range validation (PRD §4)."""

    def test_defaults(self):
        cfg = TimeoutConfig()
        assert cfg.connect_timeout == 60
        assert cfg.idle_timeout == 180
        assert cfg.total_timeout == 600

    def test_env_override(self):
        env = {
            "MAAS_CONNECT_TIMEOUT": "30",
            "MAAS_IDLE_TIMEOUT": "90",
            "MAAS_TOTAL_TIMEOUT": "300",
        }
        cfg = TimeoutConfig.from_env(env)
        assert cfg.connect_timeout == 30
        assert cfg.idle_timeout == 90
        assert cfg.total_timeout == 300

    def test_env_override_partial(self):
        env = {"MAAS_IDLE_TIMEOUT": "120"}
        cfg = TimeoutConfig.from_env(env)
        assert cfg.connect_timeout == 60  # default
        assert cfg.idle_timeout == 120

    def test_rejects_non_positive(self):
        with pytest.raises(ValueError):
            TimeoutConfig(connect_timeout=0)
        with pytest.raises(ValueError):
            TimeoutConfig(idle_timeout=-1)

    def test_rejects_total_below_connect(self):
        """Total must be >= connect (otherwise connect can never fire)."""
        with pytest.raises(ValueError):
            TimeoutConfig(connect_timeout=60, total_timeout=30)

    def test_rejects_non_numeric_env(self):
        with pytest.raises(ValueError):
            TimeoutConfig.from_env({"MAAS_IDLE_TIMEOUT": "abc"})

    def test_rejects_out_of_range_env(self):
        with pytest.raises(ValueError):
            TimeoutConfig.from_env({"MAAS_TOTAL_TIMEOUT": "0"})


# ===========================================================================
# Task 2: ActivityMonitor (G-WAIT2, G-WAIT3, G-WAIT4)
# ===========================================================================

from stream_reliability import ActivityMonitor  # noqa: E402


class FakeClock:
    """A controllable monotonic clock for deterministic tests."""

    def __init__(self, start: float = 0.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


class TestActivityMonitor:
    """Upstream activity detection (PRD §3, G-WAIT2/3/4)."""

    def test_reasoning_chunk_refreshes_idle(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(5)
        mon.record_upstream_activity(kind="reasoning")
        clock.advance(9)  # 9 < 10 since last activity
        assert not mon.is_idle_expired()

    def test_text_chunk_refreshes_idle(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(5)
        mon.record_upstream_activity(kind="text")
        clock.advance(9)
        assert not mon.is_idle_expired()

    def test_tool_chunk_refreshes_idle(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(5)
        mon.record_upstream_activity(kind="tool")
        clock.advance(9)
        assert not mon.is_idle_expired()

    def test_usage_and_ping_refresh_idle(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(5)
        mon.record_upstream_activity(kind="usage")
        clock.advance(9)
        assert not mon.is_idle_expired()
        clock.advance(1)  # would expire without new activity
        mon.record_upstream_activity(kind="ping")
        clock.advance(9)
        assert not mon.is_idle_expired()

    def test_no_activity_triggers_idle_timeout(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(11)
        assert mon.is_idle_expired()

    def test_total_timeout_not_refreshed_by_activity(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=20)
        mon.mark_connected()
        # Continuous reasoning every 5s — idle never expires.
        for _ in range(5):
            clock.advance(5)
            mon.record_upstream_activity(kind="reasoning")
        # 25s elapsed > total 20.
        assert mon.is_total_expired()
        assert not mon.is_idle_expired()

    def test_per_request_isolation(self):
        clock = FakeClock()
        mon1 = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon2 = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon1.mark_connected()
        mon2.mark_connected()
        clock.advance(5)
        mon1.record_upstream_activity(kind="reasoning")
        clock.advance(8)  # 13s since connect, 8 since mon1 activity
        assert not mon1.is_idle_expired()
        assert mon2.is_idle_expired()  # mon2 had no activity

    def test_connect_timeout(self):
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_request_started()
        clock.advance(11)
        assert mon.is_connect_expired(connect_timeout=10)
        mon.mark_connected()
        # After connected, connect timeout no longer relevant.
        clock.advance(5)
        assert not mon.is_connect_expired(connect_timeout=10)

    def test_tcp_ack_alone_does_not_refresh(self):
        """Only application-layer bytes count as activity (PRD §3)."""
        clock = FakeClock()
        mon = ActivityMonitor(clock=clock, idle_timeout=10, total_timeout=100)
        mon.mark_connected()
        clock.advance(11)
        # No record_upstream_activity call — TCP keepalive alone.
        assert mon.is_idle_expired()


# ===========================================================================
# Task 3: SSETerminator (G-WAIT5)
# ===========================================================================

from stream_reliability import SSETerminator  # noqa: E402


def _evt(type_: str, **kw) -> dict:
    """Build an Anthropic SSE event dict."""
    d = {"type": type_}
    d.update(kw)
    return d


class TestSSETerminator:
    """SSE termination correctness (PRD §6, G-WAIT5)."""

    def test_normal_text_stream_terminates_cleanly(self):
        term = SSETerminator()
        out = []
        out += term.feed(_evt("message_start"))
        out += term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        out += term.feed(_evt("content_block_delta", index=0, delta={"type": "text_delta", "text": "Hi"}))
        out += term.feed(_evt("content_block_stop", index=0))
        out += term.feed(_evt("message_delta", delta={"stop_reason": "end_turn"}))
        out += term.feed(_evt("message_stop"))
        assert term.finish_reason_observed == "end_turn"
        assert term.is_complete
        # finalize() should produce nothing extra (already complete).
        extra = term.finalize()
        assert extra == []

    def test_normal_tool_stream_terminates_cleanly(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "tool_use", "id": "t1", "name": "get_weather"}))
        term.feed(_evt("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": '{"city":"Tokyo"}'}))
        term.feed(_evt("content_block_stop", index=0))
        term.feed(_evt("message_delta", delta={"stop_reason": "tool_use"}))
        term.feed(_evt("message_stop"))
        assert term.finish_reason_observed == "tool_use"
        assert term.is_complete

    def test_finish_reason_missing_terminals_synthesizes(self):
        """G-WAIT5: finish reason observed but missing terminal events → synthesize."""
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        term.feed(_evt("content_block_delta", index=0, delta={"type": "text_delta", "text": "Hi"}))
        # Upstream sent finish reason but no block_stop / message_delta / message_stop.
        term.feed(_evt("message_delta", delta={"stop_reason": "end_turn"}))
        extra = term.finalize()
        # Should synthesize: block_stop, message_stop (message_delta already sent).
        types = [e["type"] for e in extra]
        assert "content_block_stop" in types
        assert "message_stop" in types
        assert term.is_complete

    def test_synthesize_only_once(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        term.feed(_evt("message_delta", delta={"stop_reason": "end_turn"}))
        extra1 = term.finalize()
        extra2 = term.finalize()
        assert extra1 != []
        assert extra2 == []  # already finalized

    def test_no_finish_reason_eof_is_failure(self):
        """G-WAIT5: EOF without finish reason must fail, never fake success."""
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        term.feed(_evt("content_block_delta", index=0, delta={"type": "text_delta", "text": "Hi"}))
        # No finish reason, no message_stop — just EOF.
        result = term.finalize()
        assert term.is_failed
        assert not term.is_complete

    def test_exactly_one_message_start_and_stop(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        # Duplicate message_start should be rejected.
        errors = term.feed(_evt("message_start"))
        assert term.has_protocol_error

    def test_duplicate_message_stop_rejected(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        term.feed(_evt("content_block_delta", index=0, delta={"type": "text_delta", "text": "Hi"}))
        term.feed(_evt("content_block_stop", index=0))
        term.feed(_evt("message_delta", delta={"stop_reason": "end_turn"}))
        term.feed(_evt("message_stop"))
        # Duplicate message_stop.
        term.feed(_evt("message_stop"))
        assert term.has_protocol_error

    def test_text_delta_outside_text_block_rejected(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "tool_use"}))
        # text_delta inside a tool_use block — wrong.
        term.feed(_evt("content_block_delta", index=0, delta={"type": "text_delta", "text": "Hi"}))
        assert term.has_protocol_error

    def test_input_json_delta_outside_tool_block_rejected(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        # input_json_delta inside a text block — wrong.
        term.feed(_evt("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": "{}"}))
        assert term.has_protocol_error

    def test_block_index_opened_only_once(self):
        term = SSETerminator()
        term.feed(_evt("message_start"))
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        # Reopen same index — error.
        term.feed(_evt("content_block_start", index=0, content_block={"type": "text"}))
        assert term.has_protocol_error


# ===========================================================================
# Task 4: ReasoningFilter (G-WAIT7 partial)
# ===========================================================================

from stream_reliability import ReasoningFilter  # noqa: E402


class TestReasoningFilter:
    """GLM reasoning stays hidden, content preserved (PRD §5, G-WAIT7)."""

    def test_reasoning_only_produces_no_client_payload(self):
        rf = ReasoningFilter()
        out = rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "thinking..."}}]})
        assert out == []  # nothing emitted to client

    def test_reasoning_synonym_detected(self):
        rf = ReasoningFilter()
        out = rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "thinking..."}}]})
        assert out == []
        assert rf.reasoning_chunks == 1
        assert rf.reasoning_bytes > 0

    def test_reasoning_text_absent_from_metrics(self):
        rf = ReasoningFilter()
        secret_reasoning = "SECRET-REASONING-DO-NOT-LEAK"
        rf.filter_chunk({"choices": [{"delta": {"reasoning_content": secret_reasoning}}]})
        metrics = rf.metrics()
        # The reasoning text must not appear in any metric value.
        metrics_str = str(metrics)
        assert secret_reasoning not in metrics_str

    def test_text_after_reasoning_preserved(self):
        rf = ReasoningFilter()
        rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "thinking..."}}]})
        out = rf.filter_chunk({"choices": [{"delta": {"content": "Hello"}}]})
        assert len(out) == 1
        assert out[0]["choices"][0]["delta"]["content"] == "Hello"

    def test_tool_after_reasoning_preserved(self):
        rf = ReasoningFilter()
        rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "thinking..."}}]})
        out = rf.filter_chunk({"choices": [{"delta": {"tool_calls": [{"id": "t1", "function": {"name": "f", "arguments": "{}"}}]}}]})
        assert len(out) == 1

    def test_no_thinking_block_or_signature_synthesized(self):
        rf = ReasoningFilter()
        out = rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "thinking..."}}]})
        for evt in out:
            assert "thinking" not in str(evt).lower() or "thinking" not in evt
            assert "signature" not in str(evt).lower()

    def test_reasoning_counts_accumulate(self):
        rf = ReasoningFilter()
        rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "abc"}}]})
        rf.filter_chunk({"choices": [{"delta": {"reasoning_content": "defgh"}}]})
        assert rf.reasoning_chunks == 2
        assert rf.reasoning_bytes == 8  # 3 + 5


# ===========================================================================
# Task 5: CancellationController (G-WAIT6)
# ===========================================================================

from stream_reliability import CancellationController  # noqa: E402


class TestCancellationController:
    """Client cancellation propagation (PRD §7, G-WAIT6)."""

    def test_abort_triggers_callbacks(self):
        ctrl = CancellationController()
        called = []
        ctrl.on_abort(lambda: called.append("upstream"))
        ctrl.on_abort(lambda: called.append("cleanup"))
        ctrl.abort()
        assert called == ["upstream", "cleanup"]

    def test_abort_is_idempotent(self):
        ctrl = CancellationController()
        count = [0]
        ctrl.on_abort(lambda: count.__setitem__(0, count[0] + 1))
        ctrl.abort()
        ctrl.abort()  # second abort — no double-terminate
        ctrl.abort()
        assert count[0] == 1

    def test_is_aborted_flag(self):
        ctrl = CancellationController()
        assert not ctrl.is_aborted
        ctrl.abort()
        assert ctrl.is_aborted

    def test_callbacks_cleared_after_abort(self):
        ctrl = CancellationController()
        called = []
        ctrl.on_abort(lambda: called.append("a"))
        ctrl.abort()
        # Registering after abort should call immediately but not accumulate.
        ctrl.on_abort(lambda: called.append("b"))
        assert called == ["a", "b"]
        # Re-abort doesn't re-call.
        ctrl.abort()
        assert called == ["a", "b"]

    def test_abort_does_not_raise_on_callback_exception(self):
        ctrl = CancellationController()
        ctrl.on_abort(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        called = []
        ctrl.on_abort(lambda: called.append("after-bad"))
        ctrl.abort()  # should not raise
        assert called == ["after-bad"]


# ===========================================================================
# Task 6: Backpressure + size limits (PRD §8)
# ===========================================================================

from stream_reliability import SizeLimits, ConcurrencyGuard  # noqa: E402


class TestSizeLimits:
    """Bounded sizes with stable error codes (PRD §8)."""

    def test_oversized_sse_event_rejected(self):
        limits = SizeLimits(max_sse_event_bytes=100)
        ok, code = limits.check_sse_event("x" * 101)
        assert not ok
        assert code == ErrorCodes.STREAM_PROTOCOL

    def test_sse_event_within_limit(self):
        limits = SizeLimits(max_sse_event_bytes=100)
        ok, code = limits.check_sse_event("x" * 100)
        assert ok
        assert code is None

    def test_tool_args_over_limit(self):
        limits = SizeLimits(max_tool_args_bytes=50)
        ok, code = limits.check_tool_args("x" * 51)
        assert not ok
        assert code == ErrorCodes.TOOL_ARGS_TOO_LARGE

    def test_request_body_over_limit(self):
        limits = SizeLimits(max_request_body_bytes=1000)
        ok, code = limits.check_request_body(b"x" * 1001)
        assert not ok
        assert code == ErrorCodes.STREAM_PROTOCOL


class TestConcurrencyGuard:
    """Over-capacity rejection (PRD §12)."""

    def test_admit_up_to_limit(self):
        guard = ConcurrencyGuard(max_concurrency=3)
        assert guard.try_admit() is True
        assert guard.try_admit() is True
        assert guard.try_admit() is True

    def test_reject_over_limit(self):
        guard = ConcurrencyGuard(max_concurrency=2)
        guard.try_admit()
        guard.try_admit()
        assert guard.try_admit() is False

    def test_release_frees_slot(self):
        guard = ConcurrencyGuard(max_concurrency=1)
        guard.try_admit()
        assert guard.try_admit() is False
        guard.release()
        assert guard.try_admit() is True

    def test_over_capacity_error_code(self):
        guard = ConcurrencyGuard(max_concurrency=1)
        guard.try_admit()
        ok, code = guard.try_admit_with_code()
        assert not ok
        assert code == ErrorCodes.OVER_CAPACITY

    def test_active_count(self):
        guard = ConcurrencyGuard(max_concurrency=5)
        guard.try_admit()
        guard.try_admit()
        assert guard.active == 2
        guard.release()
        assert guard.active == 1


# ===========================================================================
# Task 7: Observability (G-WAIT7)
# ===========================================================================

from stream_reliability import RequestMetrics, ObservabilitySink  # noqa: E402


class TestRequestMetrics:
    """Sanitized per-request metrics (PRD §10, G-WAIT7)."""

    def test_request_id_generated(self):
        m = RequestMetrics()
        assert isinstance(m.request_id, str)
        assert len(m.request_id) > 0

    def test_request_ids_unique(self):
        ids = {RequestMetrics().request_id for _ in range(100)}
        assert len(ids) == 100

    def test_leak_scan_no_key_in_metrics(self):
        m = RequestMetrics()
        secret_key = "sk-super-secret-key-1234567890"
        # Metrics should never store the key.
        m.record_state(RequestState.CONNECTING)
        m.record_state(RequestState.COMPLETED)
        metrics_str = str(m.to_dict())
        assert secret_key not in metrics_str

    def test_leak_scan_no_reasoning_in_metrics(self):
        m = RequestMetrics()
        secret_reasoning = "SECRET-REASONING-CONTENT"
        m.record_reasoning(chunks=1, bytes_=len(secret_reasoning))
        metrics_str = str(m.to_dict())
        assert secret_reasoning not in metrics_str
        # But counts should be present.
        assert m.reasoning_chunks == 1

    def test_tool_count_without_names_or_args(self):
        m = RequestMetrics()
        m.record_tool_call()
        m.record_tool_call()
        d = m.to_dict()
        assert d["tool_calls"] == 2
        assert "tool_name" not in str(d)
        assert "tool_args" not in str(d)

    def test_state_transitions_recorded(self):
        m = RequestMetrics()
        m.record_state(RequestState.ACCEPTED)
        m.record_state(RequestState.CONNECTING)
        m.record_state(RequestState.UPSTREAM_ACTIVE_HIDDEN)
        m.record_state(RequestState.COMPLETED)
        d = m.to_dict()
        assert d["final_state"] == "completed"


class TestObservabilitySink:
    """Loopback-only status, sanitized aggregate (PRD §11)."""

    def test_status_includes_required_fields(self):
        sink = ObservabilitySink()
        m = RequestMetrics()
        sink.register(m)
        status = sink.status()
        for field in ("version", "uptime", "active_requests", "timeout_config"):
            assert field in status

    def test_status_rejects_non_loopback(self):
        sink = ObservabilitySink()
        status = sink.status(remote_addr="10.0.0.5")
        assert status["allowed"] is False

    def test_status_allows_loopback(self):
        sink = ObservabilitySink()
        for addr in ("127.0.0.1", "::1", "localhost"):
            status = sink.status(remote_addr=addr)
            assert status["allowed"] is True

    def test_status_no_secrets(self):
        sink = ObservabilitySink()
        m = RequestMetrics()
        sink.register(m)
        secret = "sk-secret-key-leak-test"
        status_str = str(sink.status())
        assert secret not in status_str

    def test_active_count(self):
        sink = ObservabilitySink()
        m1 = RequestMetrics()
        m2 = RequestMetrics()
        sink.register(m1)
        sink.register(m2)
        assert sink.status()["active_requests"] == 2
        sink.complete(m1.request_id)
        assert sink.status()["active_requests"] == 1
