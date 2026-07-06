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

  P0  remove image blocks entirely (largest first, any position) - base64
      image payloads tokenize at ~2.5 chars/token on the GLM tokenizer and a
      single screenshot can add 100K+ real tokens the text estimator misses;
      only used when no vision route is available (see below)
  P1  clear tool_result contents and shrink tool_use inputs in old messages
      (oldest first; the most recent CWG_KEEP_RECENT_MESSAGES messages are
      untouched by this phase). tool_use inputs keep their real parameter
      keys with values silently truncated - never a stub dict, which the
      backend model imitates for new calls (invalid tool parameters)
  P2  truncate remaining large strings to their head, in progressively
      smaller keep sizes; tool_result blocks shrink before text blocks, and
      the text of the newest message shrinks last

Vision routing: when CWG_VISION_MODEL is set (e.g. "vision-openrouter") and a
request carries image blocks, the request is rerouted to that model instead of
failing on the text-only execution model. The size budget switches to the
vision model's window (CWG_VISION_TRIGGER/TARGET, default 110K/100K for a
128K deployment); images are KEPT (counted at a flat ~1.6K tokens each, since
real vision models bill tiles, not base64 chars) and only text is trimmed.
Models listed in CWG_VISION_KEEP_MODELS (default: the vision model itself)
are never rerouted but still get the vision budget when they carry images.

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
  CWG_STRIP_IMAGES=overflow       "overflow": remove images while trimming
                                  (default); "never": leave images alone.
                                  Only applies when no vision route is taken.
  CWG_VISION_MODEL=               model alias to reroute image requests to
                                  (empty = disabled, images are stripped on
                                  overflow instead)
  CWG_VISION_TRIGGER_TOKENS=110000  vision-route trigger (text estimate)
  CWG_VISION_TARGET_TOKENS=100000   vision-route trim target
  CWG_VISION_KEEP_MODELS=         comma-separated aliases never rerouted
                                  (default: the vision model itself)
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
DEFAULT_VISION_TRIGGER_TOKENS = 110000
DEFAULT_VISION_TARGET_TOKENS = 100000

# Flat per-image cost estimate on a real vision model (tile-based billing).
VISION_IMAGE_TOKENS = 1600

# P2 passes: keep this many head chars of each oversized string per round.
TRUNCATE_KEEP_CHARS = (8000, 2000, 400)

# High-entropy base64 tokenizes much denser than prose/code on the GLM
# tokenizer (~2.5-3 chars/token observed vs 3.7 for ASCII text).
IMAGE_CHARS_PER_TOKEN = 2.5

CLEARED_STUB = "[cleared by context_window_guard: prompt exceeded the model context window]"

# P1 keeps this many head chars of each oversized tool_use input value.
TOOL_INPUT_KEEP_CHARS = 120
IMAGE_STUB_BLOCK = {
    "type": "text",
    "text": "[image removed by context_window_guard: the prompt exceeded the "
    "model context window and the routed model cannot process images]",
}
IMAGE_BLOCK_TYPES = {"image", "image_url"}


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


