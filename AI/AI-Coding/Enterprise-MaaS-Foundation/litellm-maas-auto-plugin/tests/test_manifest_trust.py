#!/usr/bin/env python3
"""Behavior tests for the strict manifest trust function and launcher boundary
(PRD-release-closure §3.1, §3.3).

These tests EXECUTE the scripts with temporary HOME and fake binaries — they
do not search source text. Covers forged/missing manifest, empty hashes, path
injection, selector collision, modified files, combined flags, launcher URL
validation, and migration full-hash matching.

    python3 -m pytest tests/test_manifest_trust.py
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP_SCRIPT = str(ROOT / "client" / "claude-litellm-setup.sh")
LAUNCHER_SCRIPT = str(ROOT / "client" / "claude-litellm")
MIGRATE_SCRIPT = str(ROOT / "client" / "claude-litellm-migrate.sh")

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL %s" % name)


def _install(home, key="sk-test-key", base_url="http://127.0.0.1:4000"):
    """Run a clean install into a temp HOME. Returns the subprocess result."""
    return subprocess.run(
        ["bash", SETUP_SCRIPT, "--base-url", base_url],
        env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": key},
        capture_output=True, text=True, timeout=10,
    )


def _run_setup(home, *args):
    return subprocess.run(
        ["bash", SETUP_SCRIPT, *args],
        env={**os.environ, "HOME": home},
        capture_output=True, text=True, timeout=10,
    )


def _manifest_path(home):
    return os.path.join(home, ".config", "claude-litellm", "manifest.json")


def _env_path(home):
    return os.path.join(home, ".config", "claude-litellm", "env")


# ── Manifest trust: verify fails without manifest ────────────────────────────

def test_verify_fails_without_manifest():
    """§3.1: --verify must fail when the manifest is missing."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        os.remove(_manifest_path(home))
        result = _run_setup(home, "--verify")
        check("verify without manifest exits nonzero", result.returncode != 0)


def test_verify_fails_with_forged_manifest():
    """§3.1: a forged manifest (correct creator but wrong hashes) must fail."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        # Forge a manifest with the right creator but a fake launcher hash.
        mp = _manifest_path(home)
        with open(mp) as f:
            m = json.load(f)
        m["hashes"]["launcher"] = "a" * 64
        with open(mp, "w") as f:
            json.dump(m, f)
        result = _run_setup(home, "--verify")
        check("forged manifest verify exits nonzero", result.returncode != 0)


def test_verify_fails_with_empty_manifest():
    """§3.1: an empty manifest file must fail verify."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        with open(_manifest_path(home), "w") as f:
            f.write("{}")
        result = _run_setup(home, "--verify")
        check("empty manifest verify exits nonzero", result.returncode != 0)


def test_verify_fails_with_bad_json_manifest():
    """§3.1: a malformed (bad JSON) manifest must fail verify."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        with open(_manifest_path(home), "w") as f:
            f.write("{not valid json")
        result = _run_setup(home, "--verify")
        check("bad-json manifest verify exits nonzero", result.returncode != 0)


# ── Manifest trust: install refuses forged manifest overwrite ─────────────────

def test_install_refuses_forged_manifest_overwrite():
    """§3.1: a forged manifest must not authorize overwriting a user launcher."""
    with tempfile.TemporaryDirectory() as home:
        bin_dir = os.path.join(home, ".local", "bin")
        config_dir = os.path.join(home, ".config", "claude-litellm")
        os.makedirs(bin_dir)
        os.makedirs(config_dir)
        # User-owned launcher.
        user_launcher = os.path.join(bin_dir, "claude-litellm")
        with open(user_launcher, "w") as f:
            f.write("#!/bin/bash\necho 'user-owned'\n")
        os.chmod(user_launcher, 0o755)
        # Forged manifest: correct creator, arbitrary launcher hash.
        with open(os.path.join(config_dir, "manifest.json"), "w") as f:
            json.dump({
                "version": 1,
                "created_by": "claude-litellm-setup.sh",
                "files": [user_launcher],
                "hashes": {"launcher": "b" * 64, "selector": "", "profile": ""},
                "model": "claude-glm-5.2",
                "base_url": "http://127.0.0.1:4000",
            }, f)
        result = _install(home)
        check("forged manifest install exits nonzero", result.returncode != 0)
        with open(user_launcher) as f:
            check("user launcher preserved", "user-owned" in f.read())


def test_install_refuses_selector_collision_without_manifest():
    """§3.1: a pre-existing user-owned claude-select must not be overwritten
    without a valid manifest."""
    with tempfile.TemporaryDirectory() as home:
        bin_dir = os.path.join(home, ".local", "bin")
        os.makedirs(bin_dir)
        user_select = os.path.join(bin_dir, "claude-select")
        with open(user_select, "w") as f:
            f.write("#!/bin/bash\necho 'user-select'\n")
        os.chmod(user_select, 0o755)
        result = _install(home)
        check("selector collision install exits nonzero", result.returncode != 0)
        with open(user_select) as f:
            check("user selector preserved", "user-select" in f.read())


# ── Manifest trust: uninstall refuses without valid manifest ─────────────────

def test_uninstall_refuses_without_manifest():
    """§3.1: uninstall without a valid manifest must not delete files."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        os.remove(_manifest_path(home))
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = _run_setup(home, "--uninstall")
        check("uninstall without manifest exits nonzero", result.returncode != 0)
        check("launcher preserved", os.path.exists(launcher))


