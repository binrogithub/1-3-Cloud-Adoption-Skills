"""Stream activity and termination control — the reliability deep module.

TEST-ONLY / NON-AUTHORITATIVE: This Python module is the v1 prototype. It is
NOT wired into the production request path. The authoritative production
implementation is the Node adapter at adapter/server.js + adapter/lifecycle.js
(RequestLifecycleController). This file is retained for reference and offline
unit testing only (tests/test_stream_reliability*.py). Do not import it from
production code.

Implements the request-level state machine, activity monitoring, SSE termination
correctness, reasoning filtering, cancellation propagation, backpressure/size
limits, and sanitized observability for the MaaS protocol adapter.

Design (PRD: docs/PRD_MAAS_STREAM_WAIT_RELIABILITY_V1.md):
  * Per-request state isolation — no global mutable stream state.
  * Pluggable clock — tests inject a fake clock; production uses time.monotonic.
  * stdlib only — no external dependencies.
  * Sanitized — never logs key, prompt, response, reasoning, or tool args.
"""
from __future__ import annotations

import enum
import os
import time
from dataclasses import dataclass, field
from typing import Callable


# ===========================================================================
# Error codes (PRD §9)
# ===========================================================================


class ErrorCodes:
    """Stable error codes with retryable flags and HTTP status mapping."""

    CONNECT_TIMEOUT = "MAAS_CONNECT_TIMEOUT"
    IDLE_TIMEOUT = "MAAS_IDLE_TIMEOUT"
    TOTAL_TIMEOUT = "MAAS_TOTAL_TIMEOUT"
    UPSTREAM_HTTP = "MAAS_UPSTREAM_HTTP"
    STREAM_EOF = "MAAS_STREAM_EOF"
    STREAM_PROTOCOL = "MAAS_STREAM_PROTOCOL"
    TOOL_ARGS_TOO_LARGE = "MAAS_TOOL_ARGS_TOO_LARGE"
    CLIENT_ABORTED = "MAAS_CLIENT_ABORTED"
    OVER_CAPACITY = "MAAS_OVER_CAPACITY"

    _RETRYABLE = frozenset({
        CONNECT_TIMEOUT,
        IDLE_TIMEOUT,
        TOTAL_TIMEOUT,
        STREAM_EOF,
        OVER_CAPACITY,
    })

    _HTTP_STATUS = {
        CONNECT_TIMEOUT: 504,
        IDLE_TIMEOUT: 504,
        TOTAL_TIMEOUT: 504,
        UPSTREAM_HTTP: 502,  # resolved per-request from upstream status
        STREAM_EOF: 502,
        STREAM_PROTOCOL: 502,
        TOOL_ARGS_TOO_LARGE: 422,
        CLIENT_ABORTED: 499,  # client closed; no response written
        OVER_CAPACITY: 503,
    }

    @classmethod
    def is_retryable(cls, code: str) -> bool:
        return code in cls._RETRYABLE

    @classmethod
    def http_status(cls, code: str) -> int:
        return cls._HTTP_STATUS.get(code, 502)


# ===========================================================================
# Request state machine (PRD §core state machine — 11 states)
# ===========================================================================


class RequestState(enum.Enum):
    ACCEPTED = "accepted"
    CONNECTING = "connecting"
    UPSTREAM_ACTIVE_HIDDEN = "upstream_active_hidden"
    VISIBLE_STREAMING = "visible_streaming"
    COMPLETING = "completing"
    COMPLETED = "completed"
    CLIENT_ABORTED = "client_aborted"
    CONNECT_TIMEOUT = "connect_timeout"
    IDLE_TIMEOUT = "idle_timeout"
    TOTAL_TIMEOUT = "total_timeout"
    UPSTREAM_FAILED = "upstream_failed"

    @classmethod
    def terminal_states(cls) -> frozenset:
        return frozenset({
            cls.COMPLETED,
            cls.CLIENT_ABORTED,
            cls.CONNECT_TIMEOUT,
            cls.IDLE_TIMEOUT,
            cls.TOTAL_TIMEOUT,
            cls.UPSTREAM_FAILED,
        })

    @property
    def is_terminal(self) -> bool:
        return self in self.terminal_states()


