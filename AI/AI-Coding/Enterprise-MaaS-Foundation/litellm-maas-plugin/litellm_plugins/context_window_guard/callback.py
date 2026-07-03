"""
context_window_guard - LiteLLM custom callback (plugin, no core patches).

Problem: Claude Code believes claude-opus-4-6 has a 200K context window, but
the GLM-5.2 backend on Huawei MaaS rejects prompts over 196,608 tokens
("Tokenizer encode failed: the prompt length ... must less than ...").
Nothing on the proxy trims context: Anthropic context_management is dropped
by drop_params for OpenAI-compatible backends, and Claude Code's client-side
auto-compact can be leapfrogged by a single turn that adds >100K tokens
(e.g. eight parallel ~25K-token file reads).

Fix: estimate the prompt size before the upstream call; when it exceeds
CWG_TRIGGER_TOKENS, shrink the request toward CWG_TARGET_TOKENS the same way
Anthropic's server-side context edits would:

  P1  clear tool_result contents and tool_use inputs in old messages
      (oldest first; the most recent CWG_KEEP_RECENT_MESSAGES messages are
      untouched by this phase)
  P2  truncate remaining large strings to their head, in progressively
      smaller keep sizes; tool_result blocks shrink before text blocks, and
      the text of the newest message shrinks last

Invariants (mirrors anthropic_stream_guard):
  I1  No shared mutable state across requests.
  I2  Fail-open: any error returns the request unmodified.
  I3  The system prompt and tool definitions are never modified.
  I5  Logs carry token counts and block counts only, never payload content.

Env:
  CWG_TRIGGER_TOKENS=175000       estimated tokens that arm trimming
  CWG_TARGET_TOKENS=150000        estimated tokens trimming aims for
  CWG_KEEP_RECENT_MESSAGES=2      newest messages exempt from phase P1
  CWG_ASCII_CHARS_PER_TOKEN=3.7   estimator divisor for ASCII text
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger

DEFAULT_TRIGGER_TOKENS = 175000
DEFAULT_TARGET_TOKENS = 150000
DEFAULT_KEEP_RECENT_MESSAGES = 2
DEFAULT_ASCII_CHARS_PER_TOKEN = 3.7

# P2 passes: keep this many head chars of each oversized string per round.
TRUNCATE_KEEP_CHARS = (8000, 2000, 400)

CLEARED_STUB = "[cleared by context_window_guard: prompt exceeded the model context window]"
CLEARED_INPUT_STUB = {"cleared_by_proxy": "tool input removed to fit the model context window"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        verbose_proxy_logger.warning(
            "context_window_guard ignored invalid integer env %s=%r", name, raw
        )
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


ASCII_CHARS_PER_TOKEN = _env_float(
    "CWG_ASCII_CHARS_PER_TOKEN", DEFAULT_ASCII_CHARS_PER_TOKEN
)


def _estimate_tokens(text: str) -> int:
    """Conservative estimate: ~3.7 ASCII chars/token, 1 token per CJK char."""
    if text.isascii():
        return int(len(text) / ASCII_CHARS_PER_TOKEN) + 1
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return int((len(text) - non_ascii) / ASCII_CHARS_PER_TOKEN) + non_ascii + 1


def _payload_estimate(data: Dict[str, Any]) -> int:
    fields = {
        key: data.get(key)
        for key in ("messages", "system", "tools")
        if key in data
    }
    try:
        payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        payload = str(fields)
    return _estimate_tokens(payload)


def _truncated(text: str, keep: int) -> str:
    removed = len(text) - keep
    return text[:keep] + f"\n[...truncated by context_window_guard: {removed} chars removed]"


class _Slot:
    """One shrinkable string plus how to write back into the request."""

    __slots__ = ("kind", "container", "field", "msg_pos")

    def __init__(self, kind: str, container: Any, field: Any, msg_pos: int) -> None:
        self.kind = kind          # "tool_result" | "text" | "tool_use_input"
        self.container = container  # dict (block/message) or list (content items)
        self.field = field        # key or list index holding the string
        self.msg_pos = msg_pos    # message index, for keep-recent decisions

    def get(self) -> Any:
        try:
            return self.container[self.field]
        except (KeyError, IndexError, TypeError):
            return None

    def set(self, value: Any) -> None:
        self.container[self.field] = value


def _collect_slots(messages: List[Any]) -> List[_Slot]:
    slots: List[_Slot] = []
    for pos, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            slots.append(_Slot("text", message, "content", pos))
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and isinstance(block.get("text"), str):
                slots.append(_Slot("text", block, "text", pos))
            elif btype == "tool_use" and isinstance(block.get("input"), dict):
                slots.append(_Slot("tool_use_input", block, "input", pos))
            elif btype == "tool_result":
                inner = block.get("content")
                if isinstance(inner, str):
                    slots.append(_Slot("tool_result", block, "content", pos))
                elif isinstance(inner, list):
                    for idx, item in enumerate(inner):
                        if isinstance(item, dict) and isinstance(item.get("text"), str):
                            slots.append(_Slot("tool_result", item, "text", pos))
    return slots


def _slot_estimate(slot: _Slot) -> int:
    value = slot.get()
    if isinstance(value, str):
        return _estimate_tokens(value)
    if isinstance(value, dict):
        try:
            return _estimate_tokens(json.dumps(value, ensure_ascii=False))
        except (TypeError, ValueError):
            return _estimate_tokens(str(value))
    return 0


def trim_request(
    data: Dict[str, Any],
    trigger: int,
    target: int,
    keep_recent: int,
) -> Optional[Tuple[int, int, int, int]]:
    """Mutate data in place; returns (before, after, cleared, truncated)
    estimates/counters, or None when the request was under the trigger."""
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    before = _payload_estimate(data)
    if before <= trigger:
        return None

    running = before
    cleared = 0
    truncated = 0
    slots = _collect_slots(messages)
    keep_from = max(0, len(messages) - keep_recent)

    # P1: clear old tool_result contents and tool_use inputs entirely.
    for slot in slots:
        if running <= target:
            break
        if slot.msg_pos >= keep_from or slot.kind == "text":
            continue
        saved = _slot_estimate(slot)
        if saved <= 0:
            continue
        if slot.kind == "tool_use_input":
            slot.set(dict(CLEARED_INPUT_STUB))
        else:
            slot.set(CLEARED_STUB)
        running -= saved - _slot_estimate(slot)
        cleared += 1

    # P2: truncate whatever is still large, tool_results before text, the
    # newest message's text last. Rounds shrink the keep size.
    last_pos = len(messages) - 1
    ordered = sorted(
        (s for s in slots if s.kind != "tool_use_input"),
        key=lambda s: (
            1 if s.kind == "text" else 0,
            2 if (s.kind == "text" and s.msg_pos == last_pos) else 0,
            s.msg_pos,
        ),
    )
    for keep in TRUNCATE_KEEP_CHARS:
        if running <= target:
            break
        for slot in ordered:
            if running <= target:
                break
            value = slot.get()
            if not isinstance(value, str) or len(value) <= keep + 200:
                continue
            saved = _estimate_tokens(value)
            slot.set(_truncated(value, keep))
            running -= saved - _estimate_tokens(slot.get())
            truncated += 1

    after = _payload_estimate(data)
    return before, after, cleared, truncated


class ContextWindowGuard(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self.trigger = _env_int("CWG_TRIGGER_TOKENS", DEFAULT_TRIGGER_TOKENS)
        self.target = _env_int("CWG_TARGET_TOKENS", DEFAULT_TARGET_TOKENS)
        if self.target >= self.trigger:
            self.target = int(self.trigger * 0.85)
        self.keep_recent = _env_int(
            "CWG_KEEP_RECENT_MESSAGES", DEFAULT_KEEP_RECENT_MESSAGES
        )

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        try:
            if not isinstance(data, dict):
                return data
            result = trim_request(data, self.trigger, self.target, self.keep_recent)
            if result is None:
                return data
            before, after, cleared, truncated = result
            verbose_proxy_logger.warning(
                "[context_window_guard] trimmed request: est %s -> %s tokens "
                "(cleared=%s truncated=%s trigger=%s target=%s)",
                before, after, cleared, truncated, self.trigger, self.target,
            )
            metadata = data.get("metadata")
            if isinstance(metadata, dict):
                metadata["context_window_guard"] = {
                    "estimated_tokens_before": before,
                    "estimated_tokens_after": after,
                    "blocks_cleared": cleared,
                    "blocks_truncated": truncated,
                }
        except Exception as err:  # I2 fail-open; I5 no payload in logs
            verbose_proxy_logger.error(
                "[context_window_guard] %s during trim (request passed through)",
                type(err).__name__,
            )
        return data


proxy_handler_instance = ContextWindowGuard()
