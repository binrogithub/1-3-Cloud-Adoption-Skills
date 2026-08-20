"""Tests for scripts/exa-headers-helper.py — the fail-closed Exa MCP auth helper.

Contract (PRD §7, G-EXA1, G-EXA5):
  * Validates CLAUDE_CODE_MCP_SERVER_NAME == "exa-search".
  * Validates CLAUDE_CODE_MCP_URL scheme HTTPS, host mcp.exa.ai, path /mcp.
  * Validates the key file is a regular file, non-symlink, owned by current
    user, mode exactly 0600, single non-empty line.
  * On success, stdout is exactly one JSON object {"x-api-key": "<value>"}.
  * On any failure, exits non-zero, prints a stable error code to stderr, and
    NEVER prints the key value to stdout or stderr.
  * Performs no network access and no file writes.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "exa-headers-helper.py"

EXA_URL = "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
KEY_VALUE = "test-exa-key-abc123"


# ---------------------------------------------------------------------------
# Fixture: run_helper
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_helper(tmp_path: Path):
    """Return a callable that runs the helper with HOME=tmp_path."""
    base_env = dict(os.environ)
    base_env["HOME"] = str(tmp_path)

    def _run(
        *,
        server: str = "exa-search",
        url: str = EXA_URL,
        env_override: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        env = dict(base_env)
        env["CLAUDE_CODE_MCP_SERVER_NAME"] = server
        env["CLAUDE_CODE_MCP_SERVER_URL"] = url
        if env_override:
            env.update(env_override)
        return subprocess.run(
            [sys_exec(), str(HELPER)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    return _run


def sys_exec() -> str:
    return os.environ.get("PYTHON", "python3")


@pytest.fixture()
def key_file(tmp_path: Path):
    """Create a valid 0600 key file and return its path."""
    kf = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    kf.parent.mkdir(parents=True)
    kf.write_text(KEY_VALUE + "\n")
    kf.chmod(0o600)
    return kf


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_key_emits_only_x_api_key(run_helper, key_file):
    result = run_helper()
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert json.loads(result.stdout) == {"x-api-key": KEY_VALUE}
    assert result.stderr == ""


def test_valid_key_stdout_is_single_json_object(run_helper, key_file):
    result = run_helper()
    assert result.returncode == 0
    # Exactly one line of JSON on stdout.
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert set(parsed.keys()) == {"x-api-key"}


# ---------------------------------------------------------------------------
# Key file failures (G-EXA5 failure matrix)
# ---------------------------------------------------------------------------


def test_missing_key_file_fails_closed(run_helper, tmp_path):
    # No key file created.
    result = run_helper()
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_empty_key_file_fails_closed(run_helper, tmp_path):
    kf = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    kf.parent.mkdir(parents=True)
    kf.write_text("\n")
    kf.chmod(0o600)
    result = run_helper()
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_multiline_key_fails_closed(run_helper, tmp_path):
    kf = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    kf.parent.mkdir(parents=True)
    kf.write_text("line-one\nline-two\n")
    kf.chmod(0o600)
    result = run_helper()
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "line-one" not in combined
    assert "line-two" not in combined


def test_symlink_key_file_fails_closed(run_helper, tmp_path):
    kf_dir = tmp_path / ".config" / "claude-maas"
    kf_dir.mkdir(parents=True)
    target = kf_dir / "real-key"
    target.write_text(KEY_VALUE + "\n")
    target.chmod(0o600)
    link = kf_dir / "exa-api-key"
    link.symlink_to(target)
    result = run_helper()
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_key_file_mode_0644_fails_closed(run_helper, tmp_path):
    kf = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    kf.parent.mkdir(parents=True)
    kf.write_text(KEY_VALUE + "\n")
    kf.chmod(0o644)
    result = run_helper()
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_key_file_is_directory_fails_closed(run_helper, tmp_path):
    kf_dir = tmp_path / ".config" / "claude-maas"
    kf_dir.mkdir(parents=True)
    (kf_dir / "exa-api-key").mkdir()
    result = run_helper()
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Server / URL failures
# ---------------------------------------------------------------------------


def test_wrong_server_name_fails_closed(run_helper, key_file):
    result = run_helper(server="not-exa")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_http_url_fails_closed(run_helper, key_file):
    result = run_helper(url="http://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_wrong_host_fails_closed(run_helper, key_file):
    result = run_helper(url="https://evil.example.com/mcp?tools=web_search_exa,web_fetch_exa")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_wrong_path_fails_closed(run_helper, key_file):
    result = run_helper(url="https://mcp.exa.ai/other?tools=web_search_exa,web_fetch_exa")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_unexpected_tool_query_fails_closed(run_helper, key_file):
    # A tool query that includes a prohibited tool must be rejected.
    result = run_helper(
        url="https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,exa_contents"
    )
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


def test_missing_url_env_fails_closed(run_helper, key_file):
    result = run_helper(url="")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Key never leaks on any failure path
# ---------------------------------------------------------------------------


def test_key_never_in_output_on_any_failure(run_helper, tmp_path):
    """Even when the key file exists but the server is wrong, no key leaks."""
    kf = tmp_path / ".config" / "claude-maas" / "exa-api-key"
    kf.parent.mkdir(parents=True)
    kf.write_text(KEY_VALUE + "\n")
    kf.chmod(0o600)
    result = run_helper(server="wrong")
    assert result.returncode != 0
    assert KEY_VALUE not in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# No file writes / no network (the helper must not create or modify files)
# ---------------------------------------------------------------------------


def test_helper_does_not_write_files(run_helper, key_file, tmp_path):
    snapshot_before = {str(p): p.stat().st_mtime_ns for p in tmp_path.rglob("*")}
    result = run_helper()
    assert result.returncode == 0
    snapshot_after = {str(p): p.stat().st_mtime_ns for p in tmp_path.rglob("*")}
    # No new files created.
    assert set(snapshot_after) == set(snapshot_before)
