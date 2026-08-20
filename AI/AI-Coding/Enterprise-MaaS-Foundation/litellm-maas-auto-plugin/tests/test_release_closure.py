#!/usr/bin/env python3
"""Regression tests for the release-closure P0/P1 fixes
(PRD-release-closure-native-claude-litellm §3.1, §3.4).

P0-1: trusted internal Sidecar keys (Vision/Premium) must pass through
route_request and async_pre_call_hook unchanged. Public keys and unknown
models are rejected.

    python3 -m pytest tests/test_release_closure.py
"""

import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
SIDECAR_CALLBACK = ROOT / "litellm_plugins" / "sidecar" / "callback.py"

# ── Module stubs (same pattern as test_sidecar_integration.py) ───────────────
litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
if not hasattr(litellm, "token_counter"):
    litellm.token_counter = lambda **kwargs: 100
lm = types.ModuleType("litellm._logging")
lm.verbose_proxy_logger = logging.getLogger("test")
sys.modules.setdefault("litellm._logging", lm)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
cl = types.ModuleType("litellm.integrations.custom_logger")
class CustomLogger:
    pass
cl.CustomLogger = CustomLogger
sys.modules.setdefault("litellm.integrations.custom_logger", cl)

# Load sidecar first so smart_router's `import sidecar` finds it.
spec2 = importlib.util.spec_from_file_location("sidecar", SIDECAR_CALLBACK)
sidecar = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(sidecar)
sys.modules["sidecar"] = sidecar

# Stub glm_loop_breaker (imported lazily by detect_triggers).
glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

