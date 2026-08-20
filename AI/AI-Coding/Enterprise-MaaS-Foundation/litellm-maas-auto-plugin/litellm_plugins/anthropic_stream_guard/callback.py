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
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger

# ── Tool Argument Guard (PRD-tool-argument-guard) ───────────────────────────
# Loaded lazily so a missing /app/tool_argument_guard.py degrades gracefully.
# In observe mode the guard validates and records metrics but does not change
# output. In enforce mode it buffers tool blocks, validates, normalizes,
# repairs via Premium, and rejects unresolved invalid calls. In off mode it is
# a complete no-op.

def _load_tool_argument_guard():
    try:
        import tool_argument_guard  # type: ignore
        return tool_argument_guard
    except ImportError:
        return None


_TAG = _load_tool_argument_guard()
_TAG_ENFORCE = bool(_TAG and _TAG.is_enforce())
_TAG_OBSERVE = bool(_TAG and _TAG.is_observe())
_TAG_PREMIUM_ENABLED = bool(
    _TAG and os.getenv("TOOL_ARG_PREMIUM_REPAIR", "true").lower() in ("1", "true", "yes", "on")
)


def _load_sidecar_for_repair():
    """Import the sidecar module for Premium tool-argument repair."""
    try:
        import sidecar  # type: ignore
        return sidecar
    except ImportError:
        return None


def _make_tool_start(index: int, tool_id: str, name: str) -> Dict[str, Any]:
    """Build a canonical content_block_start for a repaired tool_use block."""
    return {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "tool_use", "id": tool_id, "name": name, "input": {}},
    }


def _make_text_start(index: int) -> Dict[str, Any]:
    """Build a content_block_start for a safe-text replacement block."""
    return {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "text", "text": ""},
    }

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
# Raw tool-call markup the model emits as visible text when the backend endpoint
# has no tool-call parser. The guard passes it through byte-identical (it does
# NOT rewrite improvised markup) and counts it via asg_unparsed_tool_markup_total.
#
# PRD-glm52-mainline-sidecars §10.1/§16: this raw markup is the Premium recovery
# sidecar's trigger signal 2. Correlation to the next turn is automatic — the
# markup text becomes part of the assistant message in conversation history, and
# the next request's sidecar.detect_triggers scans the last assistant message
# for this same prefix. No separate signal channel is needed.
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

# Internal sidecar key (PRD-glm52-mainline-sidecars §6/§13). When set, requests
# authenticated with this key are internal sidecar calls to /v1/chat/completions
# and skip the Anthropic-specific normalizations that would corrupt their
# OpenAI-format payloads. Read at call time (not import time) so it can be
# rotated without a restart.
_SIDECAR_API_KEY = os.getenv("SIDECAR_API_KEY", "")


def _is_sidecar_internal_key(user_api_key_dict) -> bool:
    """True when the authenticated key is the configured internal sidecar key.

    This is the recursion bypass (I5/I10): key identity, not client metadata.
    LiteLLM stores keys as SHA-256 hashes in the 'token'/'api_key' field, so we
    compare against the hash of SIDECAR_API_KEY (and accept a raw match for tests).

    ``user_api_key_dict`` is a LiteLLM UserAPIKeyAuth Pydantic model in
    production (NOT a plain dict), so we use getattr — which works for both
    Pydantic models and plain dicts (tests).
    """
    key_env = os.getenv("SIDECAR_API_KEY", "")
    if not key_env or user_api_key_dict is None:
        return False
    authed = (
        getattr(user_api_key_dict, "token", None)
        or getattr(user_api_key_dict, "api_key", None)
        or (user_api_key_dict.get("key") if isinstance(user_api_key_dict, dict) else None)
        or ""
    )
    if not authed:
        return False
    import hashlib as _hl
    hashed = _hl.sha256(key_env.encode("utf-8")).hexdigest()
    return authed == key_env or authed == hashed

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


# ── Typed error: raw tool-call markup as text (PRD-remove-tool-disabling §5.4) ─
#
# When the model emits raw <tool_call markup inside assistant text, the tool
# call did not execute. Forwarding it as prose would let the user read a
# fabricated success ("✅ 脚本已写好").  Instead, raise this typed error so the
# proxy returns HTTP 502 UNPARSED_TOOL_MARKUP — the same shape as
# VISION_SIDECAR_UNAVAILABLE.  The _litellm_adapter maps it via http_status.
#
# This check runs regardless of whether the request declared tools.  The old
# gate (st.request_has_tools) was the §2.3 bite point: after the hard-stop
# deleted tools, request_has_tools went False and detection shut off exactly
# when it was needed most.

