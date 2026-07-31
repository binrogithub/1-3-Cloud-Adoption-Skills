"""Deterministic, observable router for GLM and US-hosted OpenRouter pools."""

import json
import os
import re
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger


GLM_MODEL = os.getenv("SMART_ROUTER_GLM_MODEL", "claude-*")
VISION_MODEL = os.getenv("SMART_ROUTER_VISION_MODEL", "vision-openrouter")
VISION_FALLBACK_MODEL = os.getenv(
    "SMART_ROUTER_VISION_FALLBACK_MODEL", "vision-openrouter-secondary"
)
PREMIUM_MODEL = os.getenv("SMART_ROUTER_PREMIUM_MODEL", "premium-openrouter")
PREMIUM_CONTEXT_THRESHOLD = int(
    os.getenv("SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD", "198000")
)
RULES_FILE = Path(
    os.getenv(
        "SMART_ROUTER_RULES_FILE",
        str(Path(__file__).with_name("smart_router_rules.json")),
    )
)

_TOP_LEVEL_KEYS = {
    "router_version",
    "vision_rules",
    "premium_rules",
    "cross_border_block_rules",
    "complexity",
}
_RULE_KEYS = {"id", "languages", "pattern", "allow_downgrade"}
_COMPLEXITY_KEYS = {"weights", "code_pattern", "reasoning_pattern", "multistep_pattern"}
_WEIGHT_KEYS = {"token_ratio", "code", "reasoning", "multistep", "premium_intent"}

# Metrics degrade to no-ops if prometheus_client is unavailable. Label values
# come only from validated rule IDs and configured model names.
try:
    from prometheus_client import Counter as _Counter
    from prometheus_client import Histogram as _Histogram

    ROUTE_REQUESTS = _Counter(
        "smart_router_requests_total",
        "Requests classified by the deterministic smart router",
        ["route", "matched_rule", "router_version"],
    )
    FALLBACKS = _Counter(
        "smart_router_fallbacks_total",
        "Request-scoped fallback chains selected by the smart router",
        ["source", "target", "reason"],
    )
    CROSS_BORDER_BLOCKS = _Counter(
        "smart_router_cross_border_blocks_total",
        "GLM-to-US fallbacks blocked by residency or sensitivity rules",
        ["matched_rule"],
    )
    COMPLEXITY_SCORES = _Histogram(
        "smart_router_complexity_score",
        "Observational complexity score; never used to select a route",
        ["route"],
        buckets=(0.1, 0.25, 0.5, 0.75, 0.9, 1.0),
    )
except Exception:  # pragma: no cover - only used in minimal installations
    class _Noop:
        def labels(self, **kwargs):
            return self

        def inc(self):
            return None

        def observe(self, value):
            return None

    ROUTE_REQUESTS = FALLBACKS = CROSS_BORDER_BLOCKS = COMPLEXITY_SCORES = _Noop()


def _validate_rules(raw):
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("rules must contain exactly the documented top-level keys")
    if not isinstance(raw["router_version"], str) or not raw["router_version"]:
        raise ValueError("router_version must be a non-empty string")
    for group in ("vision_rules", "premium_rules", "cross_border_block_rules"):
        if not isinstance(raw[group], list):
            raise ValueError("%s must be an array" % group)
        seen = set()
        for rule in raw[group]:
            allowed = _RULE_KEYS if group == "premium_rules" else _RULE_KEYS - {"allow_downgrade"}
            if not isinstance(rule, dict) or not {"id", "languages", "pattern"} <= set(rule):
                raise ValueError("%s entries require id, languages, and pattern" % group)
            if set(rule) - allowed:
                raise ValueError("%s entry has unknown keys" % group)
            if rule["id"] in seen:
                raise ValueError("duplicate rule id: %s" % rule["id"])
            seen.add(rule["id"])
            if not isinstance(rule["languages"], list) or not rule["languages"]:
                raise ValueError("%s.languages must be a non-empty array" % rule["id"])
            re.compile(rule["pattern"], re.IGNORECASE)
            if "allow_downgrade" in rule and not isinstance(rule["allow_downgrade"], bool):
                raise ValueError("%s.allow_downgrade must be boolean" % rule["id"])
    complexity = raw["complexity"]
    if not isinstance(complexity, dict) or set(complexity) != _COMPLEXITY_KEYS:
        raise ValueError("complexity must contain exactly the documented keys")
    weights = complexity["weights"]
    if not isinstance(weights, dict) or set(weights) != _WEIGHT_KEYS:
        raise ValueError("complexity.weights keys do not match the schema")
    if any(not isinstance(value, (int, float)) or value < 0 or value > 1 for value in weights.values()):
        raise ValueError("complexity weights must be numbers between 0 and 1")
    if abs(sum(weights.values()) - 1.0) > 0.000001:
        raise ValueError("complexity weights must sum to 1")
    for key in ("code_pattern", "reasoning_pattern", "multistep_pattern"):
        re.compile(complexity[key], re.IGNORECASE)
    return raw


