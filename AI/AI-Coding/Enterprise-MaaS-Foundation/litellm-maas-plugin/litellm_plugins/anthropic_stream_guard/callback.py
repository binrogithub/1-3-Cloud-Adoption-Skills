"""
anthropic_stream_guard - LiteLLM custom callback (plugin, no core patches).

Fixes the malformed Anthropic SSE stream produced by LiteLLM's
messages->chat/completions adapter for backends that always emit
reasoning_content (e.g. GLM-5.2 on Huawei MaaS): the whole response arrives
as ONE "text" content block mixing thinking_delta and text_delta events.
Also strips Anthropic thinking/reasoning request params so /v1/messages
stays on /chat/completions instead of the unsupported Responses API.

Security / hardening invariants (do not break when maintaining):
  I1  No shared mutable state across requests: all stream state lives in a
      per-call _StreamState. Tenant isolation depends on this.
  I2  Fail-open: any per-chunk error flushes buffered events and passes the
      original bytes through. The guard must never kill a stream.
  I3  Only events whose "type" is in ANTHROPIC_EVENT_TYPES are ever
      re-serialized; everything else is forwarded byte-identical. This is
      the SSE-injection defense: attacker-influenced payloads can never
      reach the f-string in _sse() with an unvalidated event type.
  I4  Parsing is bounded: chunks larger than ASG_MAX_PARSE_BYTES are never
      json-parsed (forwarded as-is, counted).
  I5  Logs never contain payload content - only event indexes, block types,
      and exception class names.
  I6  The byte-level fast path is adversarial-safe: delta-family markers can
      be faked inside user-influenced text, so any ambiguity (>1 distinct
      marker) falls back to full JSON parsing. Faking markers can only cause
      extra parsing, never a wrong rewrite.
  I7  Zero third-party dependencies. Metrics degrade to no-ops if
      prometheus_client is unavailable.

Env:
  ASG_STRIP_THINKING=true|false   strip thinking/reasoning params (default true)
  ASG_MAX_PARSE_BYTES=262144      max SSE event size that will be parsed

Prometheus metrics (exported via the proxy /metrics endpoint):
  asg_retyped_blocks_total      first-block type corrections
  asg_synthesized_blocks_total  synthesized stop/start pairs
  asg_parse_errors_total        chunks that failed to parse (passed through)
  asg_oversize_passthrough_total chunks skipped due to size cap
"""

import json
import os
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger

ANTHROPIC_EVENT_TYPES = {
    "message_start",
    "content_block_start",
    "content_block_delta",
    "content_block_stop",
    "message_delta",
    "message_stop",
    "ping",
    "error",
}

INDEXED_EVENTS = {"content_block_start", "content_block_delta", "content_block_stop"}
THINKING_DELTAS = {"thinking_delta", "signature_delta"}

STRIP_THINKING = os.getenv("ASG_STRIP_THINKING", "true").strip().lower() != "false"
STRIPPED_REQUEST_KEYS = ("thinking", "reasoning", "reasoning_effort")

try:
    MAX_PARSE_BYTES = max(4096, int(os.getenv("ASG_MAX_PARSE_BYTES", "262144")))
except ValueError:
    MAX_PARSE_BYTES = 262144

# ---- metrics (I7: degrade to no-ops, never fail the proxy) ----------------
try:
    from prometheus_client import Counter as _Counter

    RETYPED = _Counter(
        "asg_retyped_blocks_total", "content_block_start events retyped"
    )
    SYNTHESIZED = _Counter(
        "asg_synthesized_blocks_total", "synthesized stop/start pairs"
    )
    PARSE_ERRORS = _Counter(
        "asg_parse_errors_total", "chunks that failed to parse (passed through)"
    )
    OVERSIZE = _Counter(
        "asg_oversize_passthrough_total", "chunks skipped due to ASG_MAX_PARSE_BYTES"
    )
except Exception:  # duplicate registration, missing dep, ...

    class _Noop:
        def inc(self, *_a, **_k):
            pass

    RETYPED = SYNTHESIZED = PARSE_ERRORS = OVERSIZE = _Noop()