class UnparsedToolMarkupError(Exception):
    """Model emitted raw tool-call markup as text; the tool call did not execute.

    Propagates to the client as HTTP 502 UNPARSED_TOOL_MARKUP via the
    _litellm_adapter (same mapping as sidecar.SidecarError subclasses).
    """

    http_status = 502
    error_code = "UNPARSED_TOOL_MARKUP"


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


def _raise_if_raw_markup_in_response(response: Any) -> None:
    """Non-streaming counterpart of the stream markup check (PRD §5.4).

    Scans the response text content for raw <tool_call markup. If found,
    raises UnparsedToolMarkupError (→ 502). Handles both Anthropic-shape
    (content[].text) and OpenAI-shape (choices[].message.content) responses.
    """
    if not isinstance(response, dict):
        return
    # Anthropic shape: content is a list of blocks.
    content = response.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str) and TOOL_MARKUP_PREFIX.decode("utf-8", "ignore") in text:
                    TOOL_MARKUP.inc()
                    raise UnparsedToolMarkupError(
                        "model emitted raw tool-call markup as text; the tool "
                        "call did not execute"
                    )
    # OpenAI shape: choices[].message.content is a string.
    choices = response.get("choices")
    if isinstance(choices, list):
        _prefix = TOOL_MARKUP_PREFIX.decode("utf-8", "ignore")
        for choice in choices:
            msg = (choice or {}).get("message") if isinstance(choice, dict) else None
            if isinstance(msg, dict):
                text = msg.get("content", "")
                if isinstance(text, str) and _prefix in text:
                    TOOL_MARKUP.inc()
                    raise UnparsedToolMarkupError(
                        "model emitted raw tool-call markup as text; the tool "
                        "call did not execute"
                    )


def _out_event(out: Any) -> Any:
    """Extract the event dict from a yielded output (bytes SSE or dict)."""
    if isinstance(out, dict):
        return out
    if isinstance(out, (bytes, bytearray)):
        for ln in out.decode("utf-8", "replace").split("\n"):
            if ln.startswith("data: "):
                try:
                    return json.loads(ln[6:])
                except (ValueError, json.JSONDecodeError):
                    return None
    return None


def _tag_session_anchor(request_data: Any) -> str:
    """Extract a session anchor from request data for fingerprinting."""
    if not isinstance(request_data, dict):
        return ""
    meta = request_data.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("session_id"):
        return str(meta["session_id"])
    for msg in (request_data.get("messages") or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:512]
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") in {"text", "input_text"}
                )[:512]
    return ""


async def _validate_non_stream_tools(data: dict, response: Any) -> None:
    """Validate tool_use blocks in a non-streaming response (PRD v2 §7.6 R6).

    Uses the same decide() as streaming so the decision is transport-neutral and
    atomic. Delegates Anthropic and OpenAI rendering to sub-functions.
    """
    if not isinstance(response, dict):
        return
    schema_map = _TAG.build_schema_map(data)
    if not schema_map.has_tools:
        return
    session_anchor = _tag_session_anchor(data)

    # Anthropic shape: content[].tool_use
    content = response.get("content")
    if isinstance(content, list):
        await _validate_non_stream_anthropic(content, response, schema_map, session_anchor)

    # OpenAI shape: choices[].message.tool_calls[].function.arguments
    choices = response.get("choices")
    if isinstance(choices, list):
        await _validate_non_stream_openai(choices, schema_map, session_anchor)


async def _validate_non_stream_anthropic(content, response, schema_map, session_anchor):
    """Validate Anthropic non-stream tool_use blocks atomically (R6)."""
    tool_blocks = [(i, b, b.get("input")) for i, b in enumerate(content)
                   if isinstance(b, dict) and b.get("type") == "tool_use"]
    if not tool_blocks:
        return
    tool_calls = [
        {"index": i, "name": b.get("name", ""), "tool_id": b.get("id", ""), "args": a}
        for i, b, a in tool_blocks
    ]
    decision = await _TAG.decide(tool_calls, schema_map, repair_fn=_premium_repair, session_anchor=session_anchor)
    tr_by_idx = {tr.index: tr for tr in decision.per_tool}

    if decision.outcome == _TAG.DecisionOutcome.REJECTED:
        for i, block, _ in tool_blocks:
            tr = tr_by_idx.get(i) or tr_by_idx.get(tool_blocks[0][0])
            _replace_with_text(block, tr.reason if tr else "set_rejected")
        if response.get("stop_reason") == "tool_use":
            response["stop_reason"] = "end_turn"
    else:
        for i, block, _ in tool_blocks:
            tr = tr_by_idx.get(i)
            if tr and tr.outcome in ("pass", "repair"):
                block["input"] = tr.args


