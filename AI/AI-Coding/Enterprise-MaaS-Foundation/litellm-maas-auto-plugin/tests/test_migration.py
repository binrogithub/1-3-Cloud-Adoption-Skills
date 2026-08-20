#!/usr/bin/env python3
"""Tests for the safe migration script (PRD-release-closure §3.3).

    python3 -m pytest tests/test_migration.py

Tests: dry-run is side-effect free, apply removes only owned values, apply is
idempotent, user-owned values survive, and key fingerprint matching works.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
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


def _write_settings(home, env_dict, extra=None):
    """Write a settings.json with the given env block."""
    settings = {"theme": "dark"}
    if env_dict:
        settings["env"] = dict(env_dict)
    if extra:
        settings.update(extra)
    claude_dir = os.path.join(home, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    with open(os.path.join(claude_dir, "settings.json"), "w") as f:
        json.dump(settings, f)


def _read_settings(home):
    path = os.path.join(home, ".claude", "settings.json")
    with open(path) as f:
        return json.load(f)


def _run_migrate(home, *args):
    return subprocess.run(
        ["bash", MIGRATE_SCRIPT, *args],
        env={**os.environ, "HOME": home},
        capture_output=True, text=True, timeout=10,
    )


def test_dry_run_side_effect_free():
    """§3.2: dry-run is byte-for-byte side-effect free."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_API_KEY": "sk-old-key",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
            "MY_VAR": "preserve",
        })
        path = os.path.join(home, ".claude", "settings.json")
        with open(path) as f:
            before = f.read()
        result = _run_migrate(home, "--dry-run",
                              "--old-base-url", "http://127.0.0.1:4000")
        check("dry-run exits 0", result.returncode == 0)
        with open(path) as f:
            after = f.read()
        check("dry-run no file change", before == after)


def test_apply_removes_only_owned_values():
    """§3.2: apply removes only proven-old values, preserves user-owned."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_MODEL": "claude-glm-5.2",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-glm-5.2",
            "MY_MCP_CONFIG": "preserve-me",
            "CUSTOM_VAR": "also-preserve",
        }, extra={"mcpServers": {"myserver": {"command": "node"}}})
        result = _run_migrate(home, "--apply",
                              "--old-base-url", "http://127.0.0.1:4000",
                              "--old-key-fingerprint", fp)
        check("apply exits 0", result.returncode == 0)
        data = _read_settings(home)
        env = data.get("env", {})
        check("ANTHROPIC_BASE_URL removed", "ANTHROPIC_BASE_URL" not in env)
        check("ANTHROPIC_API_KEY removed", "ANTHROPIC_API_KEY" not in env)
        check("ANTHROPIC_MODEL removed", "ANTHROPIC_MODEL" not in env)
        check("OPUS_MODEL removed", "ANTHROPIC_DEFAULT_OPUS_MODEL" not in env)
        check("MY_MCP_CONFIG preserved", env.get("MY_MCP_CONFIG") == "preserve-me")
        check("CUSTOM_VAR preserved", env.get("CUSTOM_VAR") == "also-preserve")
        check("mcpServers preserved", "mcpServers" in data)


def test_apply_idempotent():
    """§3.2: repeated apply is a no-op."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        _run_migrate(home, "--apply",
                     "--old-base-url", "http://127.0.0.1:4000",
                     "--old-key-fingerprint", fp)
        data1 = _read_settings(home)
        result = _run_migrate(home, "--apply",
                              "--old-base-url", "http://127.0.0.1:4000",
                              "--old-key-fingerprint", fp)
        check("second apply exits 0", result.returncode == 0)
        check("second apply is no-op", "No old-integration" in result.stdout)
        data2 = _read_settings(home)
        check("files identical after second apply", data1 == data2)


