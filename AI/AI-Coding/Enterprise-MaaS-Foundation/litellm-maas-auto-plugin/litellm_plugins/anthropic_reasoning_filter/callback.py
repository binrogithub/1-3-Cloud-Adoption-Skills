"""Hide provider reasoning from Anthropic clients while preserving model thinking upstream.

The callback is deliberately response-only. OpenAI chat-completions responses
remain untouched, so OpenCode can still consume ``reasoning_content`` if its
provider integration supports it. Anthropic ``thinking`` blocks are removed
and remaining content-block indexes are compacted for Claude Code.

Scope (PRD-multi-family-routing-v2 §3): stripping is driven by the model
registry's ``reasoning_filter`` flag. For real Anthropic models (sonnet/haiku)
the user selected the model for its thinking, so the flag is False and thinking
passes through unchanged. GLM thinking is a provider artifact and is stripped
as before. Unknown models default to stripping (conservative). See
``_model_profile`` and the coupling note below.
"""

import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

from litellm.integrations.custom_logger import CustomLogger


HIDE_REASONING = os.getenv("ARF_HIDE_REASONING", "true").strip().lower() != "false"
_HIDDEN_BLOCK_TYPES = {"thinking", "redacted_thinking"}
_HIDDEN_DELTA_TYPES = {"thinking_delta", "signature_delta"}
_INDEXED_EVENTS = {"content_block_start", "content_block_delta", "content_block_stop"}


# ---- model registry (PRD-multi-family-routing-v2 §3) -----------------------
# One source of truth for model capabilities, replacing the per-plugin
# _classify_model_family regex. The model ID is a primary key: exact lookup.
_FALLBACK_PROFILE = {
    "family": "other", "reasoning_filter": False, "loop_breaker": False,
    "affinity": False, "sampling_params": "pass",
}


def _registry_path():
    env = os.getenv("MODEL_REGISTRY_FILE")
    if env:
        return Path(env)
    cb = Path(__file__)
    for cand in (cb.with_name("model_registry.json"), cb.parents[1] / "model_registry.json"):
        if cand.exists():
            return cand
    return cb.with_name("model_registry.json")


def _load_registry():
    try:
        with _registry_path().open(encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict) or "models" not in raw:
            raise ValueError("registry missing 'models'")
        return raw
    except Exception:
        return {"fallback": dict(_FALLBACK_PROFILE), "models": {}}


REGISTRY = _load_registry()


def _model_profile(model_name):
    """Resolve a model ID to its capability profile (exact registry lookup).

    Unknown IDs return the inert fallback (reasoning_filter False = pass
    through, do not strip) and log a warning — a registry miss is a config bug
    (PRD-deployment-reconciliation P1-2). Stripping on a miss would silently
    remove thinking from genuine Anthropic responses (F-C).
    """
    name = str(model_name or "")
    models = REGISTRY.get("models") or {}
    if name in models:
        return models[name]
    if name:
        import logging as _log
        _log.getLogger("anthropic_reasoning_filter").warning(
            "model_registry miss: %s (using inert fallback, not stripping)", name)
    return REGISTRY.get("fallback") or _FALLBACK_PROFILE


def _should_strip(data: Any, request_data: Any) -> bool:
    """Return True when thinking blocks should be stripped for this request.

    Driven by the registry's ``reasoning_filter`` flag: GLM (provider artifact)
    strips; real Anthropic sonnet/haiku and unknown models pass through. A
    registry miss does NOT strip — stripping an unknown could remove thinking
    from a genuine Anthropic response (F-C).
    """
    model = None
    if isinstance(data, dict):
        model = data.get("model")
    if model is None and isinstance(request_data, dict):
        model = request_data.get("model")
    return bool(_model_profile(model).get("reasoning_filter", False))