async def _validate_non_stream_openai(choices, schema_map, session_anchor):
    """Validate OpenAI non-stream tool_calls atomically (R6)."""
    for choice in choices:
        msg = (choice or {}).get("message") if isinstance(choice, dict) else None
        if not isinstance(msg, dict):
            continue
        tool_calls_raw = msg.get("tool_calls")
        if not isinstance(tool_calls_raw, list) or not tool_calls_raw:
            continue

        tc_entries = []
        for j, tc in enumerate(tool_calls_raw):
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            args = None
            if isinstance(fn.get("arguments"), str):
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError:
                    args = None
            tc_entries.append((j, tc, fn, fn.get("name", ""), args))

        if not tc_entries:
            continue
        tool_calls = [{"index": j, "name": name, "tool_id": "", "args": a} for j, _, _, name, a in tc_entries]
        decision = await _TAG.decide(tool_calls, schema_map, repair_fn=_premium_repair, session_anchor=session_anchor)

        if decision.outcome == _TAG.DecisionOutcome.REJECTED:
            msg["tool_calls"] = []
            if choice.get("finish_reason") == "tool_calls":
                choice["finish_reason"] = "stop"
        else:
            tr_by_idx = {tr.index: tr for tr in decision.per_tool}
            for j, tc, fn, _, _ in tc_entries:
                tr = tr_by_idx.get(j)
                if tr and tr.outcome in ("pass", "repair"):
                    fn["arguments"] = json.dumps(tr.args, ensure_ascii=False)


def _replace_with_text(block: dict, reason: str) -> None:
    """Replace a tool_use block with a safe text block (PRD §11.3)."""
    tool_name = block.get("name", "")
    block["type"] = "text"
    block["text"] = _TAG.REJECTION_TEXT
    block.pop("input", None)
    block.pop("id", None)
    block.pop("name", None)
    _TAG.TAG_REJECTIONS.labels(tool=tool_name, reason=reason).inc()


def _observe_non_stream_tools(data: dict, response: Any) -> None:
    """Observe-mode non-stream validation (PRD §7.2, §12).

    Validates tool_use blocks against the request schemas and emits metrics
    WITHOUT modifying the response (PRD §7.2): no normalization, no Premium
    calls, no rejection, no byte changes.
    """
    if not isinstance(response, dict) or _TAG is None:
        return
    schema_map = _TAG.build_schema_map(data)
    if not schema_map.has_tools:
        return

    def _validate_one(tool_name: str, args: Any) -> None:
        schema = schema_map.get(tool_name)
        if schema is None:
            _TAG.TAG_REJECTIONS.labels(tool=tool_name, reason="unknown_tool").inc()
            _TAG.TAG_CALLS.labels(tool=tool_name, outcome="unknown").inc()
            return
        ok, errors = _TAG.validate_arguments(args, schema)
        if ok:
            _TAG.TAG_CALLS.labels(tool=tool_name, outcome="pass").inc()
        else:
            _TAG.record_validation_failure(tool_name, schema_map.hash_of(tool_name), errors)
            _TAG.TAG_CALLS.labels(tool=tool_name, outcome="invalid").inc()

    # Anthropic shape: content[].tool_use
    content = response.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "")
            args = block.get("input")
            if isinstance(args, dict):
                _validate_one(tool_name, args)

    # OpenAI shape: choices[].message.tool_calls[].function.arguments
    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            msg = (choice or {}).get("message") if isinstance(choice, dict) else None
            if not isinstance(msg, dict):
                continue
            tool_calls = msg.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                tool_name = fn.get("name", "")
                args_str = fn.get("arguments")
                if not isinstance(args_str, str):
                    continue
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    _TAG.TAG_REJECTIONS.labels(tool=tool_name, reason="parse_error").inc()
                    _TAG.TAG_CALLS.labels(tool=tool_name, outcome="invalid").inc()
                    continue
                if isinstance(args, dict):
                    _validate_one(tool_name, args)


async def _premium_repair(tool_name, schema, args, errors, session_anchor):
    """Call the sidecar's repair_tool_arguments (one shot per fingerprint)."""
    if not _TAG_PREMIUM_ENABLED:
        return None
    try:
        sidecar = _load_sidecar_for_repair()
        if sidecar is None:
            return None
        return await sidecar.repair_tool_arguments(
            tool_name, schema, args, errors, session_anchor,
        )
    except Exception as exc:
        verbose_proxy_logger.error(
            "[tool_argument_guard] premium repair error: %s: %s",
            type(exc).__name__, exc,
        )
        return None