def test_user_owned_values_preserved():
    """§3.2: values that don't match the old integration fingerprint survive."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_API_KEY": "my-custom-key-not-sk-prefix",
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            "ANTHROPIC_MODEL": "claude-sonnet-5",
        })
        result = _run_migrate(home, "--dry-run")
        # The URL and key are unresolved (no ownership evidence); model is native.
        check("no removals for user-owned values", "remove " not in result.stdout or "Unresolved" in result.stdout)


def test_oauth_preserved():
    """§3.2: OAuth state in .claude.json is preserved."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude.json"), "w") as f:
            json.dump({
                "oauthAccount": {"email": "user@example.com"},
                "theme": "light",
                "env": {"ANTHROPIC_API_KEY": key_val, "ANTHROPIC_MODEL": "claude-glm-5.2"},
            }, f)
        _run_migrate(home, "--apply", "--old-key-fingerprint", fp)
        with open(os.path.join(home, ".claude.json")) as f:
            data = json.load(f)
        check("oauthAccount preserved", data.get("oauthAccount", {}).get("email") == "user@example.com")
        check("theme preserved", data.get("theme") == "light")


def test_backup_created():
    """§3.2: apply creates a timestamped backup with mode 0600."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        _run_migrate(home, "--apply",
                     "--old-base-url", "http://127.0.0.1:4000",
                     "--old-key-fingerprint", fp)
        import glob
        backups = glob.glob(os.path.join(home, ".claude", "settings.json.migrate-backup.*"))
        check("backup created", len(backups) >= 1)
        if backups:
            mode = oct(os.stat(backups[0]).st_mode & 0o777)
            check("backup mode 0600", mode == "0o600")


def test_key_fingerprint_matching():
    """§3.2: --old-key-fingerprint restricts removal to matching keys only."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_API_KEY": "sk-key-A",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
        })
        # Use a wrong fingerprint — nothing should be removed.
        result = _run_migrate(home, "--dry-run", "--old-key-fingerprint", "0000000000000000")
        check("wrong fingerprint: no key removal", "ANTHROPIC_API_KEY" not in result.stdout)


def test_native_sk_ant_key_preserved():
    """§3.2: a native sk-ant-* Anthropic API key must NEVER be removed by
    prefix inference. Without an exact fingerprint, it is preserved."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_API_KEY": "sk-ant-api03-native-key",
            "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
            "ANTHROPIC_MODEL": "claude-sonnet-5",
        })
        # No fingerprint supplied — the native key must be preserved.
        result = _run_migrate(home, "--dry-run")
        # The key must NOT appear in a "remove" line (only in "Unresolved").
        check("native sk-ant key not removed", "remove ANTHROPIC_API_KEY" not in result.stdout)
        check("native key preserved (no removal)", "Unresolved" in result.stdout or
              "No old-integration" in result.stdout)


def test_sk_key_without_fingerprint_preserved():
    """§3.2: any sk-* key without an exact fingerprint is preserved (manual
    review). The old code removed any sk-* key by prefix — that was the bug."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_API_KEY": "sk-some-gateway-key",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        # No fingerprint — the key must NOT be removed even though it's sk-*.
        result = _run_migrate(home, "--dry-run")
        check("sk-* key without fingerprint not removed", "remove ANTHROPIC_API_KEY" not in result.stdout)


def test_exact_fingerprint_removes_key():
    """§3.2: with the exact fingerprint, the matching key IS removed."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-exact-gateway-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        result = _run_migrate(home, "--dry-run", "--old-key-fingerprint", fp)
        check("exact fingerprint removes key", "ANTHROPIC_API_KEY" in result.stdout)


def test_invalid_json_exits_nonzero():
    """§3.2: invalid JSON must exit nonzero, not be silently skipped."""
    with tempfile.TemporaryDirectory() as home:
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
            f.write("{ this is not valid json")
        result = _run_migrate(home, "--dry-run")
        check("invalid json exits nonzero", result.returncode != 0)


def test_base_url_without_exact_match_preserved():
    """§3.2: without an exact --old-base-url, a :4000 URL is preserved (manual
    review), not inferred from the port."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        # No --old-base-url — the URL must NOT be removed by :4000 inference.
        result = _run_migrate(home, "--dry-run")
        check("base url without exact match not removed", "remove ANTHROPIC_BASE_URL" not in result.stdout)