def load_rules(path=RULES_FILE):
    with Path(path).open(encoding="utf-8") as handle:
        return _validate_rules(json.load(handle))


RULES = load_rules()


def _compiled_rules(name):
    return [
        (rule, re.compile(rule["pattern"], re.IGNORECASE))
        for rule in RULES[name]
    ]


VISION_RULES = _compiled_rules("vision_rules")
PREMIUM_RULES = _compiled_rules("premium_rules")
CROSS_BORDER_BLOCK_RULES = _compiled_rules("cross_border_block_rules")
COMPLEXITY_PATTERNS = {
    key: re.compile(RULES["complexity"][key], re.IGNORECASE)
    for key in ("code_pattern", "reasoning_pattern", "multistep_pattern")
}


def _has_image(data):
    """Check only the latest user message for images (current turn).

    Multi-turn conversations include prior messages (with their images) in
    the request payload.  Routing every subsequent turn to the vision model
    wastes quota and adds latency.  By inspecting only the *last* user
    message we ensure image routing fires only when the current turn
    actually carries an image.
    """
    for key in ("messages", "input"):
        messages = data.get(key) or []
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") in {
                    "image",
                    "image_url",
                    "input_image",
                }:
                    return True
            # Only the latest user message matters; stop after finding it.
            return False
    return False


_IMAGE_BLOCK_TYPES = {"image", "image_url", "input_image"}


def _strip_images(data):
    """Remove image content blocks from historical messages in-place.

    GLM (and other text-only backends) reject requests whose message history
    contains ``image_url`` content blocks, even when the current turn is
    pure text.  This causes LiteLLM to fall back to a premium external model
    — defeating the purpose of the ``_has_image`` fix.

    When the smart router decides to route to GLM (i.e. the current turn has
    no image), we strip image blocks from prior messages so GLM accepts the
    request.  Text blocks in the same message are preserved so the
    conversation context is retained.
    """
    for key in ("messages", "input"):
        messages = data.get(key)
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            # Keep only non-image blocks.  If a message would become empty
            # (all blocks were images), replace with a short placeholder so
            # the role sequence stays valid.
            filtered = [
                block
                for block in content
                if not (isinstance(block, dict) and block.get("type") in _IMAGE_BLOCK_TYPES)
            ]
            if not filtered:
                filtered = [{"type": "text", "text": "[image omitted]"}]
            message["content"] = filtered


def _latest_user_text(data):
    for key in ("messages", "input"):
        for message in reversed(data.get(key) or []):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") in {"text", "input_text"}
                )
    return ""


def _policy_text(data):
    """Return all request text relevant to residency/fallback policy."""
    values = [
        data.get("messages"),
        data.get("input"),
        data.get("system"),
        data.get("instructions"),
        data.get("tools"),
    ]
    return " ".join(
        json.dumps(value, ensure_ascii=False, default=str)
        for value in values
        if value
    )


def _estimate_tokens(data):
    messages = data.get("messages") or data.get("input") or []
    try:
        from litellm import token_counter

        estimate = int(token_counter(model=data.get("model"), messages=messages))
    except Exception:
        estimate = len(json.dumps(messages, ensure_ascii=False, default=str)) // 4
    for key in ("system", "instructions", "tools"):
        if data.get(key):
            estimate += max(
                1, len(json.dumps(data[key], ensure_ascii=False, default=str)) // 4
            )
    return estimate


def _first_match(rules, text):
    for rule, pattern in rules:
        if pattern.search(text):
            return rule
    return None