# ===========================================================================
# Timeout configuration (PRD §4 — three-layer time boundary)
# ===========================================================================


@dataclass(frozen=True)
class TimeoutConfig:
    """Three-layer timeout with env-var override and range validation."""

    connect_timeout: float = 60.0
    idle_timeout: float = 180.0
    total_timeout: float = 600.0

    def __post_init__(self) -> None:
        if self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be positive")
        if self.idle_timeout <= 0:
            raise ValueError("idle_timeout must be positive")
        if self.total_timeout <= 0:
            raise ValueError("total_timeout must be positive")
        if self.total_timeout < self.connect_timeout:
            raise ValueError("total_timeout must be >= connect_timeout")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "TimeoutConfig":
        env = env if env is not None else dict(os.environ)
        defaults = cls()
        connect = _parse_positive_float(env.get("MAAS_CONNECT_TIMEOUT"), defaults.connect_timeout)
        idle = _parse_positive_float(env.get("MAAS_IDLE_TIMEOUT"), defaults.idle_timeout)
        total = _parse_positive_float(env.get("MAAS_TOTAL_TIMEOUT"), defaults.total_timeout)
        return cls(connect_timeout=connect, idle_timeout=idle, total_timeout=total)


def _parse_positive_float(raw: str | None, default: float) -> float:
    if raw is None or raw == "":
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid timeout value: {raw!r}")
    if val <= 0:
        raise ValueError(f"timeout must be positive: {raw!r}")
    return val


# ===========================================================================
# Clock — pluggable so tests inject a fake clock
# ===========================================================================


def default_clock() -> float:
    return time.monotonic()


# ===========================================================================
# Activity monitor (PRD §3 — upstream activity detection)
# ===========================================================================


class ActivityMonitor:
    """Per-request upstream activity tracker.

    Any application-layer body byte (reasoning, text, tool, usage, ping) refreshes
    the idle timer. The total timer is never refreshed. TCP ACKs alone do not
    count as activity. State is per-instance (per-request isolation).
    """

    def __init__(
        self,
        clock: Callable[[], float] = default_clock,
        idle_timeout: float = 180.0,
        total_timeout: float = 600.0,
    ):
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._total_timeout = total_timeout
        self._request_started_at: float | None = None
        self._connected_at: float | None = None
        self._last_activity_at: float | None = None

    def mark_request_started(self) -> None:
        self._request_started_at = self._clock()

    def mark_connected(self) -> None:
        now = self._clock()
        # Connecting implies the request was started.
        if self._request_started_at is None:
            self._request_started_at = now
        self._connected_at = now
        # First activity is the connection itself.
        self._last_activity_at = now

    def record_upstream_activity(self, kind: str = "unknown") -> None:
        """Record an application-layer upstream body byte/chunk.

        kind: "reasoning", "text", "tool", "usage", "ping", or other.
        All kinds refresh the idle timer.
        """
        self._last_activity_at = self._clock()

    def is_connect_expired(self, connect_timeout: float) -> bool:
        if self._request_started_at is None or self._connected_at is not None:
            return False
        return (self._clock() - self._request_started_at) >= connect_timeout

    def is_idle_expired(self) -> bool:
        if self._last_activity_at is None:
            return False
        return (self._clock() - self._last_activity_at) >= self._idle_timeout

    def is_total_expired(self) -> bool:
        if self._request_started_at is None:
            return False
        return (self._clock() - self._request_started_at) >= self._total_timeout


# ===========================================================================
# SSE termination state machine (PRD §6, G-WAIT5)
# ===========================================================================


# Trustworthy upstream finish reasons that permit synthesizing terminal events.
_TRUSTWORTHY_FINISH_REASONS = frozenset({
    "end_turn",
    "stop_sequence",
    "tool_use",
    "max_tokens",
})