# ---- stream-guard / filter signature coupling ------------------------------
# The stream guard (anthropic_stream_guard) synthesizes thinking blocks with
# signature:"" when repairing GLM streams (mixed reasoning_content+text delta
# families) -- see _make_start ({"type":"thinking","thinking":"","signature":""})
# and _normalize_thinking_signatures (sets signature="" on None). These
# synthesized blocks have invalid signatures. They are safe because:
#   (a) the stream guard only synthesizes thinking for GLM-shaped streams --
#       Anthropic-native streams (sonnet/haiku via OpenRouter) don't have mixed
#       reasoning_content+text delta families, so no synthesis occurs; and
#   (b) this filter strips thinking from GLM responses (reasoning_filter=True)
#       before they reach the client, so the invalid-signature blocks never
#       reach history.
# If the stream guard is ever extended to synthesize thinking for Anthropic
# streams, this filter's registry-driven scope must be revisited.


def _parse_anthropic_sse(chunk: Any) -> Optional[Dict[str, Any]]:
    if isinstance(chunk, dict):
        return chunk if isinstance(chunk.get("type"), str) else None
    if not isinstance(chunk, (bytes, bytearray)):
        return None
    try:
        text = bytes(chunk).decode("utf-8")
    except UnicodeDecodeError:
        return None
    data_lines = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
    if len(data_lines) != 1:
        return None
    try:
        event = json.loads(data_lines[0])
    except (TypeError, ValueError):
        return None
    return event if isinstance(event, dict) and isinstance(event.get("type"), str) else None


def _serialize(event: Dict[str, Any], original: Any) -> Any:
    if isinstance(original, (bytes, bytearray)):
        return (
            "event: {0}\ndata: {1}\n\n".format(
                event["type"], json.dumps(event, ensure_ascii=True, separators=(",", ":"))
            )
        ).encode("utf-8")
    return event


def _content_list(response: Any):
    if isinstance(response, dict):
        return response.get("content")
    return getattr(response, "content", None)


def filter_nonstream_response(response: Any) -> Any:
    """Remove Anthropic thinking blocks from a completed Messages response."""
    content = _content_list(response)
    if not isinstance(content, list):
        return response
    filtered = []
    for block in content:
        block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if block_type not in _HIDDEN_BLOCK_TYPES:
            filtered.append(block)
    if isinstance(response, dict):
        response["content"] = filtered
    else:
        try:
            response.content = filtered
        except Exception:
            pass
    return response


class AnthropicReasoningFilter(CustomLogger):
    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # ARF_HIDE_REASONING is the master switch. When false, pass through
        # everything unchanged. When true, strip only for GLM-family (and
        # unknown "other") models; real Anthropic sonnet/haiku keep thinking.
        if HIDE_REASONING and _should_strip(data, None):
            filter_nonstream_response(response)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        if not HIDE_REASONING or not _should_strip(request_data, None):
            async for chunk in response:
                yield chunk
            return

        hidden_indexes = set()
        visible_indexes: Dict[int, int] = {}
        next_visible_index = 0

        async for chunk in response:
            event = _parse_anthropic_sse(chunk)
            if event is None:
                yield chunk
                continue

            event_type = event.get("type")
            original_index = event.get("index")

            if event_type == "content_block_start" and isinstance(original_index, int):
                block = event.get("content_block")
                block_type = block.get("type") if isinstance(block, dict) else None
                if block_type in _HIDDEN_BLOCK_TYPES:
                    hidden_indexes.add(original_index)
                    continue
                visible_indexes[original_index] = next_visible_index
                next_visible_index += 1

            if (
                event_type == "content_block_delta"
                and isinstance(event.get("delta"), dict)
                and event["delta"].get("type") in _HIDDEN_DELTA_TYPES
            ):
                continue

            if isinstance(original_index, int) and original_index in hidden_indexes:
                if event_type == "content_block_stop":
                    hidden_indexes.discard(original_index)
                continue

            if event_type in _INDEXED_EVENTS and isinstance(original_index, int):
                mapped = visible_indexes.get(original_index)
                if mapped is not None and mapped != original_index:
                    event = dict(event)
                    event["index"] = mapped
                if event_type == "content_block_stop":
                    visible_indexes.pop(original_index, None)

            yield _serialize(event, chunk)


proxy_handler_instance = AnthropicReasoningFilter()