def _complexity_score(text, tokens, premium_match):
    weights = RULES["complexity"]["weights"]
    features = {
        "token_ratio": min(1.0, tokens / float(PREMIUM_CONTEXT_THRESHOLD + 1)),
        "code": float(bool(COMPLEXITY_PATTERNS["code_pattern"].search(text))),
        "reasoning": float(bool(COMPLEXITY_PATTERNS["reasoning_pattern"].search(text))),
        "multistep": float(bool(COMPLEXITY_PATTERNS["multistep_pattern"].search(text))),
        "premium_intent": float(bool(premium_match)),
    }
    return round(sum(features[key] * weights[key] for key in weights), 4)


def _provider_capability_reason(route_reason):
    if route_reason == "image" or route_reason.startswith("vision:"):
        return "requires_vision_capability"
    if route_reason.startswith("premium:"):
        return "requires_premium_advisor_capability"
    if route_reason == "context_over_198k":
        return "requires_large_context_capability"
    return None


def _fallbacks(route_reason, tokens, premium_rule, cross_border_blocked):
    if route_reason == "image" or route_reason.startswith("vision:"):
        return [VISION_FALLBACK_MODEL]
    if route_reason.startswith("premium:"):
        if (
            tokens <= PREMIUM_CONTEXT_THRESHOLD
            and premium_rule
            and premium_rule.get("allow_downgrade", False)
        ):
            return [GLM_MODEL]
        return []
    if route_reason == "glm_execution" and not cross_border_blocked:
        return [PREMIUM_MODEL]
    return []


def route_request(data):
    """Mutate a request using hard rules; scoring is observational only."""
    original = data.get("model", GLM_MODEL)
    tokens = _estimate_tokens(data)
    text = _latest_user_text(data)
    policy_text = _policy_text(data)
    image = _has_image(data)
    vision_rule = _first_match(VISION_RULES, text)
    premium_rule = _first_match(PREMIUM_RULES, text)
    cross_border_rule = _first_match(CROSS_BORDER_BLOCK_RULES, policy_text)

    if image:
        target, matched_rule = VISION_MODEL, "image"
    elif tokens > PREMIUM_CONTEXT_THRESHOLD:
        target, matched_rule = PREMIUM_MODEL, "context_over_198k"
    elif vision_rule:
        target, matched_rule = VISION_MODEL, "vision:%s" % vision_rule["id"]
    elif premium_rule:
        target, matched_rule = PREMIUM_MODEL, "premium:%s" % premium_rule["id"]
    else:
        target, matched_rule = original, "glm_execution"

    fallback_chain = _fallbacks(
        matched_rule, tokens, premium_rule, bool(cross_border_rule)
    )
    data["model"] = target
    if fallback_chain:
        # LiteLLM supports client/request-scoped fallbacks. This avoids a global,
        # capability-blind fallback chain.
        data["fallbacks"] = fallback_chain
    else:
        data.pop("fallbacks", None)

    # When routing to GLM (text-only backend), strip image blocks from
    # historical messages so GLM doesn't reject the request and trigger
    # an unnecessary fallback to a premium external model.
    if matched_rule == "glm_execution":
        _strip_images(data)

    complexity_score = _complexity_score(text, tokens, premium_rule)
    metadata = data.setdefault("metadata", {})
    metadata["smart_router"] = {
        "original_model": original,
        "target_model": target,
        "route_reason": matched_rule,
        "matched_rule": matched_rule,
        "estimated_tokens": tokens,
        "complexity_score": complexity_score,
        "router_version": RULES["router_version"],
        "context_threshold": PREMIUM_CONTEXT_THRESHOLD,
        "languages": ["zh", "en", "pt-BR", "es"],
        "fallback_chain": fallback_chain,
        "cross_border_fallback_blocked": bool(cross_border_rule),
    }
    provider_capability_reason = _provider_capability_reason(matched_rule)
    if provider_capability_reason:
        metadata["smart_router"][
            "provider_capability_reason"
        ] = provider_capability_reason
    ROUTE_REQUESTS.labels(
        route=target,
        matched_rule=matched_rule,
        router_version=RULES["router_version"],
    ).inc()
    COMPLEXITY_SCORES.labels(route=target).observe(complexity_score)
    for fallback in fallback_chain:
        FALLBACKS.labels(
            source=target,
            target=fallback,
            reason=matched_rule,
        ).inc()
    if cross_border_rule and matched_rule == "glm_execution":
        CROSS_BORDER_BLOCKS.labels(matched_rule=cross_border_rule["id"]).inc()
    return data


class SmartRouter(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        return route_request(data)


proxy_handler_instance = SmartRouter()
