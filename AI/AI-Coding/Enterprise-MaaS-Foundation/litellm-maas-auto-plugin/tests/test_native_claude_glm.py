#!/usr/bin/env python3
"""Tests for native Claude + selectable GLM-5.2 (PRD-native-claude-litellm-selection).

Client isolation tests (§12.1): the GLM launcher does not touch native Claude
settings, cleans inherited Anthropic vars, and execs the native binary.
Server tests (§12.3): no native Claude aliases in the registry, GLM routes
through smart_router, non-GLM selectors are not rewritten.

Run: python3 -m pytest tests/test_native_claude_glm.py
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL %s" % name)


# ── Server tests (§12.3) ─────────────────────────────────────────────────────

def test_no_native_claude_aliases_in_registry():
    """§12.3: default/opus/sonnet/haiku are not gateway aliases to GLM."""
    registry = json.loads((ROOT / "litellm_plugins" / "model_registry.json").read_text())
    models = set(registry.get("models", {}).keys())
    # No native Claude selector names should be in the registry as GLM aliases.
    for native_name in ("default", "opus", "sonnet", "haiku", "claude-opus-4-6", "coding-auto", "meli-coding-fast"):
        check("registry has no %s alias" % native_name, native_name not in models)
    # claude-glm-5.2 must remain as the public GLM group.
    check("registry has claude-glm-5.2", "claude-glm-5.2" in models)


def test_glm_model_routes_to_glm_family():
    """§12.3: claude-glm-5.2 is a GLM-family model in the registry."""
    registry = json.loads((ROOT / "litellm_plugins" / "model_registry.json").read_text())
    entry = registry.get("models", {}).get("claude-glm-5.2")
    check("claude-glm-5.2 exists", entry is not None)
    if entry:
        check("claude-glm-5.2 family is glm", entry.get("family") == "glm")
        check("claude-glm-5.2 not internal", entry.get("internal") is False)


def test_native_selector_not_rewritten_to_glm():
    """§3.1: a non-GLM model arriving at the gateway is REJECTED (not rewritten
    or passed through with GLM metadata)."""
    import importlib.util, types, logging
    litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
    litellm.token_counter = lambda **kw: 100
    lm = types.ModuleType("litellm._logging")
    lm.verbose_proxy_logger = logging.getLogger("test")
    sys.modules.setdefault("litellm._logging", lm)
    sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
    cl = types.ModuleType("litellm.integrations.custom_logger")
    class CustomLogger: pass
    cl.CustomLogger = CustomLogger
    sys.modules.setdefault("litellm.integrations.custom_logger", cl)

    # Load smart_router
    router_path = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
    spec = importlib.util.spec_from_file_location("smart_router_native_test", router_path)
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)

    # A non-GLM model should not be in the glm family.
    profile = router._model_profile("opus")
    check("opus is not glm family", profile.get("family") != "glm")
    profile2 = router._model_profile("claude-glm-5.2")
    check("claude-glm-5.2 is glm family", profile2.get("family") == "glm")

    # route_request should reject non-GLM models.
    rejected = False
    try:
        router.route_request({"model": "opus", "messages": [{"role": "user", "content": "hi"}]})
    except Exception:
        rejected = True
    check("opus rejected by router", rejected)


# ── Client isolation tests (§12.1) ───────────────────────────────────────────

def test_claude_glm_setup_does_not_touch_settings():
    """§12.1: installing claude-litellm does not modify ~/.claude/settings.json."""
    with tempfile.TemporaryDirectory() as home:
        # Create a fake ~/.claude/settings.json with some user content.
        claude_dir = os.path.join(home, ".claude")
        os.makedirs(claude_dir)
        settings_path = os.path.join(claude_dir, "settings.json")
        original_settings = json.dumps({"theme": "dark", "env": {"SOME_VAR": "value"}})
        with open(settings_path, "w") as f:
            f.write(original_settings)

        # Run claude-litellm-setup.sh in this fake HOME.
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        result = subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        # settings.json must be byte-identical.
        with open(settings_path) as f:
            after = f.read()
        check("settings.json unchanged", after == original_settings)


def test_claude_glm_setup_does_not_touch_claude_json():
    """§12.1: installing claude-litellm does not modify ~/.claude.json."""
    with tempfile.TemporaryDirectory() as home:
        claude_json = os.path.join(home, ".claude.json")
        original = json.dumps({"oauthAccount": {"email": "user@example.com"}, "theme": "light"})
        with open(claude_json, "w") as f:
            f.write(original)

        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        with open(claude_json) as f:
            after = f.read()
        check(".claude.json unchanged", after == original)


def test_claude_glm_setup_does_not_touch_profile():
    """§12.1: installing claude-litellm does not modify shell profiles."""
    with tempfile.TemporaryDirectory() as home:
        bashrc = os.path.join(home, ".bashrc")
        original = "# user bashrc\nexport PATH=/usr/local/bin:$PATH\n"
        with open(bashrc, "w") as f:
            f.write(original)

        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        with open(bashrc) as f:
            after = f.read()
        check(".bashrc unchanged", after == original)


def test_claude_glm_setup_creates_isolated_profile():
    """§6.1: setup creates ~/.config/claude-litellm/env with mode 0600."""
    with tempfile.TemporaryDirectory() as home:
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        env_file = os.path.join(home, ".config", "claude-litellm", "env")
        check("env file exists", os.path.exists(env_file))
        if os.path.exists(env_file):
            mode = oct(os.stat(env_file).st_mode & 0o777)
            check("env file mode 0600", mode == "0o600")
            content = open(env_file).read()
            check("env has ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL=http://127.0.0.1:4000" in content)
            check("env has ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY=sk-test-key" in content)
            check("env has ANTHROPIC_MODEL", "ANTHROPIC_MODEL=claude-glm-5.2" in content)


def test_claude_glm_setup_installs_launcher():
    """§6.1: setup installs the claude-litellm launcher to ~/.local/bin/."""
    with tempfile.TemporaryDirectory() as home:
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        check("launcher installed", os.path.exists(launcher))
        if os.path.exists(launcher):
            check("launcher executable", os.access(launcher, os.X_OK))


def test_claude_glm_uninstall_removes_only_owned_files():
    """§12.1: uninstall removes only integration-owned files, not native state."""
    with tempfile.TemporaryDirectory() as home:
        # Install
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )
        # Create fake native state
        claude_dir = os.path.join(home, ".claude")
        os.makedirs(claude_dir)
        settings_path = os.path.join(claude_dir, "settings.json")
        with open(settings_path, "w") as f:
            f.write('{"theme": "dark"}')

        # Uninstall
        subprocess.run(
            ["bash", setup_script, "--uninstall"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )

        # Integration files removed
        check("launcher removed", not os.path.exists(os.path.join(home, ".local", "bin", "claude-litellm")))
        check("config dir removed", not os.path.exists(os.path.join(home, ".config", "claude-litellm")))
        # Native state preserved
        check("settings.json preserved", os.path.exists(settings_path))


def test_install_refuses_empty_manifest_collision():
    """§3.1: an empty or forged manifest must NOT bypass the ownership check.
    A user-owned launcher must be preserved even if an empty manifest exists."""
    with tempfile.TemporaryDirectory() as home:
        # Simulate a user-owned launcher + empty manifest.
        bin_dir = os.path.join(home, ".local", "bin")
        config_dir = os.path.join(home, ".config", "claude-litellm")
        os.makedirs(bin_dir)
        os.makedirs(config_dir)
        # User-owned launcher.
        user_launcher = os.path.join(bin_dir, "claude-litellm")
        with open(user_launcher, "w") as f:
            f.write("#!/bin/bash\necho 'user-owned'\n")
        os.chmod(user_launcher, 0o755)
        # Empty/forged manifest (should NOT prove ownership).
        with open(os.path.join(config_dir, "manifest.json"), "w") as f:
            f.write("{}")
        # Attempt install — must refuse to overwrite.
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        result = subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key"},
            capture_output=True, text=True, timeout=10,
        )
        check("empty manifest: install exits nonzero", result.returncode != 0)
        # The user-owned launcher must be preserved.
        with open(user_launcher) as f:
            content = f.read()
        check("empty manifest: user launcher preserved", "user-owned" in content)


def test_claude_select_no_default():
    """§5.3: claude-select with no subcommand exits nonzero (no silent default)."""
    select_script = str(ROOT / "client" / "claude-select")
    result = subprocess.run(
        ["bash", select_script],
        capture_output=True, text=True, timeout=5,
    )
    check("claude-select no subcommand exits nonzero", result.returncode != 0)


def test_claude_glm_launcher_cleans_inherited_anthropic():
    """§6.3: the launcher removes inherited Anthropic vars from the child env."""
    # This test uses a fake claude binary that prints its env.
    with tempfile.TemporaryDirectory() as home:
        # Install with key from CLAUDE_LITELLM_KEY env (not argv).
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-glm-key"},
            capture_output=True, text=True, timeout=10,
        )

        # Create a fake claude binary that prints ANTHROPIC_API_KEY
        fake_bin_dir = os.path.join(home, "fakebin")
        os.makedirs(fake_bin_dir)
        fake_claude = os.path.join(fake_bin_dir, "claude")
        with open(fake_claude, "w") as f:
            f.write("""#!/usr/bin/env bash