# ---- byte-level fast path (I6) --------------------------------------------
_DELTA_PREFIX = b"event: content_block_delta"
_FAMILY_MARKERS = (
    (b'"thinking_delta"', "thinking"),
    (b'"signature_delta"', "thinking"),
    (b'"text_delta"', "text"),
    (b'"input_json_delta"', "tool_use"),
)


def _sniff_delta_family(chunk: bytes) -> Tuple[Optional[str], bool]:
    """Return (family, ambiguous). Ambiguous when 0 or >1 distinct families
    match - attacker-controlled text can fake markers, so ambiguity always
    falls back to full parsing (I6)."""
    family: Optional[str] = None
    for marker, fam in _FAMILY_MARKERS:
        if marker in chunk:
            if family is not None and family != fam:
                return None, True
            family = fam
    return family, family is None


def _parse_sse(chunk: bytes) -> Optional[Dict[str, Any]]:
    """Parse one serialized SSE event; None if not a single anthropic event."""
    try:
        text = chunk.decode("utf-8")
    except Exception:
        return None
    event_dict = None
    for line in text.split("\n"):
        if line.startswith("data: "):
            if event_dict is not None:  # multiple data lines -> not ours, bail
                return None
            try:
                event_dict = json.loads(line[6:])
            except Exception:
                PARSE_ERRORS.inc()
                return None
    if isinstance(event_dict, dict) and event_dict.get("type") in ANTHROPIC_EVENT_TYPES:
        return event_dict
    return None


def _sse(event: Dict[str, Any]) -> bytes:
    # I3: event["type"] is always whitelist-validated or self-constructed.
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()


def _delta_family(event: Dict[str, Any]) -> Optional[str]:
    delta = event.get("delta")
    if not isinstance(delta, dict):
        return None
    dtype = delta.get("type")
    if dtype in THINKING_DELTAS:
        return "thinking"
    if dtype == "text_delta":
        return "text"
    if dtype == "input_json_delta":
        return "tool_use"
    return None


def _make_start(index: int, block_type: str) -> Dict[str, Any]:
    block = (
        {"type": "thinking", "thinking": ""}
        if block_type == "thinking"
        else {"type": "text", "text": ""}
    )
    return {"type": "content_block_start", "index": index, "content_block": block}


class _StreamState:
    """Per-request state only (I1). Never promote fields to module/class level."""

    __slots__ = ("offset", "cur_index", "cur_type", "block_open", "pending")

    def __init__(self) -> None:
        self.offset = 0          # index shift from synthesized blocks
        self.cur_index = 0       # output-side index of the open block
        self.cur_type = ""       # effective type of the open block
        self.block_open = False
        # buffered (event, raw_chunk); raw only reusable while offset == 0
        self.pending: Optional[Tuple[Dict[str, Any], Any]] = None


