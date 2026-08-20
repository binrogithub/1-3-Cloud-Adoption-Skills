"""Tests for scripts/uninstall-exa.sh — isolated Exa uninstall lifecycle.

Contract (PRD §12.3, G-EXA6):
  * Default removes only the owned isolated MCP entry + two permissions from
    ~/.claude-maas/, and RETAINS the key file.
  * --purge additionally deletes ~/.config/claude-maas/exa-api-key.
  * Idempotent: running twice is a no-op.
  * Does not modify plain Claude, MaaS config, or unrelated MCP/state.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNINSTALL = ROOT / "scripts" / "uninstall-exa.sh"

KEY_VALUE = "test-exa-key"
PERM_SEARCH = "mcp__exa-search__web_search_exa"
PERM_FETCH = "mcp__exa-search__web_fetch_exa"


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def installed_home(tmp_path: Path):
    """A fake HOME with the isolated Exa config installed + unrelated state."""
    home = tmp_path

    # Key file.
    key_dir = home / ".config" / "claude-maas"
    key_dir.mkdir(parents=True)
    (key_dir / "exa-api-key").write_text(KEY_VALUE + "\n")
    (key_dir / "exa-api-key").chmod(0o600)
    # MaaS config (must be preserved).
    (key_dir / "config.json").write_text(json.dumps({"model": "glm-5.2"}))
    (key_dir / "api-key").write_text("maas-key\n")

    # Isolated claude-maas profile.
    cm_dir = home / ".claude-maas"
    cm_dir.mkdir(parents=True)
    claude_json = {
        "mcpServers": {
            "exa-search": {
                "type": "http",
                "url": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa",
                "headersHelper": "/abs/scripts/exa-headers-helper.py",
            },
            "other-mcp": {"command": "node", "args": ["x.js"]},
        }
    }
    (cm_dir / ".claude.json").write_text(json.dumps(claude_json, indent=2))
    settings = {
        "permissions": {"allow": ["Bash(ls:*)", PERM_SEARCH, PERM_FETCH]},
        "theme": "dark",
    }
    (cm_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # Plain Claude (must be untouched).
    plain = home / ".claude"
    plain.mkdir(parents=True)
    (plain / "settings.json").write_text(json.dumps({"theme": "light"}))

    return home


@pytest.fixture()
def run_uninstall(installed_home: Path):
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(installed_home)

    def _run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(UNINSTALL), *args],
            env=base_env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    return _run


# ---------------------------------------------------------------------------
# Default uninstall: removes MCP + perms, retains key
# ---------------------------------------------------------------------------


def test_default_removes_exa_mcp(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    data = json.loads((installed_home / ".claude-maas" / ".claude.json").read_text())
    assert "exa-search" not in data.get("mcpServers", {})


def test_default_removes_exa_permissions(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    settings = json.loads((installed_home / ".claude-maas" / "settings.json").read_text())
    allow = settings.get("permissions", {}).get("allow", [])
    assert PERM_SEARCH not in allow
    assert PERM_FETCH not in allow


def test_default_retains_key(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    key = installed_home / ".config" / "claude-maas" / "exa-api-key"
    assert key.exists()
    assert key.read_text() == KEY_VALUE + "\n"


def test_default_preserves_unrelated_mcp(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    data = json.loads((installed_home / ".claude-maas" / ".claude.json").read_text())
    assert "other-mcp" in data["mcpServers"]


def test_default_preserves_unrelated_permissions(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    settings = json.loads((installed_home / ".claude-maas" / "settings.json").read_text())
    assert "Bash(ls:*)" in settings["permissions"]["allow"]
    assert settings["theme"] == "dark"


def test_default_preserves_maas_config(run_uninstall, installed_home):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    cfg = installed_home / ".config" / "claude-maas" / "config.json"
    assert json.loads(cfg.read_text())["model"] == "glm-5.2"
    assert (installed_home / ".config" / "claude-maas" / "api-key").read_text() == "maas-key\n"


def test_default_does_not_touch_plain_claude(run_uninstall, installed_home):
    before = (installed_home / ".claude" / "settings.json").read_bytes()
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    after = (installed_home / ".claude" / "settings.json").read_bytes()
    assert before == after


# ---------------------------------------------------------------------------
# --purge also deletes the key
# ---------------------------------------------------------------------------


def test_purge_deletes_key(run_uninstall, installed_home):
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    key = installed_home / ".config" / "claude-maas" / "exa-api-key"
    assert not key.exists()


def test_pge_preserves_maas_config(run_uninstall, installed_home):
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    # MaaS config and key must survive purge.
    assert (installed_home / ".config" / "claude-maas" / "config.json").exists()
    assert (installed_home / ".config" / "claude-maas" / "api-key").read_text() == "maas-key\n"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_default_is_idempotent(run_uninstall, installed_home):
    r1 = run_uninstall()
    assert r1.returncode == 0, r1.stderr
    data1 = (installed_home / ".claude-maas" / ".claude.json").read_bytes()
    r2 = run_uninstall()
    assert r2.returncode == 0, r2.stderr
    data2 = (installed_home / ".claude-maas" / ".claude.json").read_bytes()
    assert data1 == data2


def test_purge_is_idempotent(run_uninstall, installed_home):
    r1 = run_uninstall("--purge")
    assert r1.returncode == 0, r1.stderr
    r2 = run_uninstall("--purge")
    assert r2.returncode == 0, r2.stderr


# ---------------------------------------------------------------------------
# Key never leaks
# ---------------------------------------------------------------------------


def test_key_never_in_output(run_uninstall):
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    assert KEY_VALUE not in result.stdout + result.stderr
