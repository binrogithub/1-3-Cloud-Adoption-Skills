"""Tests for scripts/migrate-exa.sh — retire legacy plain-Claude Exa config.

Contract (PRD §8, G-EXA2, G-EXA6):
  * --dry-run is byte-for-byte side-effect free and never prints the key.
  * --apply removes ONLY:
      - mcpServers.exa-search (command == exa-mcp) from ~/.claude.json
      - env.EXA_API_KEY from ~/.claude/settings.json
      - four old tool permissions from ~/.claude/settings.json
  * Unrelated MCP, env, permissions, OAuth metadata, theme, hooks, 1M context
    remain byte-identical.
  * An unknown Exa entry (wrong command) fails closed — not removed.
  * Simulated second-file failure restores the first file (transactional).
  * Idempotent: repeated apply is a no-op.
  * No persistent key-bearing backups (.bak) are created.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "scripts" / "migrate-exa.sh"

EXA_KEY = "old-exa-key-xyz"
OLD_PERMS = [
    "mcp__exa-search__exa_search",
    "mcp__exa-search__exa_answer",
    "mcp__exa-search__exa_find_similar",
    "mcp__exa-search__exa_contents",
]


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def legacy_home(tmp_path: Path):
    """A fake HOME with the legacy plain-Claude Exa shape + unrelated state."""
    home = tmp_path
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)

    # ~/.claude.json with legacy exa-search (stdio exa-mcp) + unrelated MCP.
    claude_json = {
        "mcpServers": {
            "exa-search": {
                "command": "exa-mcp",
                "args": ["--key", EXA_KEY],
                "env": {"EXA_API_KEY": EXA_KEY},
            },
            "user-mcp": {"command": "node", "args": ["/home/user/srv.js"]},
        },
        "theme": "dark",
    }
    (claude_dir / ".claude.json").write_text(json.dumps(claude_json, indent=2))

    # ~/.claude/settings.json with EXA_API_KEY + old perms + unrelated state.
    settings = {
        "permissions": {
            "allow": ["Bash(ls:*)", *OLD_PERMS],
        },
        "env": {
            "EXA_API_KEY": EXA_KEY,
            "ANTHROPIC_API_KEY": "sk-ant-keep-me",
            "SOME_USER_VAR": "user-val",
        },
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo user"}]}
            ]
        },
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # OAuth credentials (must be preserved).
    creds = {"claudeAiOauth": {"accessToken": "oauth-keep", "refreshToken": "refresh-keep"}}
    (claude_dir / "credentials.json").write_text(json.dumps(creds, indent=2))

    return home


@pytest.fixture()
def run_migrate(legacy_home: Path):
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(legacy_home)

    def _run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(MIGRATE), *args],
            env=base_env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    return _run


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    snap: dict[str, bytes] = {}
    if not root.exists():
        return snap
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snap[str(path.relative_to(root))] = path.read_bytes()
    return snap


# ---------------------------------------------------------------------------
# --dry-run is side-effect free
# ---------------------------------------------------------------------------


def test_dry_run_is_side_effect_free(run_migrate, legacy_home):
    before = _snapshot_tree(legacy_home)
    result = run_migrate("--dry-run")
    assert result.returncode == 0, result.stderr
    after = _snapshot_tree(legacy_home)
    assert before == after, "--dry-run modified the filesystem"


def test_dry_run_never_prints_key(run_migrate):
    result = run_migrate("--dry-run")
    assert result.returncode == 0, result.stderr
    assert EXA_KEY not in result.stdout + result.stderr


def test_no_mode_arg_fails(run_migrate):
    assert run_migrate().returncode != 0


# ---------------------------------------------------------------------------
# --apply removes only the legacy Exa shape
# ---------------------------------------------------------------------------


def test_apply_removes_exa_mcp_from_claude_json(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    data = json.loads((legacy_home / ".claude" / ".claude.json").read_text())
    assert "exa-search" not in data.get("mcpServers", {})


def test_apply_preserves_unrelated_mcp(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    data = json.loads((legacy_home / ".claude" / ".claude.json").read_text())
    assert "user-mcp" in data["mcpServers"]


def test_apply_removes_exa_api_key_env(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    assert "EXA_API_KEY" not in settings.get("env", {})


def test_apply_removes_old_permissions(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    allow = settings.get("permissions", {}).get("allow", [])
    for perm in OLD_PERMS:
        assert perm not in allow, f"old perm not removed: {perm}"


def test_apply_preserves_unrelated_permissions(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    allow = settings["permissions"]["allow"]
    assert "Bash(ls:*)" in allow


def test_apply_preserves_anthropic_api_key(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    assert settings["env"]["ANTHROPIC_API_KEY"] == "sk-ant-keep-me"


def test_apply_preserves_user_env_vars(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    assert settings["env"]["SOME_USER_VAR"] == "user-val"


def test_apply_preserves_theme_and_hooks(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    assert settings["theme"] == "dark"
    assert "PreToolUse" in settings["hooks"]


def test_apply_preserves_oauth(run_migrate, legacy_home):
    creds_path = legacy_home / ".claude" / "credentials.json"
    before = creds_path.read_bytes()
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    assert creds_path.read_bytes() == before


def test_apply_preserves_claude_json_theme(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    data = json.loads((legacy_home / ".claude" / ".claude.json").read_text())
    assert data["theme"] == "dark"


# ---------------------------------------------------------------------------
# Key never leaks
# ---------------------------------------------------------------------------


def test_apply_never_prints_key(run_migrate):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    assert EXA_KEY not in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Fail closed on unknown Exa shape
# ---------------------------------------------------------------------------


def test_apply_fails_closed_on_wrong_command(tmp_path: Path):
    """If exa-search uses a different command, do not remove it."""
    home = tmp_path
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    claude_json = {
        "mcpServers": {
            "exa-search": {"command": "some-other-tool", "args": []},
        }
    }
    (claude_dir / ".claude.json").write_text(json.dumps(claude_json, indent=2))
    (claude_dir / "settings.json").write_text(json.dumps({"permissions": {"allow": []}}, indent=2))

    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(MIGRATE), "--apply"], env=env, capture_output=True, text=True, timeout=15
    )
    # Should fail closed — unknown shape.
    assert result.returncode != 0
    data = json.loads((claude_dir / ".claude.json").read_text())
    assert "exa-search" in data["mcpServers"], "unknown exa entry was removed"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_apply_is_idempotent(run_migrate, legacy_home):
    r1 = run_migrate("--apply")
    assert r1.returncode == 0, r1.stderr
    snap1 = _snapshot_tree(legacy_home)
    r2 = run_migrate("--apply")
    assert r2.returncode == 0, r2.stderr
    snap2 = _snapshot_tree(legacy_home)
    assert snap1 == snap2, "second --apply changed the filesystem"


# ---------------------------------------------------------------------------
# No persistent key-bearing backups
# ---------------------------------------------------------------------------


def test_apply_creates_no_key_bearing_backup(run_migrate, legacy_home):
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    # No .bak files should contain the key.
    for path in legacy_home.rglob("*.bak"):
        assert EXA_KEY not in path.read_text(errors="ignore"), f"key in backup: {path}"