# Load smart_router.
spec = importlib.util.spec_from_file_location("smart_router_closure_test", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL %s" % name)


# ── P0-1: internal-key bypass in route_request ───────────────────────────────

INTERNAL_MODELS = [
    "vision-openrouter",
    "vision-openrouter-secondary",
    "premium-openrouter",
]


def _set_internal_key(key):
    """Set the sidecar internal key for testing, return the old value.

    Also ensures sys.modules['sidecar'] points to OUR sidecar module, so
    router._load_sidecar() (which does `import sidecar`) sees the key we set.
    Other test files may have replaced sys.modules['sidecar'] with their own
    copy during their tests.
    """
    sys.modules["sidecar"] = sidecar
    old = sidecar.SIDECAR_API_KEY
    sidecar.SIDECAR_API_KEY = key
    return old


def _restore_internal_key(old):
    sidecar.SIDECAR_API_KEY = old


def test_internal_key_passes_route_request():
    """§3.1: a trusted internal key routing a registered internal model passes
    through route_request unchanged (no ContextLimitError, no GLM rewrite)."""
    old = _set_internal_key("test-internal-key")
    try:
        internal_key = {"key": "test-internal-key"}
        for model in INTERNAL_MODELS:
            data = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
            try:
                result = router.route_request(data, internal_key)
                check(
                    "%s passes route_request" % model,
                    result.get("model") == model,
                )
            except Exception as exc:
                check("%s passes route_request (got %s)" % (model, type(exc).__name__), False)
    finally:
        _restore_internal_key(old)


def test_internal_key_passes_async_pre_call_hook():
    """§3.1: the bypass must work through async_pre_call_hook (the real entry
    point), not only route_request. This is the regression the review demanded."""
    old = _set_internal_key("test-internal-key")
    try:
        internal_key = {"key": "test-internal-key"}
        for model in INTERNAL_MODELS:
            data = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
            try:
                result = asyncio.run(
                    router.proxy_handler_instance.async_pre_call_hook(
                        internal_key, None, data, "completion"
                    )
                )
                check(
                    "%s passes async_pre_call_hook" % model,
                    result is not None and result.get("model") == model,
                )
            except Exception as exc:
                check(
                    "%s passes async_pre_call_hook (got %s)" % (model, type(exc).__name__),
                    False,
                )
    finally:
        _restore_internal_key(old)


def test_client_key_vision_rejected():
    """§3.1: a public (non-internal) key cannot route an internal model.
    Defense-in-depth — LiteLLM model ACL is the primary gate."""
    old = _set_internal_key("test-internal-key")
    try:
        client_key = {"key": "client-key-not-internal"}
        for model in INTERNAL_MODELS:
            data = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
            rejected = False
            try:
                router.route_request(data, client_key)
            except router.ContextLimitError:
                rejected = True
            except Exception:
                rejected = True
            check("%s rejected for client key" % model, rejected)
    finally:
        _restore_internal_key(old)


def test_client_key_opus_rejected():
    """§3.1: a native Claude selector (opus) is rejected for any key that is
    not a trusted internal key routing a registered internal model."""
    old = _set_internal_key("test-internal-key")
    try:
        client_key = {"key": "client-key-not-internal"}
        data = {"model": "opus", "messages": [{"role": "user", "content": "hi"}]}
        rejected = False
        try:
            router.route_request(data, client_key)
        except router.ContextLimitError:
            rejected = True
        except Exception:
            rejected = True
        check("opus rejected for client key", rejected)
    finally:
        _restore_internal_key(old)


def test_internal_key_unknown_model_rejected():
    """§3.1: the internal key cannot bypass for an arbitrary/unknown model.
    The bypass requires BOTH the internal key AND a registered internal model."""
    old = _set_internal_key("test-internal-key")
    try:
        internal_key = {"key": "test-internal-key"}
        data = {"model": "some-unknown-model", "messages": [{"role": "user", "content": "hi"}]}
        rejected = False
        try:
            router.route_request(data, internal_key)
        except router.ContextLimitError:
            rejected = True
        except Exception:
            rejected = True
        check("unknown model rejected even with internal key", rejected)
    finally:
        _restore_internal_key(old)


def test_internal_key_glm_model_rejected():
    """§3.1: the internal key routing a GLM model is not an internal bypass —
    GLM models are not internal. This should go through normal GLM routing
    (not rejected, not bypassed)."""
    old = _set_internal_key("test-internal-key")
    try:
        internal_key = {"key": "test-internal-key"}
        data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        # GLM is not internal, so the bypass does not fire. Normal GLM routing
        # applies — the request should succeed and be routed to claude-glm-5.2.
        result = router.route_request(data, internal_key)
        check(
            "glm model routes normally with internal key",
            result.get("model") == "claude-glm-5.2",
        )
    finally:
        _restore_internal_key(old)


def test_client_key_glm_routes_normally():
    """§3.1: a public key routing the canonical GLM model works normally
    (existing behavior preserved)."""
    old = _set_internal_key("test-internal-key")
    try:
        client_key = {"key": "client-key-not-internal"}
        data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        result = router.route_request(data, client_key)
        check(
            "client key glm routes normally",
            result.get("model") == "claude-glm-5.2",
        )
    finally:
        _restore_internal_key(old)


def test_no_sidecar_module_still_rejects_non_glm():
    """If the sidecar module is unavailable, internal models are still rejected
    (the bypass requires a loaded sidecar to verify the key). This prevents a
    misconfigured deployment from silently allowing internal model access."""
    original_load = router._load_sidecar
    router._load_sidecar = lambda: None
    old = _set_internal_key("test-internal-key")
    try:
        internal_key = {"key": "test-internal-key"}
        data = {"model": "vision-openrouter", "messages": [{"role": "user", "content": "hi"}]}
        rejected = False
        try:
            router.route_request(data, internal_key)
        except router.ContextLimitError:
            rejected = True
        except Exception:
            rejected = True
        check("internal model rejected when sidecar absent", rejected)
    finally:
        _restore_internal_key(old)
        router._load_sidecar = original_load


# ── Run all tests ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_internal_key_passes_route_request,
    test_internal_key_passes_async_pre_call_hook,
    test_client_key_vision_rejected,
    test_client_key_opus_rejected,
    test_internal_key_unknown_model_rejected,
    test_internal_key_glm_model_rejected,
    test_client_key_glm_routes_normally,
    test_no_sidecar_module_still_rejects_non_glm,
]

for _t in ALL_TESTS:
    try:
        _t()
    except Exception as e:
        FAIL += 1
        print("  ERROR %s: %s: %s" % (_t.__name__, type(e).__name__, e))


def test_release_closure_all_pass():
    """Pytest entry point."""
    assert FAIL == 0, "%d release-closure checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