echo "KEY=$ANTHROPIC_API_KEY"
echo "MODEL=$ANTHROPIC_MODEL"
echo "BASE=$ANTHROPIC_BASE_URL"
""")
        os.chmod(fake_claude, 0o755)

        # Run claude-litellm with inherited ANTHROPIC_API_KEY set to a DIFFERENT key.
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = subprocess.run(
            ["bash", launcher, "--test"],
            env={
                **os.environ,
                "HOME": home,
                "PATH": fake_bin_dir + ":" + os.environ.get("PATH", ""),
                "ANTHROPIC_API_KEY": "sk-inherited-oauth-key",  # should NOT reach the child
            },
            capture_output=True, text=True, timeout=5,
        )
        # The child should have the GLM key, not the inherited OAuth key.
        check("inherited key cleaned", "sk-inherited-oauth-key" not in result.stdout)
        check("glm key set", "sk-glm-key" in result.stdout)


def test_claude_glm_launcher_rejects_tampered_model():
    """§3.3: the launcher must reject a tampered profile whose model is not
    claude-glm-5.2. A modified profile selecting premium-openrouter must exit
    nonzero and NOT exec the child."""
    with tempfile.TemporaryDirectory() as home:
        # Install normally.
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-glm-key"},
            capture_output=True, text=True, timeout=10,
        )
        # Tamper the profile: change the model to premium-openrouter.
        env_file = os.path.join(home, ".config", "claude-litellm", "env")
        with open(env_file) as f:
            content = f.read()
        content = content.replace("ANTHROPIC_MODEL=claude-glm-5.2", "ANTHROPIC_MODEL=premium-openrouter")
        with open(env_file, "w") as f:
            f.write(content)
        # Create a fake claude binary that would print if exec'd.
        fake_bin_dir = os.path.join(home, "fakebin")
        os.makedirs(fake_bin_dir)
        fake_claude = os.path.join(fake_bin_dir, "claude")
        with open(fake_claude, "w") as f:
            f.write("#!/usr/bin/env bash\necho 'CHILD_EXECUTED'\n")
        os.chmod(fake_claude, 0o755)
        # Run the launcher — it must reject the tampered model.
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = subprocess.run(
            ["bash", launcher, "--test"],
            env={
                **os.environ,
                "HOME": home,
                "PATH": fake_bin_dir + ":" + os.environ.get("PATH", ""),
            },
            capture_output=True, text=True, timeout=5,
        )
        check("tampered model exits nonzero", result.returncode != 0)
        check("tampered model not exec'd", "CHILD_EXECUTED" not in result.stdout)
        check("tampered model error message", "claude-glm-5.2" in result.stderr)


# NOTE: The source-string verify tests (profile model, key-not-in-argv, ACL
# 401/403, vision-secondary, manifest hashes) were removed — they are now
# covered by behavior tests in tests/test_manifest_trust.py that actually
# execute the scripts (PRD §3.1: "Source-string searches do not satisfy this
# gate").


def test_launcher_exports_1m_env_vars():
    """R10 §6: the launcher exports the 1M context environment variables.
    Tests the launcher's environment, not model self-reporting."""
    with tempfile.TemporaryDirectory() as home:
        # Install claude-litellm
        setup_script = str(ROOT / "client" / "claude-litellm-setup.sh")
        subprocess.run(
            ["bash", setup_script, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-glm-key"},
            capture_output=True, text=True, timeout=10,
        )
        # Create a fake claude binary that prints the env vars we care about
        fake_bin_dir = os.path.join(home, "fakebin")
        os.makedirs(fake_bin_dir)
        fake_claude = os.path.join(fake_bin_dir, "claude")
        with open(fake_claude, "w") as f:
            f.write("""#!/usr/bin/env bash
echo "MODEL=$ANTHROPIC_MODEL"
echo "DISABLE_COMPACT=$DISABLE_COMPACT"
echo "MAX_CONTEXT=$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
echo "MAX_OUTPUT=$CLAUDE_CODE_MAX_OUTPUT_TOKENS"
echo "BASE=$ANTHROPIC_BASE_URL"
echo "KEY=$ANTHROPIC_API_KEY"
""")
        os.chmod(fake_claude, 0o755)
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = subprocess.run(
            ["bash", launcher, "--test"],
            env={**os.environ, "HOME": home,
                 "PATH": fake_bin_dir + ":" + os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=5,
        )
        check("canonical model exported", "MODEL=claude-glm-5.2" in result.stdout)
        check("DISABLE_COMPACT=1 exported", "DISABLE_COMPACT=1" in result.stdout)
        check("MAX_CONTEXT=1000000 exported", "MAX_CONTEXT=1000000" in result.stdout)
        check("MAX_OUTPUT=128000 exported", "MAX_OUTPUT=128000" in result.stdout)
        check("gateway URL exported", "BASE=http://127.0.0.1:4000" in result.stdout)
        check("GLM key exported", "KEY=sk-glm-key" in result.stdout)


# ── Run all tests ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_no_native_claude_aliases_in_registry,
    test_glm_model_routes_to_glm_family,
    test_native_selector_not_rewritten_to_glm,
    test_claude_glm_setup_does_not_touch_settings,
    test_claude_glm_setup_does_not_touch_claude_json,
    test_claude_glm_setup_does_not_touch_profile,
    test_claude_glm_setup_creates_isolated_profile,
    test_claude_glm_setup_installs_launcher,
    test_claude_glm_uninstall_removes_only_owned_files,
    test_install_refuses_empty_manifest_collision,
    test_claude_select_no_default,
    test_claude_glm_launcher_cleans_inherited_anthropic,
    test_claude_glm_launcher_rejects_tampered_model,
    test_launcher_exports_1m_env_vars,
]

for _t in ALL_TESTS:
    try:
        _t()
    except Exception as e:
        FAIL += 1
        print("  ERROR %s: %s: %s" % (_t.__name__, type(e).__name__, e))


def test_native_claude_glm_all_pass():
    """Pytest entry point."""
    assert FAIL == 0, "%d native-claude-litellm checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