class AnthropicStreamGuard(CustomLogger):
    # ---- request side ------------------------------------------------------

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Strip Anthropic thinking/reasoning params so /v1/messages routes
        via chat/completions instead of the (unsupported) Responses API."""
        if STRIP_THINKING and isinstance(data, dict):
            for key in STRIPPED_REQUEST_KEYS:
                data.pop(key, None)
        return data

    # ---- response side -----------------------------------------------------

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        st = _StreamState()
        async for chunk in response:
            try:
                is_bytes = isinstance(chunk, (bytes, bytearray))

                # I4: never parse oversized events; forward as-is.
                if is_bytes and len(chunk) > MAX_PARSE_BYTES:
                    OVERSIZE.inc()
                    for out in self._flush_pending(st):
                        yield out
                    yield chunk
                    continue

                # I6 fast path: steady-state delta whose family matches the
                # open block needs no JSON parsing at all.
                if (
                    is_bytes
                    and st.pending is None
                    and st.offset == 0
                    and st.block_open
                    and chunk.startswith(_DELTA_PREFIX)
                ):
                    family, ambiguous = _sniff_delta_family(bytes(chunk))
                    if not ambiguous and family == st.cur_type:
                        yield chunk
                        continue
                    # mismatch or ambiguity -> full parse below

                event = (
                    _parse_sse(chunk)
                    if is_bytes
                    else (
                        chunk
                        if isinstance(chunk, dict)
                        and chunk.get("type") in ANTHROPIC_EVENT_TYPES
                        else None
                    )
                )
                if event is None:  # not an anthropic event -> passthrough
                    for out in self._flush_pending(st):
                        yield out
                    yield chunk
                    continue

                for out in self._process(st, event, chunk, is_bytes):
                    yield out
            except Exception as err:  # I2 fail-open; I5 no payload in logs
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while processing a chunk "
                    "(passing through)",
                    type(err).__name__,
                )
                if st.pending is not None:
                    yield st.pending[1]
                    st.pending = None
                yield chunk
        if st.pending is not None:  # end of stream: flush dangling start
            yield st.pending[1]

    # ---- state machine -------------------------------------------------------

    def _flush_pending(self, st: _StreamState):
        if st.pending is not None:
            event, raw = st.pending
            st.pending = None
            st.cur_index = event.get("index", st.cur_index)
            st.cur_type = (event.get("content_block") or {}).get("type", "")
            st.block_open = True
            yield raw if st.offset == 0 else _sse(event)

    def _process(self, st, event, raw, as_bytes):
        etype = event["type"]
        shifted = False
        if etype in INDEXED_EVENTS and st.offset:
            event = dict(event)
            event["index"] = event.get("index", 0) + st.offset
            shifted = True

        def emit(ev, original_ok: bool):
            """Serialize ev; reuse original bytes when nothing changed."""
            if original_ok and not shifted:
                return raw
            return _sse(ev) if as_bytes else ev

        if etype == "content_block_start":
            for out in self._flush_pending(st):
                yield out
            st.pending = (event, raw if not shifted else _sse(event))
            return

        if etype == "content_block_delta":
            family = _delta_family(event)

            if st.pending is not None:
                start_event, start_raw = st.pending
                st.pending = None
                declared = (start_event.get("content_block") or {}).get("type", "")
                if family in ("text", "thinking") and declared in ("text", "thinking") and family != declared:
                    start_event = _make_start(start_event.get("index", 0), family)
                    RETYPED.inc()
                    verbose_proxy_logger.debug(
                        "[anthropic_stream_guard] retyped block %s -> %s",
                        start_event["index"], family,
                    )
                    yield _sse(start_event) if as_bytes else start_event
                else:
                    yield start_raw
                st.cur_index = start_event.get("index", 0)
                st.cur_type = (start_event.get("content_block") or {}).get("type", "")
                st.block_open = True
                yield emit(event, original_ok=True)
                return

            if (
                st.block_open
                and family in ("text", "thinking")
                and st.cur_type in ("text", "thinking")
                and family != st.cur_type
            ):
                # synthesize the block transition the adapter forgot to emit
                stop_ev = {"type": "content_block_stop", "index": st.cur_index}
                yield _sse(stop_ev) if as_bytes else stop_ev
                st.offset += 1
                st.cur_index += 1
                st.cur_type = family
                new_start = _make_start(st.cur_index, family)
                SYNTHESIZED.inc()
                verbose_proxy_logger.debug(
                    "[anthropic_stream_guard] synthesized %s block at index %s",
                    family, st.cur_index,
                )
                yield _sse(new_start) if as_bytes else new_start
                event = dict(event)
                event["index"] = st.cur_index
                yield _sse(event) if as_bytes else event
                return

            yield emit(event, original_ok=True)
            return

        if etype == "content_block_stop":
            for out in self._flush_pending(st):  # empty block: start then stop
                yield out
            st.block_open = False
            yield emit(event, original_ok=True)
            return

        # message_* / ping / error
        for out in self._flush_pending(st):
            yield out
        yield emit(event, original_ok=True)


proxy_handler_instance = AnthropicStreamGuard()
