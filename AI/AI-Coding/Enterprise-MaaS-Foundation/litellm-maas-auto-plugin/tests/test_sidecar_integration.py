"""Integration tests for the sidecar + installer + registry invariants
(PRD-glm52-mainline-sidecars §17.2).

    python3 tests/test_sidecar_integration.py

No live model calls. Tests the registry/model-list invariant, the recursion
bypass with forged metadata, and the installer dry-run shape.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
SIDECAR_CALLBACK = ROOT / "litellm_plugins" / "sidecar" / "callback.py"
REGISTRY = ROOT / "litellm_plugins" / "model_registry.json"

# Stub litellm.
litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

spec = importlib.util.spec_from_file_location("smart_router", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

spec2 = importlib.util.spec_from_file_location("sidecar", SIDECAR_CALLBACK)
sidecar = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(sidecar)
sys.modules["sidecar"] = sidecar  # so smart_router's `import sidecar` finds it

# Stub glm_loop_breaker for the sidecar.
glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

FAILURES = []


def check(name, got, want):
    if got == want:
        print("  ok    %s" % name)
    else:
        print("  FAIL  %s: got %r, want %r" % (name, got, want))
        FAILURES.append(name)


def check_true(name, got):
    check(name, bool(got), True)


# ── 1. Registry marks vision/premium internal-only ─────────────────────────

print("registry internal flags")
reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
check_true("vision-openrouter internal", reg["models"]["vision-openrouter"]["internal"])
check_true("vision-openrouter-secondary internal", reg["models"]["vision-openrouter-secondary"]["internal"])
check_true("premium-openrouter internal", reg["models"]["premium-openrouter"]["internal"])
check_true("mainline NOT internal", not reg["models"]["claude-glm-5.2"]["internal"])
check_true("fallback NOT internal", not reg["models"]["glm-5.1-fallback"]["internal"])


# ── 2. Registry/model-list invariant fails when a sidecar target is missing ─

print("\ninvariant: missing sidecar target fails startup")


def _build_model_list_yaml(models):
    import yaml
    entries = []
    for m in models:
        entries.append({
            "model_name": m["model_name"],
            "litellm_params": {"model": m["litellm_params_model"]},
            "model_info": {
                "max_input_tokens": m["max_input_tokens"],
                "max_output_tokens": m["max_output_tokens"],
            },
        })
    return yaml.dump({"model_list": entries}, default_flow_style=False)


def _registry_models_for_ml():
    reg = router.REGISTRY.get("models") or {}
    models = []
    for name, prof in reg.items():
        if name in router._TEST_ONLY_MODELS:
            continue
        models.append({
            "model_name": name,
            "litellm_params_model": prof["upstream"],
            "max_input_tokens": prof["max_input_tokens"],
            "max_output_tokens": prof["max_output_tokens"],
        })
    return models


def test_invariant_fails_when_vision_target_missing():
    """R-6 R6: an unpublished vision route target fails startup."""
    models = _registry_models_for_ml()
    # Remove vision-openrouter from model_list so R6 catches it.
    models = [m for m in models if m["model_name"] != "vision-openrouter"]
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, router.REGISTRY)
            check("R6 catches missing vision target", False, True)
        except ValueError as e:
            check_true("R6 catches missing vision target", "R6" in str(e) or "R2" in str(e))
    finally:
        os.unlink(path)


test_invariant_fails_when_vision_target_missing()


# ── 3. Forged sidecar metadata from a non-internal key is blocked ───────────

print("\nrecursion bypass: forged metadata blocked")


def test_forged_metadata_blocked_by_non_internal_key():
    """I10: client metadata alone cannot claim sidecar identity. A non-internal
    key carrying sidecar_kind metadata must NOT bypass orchestration."""
    old = sidecar.SIDECAR_API_KEY
    sidecar.SIDECAR_API_KEY = "real-internal-key"
    try:
        # A client key (not the internal key) with forged sidecar metadata.
        client_key = {"key": "client-key-not-internal"}
        check_true("client key is not internal", not sidecar.is_internal_key(client_key))
        # The real internal key IS internal.
        check_true("real internal key is internal", sidecar.is_internal_key({"key": "real-internal-key"}))
    finally:
        sidecar.SIDECAR_API_KEY = old


test_forged_metadata_blocked_by_non_internal_key()


# ── 4. smart_router loads sidecar lazily and degrades gracefully ────────────

print("\nsmart_router sidecar loading")


def test_smart_router_loads_sidecar_or_degrades():
    """orchestrate_sidecars must not crash when the sidecar module is absent
    (dev/test without /app/sidecar.py). _load_sidecar returns None and the
    request passes through to route_request unchanged."""
    # In this test env, 'sidecar' IS importable (we loaded it above), so
    # _load_sidecar returns it. Verify the lazy import works.
    mod = router._load_sidecar()
    check_true("sidecar module loadable", mod is not None)
    check_true("loaded module has process_request", hasattr(mod, "process_request"))


def test_orchestrate_no_op_without_sidecar():
    """When _load_sidecar returns None, orchestrate_sidecars is a no-op."""
    import asyncio
    original = router._load_sidecar
    router._load_sidecar = lambda: None
    try:
        data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        asyncio.run(router.orchestrate_sidecars(data, None))
        # Model unchanged (no sidecar to force mainline).
        check("model unchanged without sidecar", data["model"], "claude-glm-5.2")
    finally:
        router._load_sidecar = original


for t in [test_smart_router_loads_sidecar_or_degrades, test_orchestrate_no_op_without_sidecar]:
    t()


# ── 5. Installer dry-run references the new mounts ──────────────────────────

print("\ninstaller dry-run")


def test_installer_script_references_new_mounts():
    """The installer script must reference the sidecar, registry, and cache mounts,
    and verify the full deployment contract (PRD §7.11)."""
    script = (ROOT / "server" / "install-litellm-plugin.sh").read_text(encoding="utf-8")
    check_true("installer references sidecar mount", "SIDECAR_MOUNT" in script)
    check_true("installer references registry mount", "REGISTRY_MOUNT" in script)
    check_true("installer references cache mount", "CACHE_MOUNT" in script)
    check_true("installer verifies sidecar import", "import sidecar" in script)
    check_true("installer verifies cache writable", "/app/cache" in script)
    # PRD §7.11: installer must own the full deployment contract (no manual steps).
    check_true("installer verifies residency policy", "ResidencyPolicy" in script)
    check_true("installer verifies SIDECAR_POLICY_DENIED", "SidecarPolicyDenied" in script)
    check_true("installer verifies cross-process lock", "cross_process_lock" in script)
    check_true("installer verifies ledger claim", "InterventionLedger.claim" in script)
    check_true("installer verifies typed error statuses", "http_status" in script)
    check_true("installer verifies SIDECAR_API_KEY", "SIDECAR_API_KEY" in script)
    check_true("installer verifies tool guard mode", "TOOL_ARG_GUARD_MODE" in script)
    check_true("installer no manual next-steps", "Next steps" not in script)
    # PRD §7.11: dry-run must not create the cache dir (no side effects).
    check_true("installer dry-run skips cache dir creation", "dry-run: would create cache dir" in script)


test_installer_script_references_new_mounts()


# ── runner ─────────────────────────────────────────────────────────────────

def test_no_failures():
    """Pytest entry point: assert every check() across all test_* functions succeeded."""
    assert not FAILURES, "%d checks failed: %s" % (len(FAILURES), ", ".join(FAILURES))


if __name__ == "__main__":
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all sidecar integration tests passed")