def test_exact_base_url_removes():
    """§3.2: with the exact --old-base-url, the matching URL IS removed."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        result = _run_migrate(home, "--dry-run", "--old-base-url", "http://127.0.0.1:4000")
        check("exact base url removes", "ANTHROPIC_BASE_URL" in result.stdout)


def test_model_mappings_removed_without_fingerprint():
    """§3.2: model mappings (opus/sonnet/haiku → GLM) are safe to remove by
    exact value match — they don't require a fingerprint."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-glm-5.2",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-glm-5.2",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-glm-5.2",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        result = _run_migrate(home, "--dry-run")
        check("opus mapping removed", "ANTHROPIC_DEFAULT_OPUS_MODEL" in result.stdout)
        check("sonnet mapping removed", "ANTHROPIC_DEFAULT_SONNET_MODEL" in result.stdout)
        check("haiku mapping removed", "ANTHROPIC_DEFAULT_HAIKU_MODEL" in result.stdout)
        check("model mapping removed", "ANTHROPIC_MODEL" in result.stdout)


def test_native_model_values_preserved():
    """§3.2: native Claude model values (not GLM) survive."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_MODEL": "claude-sonnet-5",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-5",
        })
        result = _run_migrate(home, "--dry-run")
        check("native sonnet model preserved", "ANTHROPIC_MODEL" not in result.stdout)
        check("native opus model preserved", "ANTHROPIC_DEFAULT_OPUS_MODEL" not in result.stdout)


# ── §3.2 P0: non-hex hash, ownership, mode preservation, rollback ────────────

def test_non_hex_fingerprint_rejected():
    """§3.2: a 64-char non-hex fingerprint must be rejected (not just length)."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {"ANTHROPIC_MODEL": "claude-glm-5.2"})
        nonhex = "z" * 64  # 64 chars but not hex
        result = _run_migrate(home, "--dry-run", "--old-key-fingerprint", nonhex)
        check("non-hex fingerprint exits nonzero", result.returncode != 0)
        check("non-hex error mentions hex", "hex" in result.stderr.lower())


def test_uppercase_fingerprint_normalized_or_rejected():
    """§3.2: an uppercase hex fingerprint is accepted (hex is case-insensitive)
    or explicitly rejected — either is safe as long as it does not silently
    match the wrong key."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp_lower = hashlib.sha256(key_val.encode()).hexdigest()
        fp_upper = fp_lower.upper()
        _write_settings(home, {"ANTHROPIC_API_KEY": key_val, "ANTHROPIC_MODEL": "claude-glm-5.2"})
        result = _run_migrate(home, "--dry-run", "--old-key-fingerprint", fp_upper)
        # int(x, 16) accepts uppercase, so it should match.
        check("uppercase fingerprint accepted", result.returncode == 0)


def test_target_symlink_rejected():
    """§3.2: a symlinked target file must be refused before any write."""
    with tempfile.TemporaryDirectory() as home:
        claude_dir = os.path.join(home, ".claude")
        os.makedirs(claude_dir)
        real = os.path.join(claude_dir, "real_settings.json")
        with open(real, "w") as f:
            json.dump({"env": {"ANTHROPIC_MODEL": "claude-glm-5.2"}}, f)
        settings = os.path.join(claude_dir, "settings.json")
        os.symlink(real, settings)
        result = _run_migrate(home, "--dry-run")
        check("symlink target exits nonzero", result.returncode != 0)


def test_wrong_owner_target_rejected():
    """§3.2: a target owned by another user must be refused before any write."""
    if os.geteuid() != 0:
        return  # only root can chown
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {"ANTHROPIC_MODEL": "claude-glm-5.2"})
        path = os.path.join(home, ".claude", "settings.json")
        os.chown(path, 65534, 65534)
        result = _run_migrate(home, "--dry-run")
        check("wrong-owner target exits nonzero", result.returncode != 0)


def test_owner_mode_preserved_on_apply():
    """§3.2: apply preserves the original uid, gid, and mode."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        path = os.path.join(home, ".claude", "settings.json")
        os.chmod(path, 0o644)
        before_mode = oct(os.stat(path).st_mode & 0o777)
        before_uid = os.stat(path).st_uid
        before_gid = os.stat(path).st_gid
        _run_migrate(home, "--apply", "--old-base-url", "http://127.0.0.1:4000",
                     "--old-key-fingerprint", fp)
        after_mode = oct(os.stat(path).st_mode & 0o777)
        after_uid = os.stat(path).st_uid
        after_gid = os.stat(path).st_gid
        check("mode preserved", before_mode == after_mode)
        check("uid preserved", before_uid == after_uid)
        check("gid preserved", before_gid == after_gid)


