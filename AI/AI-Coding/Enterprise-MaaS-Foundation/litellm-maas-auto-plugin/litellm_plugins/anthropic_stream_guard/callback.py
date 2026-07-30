"""
anthropic_stream_guard - LiteLLM custom callback (plugin, no core patches).

Fixes the malformed Anthropic SSE stream produced by LiteLLM's
messages->chat/completions adapter for backends that always emit
reasoning_content (e.g. GLM-5.1 on Huawei MaaS): the whole response arrives
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
  ASG_AMPLIFY_INTERJECTIONS=true|false  re-surface queued mid-task user
                                  messages as top-level text (default true)
  ASG_STRIP_SERVER_TOOLS=true|false  remove Anthropic server-tool entries
                                  (web_search etc.) the backend cannot run
                                  (default true)
  ASG_TRANSLATE_TOOL_CHOICE=true|false  translate forced Anthropic tool_choice
                                  to OpenAI-compatible function choice for
                                  direct-provider adapters (default false)
  ASG_NORMALIZE_IMAGE_URL=true|false  convert OpenAI-style image_url blocks
                                  to Anthropic image/source (default true)
  ASG_MAX_PARSE_BYTES=262144      max SSE event size that will be parsed

Prometheus metrics (exported via the proxy /metrics endpoint):
  asg_retyped_blocks_total      first-block type corrections
  asg_synthesized_blocks_total  synthesized stop/start pairs
  asg_parse_errors_total        chunks that failed to parse (passed through)
  asg_oversize_passthrough_total chunks skipped due to size cap
  asg_unparsed_tool_markup_total raw tool-call markup seen in text streams
  asg_amplified_interjections_total queued user messages re-surfaced (#115)
  asg_server_tools_stripped_total Anthropic server-tool entries removed
  asg_raw_sse_repaired_total Huawei raw pretty-JSON SSE frames repaired
  asg_openai_done_dropped_total trailing data: [DONE] chunks dropped
  asg_tool_choice_translated_total forced Anthropic tool_choice translations
"""

import json
import os
import re
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
TRANSLATE_TOOL_CHOICE = (
    os.getenv("ASG_TRANSLATE_TOOL_CHOICE", "false").strip().lower() == "true"
)
NORMALIZE_IMAGE_URL = (
    os.getenv("ASG_NORMALIZE_IMAGE_URL", "true").strip().lower() != "false"
)

# ---- issue #115: queued mid-task user messages -----------------------------
# Claude Code delivers messages typed while a task is running as
# <system-reminder> text buried inside the next tool_result, relying on the
# model to notice and obey. Models without that alignment (GLM-5.1) ignore
# it. We re-surface each queued message as a standalone text block at the END
# of the newest user message, where every chat template gives it top salience.
AMPLIFY_INTERJECTIONS = (
    os.getenv("ASG_AMPLIFY_INTERJECTIONS", "true").strip().lower() != "false"
)

# ---- Anthropic server tools ------------------------------------------------
# Claude Code's WebSearch sub-request (and some main-loop requests) declare
# Anthropic SERVER tools such as web_search_20250305 - schema-less entries
# executed by Anthropic's own backend. GLM/MaaS cannot execute them and its
# request validation intermittently rejects the whole call with
# "request param validation error, 'tools'". Search is fulfilled proxy-side
# (Exa injection), so these entries are pure poison for this backend.
STRIP_SERVER_TOOLS = (
    os.getenv("ASG_STRIP_SERVER_TOOLS", "true").strip().lower() != "false"
)
SERVER_TOOL_TYPE_PREFIXES = (
    "web_search",
    "web_fetch",
    "computer_",
    "bash_",
    "text_editor_",
    "code_execution",
    "memory_",
)
INTERJECTION_MARKER = "address the user's message"
AMPLIFIED_HEADER = "[USER INTERJECTION - queued while the previous task was running]"
_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>(.*?)</system-reminder>", re.DOTALL)

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
    INTERJECTIONS = _Counter(
        "asg_amplified_interjections_total",
        "queued mid-task user messages re-surfaced as top-level text (#115)",
    )
    SERVER_TOOLS_STRIPPED = _Counter(
        "asg_server_tools_stripped_total",
        "Anthropic server-tool entries removed before the OpenAI-compatible "
        "backend (GLM/MaaS rejects them with a 'tools' validation error)",
    )
    RAW_SSE_REPAIRED = _Counter(
        "asg_raw_sse_repaired_total",
        "Huawei raw pretty-JSON SSE frames repaired into Anthropic SSE",
    )
    OPENAI_DONE_DROPPED = _Counter(
        "asg_openai_done_dropped_total",
        "OpenAI-style data: [DONE] chunks dropped after Anthropic message_stop",
    )
    TOOL_CHOICE_TRANSLATED = _Counter(
        "asg_tool_choice_translated_total",
        "Forced Anthropic tool_choice values translated to OpenAI function choice",
    )