class SSETerminator:
    """Tracks Anthropic SSE stream termination correctness.

    Enforces (PRD §6):
      * exactly one message_start and one message_stop per stream;
      * each content index opened at most once and closed before termination;
      * text_delta only in text blocks, input_json_delta only in tool_use blocks;
      * terminal events synthesized ONLY when a trustworthy finish reason was
        observed — never fakes success on a finish-reason-less EOF.
    """

    def __init__(self) -> None:
        self._message_start_sent = False
        self._message_stop_sent = False
        self._open_blocks: dict[int, str] = {}
        self._finish_reason: str | None = None
        self._message_delta_sent = False
        self._has_protocol_error = False
        self._finalized = False

    @property
    def finish_reason_observed(self) -> str | None:
        return self._finish_reason

    @property
    def is_complete(self) -> bool:
        return self._message_stop_sent

    @property
    def is_failed(self) -> bool:
        # Finalized without a finish reason and without a clean stop.
        return self._finalized and not self._message_stop_sent and self._finish_reason is None

    @property
    def has_protocol_error(self) -> bool:
        return self._has_protocol_error

    def feed(self, event: dict) -> list[dict]:
        """Process an upstream SSE event. Returns passthrough events to emit."""
        if self._has_protocol_error:
            return []
        etype = event.get("type")
        out: list[dict] = []

        if etype == "message_start":
            if self._message_start_sent:
                self._has_protocol_error = True
                return []
            self._message_start_sent = True
            out.append(event)

        elif etype == "content_block_start":
            index = event.get("index")
            block = event.get("content_block", {})
            btype = block.get("type") if isinstance(block, dict) else None
            if not isinstance(index, int) or not isinstance(btype, str):
                self._has_protocol_error = True
                return []
            if index in self._open_blocks:
                self._has_protocol_error = True
                return []
            self._open_blocks[index] = btype
            out.append(event)

        elif etype == "content_block_delta":
            index = event.get("index")
            delta = event.get("delta", {})
            dtype = delta.get("type") if isinstance(delta, dict) else None
            if not isinstance(index, int) or not isinstance(dtype, str):
                self._has_protocol_error = True
                return []
            expected = self._open_blocks.get(index)
            if expected is None:
                self._has_protocol_error = True
                return []
            # Validate delta/block pairing.
            if dtype == "text_delta" and expected != "text":
                self._has_protocol_error = True
                return []
            if dtype == "input_json_delta" and expected != "tool_use":
                self._has_protocol_error = True
                return []
            if dtype == "thinking_delta" and expected != "thinking":
                self._has_protocol_error = True
                return []
            out.append(event)

        elif etype == "content_block_stop":
            index = event.get("index")
            if not isinstance(index, int) or index not in self._open_blocks:
                self._has_protocol_error = True
                return []
            self._open_blocks.pop(index, None)
            out.append(event)

        elif etype == "message_delta":
            if self._message_delta_sent:
                self._has_protocol_error = True
                return []
            self._message_delta_sent = True
            delta = event.get("delta", {})
            reason = delta.get("stop_reason") if isinstance(delta, dict) else None
            if isinstance(reason, str) and reason in _TRUSTWORTHY_FINISH_REASONS:
                self._finish_reason = reason
            out.append(event)

        elif etype == "message_stop":
            if self._message_stop_sent:
                self._has_protocol_error = True
                return []
            self._message_stop_sent = True
            out.append(event)

        elif etype == "ping":
            out.append(event)

        elif etype == "error":
            out.append(event)

        else:
            # Unknown event type — pass through but don't error.
            out.append(event)

        return out

    def finalize(self) -> list[dict]:
        """Synthesize terminal events if a trustworthy finish reason was observed.

        Returns events to emit. If no finish reason was seen, marks the stream
        as failed (is_failed) and returns [] — never fakes a message_stop.
        """
        if self._finalized:
            return []
        self._finalized = True

        if self._finish_reason is None:
            # No trustworthy finish reason — do NOT fake success.
            return []

        if self._message_stop_sent:
            return []

        out: list[dict] = []
        # Close any still-open blocks in index order.
        for index in sorted(self._open_blocks):
            out.append({"type": "content_block_stop", "index": index})
        self._open_blocks.clear()
        # Synthesize message_delta if not already sent.
        if not self._message_delta_sent:
            out.append({"type": "message_delta", "delta": {"stop_reason": self._finish_reason}})
        # Synthesize message_stop.
        out.append({"type": "message_stop"})
        self._message_stop_sent = True
        return out