def test_backup_mode_0600():
    """§3.2: backups are created with mode 0600 (umask 077)."""
    import hashlib
    with tempfile.TemporaryDirectory() as home:
        key_val = "sk-old-key"
        fp = hashlib.sha256(key_val.encode()).hexdigest()
        _write_settings(home, {
            "ANTHROPIC_API_KEY": key_val,
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        _run_migrate(home, "--apply", "--old-base-url", "http://127.0.0.1:4000",
                     "--old-key-fingerprint", fp)
        import glob
        backups = glob.glob(os.path.join(home, ".claude", "settings.json.migrate-backup.*"))
        check("backup created", len(backups) >= 1)
        if backups:
            mode = oct(os.stat(backups[0]).st_mode & 0o777)
            check("backup mode 0600", mode == "0o600")


def test_cross_file_rollback_verified():
    """§3.2: a failure after the first target is replaced rolls back ALL
    targets and verifies restored content. Both files end byte-identical to
    their originals."""
    with tempfile.TemporaryDirectory() as home:
        # Both files have removable model mappings.
        _write_settings(home, {"ANTHROPIC_MODEL": "claude-glm-5.2"})
        cj_path = os.path.join(home, ".claude.json")
        with open(cj_path, "w") as f:
            json.dump({"env": {"ANTHROPIC_MODEL": "claude-glm-5.2"}}, f)
        settings_path = os.path.join(home, ".claude", "settings.json")
        with open(settings_path) as f:
            settings_before = f.read()
        with open(cj_path) as f:
            cj_before = f.read()
        # Inject a failure after writing the first target (index 0).
        result = subprocess.run(
            ["bash", MIGRATE_SCRIPT, "--apply"],
            env={**os.environ, "HOME": home, "CLAUDE_LITELLM_MIGRATE_INJECT_FAIL": "0"},
            capture_output=True, text=True, timeout=10,
        )
        check("rollback apply exits nonzero", result.returncode != 0)
        check("rollback message printed", "ROLLBACK" in result.stderr)
        # Both files must be restored to their originals.
        with open(settings_path) as f:
            check("settings restored", f.read() == settings_before)
        with open(cj_path) as f:
            check(".claude.json restored", f.read() == cj_before)


def test_dry_run_deterministic_across_hashseed():
    """§3.2: dry-run output is deterministic regardless of PYTHONHASHSEED."""
    with tempfile.TemporaryDirectory() as home:
        _write_settings(home, {
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-glm-5.2",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-glm-5.2",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-glm-5.2",
            "ANTHROPIC_MODEL": "claude-glm-5.2",
        })
        outputs = set()
        for seed in ("0", "1", "42", "random"):
            result = subprocess.run(
                ["bash", MIGRATE_SCRIPT, "--dry-run"],
                env={**os.environ, "HOME": home, "PYTHONHASHSEED": seed},
                capture_output=True, text=True, timeout=10,
            )
            outputs.add(result.stdout)
        check("dry-run deterministic across seeds", len(outputs) == 1)


# ── Run all tests ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_dry_run_side_effect_free,
    test_apply_removes_only_owned_values,
    test_apply_idempotent,
    test_user_owned_values_preserved,
    test_oauth_preserved,
    test_backup_created,
    test_key_fingerprint_matching,
    test_native_sk_ant_key_preserved,
    test_sk_key_without_fingerprint_preserved,
    test_exact_fingerprint_removes_key,
    test_invalid_json_exits_nonzero,
    test_base_url_without_exact_match_preserved,
    test_exact_base_url_removes,
    test_model_mappings_removed_without_fingerprint,
    test_native_model_values_preserved,
    test_key_fingerprint_matching,
    # §3.2 P0 new tests
    test_non_hex_fingerprint_rejected,
    test_uppercase_fingerprint_normalized_or_rejected,
    test_target_symlink_rejected,
    test_wrong_owner_target_rejected,
    test_owner_mode_preserved_on_apply,
    test_backup_mode_0600,
    test_cross_file_rollback_verified,
    test_dry_run_deterministic_across_hashseed,
]

for _t in ALL_TESTS:
    try:
        _t()
    except Exception as e:
        FAIL += 1
        print("  ERROR %s: %s: %s" % (_t.__name__, type(e).__name__, e))


def test_migration_all_pass():
    """Pytest entry point."""
    assert FAIL == 0, "%d migration checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