def test_uninstall_refuses_forged_manifest():
    """§3.1: a forged uninstall manifest cannot delete an arbitrary user file."""
    with tempfile.TemporaryDirectory() as home:
        bin_dir = os.path.join(home, ".local", "bin")
        config_dir = os.path.join(home, ".config", "claude-litellm")
        os.makedirs(bin_dir)
        os.makedirs(config_dir)
        # User file under BIN_DIR that should NOT be deleted.
        user_file = os.path.join(bin_dir, "my-script")
        with open(user_file, "w") as f:
            f.write("#!/bin/bash\necho 'mine'\n")
        os.chmod(user_file, 0o755)
        # Forged manifest with no hash for the user file.
        with open(os.path.join(config_dir, "manifest.json"), "w") as f:
            json.dump({
                "version": 1,
                "created_by": "claude-litellm-setup.sh",
                "files": [user_file],
                "hashes": {"launcher": "", "selector": "", "profile": ""},
                "model": "claude-glm-5.2",
                "base_url": "http://127.0.0.1:4000",
            }, f)
        result = _run_setup(home, "--uninstall")
        check("forged uninstall exits nonzero", result.returncode != 0)
        check("user file preserved", os.path.exists(user_file))


# ── Manifest trust: combined flags rejected ──────────────────────────────────

