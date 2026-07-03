"""
anthropic_stream_guard - LiteLLM custom callback (plugin, no core patches).

Fixes the malformed Anthropic SSE stream produced by LiteLLM's
messages->chat/completions adapter for backends that always emit
reasoning_content (e.g. GLM-5.2 on Huawei MaaS): the whole response arrives
as ONE "text" content block mixing thinking_delta and text_delta events.
Also strips Anthropic thinking/reasoning request params so /v1/messages
stays on /chat/completions instead of the unsupported Responses API.

Additionally repairs streams the upstream ends early: GLM on MaaS sometimes
closes its SSE right after a tool call without a terminal chunk, so the
adapter emits no message_delta/message_stop; Claude Code then reports
"API Error: Connection closed mid-response" despite having received the
content. On end-of-stream (including upstream iterator exceptions) the guard
synthesizes the missing content_block_stop / message_delta / message_stop.

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
  asg_unparsed_tool_markup_total raw tool-call markup seen in text streams
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
BLOCK_FAMILIES = {"thinking", "text", "tool_use"}
TOOL_MARKUP_PREFIX = b"<tool_call"

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
    SYNTH_TERM = _Counter(
        "asg_synthesized_terminations_total",
        "streams that ended early and got synthesized terminal events",
    )
    UPSTREAM_ERRORS = _Counter(
        "asg_upstream_stream_errors_total",
        "exceptions raised by the upstream stream iterator (stream finalized)",
    )
    TOOL_MARKUP = _Counter(
        "asg_unparsed_tool_markup_total",
        "streams where raw <tool_call markup appeared in text while the "
        "request declared tools (backend endpoint not parsing tool calls)",
    )
except Exception:  # duplicate registration, missing dep, ...

    class _Noop:
        def inc(self, *_a, **_k):
            pass

    RETYPED = SYNTHESIZED = PARSE_ERRORS = OVERSIZE = SYNTH_TERM = (
        UPSTREAM_ERRORS
    ) = TOOL_MARKUP = _Noop()

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


def _request_has_tools(request_data: Any) -> bool:
    if not isinstance(request_data, dict):
        return False
    tools = request_data.get("tools")
    return isinstance(tools, list) and len(tools) > 0


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


def _text_delta_from_input_json(event: Dict[str, Any]) -> Dict[str, Any]:
    """Treat impossible tool-call argument deltas as plain text.

    Some OpenAI-compatible backends emit tool-call deltas even when the
    Anthropic request declared no tools. LiteLLM then maps those to
    input_json_delta. Passing that through creates a fake Claude Code tool call
    named "tool"; preserving the fragment as text is the least surprising
    recovery for no-tool requests.
    """
    delta = event.get("delta") if isinstance(event, dict) else None
    if not isinstance(delta, dict) or delta.get("type") != "input_json_delta":
        return event
    fixed = dict(event)
    fixed["delta"] = {
        "type": "text_delta",
        "text": str(delta.get("partial_json") or ""),
    }
    return fixed


def _has_tool_identity(block: Any) -> bool:
    if not isinstance(block, dict):
        return False
    return isinstance(block.get("id"), str) and isinstance(block.get("name"), str)


def _text_delta_bytes(event: Any) -> Optional[bytes]:
    if not isinstance(event, dict):
        return None
    delta = event.get("delta")
    if isinstance(delta, dict) and delta.get("type") == "text_delta":
        text = delta.get("text")
        if isinstance(text, str):
            return text.encode("utf-8", errors="ignore")
    return None


def _detect_tool_markup(st: "_StreamState", event: Any) -> bool:
    sample = _text_delta_bytes(event)
    if not sample:
        return False
    combined = st.markup_tail + sample
    keep = max(0, len(TOOL_MARKUP_PREFIX) - 1)
    st.markup_tail = combined[-keep:] if keep else b""
    return TOOL_MARKUP_PREFIX in combined


def _raw_chunk_has_tool_markup(chunk: Any) -> bool:
    return isinstance(chunk, (bytes, bytearray)) and TOOL_MARKUP_PREFIX in chunk


def _normalize_thinking_signatures(value: Any, seen: Optional[set] = None) -> Any:
    """LiteLLM's success logger requires thinking.signature to be a string."""
    if seen is None:
        seen = set()
    value_id = id(value)
    if value_id in seen:
        return value
    seen.add(value_id)

    if isinstance(value, dict):
        if value.get("type") == "thinking" and value.get("signature") is None:
            value["signature"] = ""
        for item in value.values():
            _normalize_thinking_signatures(item, seen)
        return value

    if isinstance(value, list):
        for item in value:
            _normalize_thinking_signatures(item, seen)
        return value

    content = getattr(value, "content", None)
    if content is not None:
        _normalize_thinking_signatures(content, seen)

    if getattr(value, "type", None) == "thinking" and getattr(value, "signature", None) is None:
        try:
            setattr(value, "signature", "")
        except Exception:
            pass
    return value