# ===========================================================================
# Reasoning filter (PRD §5 — GLM reasoning stays hidden)
# ===========================================================================


# Verified synonyms for the reasoning content field across GLM versions.
_REASONING_FIELDS = frozenset({"reasoning_content", "reasoning"})


class ReasoningFilter:
    """Identifies and hides GLM reasoning content.

    Counts chunks and UTF-8 bytes for observability but never emits reasoning
    as text_delta, thinking block, or signature to the client.
    """

    def __init__(self) -> None:
        self.reasoning_chunks = 0
        self.reasoning_bytes = 0

    def filter_chunk(self, chunk: dict) -> list[dict]:
        """Process an upstream OpenAI-compatible chunk.

        Returns a list of chunks to pass to the client. Reasoning-only chunks
        produce []. Chunks with visible content/tool calls are passed through.
        """
        choices = chunk.get("choices") if isinstance(chunk, dict) else None
        if not isinstance(choices, list):
            return [chunk] if chunk else []

        has_reasoning = False
        has_visible = False
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                continue
            for field in _REASONING_FIELDS:
                if field in delta and delta[field]:
                    has_reasoning = True
                    self.reasoning_chunks += 1
                    self.reasoning_bytes += len(str(delta[field]).encode("utf-8"))
            if "content" in delta and delta["content"]:
                has_visible = True
            if "tool_calls" in delta and delta["tool_calls"]:
                has_visible = True

        if has_reasoning and not has_visible:
            return []
        # If both reasoning and visible content in the same chunk, strip reasoning.
        if has_reasoning and has_visible:
            stripped = self._strip_reasoning(chunk)
            return [stripped]
        return [chunk]

    def _strip_reasoning(self, chunk: dict) -> dict:
        """Return a copy of chunk with reasoning fields removed."""
        import copy
        out = copy.deepcopy(chunk)
        for choice in out.get("choices", []):
            if isinstance(choice, dict) and isinstance(choice.get("delta"), dict):
                for field in _REASONING_FIELDS:
                    choice["delta"].pop(field, None)
        return out

    def metrics(self) -> dict:
        return {
            "reasoning_chunks": self.reasoning_chunks,
            "reasoning_bytes": self.reasoning_bytes,
        }


# ===========================================================================
# Cancellation controller (PRD §7 — client cancel propagation)
# ===========================================================================