except Exception:  # duplicate registration, missing dep, ...

    class _Noop:
        def inc(self, *_a, **_k):
            pass

    RETYPED = SYNTHESIZED = PARSE_ERRORS = OVERSIZE = SYNTH_TERM = (
        UPSTREAM_ERRORS
    ) = TOOL_MARKUP = INTERJECTIONS = SERVER_TOOLS_STRIPPED = RAW_SSE_REPAIRED = (
        OPENAI_DONE_DROPPED
    ) = TOOL_CHOICE_TRANSLATED = _Noop()

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


def _parse_sse_with_repair_flag(chunk: bytes) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Parse one serialized SSE event.

    Returns (event, repaired). "repaired" is true only for Huawei's malformed
    frame shape where `data:` is followed by un-prefixed pretty JSON lines.
    """
    try:
        text = chunk.decode("utf-8")
    except Exception:
        return None, False

    event_name = None
    event_dict = None
    repaired = False
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("event: "):
            event_name = line[7:].strip()
        if line.startswith("data: "):
            if event_dict is not None:  # multiple data lines -> not ours, bail
                return None, False
            payload = line[6:]
            if payload.strip() == "[DONE]":
                return None, False
            try:
                event_dict = json.loads(payload)
            except Exception:
                PARSE_ERRORS.inc()
                return None, False
        elif line == "data:":
            if event_dict is not None:
                return None, False
            repaired = True
            payload_lines = []
            remainder_start = len(lines)
            for offset, continuation in enumerate(lines[i + 1:], start=i + 1):
                if continuation == "":
                    remainder_start = offset + 1
                    break
                payload_lines.append(continuation)
            if any(line.strip() for line in lines[remainder_start:]):
                return None, False
            if not payload_lines:
                return None, False
            try:
                event_dict = json.loads("\n".join(payload_lines))
            except Exception:
                PARSE_ERRORS.inc()
                return None, False
            break
    if (
        isinstance(event_dict, dict)
        and event_dict.get("type") in ANTHROPIC_EVENT_TYPES
        and (event_name is None or event_name == event_dict.get("type"))
    ):
        return event_dict, repaired
    return None, False


def _parse_sse(chunk: bytes) -> Optional[Dict[str, Any]]:
    """Parse one serialized SSE event; None if not a single anthropic event."""
    event, _repaired = _parse_sse_with_repair_flag(chunk)
    return event


def _is_openai_done(chunk: bytes) -> bool:
    try:
        lines = [line.strip() for line in chunk.decode("utf-8").splitlines()]
    except Exception:
        return False
    meaningful = [line for line in lines if line]
    return meaningful == ["data: [DONE]"]


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


def _last_message_strings(content):
    for block in content:
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("text"), str):
            yield block["text"]
        elif block.get("type") == "tool_result":
            inner = block.get("content")
            if isinstance(inner, str):
                yield inner
            elif isinstance(inner, list):
                for item in inner:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        yield item["text"]


def strip_server_tools(data: Dict[str, Any]) -> int:
    """Remove Anthropic server-tool entries (no input_schema, versioned
    type like web_search_20250305) from the request's tools list. Client
    tools - which always carry input_schema - are never touched. When
    nothing remains, tools and tool_choice are dropped entirely."""
    tools = data.get("tools")
    if not isinstance(tools, list):
        return 0
    kept = []
    removed = 0
    for tool in tools:
        if (
            isinstance(tool, dict)
            and "input_schema" not in tool
            and isinstance(tool.get("type"), str)
            and tool["type"].startswith(SERVER_TOOL_TYPE_PREFIXES)
        ):
            removed += 1
            continue
        kept.append(tool)
    if removed:
        if kept:
            data["tools"] = kept
        else:
            data.pop("tools", None)
            data.pop("tool_choice", None)
    return removed


def translate_forced_tool_choice(data: Dict[str, Any]) -> bool:
    """Translate Anthropic forced tool_choice to OpenAI-compatible function
    choice. `auto`, `any`, and `none` are intentionally left untouched."""
    choice = data.get("tool_choice")
    if not isinstance(choice, dict):
        return False
    if choice.get("type") != "tool" or not isinstance(choice.get("name"), str):
        return False
    data["tool_choice"] = {
        "type": "function",
        "function": {"name": choice["name"]},
    }
    return True


_DATA_URL_RE = re.compile(r"^data:([^;,]+);base64,(.*)$", re.DOTALL)


def _image_source_from_image_url(value: Any) -> Optional[Dict[str, str]]:
    if isinstance(value, dict):
        url = value.get("url")
    else:
        url = value
    if not isinstance(url, str) or not url:
        return None
    match = _DATA_URL_RE.match(url)
    if match:
        return {
            "type": "base64",
            "media_type": match.group(1),
            "data": match.group(2),
        }
    return {"type": "url", "url": url}


def normalize_image_url_blocks(data: Dict[str, Any]) -> int:
    """Convert OpenAI-style image_url blocks into Anthropic image/source.

    Meli's original failing image case used `image_url`. LiteLLM's Messages
    adapter passes Anthropic `image/source` through to vision models, but it
    silently loses OpenAI-style `image_url` blocks on /v1/messages.
    """
    if not isinstance(data, dict):
        return 0
    changed = 0
    for message in data.get("messages") or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "image_url":
                continue
            source = _image_source_from_image_url(block.get("image_url"))
            if source:
                block.clear()
                block.update({"type": "image", "source": source})
                changed += 1
    return changed


def apply_stop_sequences(data: Dict[str, Any], response: Any) -> bool:
    if not isinstance(data, dict):
        return False
    stop_sequences = data.get("stop_sequences") or data.get("stop")
    if isinstance(stop_sequences, str):
        stop_sequences = [stop_sequences]
    if not isinstance(stop_sequences, list) or not stop_sequences:
        return False
    if not isinstance(response, dict):
        return False
    content = response.get("content")
    if not isinstance(content, list):
        return False
    stopped = None
    new_content = []
    for block in content:
        if stopped is not None:
            continue
        if not isinstance(block, dict) or block.get("type") != "text":
            new_content.append(block)
            continue
        text = block.get("text")
        if not isinstance(text, str):
            new_content.append(block)
            continue
        hit = min(
            (
                (text.find(seq), seq)
                for seq in stop_sequences
                if isinstance(seq, str) and seq and text.find(seq) >= 0
            ),
            default=None,
        )
        if hit is None:
            new_content.append(block)
            continue
        index, stopped = hit
        fixed = dict(block)
        fixed["text"] = text[:index]
        new_content.append(fixed)
    if stopped is None:
        return False
    response["content"] = new_content
    response["stop_reason"] = "stop_sequence"
    response["stop_sequence"] = stopped
    return True


def amplify_user_interjections(data: Dict[str, Any]) -> int:
    """Re-surface queued mid-task user messages (#115). Only the NEWEST user
    message is scanned - older occurrences are history the client resends
    verbatim and must not be resurrected. Idempotent across retries."""
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return 0
    last = messages[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return 0
    content = last.get("content")
    if not isinstance(content, list):
        return 0
    for block in content:  # retry idempotency
        if (
            isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"].startswith(AMPLIFIED_HEADER)
        ):
            return 0
    seen = []
    for text in _last_message_strings(content):
        for match in _SYSTEM_REMINDER_RE.finditer(text):
            inner = match.group(1).strip()
            if INTERJECTION_MARKER in inner and inner not in seen:
                seen.append(inner)
    for inner in seen:
        content.append({
            "type": "text",
            "text": (
                AMPLIFIED_HEADER
                + "\nRespond to the user message below FIRST, before any "
                "further tool calls or task steps. If it changes the current "
                "plan, follow it.\n---\n" + inner + "\n---"
            ),
        })
    return len(seen)


class AnthropicStreamGuard(CustomLogger):
    # ---- request side ------------------------------------------------------

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Strip Anthropic thinking/reasoning params so /v1/messages routes
        via chat/completions instead of the (unsupported) Responses API.
        Also re-surfaces queued mid-task user messages (#115)."""
        if NORMALIZE_IMAGE_URL and isinstance(data, dict):
            try:
                normalize_image_url_blocks(data)
            except Exception as err:  # fail-open
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while normalizing image_url "
                    "blocks (request passed through)",
                    type(err).__name__,
                )
        if STRIP_THINKING and isinstance(data, dict):
            for key in STRIPPED_REQUEST_KEYS:
                data.pop(key, None)
        if STRIP_SERVER_TOOLS and isinstance(data, dict):
            try:
                stripped = strip_server_tools(data)
                if stripped:
                    SERVER_TOOLS_STRIPPED.inc(stripped)
                    verbose_proxy_logger.warning(
                        "[anthropic_stream_guard] stripped %s Anthropic "
                        "server tool(s) the backend cannot execute",
                        stripped,
                    )
            except Exception as err:  # fail-open
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while stripping server "
                    "tools (request passed through)",
                    type(err).__name__,
                )
        if TRANSLATE_TOOL_CHOICE and isinstance(data, dict):
            try:
                if translate_forced_tool_choice(data):
                    TOOL_CHOICE_TRANSLATED.inc()
                    verbose_proxy_logger.debug(
                        "[anthropic_stream_guard] translated forced "
                        "Anthropic tool_choice to function choice"
                    )
            except Exception as err:  # fail-open
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while translating "
                    "tool_choice (request passed through)",
                    type(err).__name__,
                )
        if AMPLIFY_INTERJECTIONS and isinstance(data, dict):
            try:
                count = amplify_user_interjections(data)
                if count:
                    INTERJECTIONS.inc(count)
                    verbose_proxy_logger.warning(
                        "[anthropic_stream_guard] re-surfaced %s queued user "
                        "message(s) as top-level text (#115)",
                        count,
                    )
            except Exception as err:  # fail-open, no payload in logs
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while amplifying "
                    "interjections (request passed through)",
                    type(err).__name__,
                )
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        _normalize_thinking_signatures(response)
        apply_stop_sequences(data, response)
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

                repaired_sse = False
                if is_bytes:
                    event, repaired_sse = _parse_sse_with_repair_flag(bytes(chunk))
                    if (
                        event is None
                        and st.saw_message_stop
                        and _is_openai_done(bytes(chunk))
                    ):
                        OPENAI_DONE_DROPPED.inc()
                        continue
                    if repaired_sse and event is not None:
                        RAW_SSE_REPAIRED.inc()
                        chunk = _sse(event)
                else:
                    event = (
                        chunk
                        if isinstance(chunk, dict)
                        and chunk.get("type") in ANTHROPIC_EVENT_TYPES
                        else None
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