def _shrunk_tool_input(value: Dict[str, Any]) -> Dict[str, Any]:
    """Shrink a historical tool_use input while keeping its parameter shape.

    Replacing the whole input with a stub dict teaches the backend model a
    fake calling convention that it then imitates for NEW tool calls
    (observed live: after heavy trimming, GLM invoked Bash/TaskCreate with
    {"cleared_by_proxy": ...} and the client rejected every call with
    InputValidationError). Keeping the real keys and truncating oversized
    values leaves only valid-shaped examples in the history. Truncation is
    silent — no marker text — because models copy markers into new calls.
    """
    shrunk: Dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, str):
            shrunk[key] = item[:TOOL_INPUT_KEEP_CHARS]
            continue
        try:
            dump = json.dumps(item, ensure_ascii=False)
        except (TypeError, ValueError):
            dump = str(item)
        shrunk[key] = item if len(dump) <= TOOL_INPUT_KEEP_CHARS else dump[:TOOL_INPUT_KEEP_CHARS]
    return shrunk


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
        for bidx, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and isinstance(block.get("text"), str):
                slots.append(_Slot("text", block, "text", pos))
            elif btype in IMAGE_BLOCK_TYPES:
                slots.append(_Slot("image", content, bidx, pos))
            elif btype == "tool_use" and isinstance(block.get("input"), dict):
                slots.append(_Slot("tool_use_input", block, "input", pos))
            elif btype == "tool_result":
                inner = block.get("content")
                if isinstance(inner, str):
                    slots.append(_Slot("tool_result", block, "content", pos))
                elif isinstance(inner, list):
                    for idx, item in enumerate(inner):
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") in IMAGE_BLOCK_TYPES:
                            slots.append(_Slot("image", inner, idx, pos))
                        elif isinstance(item.get("text"), str):
                            slots.append(_Slot("tool_result", item, "text", pos))
    return slots


def _slot_estimate(slot: _Slot) -> int:
    value = slot.get()
    if isinstance(value, str):
        return _estimate_tokens(value)
    if isinstance(value, dict):
        try:
            dump = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            dump = str(value)
        if slot.kind == "image":
            return int(len(dump) / IMAGE_CHARS_PER_TOKEN) + 1
        return _estimate_tokens(dump)
    return 0


