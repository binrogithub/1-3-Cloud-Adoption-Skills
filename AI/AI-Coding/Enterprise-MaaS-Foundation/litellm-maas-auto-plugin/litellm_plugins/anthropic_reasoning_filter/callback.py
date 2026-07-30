"""Hide provider reasoning from Anthropic clients while preserving model thinking upstream.

The callback is deliberately response-only. OpenAI chat-completions responses
remain untouched, so OpenCode can still consume ``reasoning_content`` if its
provider integration supports it. Anthropic ``thinking`` blocks are removed
and remaining content-block indexes are compacted for Claude Code.
"""

import json
import os
from typing import Any, AsyncGenerator, Dict, Optional

from litellm.integrations.custom_logger import CustomLogger


HIDE_REASONING = os.getenv("ARF_HIDE_REASONING", "true").strip().lower() != "false"
_HIDDEN_BLOCK_TYPES = {"thinking", "redacted_thinking"}
_HIDDEN_DELTA_TYPES = {"thinking_delta", "signature_delta"}
_INDEXED_EVENTS = {"content_block_start", "content_block_delta", "content_block_stop"}


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
        if HIDE_REASONING:
            filter_nonstream_response(response)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[Any, None]:
        if not HIDE_REASONING:
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