# ---- synthesized thinking blocks: GLM-only by construction -----------------
# _make_start and _normalize_thinking_signatures synthesize/normalize thinking
# blocks with signature:"" (an invalid signature Anthropic would reject on a
# later turn). This is safe because these paths only fire for GLM-shaped
# streams -- the mixed reasoning_content+text delta family that LiteLLM's
# messages->chat/completions adapter produces for backends like GLM on MaaS.
# Anthropic-native streams (sonnet/haiku via OpenRouter) carry real signatures
# and never have mixed delta families, so no synthesis occurs for them.
# The anthropic_reasoning_filter strips thinking from GLM responses before they
# reach the client, so these invalid-signature blocks never reach history.
# If this guard is ever extended to synthesize thinking for Anthropic-native
# streams, the reasoning filter's GLM-only scope must be revisited.
# (PRD-multi-family-routing Item 4 -- stream-guard/filter coupling.)


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


class _ToolBuffer:
    """Buffers ALL tool blocks in one assistant message for atomic validation
    (PRD-tool-argument-guard §8.1).

    Per message, retains:
      - original raw SSE bytes for replay (byte-identity);
      - tool block index, ID, name;
      - ordered partial_json fragments per block;
      - parsed message stop reason;
      - whether any bytes for a tool block have already been emitted.

    No tool block bytes are emitted before the whole tool-call set is accepted.
    """

    __slots__ = (
        "active",
        "events",
        "raw_chunks",
        "tool_blocks",
        "message_delta",
        "total_bytes",
        "limit_exceeded",
    )

    def __init__(self) -> None:
        self.active = False
        # All events (dicts) in stream order, for replay/repair.
        self.events: List[Dict[str, Any]] = []
        # Parallel list of raw chunks (bytes or dict) matching events.
        self.raw_chunks: List[Any] = []
        # Per-tool-block accumulation: {index: {name, id, fragments, start_idx}}
        self.tool_blocks: Dict[int, Dict[str, Any]] = {}
        # The message_delta event (stop reason), if seen.
        self.message_delta: Optional[Dict[str, Any]] = None
        self.total_bytes = 0
        # R4: set when a buffer limit is exceeded — triggers set-level REJECTED.
        self.limit_exceeded: Optional[str] = None

    def add(self, event: Dict[str, Any], raw: Any, as_bytes: bool) -> None:
        self.events.append(event)
        self.raw_chunks.append(raw)
        if as_bytes and isinstance(raw, (bytes, bytearray)):
            self.total_bytes += len(raw)
        etype = event.get("type")
        if etype == "content_block_start":
            cb = event.get("content_block") or {}
            if cb.get("type") == "tool_use":
                idx = event.get("index", 0)
                self.tool_blocks[idx] = {
                    "name": cb.get("name", ""),
                    "id": cb.get("id", ""),
                    "fragments": [],
                    "bytes": 0,
                    "start_event": event,
                    "start_raw": raw,
                }
                # R4: enforce tool-calls-per-message limit.
                if len(self.tool_blocks) > _TAG.MAX_CALLS and self.limit_exceeded is None:
                    self.limit_exceeded = "tool_calls_per_message"
        elif etype == "content_block_delta":
            idx = event.get("index")
            delta = event.get("delta") or {}
            if idx in self.tool_blocks and delta.get("type") == "input_json_delta":
                frag = delta.get("partial_json", "")
                if isinstance(frag, str):
                    self.tool_blocks[idx]["fragments"].append(frag)
                    self.tool_blocks[idx]["bytes"] += len(frag)
                    # R4: enforce per-call byte limit.
                    if self.tool_blocks[idx]["bytes"] > _TAG.MAX_BYTES_PER_CALL and self.limit_exceeded is None:
                        self.limit_exceeded = "arg_bytes_call_%d" % idx
                    # R4: enforce total buffer byte limit.
                    if self.total_bytes > _TAG.MAX_BUFFER_BYTES and self.limit_exceeded is None:
                        self.limit_exceeded = "total_buffer_bytes"
        elif etype == "message_delta":
            self.message_delta = event


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
        "tool_buffer",
        "schema_map",
        "session_anchor",
        "observe_validator",
        "residency_policy",
        "residency_request_id",
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
        # Tool Argument Guard buffer (enforce mode only). When active, tool
        # block events are held here until the message completes, then
        # validated/replayed/repaired/rejected atomically.
        self.tool_buffer: Optional[_ToolBuffer] = None
        self.schema_map = None
        self.session_anchor = ""
        # Observe-mode passive validator (PRD §7.2). When active, tool deltas
        # are assembled and validated for metrics WITHOUT buffering or changing
        # output bytes. None in enforce mode or when no tools are declared.
        self.observe_validator: Optional[_ObserveValidator] = None
        # R1: residency policy carried from pre-call to response-time (PRD v2 §7.1).
        # Set by the streaming hook from the request-scoped store so tool-argument
        # repair during streaming respects china-only egress policy.
        self.residency_policy = None
        self.residency_request_id = None