def test_combined_flags_rejected():
    """§3.1: --verify --uninstall must be rejected, not silently choose one."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        result = _run_setup(home, "--verify", "--uninstall")
        check("combined flags exit nonzero", result.returncode != 0)


# ── Launcher URL validation ───────────────────────────────────────────────────

def test_launcher_rejects_not_a_url():
    """§3.3: claude-litellm must reject ANTHROPIC_BASE_URL=not-a-url."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        # Tamper the profile URL to a non-URL.
        env_file = _env_path(home)
        with open(env_file) as f:
            content = f.read()
        content = content.replace(
            "ANTHROPIC_BASE_URL=http://127.0.0.1:4000",
            "ANTHROPIC_BASE_URL=not-a-url",
        )
        with open(env_file, "w") as f:
            f.write(content)
        # Create a fake claude binary.
        fake_bin_dir = os.path.join(home, "fakebin")
        os.makedirs(fake_bin_dir)
        fake_claude = os.path.join(fake_bin_dir, "claude")
        with open(fake_claude, "w") as f:
            f.write("#!/usr/bin/env bash\necho 'CHILD_EXECUTED'\n")
        os.chmod(fake_claude, 0o755)
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = subprocess.run(
            ["bash", launcher, "--test"],
            env={**os.environ, "HOME": home,
                 "PATH": fake_bin_dir + ":" + os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=5,
        )
        check("not-a-url exits nonzero", result.returncode != 0)
        check("not-a-url not exec'd", "CHILD_EXECUTED" not in result.stdout)


def test_launcher_rejects_embedded_credentials():
    """§3.3: claude-litellm must reject a URL with embedded credentials (@)."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        env_file = _env_path(home)
        with open(env_file) as f:
            content = f.read()
        content = content.replace(
            "ANTHROPIC_BASE_URL=http://127.0.0.1:4000",
            "ANTHROPIC_BASE_URL=http://user:pass@127.0.0.1:4000",
        )
        with open(env_file, "w") as f:
            f.write(content)
        fake_bin_dir = os.path.join(home, "fakebin")
        os.makedirs(fake_bin_dir)
        fake_claude = os.path.join(fake_bin_dir, "claude")
        with open(fake_claude, "w") as f:
            f.write("#!/usr/bin/env bash\necho 'CHILD_EXECUTED'\n")
        os.chmod(fake_claude, 0o755)
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        result = subprocess.run(
            ["bash", launcher, "--test"],
            env={**os.environ, "HOME": home,
                 "PATH": fake_bin_dir + ":" + os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=5,
        )
        check("embedded creds exits nonzero", result.returncode != 0)


# ── Migration: full 64-char hash ──────────────────────────────────────────────

def test_migration_full_hash_matches():
    """§3.2: a full 64-char SHA-256 fingerprint must match."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-gateway-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()  # full 64 chars
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
            json.dump({"env": {
                "ANTHROPIC_API_KEY": key_val,
                "ANTHROPIC_MODEL": "claude-glm-5.2",
            }}, f)
        result = subprocess.run(
            ["bash", MIGRATE_SCRIPT, "--dry-run",
             "--old-base-url", "http://127.0.0.1:4000",
             "--old-key-fingerprint", fp],
            env={**os.environ, "HOME": home},
            capture_output=True, text=True, timeout=10,
        )
        check("full hash dry-run exits 0", result.returncode == 0)
        check("full hash removes key", "remove ANTHROPIC_API_KEY" in result.stdout)


def test_migration_truncated_hash_does_not_match():
    """§3.2: a truncated 16-char fingerprint must NOT match (old bug)."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-gateway-key"
        fp16 = hashlib.sha256(key_val.encode()).hexdigest()[:16]
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
            json.dump({"env": {
                "ANTHROPIC_API_KEY": key_val,
                "ANTHROPIC_MODEL": "claude-glm-5.2",
            }}, f)
        result = subprocess.run(
            ["bash", MIGRATE_SCRIPT, "--dry-run",
             "--old-key-fingerprint", fp16],
            env={**os.environ, "HOME": home},
            capture_output=True, text=True, timeout=10,
        )
        # Truncated fingerprint must be rejected (exits nonzero).
        check("truncated hash exits nonzero", result.returncode != 0)


def test_migration_apply_requires_ownership_for_credentials():
    """§3.2: --apply with legacy credentials but no fingerprint must exit
    nonzero before any write (no partial cleanup)."""
    with tempfile.TemporaryDirectory() as home:
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        settings_path = os.path.join(home, ".claude", "settings.json")
        with open(settings_path, "w") as f:
            json.dump({"env": {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
                "ANTHROPIC_API_KEY": "sk-old-key",
                "ANTHROPIC_MODEL": "claude-glm-5.2",
            }}, f)
        with open(settings_path) as f:
            before = f.read()
        result = subprocess.run(
            ["bash", MIGRATE_SCRIPT, "--apply"],
            env={**os.environ, "HOME": home},
            capture_output=True, text=True, timeout=10,
        )
        check("apply without fingerprint exits nonzero", result.returncode != 0)
        with open(settings_path) as f:
            after = f.read()
        check("no partial cleanup (file unchanged)", before == after)


def test_migration_dry_run_reports_unresolved_credentials():
    """§3.2: dry-run must report unresolved legacy URL/credential fields even
    when model mappings are also removable."""
    with tempfile.TemporaryDirectory() as home:
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
            json.dump({"env": {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
                "ANTHROPIC_API_KEY": "sk-old-key",
                "ANTHROPIC_MODEL": "claude-glm-5.2",
            }}, f)
        result = subprocess.run(
            ["bash", MIGRATE_SCRIPT, "--dry-run"],
            env={**os.environ, "HOME": home},
            capture_output=True, text=True, timeout=10,
        )
        check("dry-run exits 0", result.returncode == 0)
        check("reports unresolved ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL" in result.stdout)
        check("reports unresolved ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY" in result.stdout)
        check("reports model mapping removable", "remove ANTHROPIC_MODEL" in result.stdout)


# ── §3.1 P0: custom-URL lifecycle, manifest self-trust, rollback ─────────────

def test_custom_url_install_no_arg_verify_uninstall():
    """§3.1: install with a custom URL, then no-argument --verify and --uninstall
    must work (manifest base_url compared against the profile, not the default)."""
    with tempfile.TemporaryDirectory() as home:
        # Install with a non-default URL.
        r = _install(home, base_url="http://gateway.example:4000")
        check("custom URL install exits 0", r.returncode == 0)
        # No-argument verify: manifest must validate (not bad-base-url). It will
        # still fail on the live endpoint probe, but NOT on the manifest.
        r = _run_setup(home, "--verify")
        check("no-arg verify not bad-base-url", "bad-base-url" not in r.stderr and "bad-base-url" not in r.stdout)
        # No-argument uninstall must succeed (manifest is valid).
        r = _run_setup(home, "--uninstall")
        check("no-arg uninstall exits 0", r.returncode == 0)
        check("launcher removed", not os.path.exists(os.path.join(home, ".local", "bin", "claude-litellm")))


def test_gateway_url_key_rotation():
    """§3.1: rotate the gateway URL and key from a valid prior installation."""
    with tempfile.TemporaryDirectory() as home:
        _install(home, key="sk-old-key", base_url="http://old-gw:4000")
        # Re-install with a new URL and key — the old manifest validates, so
        # upgrade is permitted.
        r = subprocess.run(
            ["bash", SETUP_SCRIPT, "--base-url", "http://new-gw:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-new-key"},
            capture_output=True, text=True, timeout=10,
        )
        check("rotation install exits 0", r.returncode == 0)
        env_file = _env_path(home)
        with open(env_file) as f:
            content = f.read()
        check("rotated URL in profile", "http://new-gw:4000" in content)
        check("rotated key in profile", "sk-new-key" in content)


def test_manifest_symlink_rejected():
    """§3.1: a symlinked manifest must be rejected (bad-manifest-meta)."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        mp = _manifest_path(home)
        real = os.path.join(home, ".config", "claude-litellm", "real_manifest")
        os.rename(mp, real)
        os.chmod(real, 0o644)
        os.symlink(real, mp)
        r = _run_setup(home, "--verify")
        check("symlink manifest verify nonzero", r.returncode != 0)
        check("symlink manifest bad-meta", "bad-manifest-meta" in r.stderr or "bad-manifest-meta" in r.stdout)
        # Uninstall must also refuse.
        r = _run_setup(home, "--uninstall")
        check("symlink manifest uninstall nonzero", r.returncode != 0)
        check("launcher preserved on symlink uninstall",
              os.path.exists(os.path.join(home, ".local", "bin", "claude-litellm")))


def test_manifest_wrong_mode_rejected():
    """§3.1: a manifest with mode 0644 must be rejected."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        mp = _manifest_path(home)
        os.chmod(mp, 0o644)
        r = _run_setup(home, "--verify")
        check("0644 manifest verify nonzero", r.returncode != 0)
        check("0644 manifest bad-meta", "bad-manifest-meta" in r.stderr or "bad-manifest-meta" in r.stdout)


def test_manifest_wrong_owner_rejected():
    """§3.1: a manifest owned by another user must be rejected."""
    if os.geteuid() != 0:
        return  # only root can chown to another uid
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        mp = _manifest_path(home)
        os.chown(mp, 65534, 65534)
        r = _run_setup(home, "--verify")
        check("wrong-owner manifest verify nonzero", r.returncode != 0)
        check("wrong-owner manifest bad-meta", "bad-manifest-meta" in r.stderr or "bad-manifest-meta" in r.stdout)


def test_embedded_credential_url_rejected_at_install():
    """§3.1: install must reject a URL with embedded credentials before writing
    a profile the launcher would reject."""
    with tempfile.TemporaryDirectory() as home:
        r = _install(home, base_url="http://user:pass@gateway:4000")
        check("embedded-cred install nonzero", r.returncode != 0)
        check("no profile written", not os.path.exists(_env_path(home)))


def test_install_rollback_on_failure():
    """§3.1: if a staged replacement fails, the previous valid set is restored.
    Injects a failure after each staged step via the test hook and proves the
    original profile is restored every time."""
    for step in ("profile", "launcher", "selector", "manifest"):
        with tempfile.TemporaryDirectory() as home:
            _install(home, key="sk-original", base_url="http://127.0.0.1:4000")
            env_file = _env_path(home)
            with open(env_file) as f:
                original_content = f.read()
            r = subprocess.run(
                ["bash", SETUP_SCRIPT, "--base-url", "http://new-gw:4000"],
                env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-new",
                     "CLAUDE_LITELLM_INJECT_FAIL": step},
                capture_output=True, text=True, timeout=10,
            )
            check("inject %s exits nonzero" % step, r.returncode != 0)
            if os.path.exists(env_file):
                with open(env_file) as f:
                    after = f.read()
                check("rollback after %s restores profile" % step, after == original_content)
            else:
                check("rollback after %s restores profile" % step, False)


def test_modified_launcher_partial_safe_uninstall():
    """§3.1: a modified launcher is preserved (hash mismatch) while other
    still-matching owned files are removed; uninstall exits nonzero."""
    with tempfile.TemporaryDirectory() as home:
        _install(home)
        launcher = os.path.join(home, ".local", "bin", "claude-litellm")
        # Modify the launcher so its hash no longer matches the manifest.
        with open(launcher, "a") as f:
            f.write("# user modification\n")
        r = _run_setup(home, "--uninstall")
        check("modified-launcher uninstall nonzero", r.returncode != 0)
        check("modified launcher preserved", os.path.exists(launcher))
        # The profile should still be removed (it matches its hash).
        check("profile removed", not os.path.exists(_env_path(home)))


# ── R10 §Testing: Legacy migration counterexamples ────────────────────────────

import hashlib as _hashlib


def _legacy_install(home, key="sk-legacy-key", base_url="http://127.0.0.1:4000"):
    """Create a synthetic legacy claude-glm installation with a valid manifest.
    Returns a dict of the created paths."""
    import shutil
    paths = {}
    config_dir = os.path.join(home, ".config", "claude-glm")
    bin_dir = os.path.join(home, ".local", "bin")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)
    # Legacy env (profile)
    env_path = os.path.join(config_dir, "env")
    with open(env_path, "w") as f:
        f.write("ANTHROPIC_BASE_URL=%s\nANTHROPIC_API_KEY=%s\nANTHROPIC_MODEL=claude-glm-5.2\n" % (base_url, key))
    os.chmod(env_path, 0o600)
    # Legacy launcher (copy the current launcher as a stand-in)
    launcher_path = os.path.join(bin_dir, "claude-glm")
    shutil.copy(LAUNCHER_SCRIPT, launcher_path)
    os.chmod(launcher_path, 0o755)
    # Shared selector
    selector_path = os.path.join(bin_dir, "claude-select")
    shutil.copy(str(ROOT / "client" / "claude-select"), selector_path)
    os.chmod(selector_path, 0o755)
    # Compute real hashes
    def _sha(p):
        return _hashlib.sha256(open(p, "rb").read()).hexdigest()
    launcher_hash = _sha(launcher_path)
    selector_hash = _sha(selector_path)
    env_hash = _sha(env_path)
    # Legacy manifest
    manifest_path = os.path.join(config_dir, "manifest.json")
    manifest = {
        "version": 1,
        "created_by": "claude-glm-setup.sh",
        "files": [launcher_path, selector_path, env_path, manifest_path],
        "hashes": {"launcher": launcher_hash, "selector": selector_hash, "profile": env_hash},
        "model": "claude-glm-5.2",
        "base_url": base_url,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    os.chmod(manifest_path, 0o600)
    paths["config_dir"] = config_dir
    paths["env"] = env_path
    paths["launcher"] = launcher_path
    paths["selector"] = selector_path
    paths["manifest"] = manifest_path
    return paths


def _snapshot(home):
    """Capture (sha256, type, uid, gid, mode) for all relevant paths."""
    import stat as _stat
    snap = {}
    candidates = [
        os.path.join(home, ".config", "claude-glm"),
        os.path.join(home, ".config", "claude-glm", "env"),
        os.path.join(home, ".config", "claude-glm", "manifest.json"),
        os.path.join(home, ".config", "claude-litellm"),
        os.path.join(home, ".config", "claude-litellm", "env"),
        os.path.join(home, ".config", "claude-litellm", "manifest.json"),
        os.path.join(home, ".local", "bin", "claude-glm"),
        os.path.join(home, ".local", "bin", "claude-litellm"),
        os.path.join(home, ".local", "bin", "claude-select"),
    ]
    for p in candidates:
        if os.path.lexists(p):
            st = os.lstat(p)
            if _stat.S_ISREG(st.st_mode):
                h = _hashlib.sha256(open(p, "rb").read()).hexdigest()
            else:
                h = None
            snap[p] = (h, _stat.S_IFMT(st.st_mode), st.st_uid, st.st_gid, _stat.S_IMODE(st.st_mode))
    return snap


def _assert_snapshot_unchanged(name, before, after):
    """Assert that every path in `before` is unchanged in `after`."""
    for p, v in before.items():
        if p in after:
            check("%s: %s unchanged" % (name, os.path.basename(p)), after[p] == v)
        else:
            check("%s: %s still exists" % (name, os.path.basename(p)), False)


def test_legacy_empty_hashes_refuses():
    """R10 #1: empty legacy hash object refuses and preserves all files."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        # Replace manifest with empty hashes
        mp = paths["manifest"]
        with open(mp) as f:
            m = json.load(f)
        m["hashes"] = {}
        with open(mp, "w") as f:
            json.dump(m, f)
        os.chmod(mp, 0o600)
        before = _snapshot(home)
        r = _install(home)
        check("empty hashes refuse (nonzero)", r.returncode != 0)
        after = _snapshot(home)
        _assert_snapshot_unchanged("empty-hashes", before, after)


def test_legacy_missing_hash_refuses():
    """R10 #2: missing launcher hash refuses and preserves all files."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        mp = paths["manifest"]
        with open(mp) as f:
            m = json.load(f)
        del m["hashes"]["launcher"]
        with open(mp, "w") as f:
            json.dump(m, f)
        os.chmod(mp, 0o600)
        before = _snapshot(home)
        r = _install(home)
        check("missing hash refuse (nonzero)", r.returncode != 0)
        after = _snapshot(home)
        _assert_snapshot_unchanged("missing-hash", before, after)


def test_legacy_extra_config_entry_refuses():
    """R10 #7: extra file in legacy config dir refuses and preserves all files."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        # Drop an extra file in the legacy config dir
        with open(os.path.join(paths["config_dir"], "user-data.json"), "w") as f:
            f.write('{"important": "data"}')
        before = _snapshot(home)
        r = _install(home)
        check("extra config entry refuse (nonzero)", r.returncode != 0)
        after = _snapshot(home)
        _assert_snapshot_unchanged("extra-entry", before, after)
        # The extra file must still exist
        check("extra file preserved", os.path.exists(os.path.join(paths["config_dir"], "user-data.json")))


def test_legacy_modified_file_refuses():
    """R10 #8: modified launcher (hash mismatch) refuses before mutation."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        # Modify the launcher so its hash no longer matches
        with open(paths["launcher"], "a") as f:
            f.write("# user modification\n")
        before = _snapshot(home)
        r = _install(home)
        check("modified legacy launcher refuse (nonzero)", r.returncode != 0)
        after = _snapshot(home)
        _assert_snapshot_unchanged("modified-launcher", before, after)


def test_legacy_valid_migrates():
    """R10 #10: valid exact legacy installation migrates successfully."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        r = _install(home)
        check("legacy migration exits 0", r.returncode == 0)
        # Old files gone
        check("old launcher gone", not os.path.exists(paths["launcher"]))
        check("old config dir gone", not os.path.exists(paths["config_dir"]))
        # New install present
        check("new launcher installed", os.path.exists(os.path.join(home, ".local", "bin", "claude-litellm")))
        check("new env installed", os.path.exists(_env_path(home)))
        check("new manifest installed", os.path.exists(_manifest_path(home)))


def test_migration_idempotent():
    """R10 #11: repeating setup after successful migration is idempotent."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        _install(home)  # migrate
        # Second install should be idempotent (current manifest validates)
        r = _install(home)
        check("idempotent reinstall exits 0", r.returncode == 0)


def test_unowned_current_with_legacy_refuses():
    """R10 #9: unowned current claude-litellm target refuses while legacy
    remains usable and byte-identical."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        # Place an unowned claude-litellm (no current manifest)
        unowned = os.path.join(home, ".local", "bin", "claude-litellm")
        with open(unowned, "w") as f:
            f.write("#!/bin/bash\necho 'user-owned'\n")
        os.chmod(unowned, 0o755)
        before = _snapshot(home)
        r = _install(home)
        check("unowned current + legacy refuse (nonzero)", r.returncode != 0)
        after = _snapshot(home)
        # Legacy files must be byte-identical
        _assert_snapshot_unchanged("unowned-current", before, after)
        # The unowned launcher must still exist
        check("unowned launcher preserved", os.path.exists(unowned))


def test_injected_failure_restores_legacy():
    """R10 #12: injected transaction failure restores exact pre-run state
    (including legacy files)."""
    with tempfile.TemporaryDirectory() as home:
        paths = _legacy_install(home)
        before = _snapshot(home)
        # Inject failure at the manifest commit step
        r = subprocess.run(
            ["bash", SETUP_SCRIPT, "--base-url", "http://127.0.0.1:4000"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_KEY": "sk-test-key",
                 "CLAUDE_LITELLM_INJECT_FAIL": "manifest"},
            capture_output=True, text=True, timeout=10,
        )
        check("injected failure exits nonzero", r.returncode != 0)
        after = _snapshot(home)
        # Legacy files must be restored (launcher, env, manifest still exist)
        check("legacy launcher restored", os.path.exists(paths["launcher"]))
        check("legacy env restored", os.path.exists(paths["env"]))
        check("legacy manifest restored", os.path.exists(paths["manifest"]))


# ── Run all tests ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_verify_fails_without_manifest,
    test_verify_fails_with_forged_manifest,
    test_verify_fails_with_empty_manifest,
    test_verify_fails_with_bad_json_manifest,
    test_install_refuses_forged_manifest_overwrite,
    test_install_refuses_selector_collision_without_manifest,
    test_uninstall_refuses_without_manifest,
    test_uninstall_refuses_forged_manifest,
    test_combined_flags_rejected,
    test_launcher_rejects_not_a_url,
    test_launcher_rejects_embedded_credentials,
    test_migration_full_hash_matches,
    test_migration_truncated_hash_does_not_match,
    test_migration_apply_requires_ownership_for_credentials,
    test_migration_dry_run_reports_unresolved_credentials,
    # §3.1 P0 new tests
    test_custom_url_install_no_arg_verify_uninstall,
    test_gateway_url_key_rotation,
    test_manifest_symlink_rejected,
    test_manifest_wrong_mode_rejected,
    test_manifest_wrong_owner_rejected,
    test_embedded_credential_url_rejected_at_install,
    test_install_rollback_on_failure,
    test_modified_launcher_partial_safe_uninstall,
    # R10 legacy migration counterexamples
    test_legacy_empty_hashes_refuses,
    test_legacy_missing_hash_refuses,
    test_legacy_extra_config_entry_refuses,
    test_legacy_modified_file_refuses,
    test_legacy_valid_migrates,
    test_migration_idempotent,
    test_unowned_current_with_legacy_refuses,
    test_injected_failure_restores_legacy,
]

for _t in ALL_TESTS:
    try:
        _t()
    except Exception as e:
        FAIL += 1
        print("  ERROR %s: %s: %s" % (_t.__name__, type(e).__name__, e))


def test_manifest_trust_all_pass():
    """Pytest entry point."""
    assert FAIL == 0, "%d manifest-trust checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
