"""Tests for scripts/configure-exa.sh — isolated Exa MCP installer.

Contract (PRD §5, §6, §12.1, G-EXA1, G-EXA2, G-EXA6):
  * Reads the Exa key from stdin (never argv), writes it to
    ~/.config/claude-maas/exa-api-key as a 0600 regular file.
  * Merges mcpServers.exa-search (http, exact URL, headersHelper) into
    ~/.claude-maas/.claude.json additively — preserves other top-level fields
    and other MCP servers.
  * Adds exactly two permissions to ~/.claude-maas/settings.json additively.
  * The key never appears in stdout, stderr, or any JSON file.
  * Idempotent: re-running updates only the key file; JSON stays byte-stable.
  * Does not touch the MaaS config (~/.config/claude-maas/config.json).
  * Atomic writes (no leftover temp files).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "configure-exa.sh"

EXA_URL = "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
KEY_VALUE = "test-exa-key-abc123"
PERM_SEARCH = "mcp__exa-search__web_search_exa"
PERM_FETCH = "mcp__exa-search__web_fetch_exa"


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def run_setup(tmp_path: Path):
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(tmp_path)

    def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SETUP), *args],
            env=base_env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return _run


# ---------------------------------------------------------------------------
# Key storage
# ---------------------------------------------------------------------------


def test_setup_writes_key_file_0600(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    key = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    assert key.read_text() == KEY_VALUE + "\n"
    assert key.stat().st_mode & 0o777 == 0o600


def test_setup_config_dir_is_0700(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    d = tmp_path / ".config" / "claude-maas"
    assert d.is_dir()
    assert d.stat().st_mode & 0o777 == 0o700


def test_setup_rejects_empty_key(run_setup):
    assert run_setup(stdin="\n").returncode != 0


def test_setup_rejects_multiline_key(run_setup):
    assert run_setup(stdin="one\ntwo\n").returncode != 0


def test_setup_rejects_no_stdin(run_setup):
    assert run_setup(stdin="").returncode != 0


def test_key_never_in_output(run_setup):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert KEY_VALUE not in result.stdout + result.stderr


def test_key_never_in_output_on_failure(run_setup):
    result = run_setup(stdin="\n")
    assert result.returncode != 0
    # No key was provided, but assert no leakage pattern regardless.
    assert "exa-api-key" not in result.stderr or "ERR" in result.stderr


# ---------------------------------------------------------------------------
# Isolated MCP definition in ~/.claude-maas/.claude.json
# ---------------------------------------------------------------------------


def test_setup_merges_exa_mcp_entry(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    cfg = json.loads((tmp_path / ".claude-maas" / ".claude.json").read_text())
    entry = cfg["mcpServers"]["exa-search"]
    assert entry["type"] == "http"
    assert entry["url"] == EXA_URL
    assert "headersHelper" in entry
    # The helper path must be absolute.
    assert entry["headersHelper"].startswith("/")


def test_setup_mcp_json_does_not_contain_key(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = (tmp_path / ".claude-maas" / ".claude.json").read_text()
    assert KEY_VALUE not in content


def test_setup_preserves_existing_mcp_servers(run_setup, tmp_path):
    # Pre-existing MCP server must survive.
    cfg_dir = tmp_path / ".claude-maas"
    cfg_dir.mkdir(parents=True)
    existing = {"mcpServers": {"other-mcp": {"command": "node", "args": ["x.js"]}}}
    (cfg_dir / ".claude.json").write_text(json.dumps(existing, indent=2))
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    cfg = json.loads((cfg_dir / ".claude.json").read_text())
    assert "other-mcp" in cfg["mcpServers"]
    assert "exa-search" in cfg["mcpServers"]


def test_setup_preserves_other_top_level_fields(run_setup, tmp_path):
    cfg_dir = tmp_path / ".claude-maas"
    cfg_dir.mkdir(parents=True)
    existing = {"theme": "dark", "mcpServers": {}}
    (cfg_dir / ".claude.json").write_text(json.dumps(existing, indent=2))
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    cfg = json.loads((cfg_dir / ".claude.json").read_text())
    assert cfg["theme"] == "dark"


# ---------------------------------------------------------------------------
# Tool permissions in ~/.claude-maas/settings.json
# ---------------------------------------------------------------------------


def test_setup_adds_exact_two_permissions(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    settings = json.loads((tmp_path / ".claude-maas" / "settings.json").read_text())
    allow = settings["permissions"]["allow"]
    assert PERM_SEARCH in allow
    assert PERM_FETCH in allow
    # No wildcard, no advanced/agent/deprecated tools.
    for entry in allow:
        assert "*" not in entry or entry in (PERM_SEARCH, PERM_FETCH)


def test_setup_settings_does_not_contain_key(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = (tmp_path / ".claude-maas" / "settings.json").read_text()
    assert KEY_VALUE not in content


def test_setup_preserves_existing_permissions(run_setup, tmp_path):
    cfg_dir = tmp_path / ".claude-maas"
    cfg_dir.mkdir(parents=True)
    existing = {"permissions": {"allow": ["Bash(ls:*)"]}, "theme": "dark"}
    (cfg_dir / "settings.json").write_text(json.dumps(existing, indent=2))
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    settings = json.loads((cfg_dir / "settings.json").read_text())
    allow = settings["permissions"]["allow"]
    assert "Bash(ls:*)" in allow
    assert PERM_SEARCH in allow
    assert PERM_FETCH in allow
    assert settings["theme"] == "dark"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_setup_is_idempotent(run_setup, tmp_path):
    r1 = run_setup(stdin="key-one\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    key = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    assert key.read_text() == "key-one\n"

    r2 = run_setup(stdin="key-two\n")
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    assert key.read_text() == "key-two\n"
    assert key.stat().st_mode & 0o777 == 0o600


def test_setup_rerun_preserves_mcp_json_bytes(run_setup, tmp_path):
    """Re-running must not change the MCP JSON (only the key file changes)."""
    r1 = run_setup(stdin="key-one\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    cfg_file = tmp_path / ".claude-maas" / ".claude.json"
    settings_file = tmp_path / ".claude-maas" / "settings.json"
    cfg_before = cfg_file.read_bytes()
    settings_before = settings_file.read_bytes()

    r2 = run_setup(stdin="key-two\n")
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    assert cfg_file.read_bytes() == cfg_before, "MCP JSON changed on re-run"
    assert settings_file.read_bytes() == settings_before, "settings changed on re-run"


# ---------------------------------------------------------------------------
# Does not touch MaaS config
# ---------------------------------------------------------------------------


def test_setup_does_not_touch_maas_config(run_setup, tmp_path):
    config_dir = tmp_path / ".config" / "claude-maas"
    config_dir.mkdir(parents=True)
    maas_cfg = {"anthropic_base_url": "https://maas.example.com/anthropic", "model": "glm-5.2"}
    (config_dir / "config.json").write_text(json.dumps(maas_cfg, indent=2))
    (config_dir / "api-key").write_text("maas-key\n")
    (config_dir / "api-key").chmod(0o600)
    before = (config_dir / "config.json").read_bytes()
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (config_dir / "config.json").read_bytes() == before
    assert (config_dir / "api-key").read_text() == "maas-key\n"


# ---------------------------------------------------------------------------
# No leftover temp files
# ---------------------------------------------------------------------------


def test_setup_no_temp_files_left(run_setup, tmp_path):
    result = run_setup(stdin=KEY_VALUE + "\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config_dir = tmp_path / ".config" / "claude-maas"
    for child in config_dir.iterdir():
        assert not child.name.startswith("tmp"), f"leftover temp: {child.name}"