def _make_start(
    index: int,
    block_type: str,
    source_block: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if block_type == "thinking":
        block = {"type": "thinking", "thinking": "", "signature": ""}
    elif block_type == "tool_use":
        source = source_block if isinstance(source_block, dict) else {}
        # Tool blocks are only synthesized after the caller has verified that
        # the stream supplied real tool identity metadata.
        block = {
            "type": "tool_use",
            "id": source["id"],
            "name": source["name"],
            "input": source.get("input") if isinstance(source.get("input"), dict) else {},
        }
    else:
        block = {"type": "text", "text": ""}
    return {"type": "content_block_start", "index": index, "content_block": block}


class _StreamState:
    """Per-request state only (I1). Never promote fields to module/class level."""

    __slots__ = (
        "offset",
        "cur_index",
        "cur_type",
        "block_open",
        "pending",
        "request_has_tools",
        "saw_message_start",
        "saw_message_delta",
        "saw_message_stop",
        "saw_tool_use",
        "last_was_bytes",
        "markup_warned",
        "markup_tail",
    )

    def __init__(self, request_has_tools: bool = False) -> None:
        self.offset = 0          # index shift from synthesized blocks
        self.cur_index = 0       # output-side index of the open block
        self.cur_type = ""       # effective type of the open block
        self.block_open = False
        # buffered (event, raw_chunk); raw only reusable while offset == 0
        self.pending: Optional[Tuple[Dict[str, Any], Any]] = None
        self.request_has_tools = request_has_tools
        # terminal-event bookkeeping for end-of-stream synthesis
        self.saw_message_start = False
        self.saw_message_delta = False
        self.saw_message_stop = False
        self.saw_tool_use = False
        self.last_was_bytes = True
        self.markup_warned = False
        self.markup_tail = b""


class AnthropicStreamGuard(CustomLogger):
    # ---- request side ------------------------------------------------------

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Strip Anthropic thinking/reasoning params so /v1/messages routes
        via chat/completions instead of the (unsupported) Responses API."""
        if STRIP_THINKING and isinstance(data, dict):
            for key in STRIPPED_REQUEST_KEYS:
                data.pop(key, None)
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        _normalize_thinking_signatures(response)
        return response

    async def async_logging_hook(self, kwargs: dict, result: Any, call_type: str):
        _normalize_thinking_signatures(result)
        return kwargs, result

    # ---- response side -----------------------------------------------------

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        st = _StreamState(request_has_tools=_request_has_tools(request_data))
        response_iter = response.__aiter__()
        while True:
            try:
                chunk = await response_iter.__anext__()
            except StopAsyncIteration:
                break
            except Exception as err:
                # Upstream died mid-stream. Finalize instead of propagating so
                # the client still receives a well-formed message (I2).
                UPSTREAM_ERRORS.inc()
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s from upstream stream "
                    "(finalizing early)",
                    type(err).__name__,
                )
                break
            try:
                is_bytes = isinstance(chunk, (bytes, bytearray))
                st.last_was_bytes = is_bytes

                # Diagnostic only (issue #111): the model writing its native
                # tool-call template as visible text means the backend endpoint
                # is not parsing tool calls. Rewriting improvised markup would
                # be unstable and could corrupt legitimate code text, so we
                # surface it via metric + log instead.
                if (
                    st.request_has_tools
                    and not st.markup_warned
                    and _raw_chunk_has_tool_markup(chunk)
                ):
                    st.markup_warned = True
                    TOOL_MARKUP.inc()
                    verbose_proxy_logger.warning(
                        "[anthropic_stream_guard] raw '<tool_call' markup in "
                        "stream text while the request declared tools - the "
                        "backend endpoint likely has no tool-call parser "
                        "(tool calls will render as plain text in clients)"
                    )

                # I4: never parse oversized events; forward as-is.
                if is_bytes and len(chunk) > MAX_PARSE_BYTES:
                    OVERSIZE.inc()
                    self._note_passthrough_terminals(st, bytes(chunk))
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
                    and (
                        not st.request_has_tools
                        or st.markup_warned
                        or (not st.markup_tail and TOOL_MARKUP_PREFIX[:1] not in chunk)
                    )
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
                    if is_bytes:
                        self._note_passthrough_terminals(st, bytes(chunk))
                    for out in self._flush_pending(st):
                        yield out
                    yield chunk
                    continue

                if (
                    st.request_has_tools
                    and not st.markup_warned
                    and _detect_tool_markup(st, event)
                ):
                    st.markup_warned = True
                    TOOL_MARKUP.inc()
                    verbose_proxy_logger.warning(
                        "[anthropic_stream_guard] raw '<tool_call' markup in "
                        "stream text while the request declared tools - the "
                        "backend endpoint likely has no tool-call parser "
                        "(tool calls will render as plain text in clients)"
                    )

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
        for out in self._finalize(st):
            yield out

    # ---- state machine -------------------------------------------------------

    @staticmethod
    def _note_passthrough_terminals(st: _StreamState, chunk: bytes) -> None:
        """Terminal markers seen in chunks we forward without parsing (multi-
        event chunks, oversized chunks) disable end-of-stream synthesis. A
        faked marker in attacker-influenced text can only SUPPRESS the rescue,
        never inject events, so this is safe in the fail-open direction."""
        if b"message_stop" in chunk:
            st.saw_message_stop = True
        if b"message_start" in chunk:
            st.saw_message_start = True

    def _finalize(self, st: _StreamState):
        """End of stream: flush a dangling start, then synthesize the terminal
        events the upstream/adapter failed to send. Without message_stop,
        Claude Code reports 'Connection closed mid-response' and discards the
        turn's continuity even though the content arrived intact."""
        for out in self._flush_pending(st):
            yield out
        if not st.saw_message_start or st.saw_message_stop:
            return
        if st.block_open:
            stop_ev = {"type": "content_block_stop", "index": st.cur_index}
            yield _sse(stop_ev) if st.last_was_bytes else stop_ev
            st.block_open = False
        if not st.saw_message_delta:
            delta_ev = {
                "type": "message_delta",
                "delta": {
                    "stop_reason": "tool_use" if st.saw_tool_use else "end_turn",
                    "stop_sequence": None,
                },
                "usage": {"output_tokens": 0},
            }
            yield _sse(delta_ev) if st.last_was_bytes else delta_ev
        stop_msg = {"type": "message_stop"}
        yield _sse(stop_msg) if st.last_was_bytes else stop_msg
        SYNTH_TERM.inc()
        verbose_proxy_logger.warning(
            "[anthropic_stream_guard] stream ended without terminal events; "
            "synthesized %s + message_stop",
            "message_delta" if not st.saw_message_delta else "message_stop",
        )

    def _flush_pending(self, st: _StreamState):
        if st.pending is not None:
            event, raw = st.pending
            st.pending = None
            st.cur_index = event.get("index", st.cur_index)
            st.cur_type = (event.get("content_block") or {}).get("type", "")
            st.block_open = True
            if st.cur_type == "tool_use":
                st.saw_tool_use = True
            yield raw if st.offset == 0 else _sse(event)

    def _process(self, st, event, raw, as_bytes):
        etype = event["type"]
        if etype == "message_start":
            st.saw_message_start = True
        elif etype == "message_delta":
            st.saw_message_delta = True
        elif etype == "message_stop":
            st.saw_message_stop = True
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
            original_ok = True
            if (
                st.pending is None
                and family == "tool_use"
                and st.cur_type != "tool_use"
            ):
                event = _text_delta_from_input_json(event)
                family = "text"
                original_ok = False

            if st.pending is not None:
                start_event, start_raw = st.pending
                st.pending = None
                declared = (start_event.get("content_block") or {}).get("type", "")
                if (
                    family == "tool_use"
                    and declared != "tool_use"
                    and (
                        not st.request_has_tools
                        or not _has_tool_identity(start_event.get("content_block"))
                    )
                ):
                    event = _text_delta_from_input_json(event)
                    family = "text"
                    original_ok = False
                if family in BLOCK_FAMILIES and family != declared:
                    source_block = start_event.get("content_block")
                    start_event = _make_start(
                        start_event.get("index", 0),
                        family,
                        source_block if isinstance(source_block, dict) else None,
                    )
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
                if st.cur_type == "tool_use":
                    st.saw_tool_use = True
                yield emit(event, original_ok=original_ok)
                return

            if (
                st.block_open
                and family in BLOCK_FAMILIES
                and st.cur_type in BLOCK_FAMILIES
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

            yield emit(event, original_ok=original_ok)
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