class _ObserveValidator:
    """Passive tool-argument validator for observe mode (PRD §7.2).

    Assembles input_json_delta fragments per tool block and validates them
    against the request schema at content_block_stop. Emits validation metrics
    (TAG_CALLS, TAG_VALIDATION_FAILURES) WITHOUT changing any output bytes.

    Unlike _ToolBuffer (enforce), this does NOT hold events, replay, repair,
    or reject. Bytes pass through unchanged.
    """

    __slots__ = ("tool_blocks",)

    def __init__(self) -> None:
        # {index: {"name": str, "fragments": [str]}}
        self.tool_blocks: Dict[int, Dict[str, Any]] = {}

    def on_event(self, event: Dict[str, Any]) -> None:
        """Track a streaming event for passive validation."""
        etype = event.get("type")
        if etype == "content_block_start":
            cb = event.get("content_block") or {}
            if cb.get("type") == "tool_use":
                idx = event.get("index", 0)
                self.tool_blocks[idx] = {"name": cb.get("name", ""), "fragments": []}
        elif etype == "content_block_delta":
            idx = event.get("index")
            delta = event.get("delta") or {}
            if idx in self.tool_blocks and delta.get("type") == "input_json_delta":
                frag = delta.get("partial_json", "")
                if isinstance(frag, str):
                    self.tool_blocks[idx]["fragments"].append(frag)

    def validate_and_record(self, schema_map) -> None:
        """Validate all assembled tool blocks and emit metrics (no byte changes).

        Called at message completion (message_delta/message_stop). Safe to call
        even if some blocks have no fragments or unknown tool names.
        """
        if _TAG is None or schema_map is None:
            return
        for idx, tb in self.tool_blocks.items():
            tool_name = tb["name"]
            fragments = tb["fragments"]
            # Assemble and parse.
            args, parse_err = _TAG.assemble_partial_json(fragments)
            if parse_err is not None:
                _TAG.TAG_REJECTIONS.labels(tool=tool_name, reason="parse_error").inc()
                _TAG.TAG_CALLS.labels(tool=tool_name, outcome="invalid").inc()
                continue
            schema = schema_map.get(tool_name)
            if schema is None:
                # Unknown tool — record but don't reject (observe mode).
                _TAG.TAG_REJECTIONS.labels(tool=tool_name, reason="unknown_tool").inc()
                _TAG.TAG_CALLS.labels(tool=tool_name, outcome="unknown").inc()
                continue
            ok, errors = _TAG.validate_arguments(args, schema)
            if ok:
                _TAG.TAG_CALLS.labels(tool=tool_name, outcome="pass").inc()
            else:
                _TAG.record_validation_failure(
                    tool_name, schema_map.hash_of(tool_name), errors
                )
                _TAG.TAG_CALLS.labels(tool=tool_name, outcome="invalid").inc()


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
        # Internal sidecar calls (PRD-glm52-mainline-sidecars) hit /v1/chat/completions
        # directly with OpenAI-format payloads. Skip the Anthropic-specific
        # normalizations (image_url -> image/source, thinking strip, server-tool
        # strip, interjection amplification) — they would corrupt the sidecar's
        # OpenAI-format image_url block and break the Luna/Opus call. The bypass
        # is keyed on the authenticated internal key identity (I5/I10), not
        # client-controlled metadata.
        if _is_sidecar_internal_key(user_api_key_dict):
            return data
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
        # Raw tool-call markup in a non-streaming response text means the model
        # tried to call a tool and the call did not execute. Raise 502 instead
        # of forwarding a fabricated success (PRD-remove-tool-disabling §5.4).
        _raise_if_raw_markup_in_response(response)
        apply_stop_sequences(data, response)
        # Increment mainline final response counter (R11 §5.6/§5.8).
        try:
            import sidecar  # type: ignore
            _model = (data or {}).get("model", "unknown") if isinstance(data, dict) else "unknown"
            sidecar.MAINLINE_FINAL_RESPONSES.labels(model=_model).inc()
        except Exception:
            pass
        # Tool Argument Guard (non-stream, PRD §12): validate tool_use blocks
        # in the complete response against the request schemas. Behavior must
        # match streaming mode (shared pure functions).
        if _TAG_ENFORCE and _TAG is not None and isinstance(data, dict):
            try:
                await _validate_non_stream_tools(data, response)
            except Exception as err:  # fail-open
                verbose_proxy_logger.error(
                    "[tool_argument_guard] non-stream validation error "
                    "(response passed through): %s: %s",
                    type(err).__name__, err,
                )
        # Observe mode (non-stream, PRD §7.2): validate + record metrics
        # WITHOUT modifying the response bytes.
        if _TAG_OBSERVE and _TAG is not None and isinstance(data, dict):
            try:
                _observe_non_stream_tools(data, response)
            except Exception as err:  # fail-open
                verbose_proxy_logger.error(
                    "[tool_argument_guard] non-stream observe error "
                    "(response passed through): %s: %s",
                    type(err).__name__, err,
                )
        return response

    async def async_logging_hook(self, kwargs: dict, result: Any, call_type: str):
        _normalize_thinking_signatures(result)
        return kwargs, result

    # ---- response side -----------------------------------------------------

    def _init_stream_state(self, request_data: dict) -> _StreamState:
        """Build the per-request stream state: schema map, residency, observe."""
        st = _StreamState(request_has_tools=_request_has_tools(request_data))
        if (_TAG_ENFORCE or _TAG_OBSERVE) and st.request_has_tools and _TAG is not None:
            try:
                st.schema_map = _TAG.build_schema_map(request_data)
                st.session_anchor = _tag_session_anchor(request_data)
            except Exception:
                st.schema_map = None
        # R1: read the residency policy from the request-scoped store.
        try:
            _meta = request_data.get("metadata") if isinstance(request_data, dict) else None
            if isinstance(_meta, dict):
                _rid = _meta.get("_residency_request_id")
                if _rid:
                    st.residency_request_id = _rid
                    _sidecar_mod = _load_sidecar_for_repair()
                    if _sidecar_mod is not None and hasattr(_sidecar_mod, "get_residency_for_request"):
                        st.residency_policy = _sidecar_mod.get_residency_for_request(_rid)
        except Exception:
            pass
        if _TAG_OBSERVE and st.schema_map is not None and _TAG is not None:
            st.observe_validator = _ObserveValidator()
        return st

    async def _process_one_chunk(self, st, chunk) -> AsyncGenerator[Any, None]:
        """Process a single chunk: parse, route to buffer/observe/passthrough."""
        is_bytes = isinstance(chunk, (bytes, bytearray))
        st.last_was_bytes = is_bytes

        # Raw tool-call markup in text means the model tried to call a tool and
        # the call did not execute. Never forward it as prose — the user would
        # read a fabricated success (PRD-remove-tool-disabling §2.2/§5.4).
        # No request_has_tools gate: after a hard-stop deletes tools, that flag
        # is False and detection would shut off exactly when needed (§2.3).
        if not st.markup_warned and _raw_chunk_has_tool_markup(chunk):
            st.markup_warned = True
            TOOL_MARKUP.inc()
            raise UnparsedToolMarkupError(
                "model emitted raw tool-call markup as text; the tool call "
                "did not execute"
            )

        # I4: oversized events forward as-is — UNLESS they may contain tool data.
        if is_bytes and len(chunk) > MAX_PARSE_BYTES:
            OVERSIZE.inc()
            if b"tool_use" in chunk or b"input_json_delta" in chunk:
                pass  # fall through to parsing
            else:
                self._note_passthrough_terminals(st, bytes(chunk))
                for out in self._flush_pending(st):
                    yield out
                yield chunk
                return

        # I6 fast path: steady-state delta matching the open block family.
        if (is_bytes and st.tool_buffer is None and st.pending is None and st.offset == 0
                and st.block_open and chunk.startswith(_DELTA_PREFIX)
                and (not st.request_has_tools or st.markup_warned
                     or (not st.markup_tail and TOOL_MARKUP_PREFIX[:1] not in chunk))):
            family, ambiguous = _sniff_delta_family(bytes(chunk))
            if not ambiguous and family == st.cur_type:
                yield chunk
                return

        # Parse the chunk into an event.
        repaired_sse = False
        if is_bytes:
            event, repaired_sse = _parse_sse_with_repair_flag(bytes(chunk))
            if event is None and st.saw_message_stop and _is_openai_done(bytes(chunk)):
                OPENAI_DONE_DROPPED.inc()
                return
            if repaired_sse and event is not None:
                RAW_SSE_REPAIRED.inc()
                chunk = _sse(event)
        else:
            event = chunk if isinstance(chunk, dict) and chunk.get("type") in ANTHROPIC_EVENT_TYPES else None
        if event is None:
            if is_bytes:
                self._note_passthrough_terminals(st, bytes(chunk))
            for out in self._flush_pending(st):
                yield out
            yield chunk
            return

        if not st.markup_warned and _detect_tool_markup(st, event):
            st.markup_warned = True
            TOOL_MARKUP.inc()
            raise UnparsedToolMarkupError(
                "model emitted raw tool-call markup as text; the tool call "
                "did not execute"
            )

        processed = list(self._process(st, event, chunk, is_bytes))

        # Enforce mode: buffer tool blocks for atomic validation.
        if await self._route_enforce_buffer(st, event, processed):
            if event.get("type") in ("message_delta", "message_stop"):
                async for out in self._process_tool_buffer(st):
                    yield out
                st.tool_buffer = None
            return

        # Observe mode: passively validate for metrics.
        self._route_observe(st, event, processed)

        for out in processed:
            yield out

    async def _route_enforce_buffer(self, st, event, processed):
        """Enforce-mode: route processed events into the tool buffer. Returns
        True if the caller should continue (buffer consumed the events), False
        if the caller should yield the processed events."""
        if not (_TAG_ENFORCE and st.schema_map is not None and st.schema_map.has_tools):
            return False
        if st.tool_buffer is None:
            for out in processed:
                ev = _out_event(out)
                if (isinstance(ev, dict) and ev.get("type") == "content_block_start"
                        and (ev.get("content_block") or {}).get("type") == "tool_use"):
                    st.tool_buffer = _ToolBuffer()
                    break
        if st.tool_buffer is not None:
            for out in processed:
                ev = _out_event(out)
                st.tool_buffer.add(ev if isinstance(ev, dict) else {}, out, isinstance(out, (bytes, bytearray)))
            return True
        return False

    def _route_observe(self, st, event, processed):
        """Observe-mode: passively validate tool args for metrics. Mutates
        st.observe_validator. Returns None (caller yields processed)."""
        if not (_TAG_OBSERVE and st.observe_validator is not None):
            return
        for out in processed:
            ev = _out_event(out)
            if isinstance(ev, dict):
                st.observe_validator.on_event(ev)
        if event.get("type") in ("message_delta", "message_stop"):
            try:
                st.observe_validator.validate_and_record(st.schema_map)
            except Exception:
                pass
            st.observe_validator = None

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        st = self._init_stream_state(request_data)
        response_iter = response.__aiter__()
        while True:
            try:
                chunk = await response_iter.__anext__()
            except StopAsyncIteration:
                break
            except Exception as err:
                UPSTREAM_ERRORS.inc()
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s from upstream stream (finalizing early)",
                    type(err).__name__,
                )
                break
            try:
                async for out in self._process_one_chunk(st, chunk):
                    yield out
            except UnparsedToolMarkupError:
                raise  # structural error — must reach the client as 502
            except Exception as err:
                verbose_proxy_logger.error(
                    "[anthropic_stream_guard] %s while processing a chunk (passing through)",
                    type(err).__name__,
                )
                if st.pending is not None:
                    yield st.pending[1]
                    st.pending = None
                yield chunk
        # Stream ended — finalize.
        # Increment mainline final response counter (R11 §5.6/§5.8).
        try:
            import sidecar  # type: ignore
            _model = (request_data or {}).get("model", "unknown") if isinstance(request_data, dict) else "unknown"
            sidecar.MAINLINE_FINAL_RESPONSES.labels(model=_model).inc()
        except Exception:
            pass
        if st.tool_buffer is not None:
            async for out in self._process_tool_buffer(st):
                yield out
            st.tool_buffer = None
        for out in self._finalize(st):
            yield out
        if st.residency_request_id:
            try:
                _sidecar_mod = _load_sidecar_for_repair()
                if _sidecar_mod is not None and hasattr(_sidecar_mod, "clear_residency_for_request"):
                    _sidecar_mod.clear_residency_for_request(st.residency_request_id)
            except Exception:
                pass

    # ---- state machine -------------------------------------------------------

    async def _process_tool_buffer(self, st: _StreamState) -> AsyncGenerator[Any, None]:
        """Process the buffered tool-call set atomically (PRD v2 §7.5 R5).

        Calls decide() then renders PASS/REPAIRED/REJECTED. Atomic: no valid
        sibling escapes when another member is rejected.
        """
        buf = st.tool_buffer
        if buf is None or not buf.tool_blocks:
            for raw in buf.raw_chunks if buf else []:
                yield raw
            return

        as_bytes = st.last_was_bytes

        # R4: limit exceeded during accumulation → reject without validation.
        if buf.limit_exceeded is not None:
            for tb in buf.tool_blocks.values():
                _TAG.TAG_REJECTIONS.labels(tool=tb["name"], reason="limit_exceeded").inc()
            async for out in self._render_rejected(st, buf, as_bytes):
                yield out
            return

        # Build tool_calls + repair_fn, call decide().
        tool_calls = [
            {"index": idx, "name": tb["name"], "tool_id": tb["id"], "fragments": tb["fragments"]}
            for idx, tb in sorted(buf.tool_blocks.items())
        ]

        async def _repair_fn(name, schema, args, errors, anchor):
            if not _TAG_PREMIUM_ENABLED:
                return None
            sidecar = _load_sidecar_for_repair()
            if sidecar is None:
                return None
            return await sidecar.repair_tool_arguments(name, schema, args, errors, anchor)

        residency_allows = st.residency_policy.allows_egress if st.residency_policy else True
        decision = await _TAG.decide(
            tool_calls, st.schema_map,
            repair_fn=_repair_fn, session_anchor=st.session_anchor,
            residency_allows_egress=residency_allows,
        )

        # Render based on outcome.
        if decision.outcome == _TAG.DecisionOutcome.PASS:
            for raw in buf.raw_chunks:
                yield raw
        elif decision.outcome == _TAG.DecisionOutcome.REPAIRED:
            async for out in self._render_repaired(st, buf, decision, as_bytes):
                yield out
        else:
            async for out in self._render_rejected(st, buf, as_bytes):
                yield out

    async def _render_repaired(self, st, buf, decision, as_bytes) -> AsyncGenerator[Any, None]:
        """Render a REPAIRED decision: each tool once with one canonical delta."""
        tool_result_by_idx = {tr.index: tr for tr in decision.per_tool}
        repair_delta_emitted: set = set()
        for ev, raw in zip(buf.events, buf.raw_chunks):
            etype = ev.get("type") if isinstance(ev, dict) else ""
            idx = ev.get("index") if isinstance(ev, dict) else None
            if etype == "content_block_start" and idx in tool_result_by_idx:
                tr = tool_result_by_idx[idx]
                yield _sse(_make_tool_start(idx, tr.tool_id, tr.tool_name)) if as_bytes else _make_tool_start(idx, tr.tool_id, tr.tool_name)
            elif etype == "content_block_delta" and idx in tool_result_by_idx:
                if idx not in repair_delta_emitted:
                    repair_delta_emitted.add(idx)
                    tr = tool_result_by_idx[idx]
                    canonical = json.dumps(tr.args, ensure_ascii=False)
                    delta_ev = {"type": "content_block_delta", "index": idx, "delta": {"type": "input_json_delta", "partial_json": canonical}}
                    yield _sse(delta_ev) if as_bytes else delta_ev
            elif etype in ("content_block_stop", "message_delta", "message_stop"):
                yield raw
            elif idx not in tool_result_by_idx:
                yield raw  # non-tool events

    async def _render_rejected(self, st, buf, as_bytes) -> AsyncGenerator[Any, None]:
        """Render a REJECTED decision: suppress ALL tool blocks, one text blocker."""
        first_tool_idx = sorted(buf.tool_blocks.keys())[0] if buf.tool_blocks else None
        blocker_emitted = False
        for ev, raw in zip(buf.events, buf.raw_chunks):
            etype = ev.get("type") if isinstance(ev, dict) else ""
            idx = ev.get("index") if isinstance(ev, dict) else None
            is_tool = idx in buf.tool_blocks
            if etype == "content_block_start":
                if is_tool and idx == first_tool_idx and not blocker_emitted:
                    blocker_emitted = True
                    yield _sse(_make_text_start(idx)) if as_bytes else _make_text_start(idx)
                elif not is_tool:
                    yield raw
            elif etype == "content_block_delta":
                if is_tool and idx == first_tool_idx and blocker_emitted:
                    delta_ev = {"type": "content_block_delta", "index": idx, "delta": {"type": "text_delta", "text": _TAG.REJECTION_TEXT}}
                    yield _sse(delta_ev) if as_bytes else delta_ev
                elif not is_tool:
                    yield raw
            elif etype == "content_block_stop":
                if not is_tool or idx == first_tool_idx:
                    yield raw
            elif etype == "message_delta":
                md = dict(ev)
                md["delta"] = dict(md.get("delta") or {})
                md["delta"]["stop_reason"] = "end_turn"
                yield _sse(md) if as_bytes else md
            elif etype == "message_stop":
                yield raw
            else:
                yield raw

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
