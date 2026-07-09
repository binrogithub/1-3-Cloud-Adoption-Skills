import json
import math
import os
import re
from collections.abc import MutableMapping
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple

from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger


DEFAULT_EXECUTION_MODEL = "glm-5.2"
DEFAULT_VISION_MODEL = "vision-openrouter"
DEFAULT_SUMMARY_MODEL = "opus-summary"
DEFAULT_SOFT_LIMIT = 180000
DEFAULT_COMPACT_TRIGGER = 150000
DEFAULT_CLEAR_TOOL_TRIGGER = 100000
DEFAULT_SEARCH_MODE = "native"
DEFAULT_CAPABILITY_MODE = "frontend_capable"
DEFAULT_TOOL_USE_KEEP = 3

EXECUTION_ALIASES = {
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "glm-5.2",
    "claude-glm1",
}

BACKEND_FALLBACK_ALIASES = {
    "claude-opus-4-6-backend",
    "claude-sonnet-4-6-backend",
    "glm-5.2-backend",
    "claude-glm1-backend",
}

IMAGE_BLOCK_TYPES = {
    "image",
    "image_url",
    "input_image",
}

STRIPPED_CONTENT_BLOCK_TYPES = {
    "thinking",
    "redacted_thinking",
}

SEARCH_INTENT_RE = re.compile(
    r"搜索|新闻|最新|今天|今日|current|latest|today|news|search",
    re.IGNORECASE,
)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        verbose_proxy_logger.warning(
            "cc_glm52_guard ignored invalid integer env %s=%r", name, value
        )
        return default
    return parsed if parsed > 0 else default