def _image_dump_length(slot: _Slot) -> int:
    value = slot.get()
    if not isinstance(value, dict):
        return 0
    try:
        return len(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return len(str(value))


def _image_text_contribution(slot: _Slot) -> int:
    """What the char-based payload estimate already counted for this image."""
    return int(_image_dump_length(slot) / ASCII_CHARS_PER_TOKEN)


def _image_estimate_correction(slot: _Slot) -> int:
    """Extra tokens the ASCII estimator misses on base64 image payloads."""
    length = _image_dump_length(slot)
    return max(
        0,
        int(length / IMAGE_CHARS_PER_TOKEN) - int(length / ASCII_CHARS_PER_TOKEN),
    )


def _estimate_with_images(
    data: Dict[str, Any],
    image_slots: List[_Slot],
    vision_route: bool,
) -> int:
    """Payload estimate with image blocks costed correctly for the route.

    Text route: base64 tokenizes DENSER than the ASCII estimator assumes
    (~2.5 chars/token observed on the GLM tokenizer; a 703KB PNG alone is
    100K+ real tokens), so correct upward. Vision route: real vision models
    bill tiles, not base64 chars, so replace each image's char-based
    contribution with a flat per-image cost."""
    base = _payload_estimate(data)
    if vision_route:
        for slot in image_slots:
            base -= _image_text_contribution(slot)
            base += VISION_IMAGE_TOKENS
        return max(0, base)
    return base + sum(_image_estimate_correction(s) for s in image_slots)


def trim_request(
    data: Dict[str, Any],
    trigger: int,
    target: int,
    keep_recent: int,
    strip_images: bool = True,
    vision_route: bool = False,
) -> Optional[Tuple[int, int, int, int, int]]:
    """Mutate data in place; returns (before, after, cleared, truncated,
    images_removed) estimates/counters, or None when under the trigger."""
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    slots = _collect_slots(messages)
    image_slots = [s for s in slots if s.kind == "image"]
    before = _estimate_with_images(data, image_slots, vision_route)
    if before <= trigger:
        return None

    running = before
    cleared = 0
    truncated = 0
    images_removed = 0
    keep_from = max(0, len(messages) - keep_recent)

    # P0: only when there is no vision route - the text-only execution model
    # cannot use images, and they are the densest payload.
    if strip_images and not vision_route:
        for slot in sorted(image_slots, key=_slot_estimate, reverse=True):
            if running <= target:
                break
            saved = _slot_estimate(slot)
            if saved <= 0:
                continue
            slot.set(dict(IMAGE_STUB_BLOCK))
            running -= saved - _slot_estimate(slot)
            images_removed += 1

    # P1: clear old tool_result contents and tool_use inputs entirely.
    for slot in slots:
        if running <= target:
            break
        if slot.msg_pos >= keep_from or slot.kind in ("text", "image"):
            continue
        saved = _slot_estimate(slot)
        if saved <= 0:
            continue
        if slot.kind == "tool_use_input":
            original = slot.get()
            if not isinstance(original, dict):
                continue
            replacement = _shrunk_tool_input(original)
            if replacement == original:
                continue
            slot.set(replacement)
        else:
            slot.set(CLEARED_STUB)
        running -= saved - _slot_estimate(slot)
        cleared += 1

    # P2: truncate whatever is still large, tool_results before text, the
    # newest message's text last. Rounds shrink the keep size.
    last_pos = len(messages) - 1
    ordered = sorted(
        (s for s in slots if s.kind not in ("tool_use_input", "image")),
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

    after = _estimate_with_images(data, image_slots, vision_route)
    return before, after, cleared, truncated, images_removed


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
        self.strip_images = (
            os.getenv("CWG_STRIP_IMAGES", "overflow").strip().lower() != "never"
        )
        self.vision_model = os.getenv("CWG_VISION_MODEL", "").strip()
        self.vision_trigger = _env_int(
            "CWG_VISION_TRIGGER_TOKENS", DEFAULT_VISION_TRIGGER_TOKENS
        )
        self.vision_target = _env_int(
            "CWG_VISION_TARGET_TOKENS", DEFAULT_VISION_TARGET_TOKENS
        )
        keep_raw = os.getenv("CWG_VISION_KEEP_MODELS", "")
        self.vision_keep_models = {
            m.strip() for m in keep_raw.split(",") if m.strip()
        }
        if self.vision_model:
            self.vision_keep_models.add(self.vision_model)

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        try:
            if not isinstance(data, dict):
                return data
            messages = data.get("messages")
            has_image = isinstance(messages, list) and any(
                s.kind == "image" for s in _collect_slots(messages)
            )

            vision_route = False
            routed_to = None
            if has_image and str(data.get("model")) in self.vision_keep_models:
                vision_route = True  # already on a vision-capable model
            elif has_image and self.vision_model:
                data["model"] = self.vision_model
                routed_to = self.vision_model
                vision_route = True
                verbose_proxy_logger.info(
                    "[context_window_guard] image request rerouted to %s",
                    self.vision_model,
                )

            trigger = self.vision_trigger if vision_route else self.trigger
            target = self.vision_target if vision_route else self.target
            result = trim_request(
                data,
                trigger,
                target,
                self.keep_recent,
                strip_images=self.strip_images,
                vision_route=vision_route,
            )
            if result is None and routed_to is None:
                return data
            if result is None:
                before = after = cleared = truncated = images_removed = None
            else:
                before, after, cleared, truncated, images_removed = result
                verbose_proxy_logger.warning(
                    "[context_window_guard] trimmed request: est %s -> %s tokens "
                    "(cleared=%s truncated=%s images_removed=%s trigger=%s "
                    "target=%s route=%s)",
                    before, after, cleared, truncated, images_removed,
                    trigger, target, routed_to or "unchanged",
                )
            metadata = data.get("metadata")
            if isinstance(metadata, dict):
                metadata["context_window_guard"] = {
                    "estimated_tokens_before": before,
                    "estimated_tokens_after": after,
                    "blocks_cleared": cleared,
                    "blocks_truncated": truncated,
                    "images_removed": images_removed,
                    "vision_route": routed_to,
                }
        except Exception as err:  # I2 fail-open; I5 no payload in logs
            verbose_proxy_logger.error(
                "[context_window_guard] %s during trim (request passed through)",
                type(err).__name__,
            )
        return data


proxy_handler_instance = ContextWindowGuard()
