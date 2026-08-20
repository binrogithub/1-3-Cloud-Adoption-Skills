"""Deterministic, observable router for GLM and US-hosted OpenRouter pools.

PRD-glm52-mainline-sidecars: GLM-5.2 owns every final answer. Images and
tool-failure recovery are handled by bounded sidecars (litellm_plugins/sidecar)
that inject structured context into the GLM request; the router no longer
routes whole turns to vision/premium. The sidecar module is imported lazily so
a missing /app/sidecar.py degrades gracefully (images pass through, no sidecar
enrichment) rather than crashing the gateway.
"""

import hashlib
import json
import logging
import os
import re
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

log = logging.getLogger("smart_router")


# The mainline model that owns every final answer (PRD §1, invariant I1).
# After sidecar processing the request is forced to this model.
MAINLINE_MODEL = os.getenv("SMART_ROUTER_MAINLINE_MODEL", "claude-glm-5.2")

GLM_MODEL = os.getenv("SMART_ROUTER_GLM_MODEL", "claude-*")
VISION_MODEL = os.getenv("SMART_ROUTER_VISION_MODEL", "vision-openrouter")
VISION_FALLBACK_MODEL = os.getenv(
    "SMART_ROUTER_VISION_FALLBACK_MODEL", "vision-openrouter-secondary"
)
# PREMIUM_MODEL is a branch (deliberate invocation only), never a fallback
# target (PRD-glm-consolidation §1/§7). Kept as a route target for Rule 6.
PREMIUM_MODEL = os.getenv("SMART_ROUTER_PREMIUM_MODEL", "premium-openrouter")
# GLM_FALLBACK_MODEL is the same-provider fallback for glm_execution failures
# (PRD-glm-consolidation §1/§3). glm-5.1 accepts sampling parameters, so a
# loop-breaker-mutated request is safe across the fallback (§4).
GLM_FALLBACK_MODEL = os.getenv("SMART_ROUTER_GLM_FALLBACK_MODEL", "glm-5.1-fallback")
# Kept as the historical context ceiling; no longer used to *route* to premium.
PREMIUM_CONTEXT_THRESHOLD = int(
    os.getenv("SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD", "198000")
)
# Length policy bands (PRD §5). Advisory tags the request; oversize records only.
ADVISORY_THRESHOLD = int(
    os.getenv("SMART_ROUTER_ADVISORY_THRESHOLD", "200000")
)
OVERSIZE_THRESHOLD = int(
    os.getenv("SMART_ROUTER_OVERSIZE_THRESHOLD", "500000")
)
# Prefix affinity consistent hash (PRD §4.1). When DEPLOYMENT_COUNT <= 1 the
# hash is a no-op and the model is left unchanged.
MAINLINE_PREFIX = os.getenv("SMART_ROUTER_MAINLINE_PREFIX", "glm")
DEPLOYMENT_COUNT = int(os.getenv("SMART_ROUTER_DEPLOYMENT_COUNT", "1"))
MAINLINE_GROUP = os.getenv("SMART_ROUTER_MAINLINE_GROUP", "claude-*")
RULES_FILE = Path(
    os.getenv(
        "SMART_ROUTER_RULES_FILE",
        str(Path(__file__).with_name("smart_router_rules.json")),
    )
)
# Server-side default data-residency gate (PRD §6 / F5). When set to
# "china-only", cross-provider fallback is blocked regardless of key/client
# metadata — protection is default-on for china-only deployments without
# trusting client-supplied request metadata.
DEFAULT_DATA_RESIDENCY = os.getenv("SMART_ROUTER_DEFAULT_DATA_RESIDENCY", "")