class GuardConfig:
    def __init__(self) -> None:
        self.execution_model = _env_str(
            "CC_GLM52_EXECUTION_MODEL", DEFAULT_EXECUTION_MODEL
        )
        self.vision_model = _env_str("CC_GLM52_VISION_MODEL", DEFAULT_VISION_MODEL)
        self.summary_model = _env_str("CC_GLM52_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL)
        self.soft_limit = _env_int("CC_GLM52_SOFT_LIMIT", DEFAULT_SOFT_LIMIT)
        self.compact_trigger = _env_int(
            "CC_GLM52_COMPACT_TRIGGER", DEFAULT_COMPACT_TRIGGER
        )
        self.clear_tool_trigger = _env_int(
            "CC_GLM52_CLEAR_TOOL_TRIGGER", DEFAULT_CLEAR_TOOL_TRIGGER
        )
        self.search_mode = _env_str("CC_GLM52_SEARCH_MODE", DEFAULT_SEARCH_MODE)
        self.capability_mode = normalize_capability_mode(
            _env_str("CC_GLM52_CAPABILITY_MODE", DEFAULT_CAPABILITY_MODE)
        )


class CCGLM52Guard(CustomLogger):
    def __init__(self, config: Optional[GuardConfig] = None) -> None:
        super().__init__()
        self.config = config or GuardConfig()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not isinstance(data, dict):
            return data

        external_model = data.get("model")
        input_tokens_estimated = estimate_input_tokens(data)
        has_image = has_image_content(data)
        stripped_blocks = strip_unsupported_content_blocks(data)
        capability_mode = request_capability_mode(data, external_model, self.config)
        search_intent = has_search_intent(data)
        backend_search_enabled = maybe_enable_backend_search(
            data, capability_mode, search_intent, self.config
        )

        internal_route_model, route_reason = self._route_model(
            external_model=external_model,
            has_image=has_image,
        )
        if internal_route_model is not None:
            data["model"] = internal_route_model

        context_action = merge_context_management(data, self.config)
        audit = {
            "external_model": external_model,
            "internal_route_model": data.get("model"),
            "route_reason": route_reason,
            "multimodal_route": has_image,
            "input_tokens_estimated": input_tokens_estimated,
            "context_action": context_action_for_estimate(
                input_tokens_estimated, context_action, self.config
            ),
            "summary_model": self.config.summary_model,
            "capability_mode": capability_mode,
            "soft_limit": self.config.soft_limit,
            "compact_trigger": self.config.compact_trigger,
            "clear_tool_trigger": self.config.clear_tool_trigger,
            "search_mode": self.config.search_mode,
            "search_intent": search_intent,
            "backend_search_enabled": backend_search_enabled,
            "search_backend_used": backend_search_enabled,
            "stripped_content_blocks": stripped_blocks,
            "call_type": str(call_type),
        }
        merge_audit_fields(data, audit)
        return data

    def _route_model(
        self, external_model: Any, has_image: bool
    ) -> Tuple[Optional[str], str]:
        if has_image:
            return self.config.vision_model, "image_content"
        if isinstance(external_model, str) and external_model in (
            EXECUTION_ALIASES | BACKEND_FALLBACK_ALIASES
        ):
            return self.config.execution_model, "execution_alias"
        return None, "unchanged"


def normalize_capability_mode(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_CAPABILITY_MODE
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"frontend", "frontend_capable", "oauth", "oauth_present"}:
        return "frontend_capable"
    if normalized in {"backend", "backend_fallback", "no_oauth", "oauth_absent"}:
        return "backend_fallback"
    return DEFAULT_CAPABILITY_MODE


def request_capability_mode(
    data: Dict[str, Any], external_model: Any, config: GuardConfig
) -> str:
    for value in iter_capability_mode_values(data):
        mode = normalize_capability_mode(value)
        if mode != DEFAULT_CAPABILITY_MODE or str(value).lower() in {
            "frontend",
            "frontend_capable",
        }:
            return mode
    if isinstance(external_model, str) and external_model in BACKEND_FALLBACK_ALIASES:
        return "backend_fallback"
    return config.capability_mode


def iter_capability_mode_values(data: Dict[str, Any]) -> Iterable[Any]:
    for key in (
        "capability_mode",
        "claude_code_capability_mode",
        "cc_glm52_capability_mode",
    ):
        if key in data:
            yield data.get(key)

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        for key in (
            "capability_mode",
            "claude_code_capability_mode",
            "cc_glm52_capability_mode",
        ):
            if key in metadata:
                yield metadata.get(key)
        guard_metadata = metadata.get("cc_glm52_guard")
        if isinstance(guard_metadata, dict) and "capability_mode" in guard_metadata:
            yield guard_metadata.get("capability_mode")

    extra_body = data.get("extra_body")
    if isinstance(extra_body, dict):
        for key in (
            "capability_mode",
            "claude_code_capability_mode",
            "cc_glm52_capability_mode",
        ):
            if key in extra_body:
                yield extra_body.get(key)


def has_search_intent(data: Dict[str, Any]) -> bool:
    return bool(SEARCH_INTENT_RE.search(latest_user_text(data)))


def latest_user_text(data: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("messages", "input"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in reversed(items):
            if isinstance(item, dict) and item.get("role") == "user":
                collect_text(item.get("content"), parts)
                return "\n".join(parts)
    return ""


def collect_text(value: Any, parts: List[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        if "<system-reminder>" not in value:
            parts.append(value)
        return
    if isinstance(value, list):
        for item in value:
            collect_text(item, parts)
        return
    if isinstance(value, dict):
        for key in ("text", "content", "input_text"):
            item = value.get(key)
            if isinstance(item, str):
                collect_text(item, parts)
            elif isinstance(item, list):
                collect_text(item, parts)


def maybe_enable_backend_search(
    data: Dict[str, Any],
    capability_mode: str,
    search_intent: bool,
    config: GuardConfig,
) -> bool:
    if capability_mode != "backend_fallback" or not search_intent:
        return False
    if config.search_mode == "disabled":
        return False
    ensure_litellm_web_search_tool(data)
    return True


def ensure_litellm_web_search_tool(data: Dict[str, Any]) -> None:
    tools = data.get("tools")
    if not isinstance(tools, list):
        tools = []
        data["tools"] = tools
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        function = tool.get("function")
        if name == "litellm_web_search":
            return
        if isinstance(function, dict) and function.get("name") == "litellm_web_search":
            return
    tools.append(litellm_web_search_tool())


def litellm_web_search_tool() -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to execute.",
            }
        },
        "required": ["query"],
    }
    return {
        "name": "litellm_web_search",
        "description": "Search the web through the LiteLLM backend search provider.",
        "input_schema": schema,
    }


def has_image_content(data: Dict[str, Any]) -> bool:
    for content in iter_content_values(data):
        if content_has_image(content):
            return True
    return False


def content_has_image(content: Any) -> bool:
    if isinstance(content, list):
        return any(block_has_image(block) for block in content)
    if isinstance(content, dict):
        return block_has_image(content)
    return False


def block_has_image(block: Any) -> bool:
    if not isinstance(block, dict):
        return False
    block_type = block.get("type")
    if block_type in IMAGE_BLOCK_TYPES:
        return True
    if "image_url" in block or ("source" in block and block_type == "image"):
        return True
    nested = block.get("content")
    return content_has_image(nested)


def iter_content_values(data: Dict[str, Any]) -> Iterable[Any]:
    for key in ("messages", "input"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "content" in item:
                    yield item.get("content")
                elif isinstance(item, list):
                    yield item
        elif isinstance(items, dict) and "content" in items:
            yield items.get("content")

    system = data.get("system")
    if system is not None:
        yield system


def strip_unsupported_content_blocks(data: Dict[str, Any]) -> int:
    stripped = 0
    for key in ("messages", "input"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("content"), list):
                content, removed = filtered_content_blocks(item["content"])
                item["content"] = content if content else ""
                stripped += removed

    if isinstance(data.get("system"), list):
        content, removed = filtered_content_blocks(data["system"])
        data["system"] = content
        stripped += removed
    return stripped


def filtered_content_blocks(blocks: List[Any]) -> Tuple[List[Any], int]:
    filtered = []
    removed = 0
    for block in blocks:
        if isinstance(block, dict) and block.get("type") in STRIPPED_CONTENT_BLOCK_TYPES:
            removed += 1
            continue
        filtered.append(block)
    return filtered, removed


def merge_context_management(data: Dict[str, Any], config: GuardConfig) -> str:
    existing = data.get("context_management")
    if not isinstance(existing, dict):
        data["context_management"] = {"edits": required_context_edits(config)}
        return "injected"

    edits = existing.get("edits")
    if not isinstance(edits, list):
        existing["edits"] = required_context_edits(config)
        return "repaired"

    changed = upsert_context_edit(
        edits,
        required_clear_tool_uses_edit(config),
        replace_fields=("trigger", "keep"),
    )
    changed = (
        upsert_context_edit(
            edits,
            required_compact_edit(config),
            replace_fields=("trigger",),
        )
        or changed
    )
    return "merged" if changed else "kept"


def required_context_edits(config: GuardConfig) -> List[Dict[str, Any]]:
    return [
        required_clear_tool_uses_edit(config),
        required_compact_edit(config),
    ]


def required_clear_tool_uses_edit(config: GuardConfig) -> Dict[str, Any]:
    return {
        "type": "clear_tool_uses_20250919",
        "trigger": {
            "type": "input_tokens",
            "value": config.clear_tool_trigger,
        },
        "keep": {
            "type": "tool_uses",
            "value": DEFAULT_TOOL_USE_KEEP,
        },
    }


def required_compact_edit(config: GuardConfig) -> Dict[str, Any]:
    return {
        "type": "compact_20260112",
        "trigger": {
            "type": "input_tokens",
            "value": config.compact_trigger,
        },
    }


def upsert_context_edit(
    edits: List[Any],
    required: Dict[str, Any],
    replace_fields: Tuple[str, ...],
) -> bool:
    required_type = required["type"]
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("type") != required_type:
            continue
        changed = False
        for field in replace_fields:
            required_value = deepcopy(required[field])
            if edit.get(field) != required_value:
                edit[field] = required_value
                changed = True
        return changed
    edits.append(deepcopy(required))
    return True


def estimate_input_tokens(data: Dict[str, Any]) -> int:
    fields = {
        key: data.get(key)
        for key in ("messages", "input", "system", "tools", "tool_choice", "prompt")
        if key in data
    }
    if not fields:
        return 0
    try:
        payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        payload = str(fields)
    return int(math.ceil(len(payload) / 4))


def context_action_for_estimate(
    input_tokens_estimated: int,
    base_action: str,
    config: GuardConfig,
) -> str:
    if input_tokens_estimated >= config.soft_limit:
        return "soft_limit_exceeded"
    if input_tokens_estimated >= config.compact_trigger:
        return "compact_configured"
    if input_tokens_estimated >= config.clear_tool_trigger:
        return "clear_tool_uses_configured"
    return base_action


def merge_audit_fields(data: Dict[str, Any], audit: Dict[str, Any]) -> None:
    metadata = data.get("metadata")
    if not isinstance(metadata, MutableMapping):
        metadata = {}
        data["metadata"] = metadata
    merge_namespaced_mapping(metadata, "cc_glm52_guard", audit)

    # Avoid creating extra_body only for audit data: many providers forward it
    # to the upstream API verbatim. If a caller already supplied a guard audit
    # namespace there, keep it in sync without adding new provider parameters.
    extra_body = data.get("extra_body")
    if isinstance(extra_body, MutableMapping):
        if "cc_glm52_guard_audit" in extra_body:
            merge_namespaced_mapping(extra_body, "cc_glm52_guard_audit", audit)


def merge_namespaced_mapping(
    target: MutableMapping[str, Any],
    key: str,
    value: Dict[str, Any],
) -> None:
    existing = target.get(key)
    if isinstance(existing, MutableMapping):
        merged = dict(existing)
        merged.update(value)
        target[key] = merged
        return
    target[key] = value


proxy_handler_instance = CCGLM52Guard()