class CancellationController:
    """Idempotent cancellation path for client abort / response close / exit.

    All trigger the same path: set a flag, run registered abort callbacks,
    clean up. Multiple abort signals don't double-terminate or raise.
    """

    def __init__(self) -> None:
        self._aborted = False
        self._callbacks: list[Callable[[], None]] = []

    @property
    def is_aborted(self) -> bool:
        return self._aborted

    def on_abort(self, callback: Callable[[], None]) -> None:
        """Register a callback to run on abort.

        If already aborted, the callback runs immediately.
        """
        if self._aborted:
            self._safe_call(callback)
            return
        self._callbacks.append(callback)

    def abort(self) -> None:
        """Trigger cancellation. Idempotent — subsequent calls are no-ops."""
        if self._aborted:
            return
        self._aborted = True
        callbacks = self._callbacks
        self._callbacks = []
        for cb in callbacks:
            self._safe_call(cb)

    def _safe_call(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            pass


# ===========================================================================
# Size limits + concurrency (PRD §8, §12)
# ===========================================================================


@dataclass(frozen=True)
class SizeLimits:
    """Bounded sizes for SSE events, tool args, request body."""

    max_sse_event_bytes: int = 1_000_000
    max_tool_args_bytes: int = 256_000
    max_request_body_bytes: int = 10_000_000

    def check_sse_event(self, data: str) -> tuple[bool, str | None]:
        if len(data.encode("utf-8")) > self.max_sse_event_bytes:
            return False, ErrorCodes.STREAM_PROTOCOL
        return True, None

    def check_tool_args(self, data: str) -> tuple[bool, str | None]:
        if len(data.encode("utf-8")) > self.max_tool_args_bytes:
            return False, ErrorCodes.TOOL_ARGS_TOO_LARGE
        return True, None

    def check_request_body(self, data: bytes) -> tuple[bool, str | None]:
        if len(data) > self.max_request_body_bytes:
            return False, ErrorCodes.STREAM_PROTOCOL
        return True, None


class ConcurrencyGuard:
    """Bounded concurrency with over-capacity rejection (PRD §12)."""

    def __init__(self, max_concurrency: int = 8):
        self._max = max_concurrency
        self._active = 0

    @property
    def active(self) -> int:
        return self._active

    def try_admit(self) -> bool:
        if self._active >= self._max:
            return False
        self._active += 1
        return True

    def try_admit_with_code(self) -> tuple[bool, str | None]:
        if self._active >= self._max:
            return False, ErrorCodes.OVER_CAPACITY
        self._active += 1
        return True, None

    def release(self) -> None:
        if self._active > 0:
            self._active -= 1


# ===========================================================================
# Observability (PRD §10, §11 — sanitized metrics + loopback status)
# ===========================================================================


import uuid


_LOOPBACK_ADDRS = frozenset({"127.0.0.1", "::1", "localhost", None})


class RequestMetrics:
    """Per-request sanitized metrics. Never stores secrets or content."""

    def __init__(self) -> None:
        self.request_id = uuid.uuid4().hex
        self._states: list[RequestState] = []
        self.reasoning_chunks = 0
        self.reasoning_bytes = 0
        self.visible_text_bytes = 0
        self.tool_calls = 0
        self.outcome: str | None = None
        self.error_code: str | None = None
        self.retryable: bool | None = None

    def record_state(self, state: RequestState) -> None:
        self._states.append(state)

    def record_reasoning(self, chunks: int, bytes_: int) -> None:
        self.reasoning_chunks += chunks
        self.reasoning_bytes += bytes_

    def record_visible_text(self, bytes_: int) -> None:
        self.visible_text_bytes += bytes_

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def record_outcome(self, outcome: str, error_code: str | None = None) -> None:
        self.outcome = outcome
        self.error_code = error_code
        self.retryable = ErrorCodes.is_retryable(error_code) if error_code else None

    @property
    def final_state(self) -> str | None:
        return self._states[-1].value if self._states else None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "final_state": self.final_state,
            "reasoning_chunks": self.reasoning_chunks,
            "reasoning_bytes": self.reasoning_bytes,
            "visible_text_bytes": self.visible_text_bytes,
            "tool_calls": self.tool_calls,
            "outcome": self.outcome,
            "error_code": self.error_code,
            "retryable": self.retryable,
        }


class ObservabilitySink:
    """Aggregate status, loopback-only, sanitized (PRD §11)."""

    VERSION = "stream-reliability-v1"

    def __init__(self, timeout_config: TimeoutConfig | None = None):
        self._timeout_config = timeout_config or TimeoutConfig()
        self._active: dict[str, RequestMetrics] = {}
        self._started_at = default_clock()

    def register(self, metrics: RequestMetrics) -> None:
        self._active[metrics.request_id] = metrics

    def complete(self, request_id: str) -> None:
        self._active.pop(request_id, None)

    def status(self, remote_addr: str | None = None) -> dict:
        allowed = remote_addr in _LOOPBACK_ADDRS
        if not allowed:
            return {"allowed": False}
        return {
            "allowed": True,
            "version": self.VERSION,
            "uptime": default_clock() - self._started_at,
            "active_requests": len(self._active),
            "timeout_config": {
                "connect": self._timeout_config.connect_timeout,
                "idle": self._timeout_config.idle_timeout,
                "total": self._timeout_config.total_timeout,
            },
        }