# ── Model registry (PRD-multi-family-routing-v2 §3) ─────────────────────────
# One source of truth for model capabilities, replacing the three duplicated
# _classify_model_family regex copies. The model ID is a primary key: exact
# lookup, not pattern matching. Each plugin loads this file independently
# (plugins are standalone modules). The DATA is shared; the loader is copied.
#
# Path resolution: MODEL_REGISTRY_FILE env var → flat-mount (/app/) → source
# tree (litellm_plugins/). In the container all plugins are at /app/*.py so
# with_name finds /app/model_registry.json; in tests parents[1] finds
# litellm_plugins/model_registry.json.
_FALLBACK_PROFILE = {
    "family": "other", "upstream": None,
    "max_input_tokens": 200000, "max_output_tokens": 64000,
    "vision": False, "sampling_params": "pass", "thinking": "pass",
    "effort": "pass", "loop_breaker": False, "affinity": False,
    "reasoning_filter": False, "display_name": None,
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
        # Fail-open: an unreadable/missing registry degrades to the fallback
        # profile for every model. The deployment keeps working.
        return {"fallback": dict(_FALLBACK_PROFILE), "models": {}}


REGISTRY = _load_registry()


def _fallback_token_cap():
    """Resolve the GLM fallback token cap from the registry (PRD-glm-consolidation §3).

    Source of truth is the fallback model's measured max_input_tokens
    (glm-5.1 = 196,608), NOT a standalone env default. The old default of
    200,000 sat 3,392 tokens above what glm-5.1 accepts, so a GLM-5.2 failure
    on a 196,609–200,000-token conversation attached a fallback that was
    guaranteed to fail — converting one recoverable error into two.

    An optional env override (SMART_ROUTER_FALLBACK_TOKEN_CAP) is honored for
    deployments that need to tune it without a registry edit, but the registry
    value is preferred. Falls back to the module-level fallback profile ceiling
    when the fallback model is absent from the registry.
    """
    env_cap = os.getenv("SMART_ROUTER_FALLBACK_TOKEN_CAP")
    if env_cap:
        try:
            return int(env_cap)
        except (TypeError, ValueError):
            pass
    models = REGISTRY.get("models") or {}
    prof = models.get(GLM_FALLBACK_MODEL)
    if prof and prof.get("max_input_tokens"):
        return int(prof["max_input_tokens"])
    return int(_FALLBACK_PROFILE["max_input_tokens"])


FALLBACK_TOKEN_CAP = _fallback_token_cap()

# ── R-6: registry ↔ model_list startup invariant (PRD §6) ───────────────────
# Both P0s in the deployment audit were configuration drift — the registry and
# the model_list disagreed, and nothing caught it. This check asserts the five
# rules from PRD §6 at import time, so a mismatch refuses to start the gateway
# instead of running for a week with the loop breaker silently off.
#
# MODEL_LIST_FILE points to the litellm_config.yaml on the deploy host. When
# unset (dev/test mode) the check is skipped — the registry alone is the source
# of truth. When set but the file is missing, the check is also skipped (a
# misconfigured path should not crash a dev box that happens to set the var).
# When set AND the file exists, violations are a hard ValueError.
MODEL_LIST_FILE = os.getenv("MODEL_LIST_FILE", "")

# Registry entries that exist for unit tests, not production. R-2 (every
# registry entry must be published in model_list) is skipped for these — they
# are legitimately unpublished because they are test-only aliases.
_TEST_ONLY_MODELS = frozenset({
    "glm-5.2",
})


def _validate_registry_vs_model_list(model_list_path, registry):
    """Assert the registry ↔ model_list invariant (PRD §6 rules 1-6).

    Raises ValueError on any violation — the gateway refuses to start. A
    missing/unset path is a no-op (dev/test mode).

    R1: every model_name in model_list has a registry entry.
    R2: every registry entry is published in model_list (skips test-only).
    R3: max_input_tokens / max_output_tokens agree for overlapping models.
    R4: registry upstream agrees with litellm_params.model.
    R5: no model_name implies a family its upstream doesn't serve.
    R6: every route target the router can emit is published in model_list.
    """
    if not model_list_path:
        return  # dev/test mode — registry alone is the source of truth
    path = Path(model_list_path)
    if not path.exists():
        return  # misconfigured path in a dev box — skip, don't crash

    import yaml
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("model_list file %s is not a YAML mapping" % path)
    model_list = config.get("model_list")
    if not isinstance(model_list, list):
        raise ValueError("model_list file %s has no 'model_list' array" % path)

    # Index the model_list by model_name for the cross-checks.
    ml_by_name = {}
    for entry in model_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("model_name")
        if name:
            ml_by_name[name] = entry

    reg_models = registry.get("models") or {}

    # R1: every published model_name has a registry entry.
    for name in ml_by_name:
        if name not in reg_models:
            raise ValueError(
                "R-6 R1: model_list entry %r has no registry entry "
                "(silent fallback for a published model)" % name
            )

    # R2: every registry entry is published (skip test-only aliases).
    for name in reg_models:
        if name in _TEST_ONLY_MODELS:
            continue
        if name not in ml_by_name:
            raise ValueError(
                "R-6 R2: registry entry %r is not published in model_list "
                "(dead config)" % name
            )

    # R3 + R4 + R5: checks over the overlapping set.
    for name, ml_entry in ml_by_name.items():
        prof = reg_models.get(name)
        if prof is None:
            continue  # R1 already caught this

        litellm_params = ml_entry.get("litellm_params") or {}
        ml_upstream = litellm_params.get("model")
        model_info = ml_entry.get("model_info") or {}
        ml_max_input = model_info.get("max_input_tokens")
        ml_max_output = model_info.get("max_output_tokens")

        # R3: token ceilings agree.
        if ml_max_input is not None and ml_max_input != prof.get("max_input_tokens"):
            raise ValueError(
                "R-6 R3: %r max_input_tokens mismatch — model_list=%r, "
                "registry=%r" % (name, ml_max_input, prof.get("max_input_tokens"))
            )
        if ml_max_output is not None and ml_max_output != prof.get("max_output_tokens"):
            raise ValueError(
                "R-6 R3: %r max_output_tokens mismatch — model_list=%r, "
                "registry=%r" % (name, ml_max_output, prof.get("max_output_tokens"))
            )

        # R4: upstream agrees.
        reg_upstream = prof.get("upstream")
        if ml_upstream is not None and reg_upstream is not None and ml_upstream != reg_upstream:
            raise ValueError(
                "R-6 R4: %r upstream mismatch — litellm_params.model=%r, "
                "registry=%r" % (name, ml_upstream, reg_upstream)
            )

        # R5: no model_name implies a family its upstream doesn't serve.
        _check_family_name_consistency(name, ml_upstream or reg_upstream or "")

    # R6: every route target the router can emit must be published in
    # model_list. An unpublished route target is a guaranteed request failure
    # at the moment that branch is taken — the image outage was exactly this.
    # Wildcards (claude-*) are exempt and reported at INFO so they are visible
    # rather than assumed (PRD-route-target-integrity §4).
    _route_targets = [
        ("VISION_MODEL", VISION_MODEL),
        ("VISION_FALLBACK_MODEL", VISION_FALLBACK_MODEL),
        ("GLM_FALLBACK_MODEL", GLM_FALLBACK_MODEL),
        ("PREMIUM_MODEL", PREMIUM_MODEL),
    ]
    for label, target in _route_targets:
        if not target or "*" in target:
            log.info("R-6 R6: %s=%r is a wildcard/empty — exempt from publish check", label, target)
            continue
        if target not in ml_by_name:
            raise ValueError(
                "R-6 R6: route target %s=%r is not published in model_list "
                "(emittable but unreachable — guaranteed failure when this "
                "branch is taken)" % (label, target)
            )
    # GLM_MODEL and MAINLINE_GROUP are wildcard patterns (claude-*); report them
    # at INFO so they are visible rather than assumed.
    for label, pattern in (("GLM_MODEL", GLM_MODEL), ("MAINLINE_GROUP", MAINLINE_GROUP)):
        if "*" in pattern:
            log.info("R-6 R6: %s=%r is a wildcard — exempt from publish check", label, pattern)
        elif pattern and pattern not in ml_by_name:
            raise ValueError(
                "R-6 R6: %s=%r is not a wildcard and not published in "
                "model_list" % (label, pattern)
            )


def _check_family_name_consistency(model_name, upstream):
    """R5: a family/version token in the name requires a matching upstream.

    "sonnet" in the name  → upstream must contain sonnet/anthropic/claude-sonnet
    "haiku" in the name   → upstream must contain haiku
    "glm" in the name     → upstream must contain glm or openai/glm
    """
    name_lower = model_name.lower()
    upstream_lower = upstream.lower()
    if "sonnet" in name_lower and "sonnet" not in upstream_lower:
        raise ValueError(
            "R-6 R5: %r contains 'sonnet' but upstream %r does not serve "
            "sonnet (the P0-2 class)" % (model_name, upstream)
        )
    if "haiku" in name_lower and "haiku" not in upstream_lower:
        raise ValueError(
            "R-6 R5: %r contains 'haiku' but upstream %r does not serve "
            "haiku" % (model_name, upstream)
        )
    if "glm" in name_lower and "glm" not in upstream_lower:
        raise ValueError(
            "R-6 R5: %r contains 'glm' but upstream %r does not serve "
            "glm" % (model_name, upstream)
        )


# Run the invariant check at import. A missing/unset file is a no-op (dev
# mode); a present file with violations is a hard fail that prevents startup.
_validate_registry_vs_model_list(MODEL_LIST_FILE, REGISTRY)

try:
    from prometheus_client import Counter as _Counter
    REGISTRY_MISSES = _Counter(
        "model_registry_miss_total",
        "Models requested but absent from the registry (configuration bug)",
        ["model"],
    )
except Exception:
    class _NoopMiss:
        def labels(self, **kwargs):
            return self
        def inc(self):
            return None
    REGISTRY_MISSES = _NoopMiss()


def _model_profile(model_name):
    """Resolve a model ID to its capability profile (PRD-multi-family-v2 §3).

    Exact lookup against the registry; an unknown ID returns the inert fallback
    profile (family "other": no affinity, no loop-breaker, no reasoning filter)
    and increments model_registry_miss_total — a miss is a config bug and must
    be visible, not absorbed (PRD-deployment-reconciliation P1-2).
    """
    name = str(model_name or "")
    models = REGISTRY.get("models") or {}
    if name in models:
        return models[name]
    if name:
        REGISTRY_MISSES.labels(model=name).inc()
        log.warning("model_registry miss: %s (using inert fallback)", name)
    return REGISTRY.get("fallback") or _FALLBACK_PROFILE


# ── Context cliff (PRD-multi-family §5 / Item 5 / PRD-deployment-reconciliation
# v2 §4 R-2) ─────────────────────────────────────────────────────────────────
# A session whose token count exceeds a model's real input ceiling cannot fit.
# Rather than silently truncating or forwarding to a certain upstream 400, we
# raise an actionable error naming that model's real limit. The ceiling comes
# from the registry's max_input_tokens — one source of truth for every family.


class ContextLimitError(Exception):
    """Actionable error: a session exceeds a model's context limit.

    This is an *intentional* error, not a router bug — the fail-open wrapper in
    async_pre_call_hook must RE-RAISE it, not swallow it. Family-agnostic: the
    message names the model and its real limit.
    """


_TOP_LEVEL_KEYS = {
    "router_version",
}

# Metrics degrade to no-ops if prometheus_client is unavailable. Label values
# come only from validated rule IDs and configured model names.
try:
    from prometheus_client import Counter as _Counter

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
    LENGTH_BANDS = _Counter(
        "smart_router_length_band_total",
        "Request context length band (normal/advisory/oversize)",
        ["band"],
    )
    MAINLINE_DEPLOYMENT_SELECTED = _Counter(
        "mainline_deployment_selected_total",
        "Mainline deployment selected by prefix affinity hash",
        ["deployment"],
    )
    ROUTER_ERRORS = _Counter(
        "smart_router_errors_total",
        "Requests that hit the fail-open path (router exception, passed through)",
        ["phase"],
    )
except Exception:  # pragma: no cover - only used in minimal installations
    class _Noop:
        def labels(self, **kwargs):
            return self

        def inc(self):
            return None

        def observe(self, value):
            return None

    ROUTE_REQUESTS = FALLBACKS = CROSS_BORDER_BLOCKS = _Noop()
    LENGTH_BANDS = MAINLINE_DEPLOYMENT_SELECTED = ROUTER_ERRORS = _Noop()


def _validate_rules(raw):
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("rules must contain exactly the documented top-level keys")
    if not isinstance(raw["router_version"], str) or not raw["router_version"]:
        raise ValueError("router_version must be a non-empty string")
    return raw


def load_rules(path=RULES_FILE):
    with Path(path).open(encoding="utf-8") as handle:
        return _validate_rules(json.load(handle))


RULES = load_rules()

# Image routing was replaced by the bounded Vision sidecar (PRD-glm52-
# mainline-sidecars §8). The sidecar extracts images, captions them via
# Luna/Luna-Pro, and injects the caption text in-place — so the mainline
# request never carries image bytes and never routes off GLM. The old
# _has_image / _references_image / _history_has_image / _strip_images and
# the image-reference regexes were deleted: keyword inference misrouted
# text-only turns, and whole-turn vision routing sent the full conversation
# to the visual model. See litellm_plugins/sidecar/callback.py.

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


def _first_user_text(data):
    """Return the text of the FIRST (oldest) user message.

    The affinity anchor must be the stable conversation prefix, not the latest
    turn (which changes every request and scatters traffic across deployments).
    Same content-block extraction as _latest_user_text, but scans oldest-first.
    """
    for key in ("messages", "input"):
        for message in (data.get(key) or []):
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


def _byte_estimate(data):
    """Cheap token estimate by byte count (len(json.dumps(messages))//4).

    The token estimate needs message bodies; it does NOT need to serialize tool
    definitions. tools can be huge and json.dumps-ing them every request is the
    exact full-payload serialization cost PRD §6 deleted the policy-text helper
    to remove (F4). We omit tools from the byte estimate entirely; the
    near-boundary token_counter call (which does see the full request) corrects
    it. system/instructions are usually strings or small lists, so we estimate
    them cheaply without json.dumps of large structures.
    """
    messages = data.get("messages") or data.get("input") or []
    estimate = len(json.dumps(messages, ensure_ascii=False, default=str)) // 4
    for key in ("system", "instructions"):
        value = data.get(key)
        if not value:
            continue
        if isinstance(value, str):
            estimate += max(1, len(value) // 4)
        else:
            # repr is cheaper than json.dumps and doesn't escape unicode. Cap
            # the serialized size so a pathological system list can't dominate.
            estimate += max(1, len(repr(value)) // 4)
    return estimate


def _context_ceiling(profile):
    """Resolve a model's real input-token ceiling (PRD R-2 / §4).

    Source of truth is the registry's max_input_tokens. Falls back to the
    module-level fallback profile ceiling if the profile is missing the field.
    """
    return int((profile or {}).get("max_input_tokens") or _FALLBACK_PROFILE["max_input_tokens"])


def _length_boundaries(ceiling):
    """Derive the advisory/oversize boundaries from a model's ceiling (PRD §7).

    Advisory at ~60% of the ceiling, oversize at the ceiling. One rule,
    correct per family: GLM (1M) → advisory 600K / oversize 1M; haiku (200K)
    → advisory 120K / oversize 200K. The global ADVISORY_THRESHOLD /
    OVERSIZE_THRESHOLD constants are fallbacks for when no profile is
    available (unknown model → fallback profile ceiling 200K).
    """
    if ceiling and ceiling > 0:
        advisory = int(ceiling * 0.6)
        oversize = ceiling
        return advisory, oversize
    return ADVISORY_THRESHOLD, OVERSIZE_THRESHOLD


def _near_boundary(byte_estimate, boundaries=None):
    """True when the byte estimate is within 20% of a band boundary.

    Only then do we pay for litellm.token_counter; otherwise the byte
    estimate is good enough to pick a band. ``boundaries`` is an
    (advisory, oversize) tuple derived from the target model's ceiling
    (PRD §7); when omitted the global fallback constants are used.
    """
    if boundaries is None:
        boundaries = (ADVISORY_THRESHOLD, OVERSIZE_THRESHOLD)
    for boundary in boundaries:
        if boundary <= 0:
            continue
        if abs(byte_estimate - boundary) <= 0.2 * boundary:
            return True
    return False


def _estimate_tokens(data, boundaries=None):
    """Estimate request tokens cheaply; call token_counter only near bands.

    PRD §6 / §5 event-loop blocking: token_counter is expensive and runs on
    the event loop. We compute a byte estimate first and only invoke the
    real counter when that estimate is within 20% of a band boundary. If
    token_counter is the test stub (returns a constant) this still works
    because the byte estimate is used everywhere except near boundaries.
    ``boundaries`` is the (advisory, oversize) tuple for the target model
    (PRD §7) so token_counter fires near the RIGHT boundary per model.
    """
    byte_estimate = _byte_estimate(data)
    if not _near_boundary(byte_estimate, boundaries):
        return byte_estimate
    messages = data.get("messages") or data.get("input") or []
    try:
        from litellm import token_counter

        estimate = int(token_counter(model=data.get("model"), messages=messages))
    except Exception:
        return byte_estimate
    # Fold in system/instructions cheaply (F4: no json.dumps of tools — the
    # token_counter call above already saw the message bodies; tool definitions
    # are intentionally omitted to avoid the full-payload serialization cost).
    for key in ("system", "instructions"):
        value = data.get(key)
        if not value:
            continue
        if isinstance(value, str):
            estimate += max(1, len(value) // 4)
        else:
            estimate += max(1, len(repr(value)) // 4)
    return estimate


def _length_band(tokens, ceiling=None):
    """Return the length band name for a token count (PRD §5 / §7).

    Bands are derived from the model's ceiling (PRD §7): advisory at ~60%,
    oversize at the ceiling. When ``ceiling`` is falsy the global fallback
    constants are used (unknown model → fallback profile ceiling 200K).
    """
    advisory, oversize = _length_boundaries(ceiling) if ceiling else (
        ADVISORY_THRESHOLD, OVERSIZE_THRESHOLD
    )
    if tokens >= oversize:
        return "oversize"
    if tokens >= advisory:
        return "advisory"
    return "normal"


def _cross_border_blocked(user_api_key_dict):
    """Structured data-residency gate (PRD §6 / F5, convergence §7.1).

    Delegates to the canonical ResidencyPolicy.from_key in _request_context
    so there is one authoritative residency parser shared by Router and Sidecar.
    Returns True if cross-provider fallback must be suppressed (china-only).
    """
    try:
        import _request_context
        policy = _request_context.ResidencyPolicy.from_key(user_api_key_dict)
        return policy.is_china_only
    except ImportError:
        # Fallback to the legacy env-only check if _request_context is unavailable.
        return DEFAULT_DATA_RESIDENCY == "china-only"


def _fallbacks(route_reason, tokens, cross_border_blocked):
    """Build the request-scoped fallback chain.

    Same-provider fallback (glm-5.1) is token-capped at the fallback model's
    measured ceiling (PRD-glm-consolidation §3): above FALLBACK_TOKEN_CAP the
    upstream error is allowed to propagate to the client rather than attaching
    a fallback that cannot fit. Premium is never a fallback target (§1/§7).

    Vision fallback (vision -> vision-secondary) is handled inside the sidecar
    module (Luna -> Luna Pro), NOT as a LiteLLM fallback chain — the sidecar
    dispatches the caption request itself and only the caption text reaches
    the mainline. So this function only handles the glm_execution path.
    """
    if route_reason == "glm_execution" and not cross_border_blocked:
        # Token cap: do not attach a fallback that cannot fit the conversation.
        if tokens <= FALLBACK_TOKEN_CAP:
            return [GLM_FALLBACK_MODEL]
        return []
    return []


def _apply_affinity(data):
    """Pin a mainline deployment alias via stateless consistent hash (PRD §4.1).

    Only applies to mainline traffic and only when DEPLOYMENT_COUNT > 1.
    Returns the selected deployment index (int), or None when this is a
    no-op (count <= 1, or the model is not GLM-family).

    Item 3 (PRD-multi-family §4): affinity rewrites data["model"] to glm-N. It
    must only apply to GLM-family traffic. On sonnet/haiku (or any non-GLM
    family) we return None — no rewrite, no deployment pin, no glm group
    fallback — so a user-initiated switch to an Anthropic model is not
    silently routed back to GLM.
    """
    if DEPLOYMENT_COUNT <= 1:
        return None
    # Only models with affinity enabled (GLM mainline) get pinned. A user who
    # switched to sonnet/haiku must not be rewritten to glm-N.
    if not _model_profile(data.get("model")).get("affinity"):
        return None
    metadata = data.get("metadata") or {}
    session_id = metadata.get("session_id")
    if session_id:
        anchor = str(session_id)
    else:
        system_text = json.dumps(
            data.get("system"), ensure_ascii=False, default=str
        )[:4096]
        first_user = _first_user_text(data)[:2048]
        anchor = system_text + first_user
    key = hashlib.sha256(anchor.encode("utf-8")).hexdigest()
    idx = int(key[:16], 16) % DEPLOYMENT_COUNT
    data["model"] = "%s-%d" % (MAINLINE_PREFIX, idx)
    # Same-provider group for cooldown; exempt from the token cap.
    data["fallbacks"] = [MAINLINE_GROUP]
    MAINLINE_DEPLOYMENT_SELECTED.labels(deployment=data["model"]).inc()
    return idx


def route_request(data, user_api_key_dict=None):
    """Mutate a request using hard rules; scoring is observational only.

    user_api_key_dict is the virtual key/team context supplied by
    async_pre_call_hook; data_residency is read from it (PRD §6 / F5), not
    from client-controlled request metadata.
    """
    original = data.get("model", GLM_MODEL)
    profile = _model_profile(original)
    model_family = profile.get("family", "other")

    # PRD-release-closure §3.1: trusted internal Sidecar keys may route the
    # exact internal model groups defined in the registry. This bypass MUST
    # occur before the non-GLM family rejection below — Vision (Luna/Luna-Pro)
    # and Premium (Opus 5) are intentionally non-GLM internal groups (registry
    # family="other", internal=true). When the sidecar's call_model re-enters
    # the gateway via loopback with the configured internal key, the request is
    # already named with the exact internal model and must pass through
    # unchanged (no GLM metadata, no fallbacks, no model rewriting). Public
    # keys remain protected by LiteLLM model ACL; this guard is defense-in-depth
    # so a public key cannot route an internal model even if the ACL mis-routes.
    if profile.get("internal") is True:
        sidecar = _load_sidecar()
        if sidecar is not None and sidecar.is_internal_key(user_api_key_dict):
            return data  # trusted internal call — pass through unchanged

    # PRD-release-closure §3.1: native Claude selectors must NEVER receive GLM
    # fallback, Sidecar processing, GLM metadata, or model rewriting. If a
    # native selector reaches the gateway, reject it before routing — do not
    # silently pass through or fall back to GLM. Native traffic should bypass
    # LiteLLM entirely; this guard ensures no accidental remapping.
    if model_family != "glm":
        raise ContextLimitError(
            "model %r is not a GLM model — native Claude selectors must use "
            "the native claude command, not the LiteLLM gateway" % original
        )

    cross_border_blocked = _cross_border_blocked(user_api_key_dict)

    # GLM-family routing: the smart_router intervenes only on GLM traffic.
    target, matched_rule = original, "glm_execution"

    # Resolve the TARGET model's profile for the context guard and length bands.
    target_profile = _model_profile(target)
    ceiling = _context_ceiling(target_profile)
    boundaries = _length_boundaries(ceiling)

    # Pass the profile-derived boundaries so token_counter fires near the RIGHT
    # boundary per model (PRD §7), not a global one that is wrong for haiku.
    tokens = _estimate_tokens(data, boundaries)

    # Length policy (PRD §5 / §7): record a band, never escalate on length.
    # Bands are derived from the target model's ceiling (PRD §7): advisory at
    # ~60% of the ceiling, oversize at the ceiling. This is correct per family
    # — for GLM (1M) advisory=600K/oversize=1M, for haiku (200K)
    # advisory=120K/oversize=200K — instead of global constants that are wrong
    # for haiku (where the old 200K advisory WAS the hard limit).
    band = _length_band(tokens, ceiling)
    LENGTH_BANDS.labels(band=band).inc()

    # ── Context cliff (PRD-multi-family §5 / Item 5 / R-2) ─────────────────
    # A session whose token count exceeds the target model's real input ceiling
    # cannot fit — raise an actionable error instead of silently truncating or
    # forwarding to a certain upstream 400. This is an intentional, actionable
    # error; the fail-open wrapper re-raises ContextLimitError.
    #
    # The ceiling comes from the registry's max_input_tokens (one source of
    # truth for every family).
    #
    # Only fire for models that are IN the registry. An unknown model (registry
    # miss → fallback profile 200K) has no reliable ceiling — firing would be a
    # false positive. The upstream returns its own error if the session is truly
    # too large.
    #
    # Background traffic (PRD §7.3): Claude Code uses a small model for
    # background tasks (title generation etc.) that isn't user-initiated. Those
    # requests are short (<4K tokens), so the `tokens > ceiling` gate naturally
    # excludes them — the cliff only fires on genuinely oversized sessions.
    # The token check is the primary gate; the metadata["background"] flag is
    # an extra safety net for deployments that set it.
    _registered_models = REGISTRY.get("models") or {}
    if (
        target in _registered_models
        and tokens > ceiling
        and not (data.get("metadata") or {}).get("background")
    ):
        raise ContextLimitError(
            "session is ~%dK tokens, %s's context limit is %dK; "
            "use /compact or switch to a larger model"
            % (tokens // 1000, target, ceiling // 1000)
        )

    fallback_chain = _fallbacks(matched_rule, tokens, cross_border_blocked)
    data["model"] = target

    # Prefix affinity applies only to mainline traffic and only when
    # DEPLOYMENT_COUNT > 1. It may override model/fallbacks with a pinned
    # alias plus the same-provider group. Same-provider fallback is exempt
    # from the token cap, so we apply it after the cross-provider decision.
    affinity_deployment = None
    if matched_rule == "glm_execution":
        affinity_deployment = _apply_affinity(data)
        if affinity_deployment is not None:
            # Affinity set data["fallbacks"] to the same-provider group;
            # drop any cross-provider fallback that was computed above.
            fallback_chain = [MAINLINE_GROUP]
        elif fallback_chain:
            data["fallbacks"] = fallback_chain
        else:
            data.pop("fallbacks", None)
    else:
        if fallback_chain:
            # LiteLLM supports client/request-scoped fallbacks. This avoids a
            # global, capability-blind fallback chain.
            data["fallbacks"] = fallback_chain
        else:
            data.pop("fallbacks", None)

    # Image blocks were stripped in-place above only for glm_execution.

    metadata = data.setdefault("metadata", {})
    smart_router_meta = {
        "original_model": original,
        "target_model": target,
        "route_reason": matched_rule,
        "matched_rule": matched_rule,
        "estimated_tokens": tokens,
        "router_version": RULES["router_version"],
        "context_threshold": PREMIUM_CONTEXT_THRESHOLD,
        "languages": ["zh", "en", "pt-BR", "es"],
        "fallback_chain": fallback_chain,
        "cross_border_fallback_blocked": cross_border_blocked,
        "length_band": band,
    }
    if affinity_deployment is not None:
        smart_router_meta["affinity_deployment"] = data["model"]
    metadata["smart_router"] = smart_router_meta
    ROUTE_REQUESTS.labels(
        route=target,
        matched_rule=matched_rule,
        router_version=RULES["router_version"],
    ).inc()
    for fallback in fallback_chain:
        FALLBACKS.labels(
            source=target,
            target=fallback,
            reason=matched_rule,
        ).inc()
    if cross_border_blocked and matched_rule == "glm_execution":
        CROSS_BORDER_BLOCKS.labels(matched_rule="data_residency").inc()
    return data


# ── Sidecar orchestration (PRD-glm52-mainline-sidecars) ─────────────────────
# The sidecar module (litellm_plugins/sidecar) is imported lazily so a missing
# /app/sidecar.py degrades gracefully: images pass through un-captioned and the
# request still succeeds on the mainline, rather than crashing the gateway.
# In tests the stub litellm has no sidecar, so this import is wrapped.

def _load_sidecar():
    """Import the sidecar module, or return None if it is unavailable."""
    try:
        import sidecar  # type: ignore
        return sidecar
    except ImportError:
        return None


def _generate_request_id() -> str:
    """Generate a request ID for the residency store (not cryptographically
    sensitive — just needs to be unique within the process)."""
    import os as _os
    return _os.urandom(16).hex()


async def orchestrate_sidecars(data, user_api_key_dict):
    """Run vision + premium sidecars, then force the mainline model (I1).

    Recursion bypass (I5/I10): if the authenticated key is the configured
    internal sidecar key, the request is an internal sidecar call re-entering
    the gateway — skip all sidecar orchestration and pass through unchanged
    (the sidecar already named the exact model: vision-openrouter /
    premium-openrouter). A request carrying sidecar metadata but NOT the
    trusted key is blocked.

    Sidecar typed errors (InvalidImageInput, ImageLimitExceeded,
    VisionSidecarUnavailable) propagate to the client as HTTP 400/413/502.
    """
    sidecar = _load_sidecar()
    if sidecar is None:
        return  # no sidecar module — pass through (dev/test or missing mount)

    # PRD-release-closure §3.1: Sidecar orchestration runs ONLY for GLM-family
    # traffic. Native Claude selectors must never trigger Vision/Premium
    # sidecars. Check the model family BEFORE any sidecar processing.
    _req_model = data.get("model", "") if isinstance(data, dict) else ""
    if _model_profile(_req_model).get("family") != "glm":
        return  # non-GLM: skip all sidecar orchestration

    # Recursion bypass: internal sidecar requests skip orchestration entirely.
    if sidecar.is_internal_key(user_api_key_dict):
        return

    # Block forged sidecar metadata from a non-internal key (I10).
    meta = data.get("metadata") if isinstance(data, dict) else None
    if isinstance(meta, dict) and meta.get("sidecar_kind"):
        # A client key claimed sidecar identity without the trusted key.
        try:
            sidecar.SIDECAR_RECURSION_BLOCKS.inc()
        except Exception:
            pass
        # Strip the forged metadata and continue on the mainline (do not execute
        # the claimed sidecar identity). The request proceeds as ordinary text.
        meta.pop("sidecar_kind", None)

    # Run the sidecars. Typed errors propagate; unexpected errors are swallowed
    # inside process_request (fail-open) so the request still reaches GLM.
    await sidecar.process_request(data, user_api_key_dict)

    # R1: stash the residency policy in the request-scoped store so the
    # streaming/non-stream response hooks can enforce china-only egress for
    # tool-argument repair. The contextvar resets in process_request's finally
    # before the stream runs, so this store is the carrier for response-time.
    try:
        policy = sidecar.ResidencyPolicy.from_key(user_api_key_dict)
        if isinstance(data, dict):
            meta = data.setdefault("metadata", {})
            if not isinstance(meta, dict):
                meta = {}
                data["metadata"] = meta
            request_id = meta.get("request_id") or _generate_request_id()
            meta["_residency_request_id"] = request_id
            sidecar.set_residency_for_request(request_id, policy)
    except Exception:
        pass  # never break the request over residency bookkeeping

    # I1: GLM-5.2 owns every final answer for GLM sessions. After sidecar
    # processing, force the mainline — but ONLY for GLM-family traffic.
    # Native Claude selectors (default/opus/sonnet/haiku) that arrive at the
    # gateway must NOT be rewritten to GLM (PRD-native-claude-glm-selection §7).
    # In normal operation, native traffic bypasses LiteLLM entirely; this guard
    # ensures no accidental remapping if a native selector does reach the gateway.
    if isinstance(data, dict):
        _req_model = data.get("model", "")
        if _model_profile(_req_model).get("family") == "glm":
            data["model"] = MAINLINE_MODEL


class SmartRouter(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        try:
            # Sidecar orchestration runs FIRST: it captions images and injects
            # premium recovery advice, then forces the mainline model (I1).
            # Typed sidecar errors (InvalidImageInput/ImageLimitExceeded/
            # VisionSidecarUnavailable) propagate to the client as HTTP errors.
            await orchestrate_sidecars(data, user_api_key_dict)
            return route_request(data, user_api_key_dict)
        except ContextLimitError:
            # Item 5 / R-2: this is an intentional, actionable error — re-raise
            # so the client sees "session is ~340K, <model>'s limit is 200K, use
            # /compact or switch to a larger model". Do NOT swallow it.
            raise
        except Exception as e:  # noqa: BLE001 - a router must never break a request
            # Typed sidecar contract errors (InvalidImageInput/ImageLimitExceeded/
            # VisionSidecarUnavailable/SidecarPolicyDenied) must propagate as their
            # declared HTTP status (400/403/413/502), NOT be swallowed by the
            # fail-open wrapper. They carry an http_status attr.
            # I8: VisionSidecarUnavailable (both visual models failed) must reach
            # the client as 502 so GLM never guesses on an un-captioned image.
            if hasattr(e, "http_status") and isinstance(getattr(e, "http_status"), int):
                # Delegate to the LiteLLM adapter (PRD-plugin-convergence §7.7).
                # The adapter maps the internal typed error to a pinned LiteLLM
                # exception so the proxy returns the correct HTTP status.
                import _litellm_adapter
                _litellm_adapter.raise_typed_error(e)
            # Fail open, but log so a malformed request that bypasses routing
            # is visible. Never log the payload — only the exception type/msg.
            # H-3: count the failure so an unqueryable error rate is visible.
            try:
                ROUTER_ERRORS.labels(phase="pre_call_hook").inc()
            except Exception:
                pass
            log.warning(
                "smart_router: passing request through unmodified: %s: %s",
                type(e).__name__,
                e,
            )
            return data


proxy_handler_instance = SmartRouter()
