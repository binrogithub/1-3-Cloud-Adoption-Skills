"""Tests for the claude-maas-setup.sh credential installer.

These tests verify the installer contract from the PRD:

  * The MaaS key is read from stdin (never argv) and stored as data with 0600.
  * config.json is written with 0600 and the expected fields.
  * Empty or multiline keys are rejected.
  * Shell profiles and ~/.claude/ are never touched.
  * The key never appears in stdout/stderr.
  * Re-running updates the key atomically (idempotency).
  * --base-url, --model, --context-tokens, --max-output-tokens are honored.
  * The default base URL ends in /anthropic, NOT /anthropic/v1.
  * URL credentials, fragments, query strings, and non-HTTPS (except
    localhost/127.0.0.1) are rejected.
  * A manifest.json is written recording intended launcher paths.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "client" / "claude-maas-setup.sh"

DEFAULT_BASE_URL = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
DEFAULT_MODEL = "glm-5.2"
DEFAULT_CONTEXT_TOKENS = 1000000
DEFAULT_MAX_OUTPUT_TOKENS = 32768
KEY_VALUE = "test-secret-key"


# ---------------------------------------------------------------------------
# Fixture: run_setup
# ---------------------------------------------------------------------------


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env with all ANTHROPIC_* keys removed."""
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def run_setup(tmp_path: Path):
    """Return a callable that runs claude-maas-setup.sh with HOME=tmp_path.

    The environment is stripped of all ANTHROPIC_* variables to prove the
    installer does not rely on inherited provider config.
    """
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(tmp_path)
    # Ensure no leftover provider config leaks in.
    for var in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
        base_env.pop(var, None)

    def _run(
        *args: str,
        stdin: str | None = None,
        env_override: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        env = dict(base_env)
        if env_override:
            env.update(env_override)
        result = subprocess.run(
            ["bash", str(SETUP), *args],
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result

    return _run


# ---------------------------------------------------------------------------
# Helper: snapshot files under a fake HOME that must remain untouched
# ---------------------------------------------------------------------------


def _snapshot_home(home: Path) -> dict[str, tuple[int, bytes]]:
    """Snapshot shell profiles and .claude* paths for later comparison."""
    paths: list[Path] = []
    # Shell profiles.
    for name in (
        ".bashrc",
        ".bash_profile",
        ".profile",
        ".zshrc",
        ".zprofile",
    ):
        paths.append(home / name)
    # Anything matching .claude* at top level.
    if home.exists():
        for child in home.iterdir():
            if child.name.startswith(".claude"):
                paths.append(child)
    snap: dict[str, tuple[int, bytes]] = {}
    for p in paths:
        if p.exists() and p.is_file():
            snap[str(p)] = (p.stat().st_mode & 0o777, p.read_bytes())
        elif p.exists() and p.is_dir():
            # Record directory existence and mode.
            snap[str(p)] = (p.stat().st_mode & 0o777, b"__DIR__")
    return snap


def _assert_home_unchanged(home: Path, before: dict[str, tuple[int, bytes]]) -> None:
    after = _snapshot_home(home)
    # No new shell-profile or .claude* entries should appear.
    new_keys = set(after) - set(before)
    assert new_keys == set(), f"installer created/modified forbidden paths: {new_keys}"
    # Existing entries must be byte-identical with the same mode.
    for path_str, (mode, content) in before.items():
        assert path_str in after, f"installer removed path: {path_str}"
        after_mode, after_content = after[path_str]
        assert after_mode == mode, f"mode changed for {path_str}: {oct(mode)} -> {oct(after_mode)}"
        assert after_content == content, f"content changed for {path_str}"


# ---------------------------------------------------------------------------
# Key storage and permissions
# ---------------------------------------------------------------------------


def test_setup_stores_key_as_data_with_strict_permissions(run_setup, tmp_path):
    result = run_setup(stdin="test-secret-key\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    key = tmp_path / ".config" / "claude-maas" / "api-key"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    assert key.read_text() == "test-secret-key\n"
    assert key.stat().st_mode & 0o777 == 0o600
    assert config.stat().st_mode & 0o777 == 0o600
    assert "test-secret-key" not in result.stdout + result.stderr


def test_setup_config_dir_is_0700(run_setup, tmp_path):
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config_dir = tmp_path / ".config" / "claude-maas"
    assert config_dir.is_dir()
    assert config_dir.stat().st_mode & 0o777 == 0o700


def test_setup_config_json_has_expected_fields(run_setup, tmp_path):
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["anthropic_base_url"] == DEFAULT_BASE_URL
    assert data["model"] == DEFAULT_MODEL
    assert data["context_tokens"] == DEFAULT_CONTEXT_TOKENS
    assert data["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


# ---------------------------------------------------------------------------
# Empty / multiline key rejection
# ---------------------------------------------------------------------------


def test_setup_rejects_empty_or_multiline_key(run_setup):
    assert run_setup(stdin="\n").returncode != 0
    assert run_setup(stdin="one\ntwo\n").returncode != 0


def test_setup_rejects_whitespace_only_key(run_setup):
    assert run_setup(stdin="   \n").returncode != 0
    assert run_setup(stdin="\t\n").returncode != 0


def test_setup_rejects_no_stdin(run_setup):
    """No key on stdin at all should fail, not hang."""
    result = run_setup(stdin="")
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Shell profiles and ~/.claude/ untouched
# ---------------------------------------------------------------------------


def test_setup_does_not_touch_shell_profiles(run_setup, tmp_path):
    # Pre-create shell profiles with known content.
    for name in (".bashrc", ".bash_profile", ".profile", ".zshrc", ".zprofile"):
        p = tmp_path / name
        p.write_text(f"# original {name}\n")
        p.chmod(0o644)
    before = _snapshot_home(tmp_path)
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    _assert_home_unchanged(tmp_path, before)


def test_setup_does_not_touch_dot_claude(run_setup, tmp_path):
    # Pre-create ~/.claude with some content.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "projects").mkdir()
    (claude_dir / "projects" / "test.json").write_text('{}\n')
    before = _snapshot_home(tmp_path)
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    _assert_home_unchanged(tmp_path, before)
    # ~/.claude should still exist and be untouched.
    assert (claude_dir / "projects" / "test.json").read_text() == '{}\n'


def test_setup_does_not_create_dot_claude(run_setup, tmp_path):
    """The installer must not create ~/.claude if it did not exist."""
    assert not (tmp_path / ".claude").exists()
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not (tmp_path / ".claude").exists()


# ---------------------------------------------------------------------------
# Key never leaks to stdout/stderr
# ---------------------------------------------------------------------------


def test_key_never_in_stdout_or_stderr(run_setup):
    result = run_setup(stdin="super-secret-xyz123\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    combined = result.stdout + result.stderr
    assert "super-secret-xyz123" not in combined


def test_key_never_in_stdout_on_failure(run_setup):
    """Even on failure, the key must not be echoed."""
    result = run_setup("--base-url", "ftp://bad.example.com/anthropic", stdin="super-secret-xyz123\n")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "super-secret-xyz123" not in combined


# ---------------------------------------------------------------------------
# Idempotency / atomic re-run
# ---------------------------------------------------------------------------


def test_setup_is_idempotent(run_setup, tmp_path):
    r1 = run_setup(stdin="key-one\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    key = tmp_path / ".config" / "claude-maas" / "api-key"
    assert key.read_text() == "key-one\n"

    r2 = run_setup(stdin="key-two\n")
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    assert key.read_text() == "key-two\n"
    assert key.stat().st_mode & 0o777 == 0o600


def test_setup_rerun_preserves_config(run_setup, tmp_path):
    r1 = run_setup("--model", "custom-model", stdin="key-one\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data1 = json.loads(config.read_text())
    assert data1["model"] == "custom-model"

    r2 = run_setup(stdin="key-two\n")
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    data2 = json.loads(config.read_text())
    # Re-running without --model should reset to default.
    assert data2["model"] == DEFAULT_MODEL


def test_setup_no_temp_files_left_behind(run_setup, tmp_path):
    """Atomic write should not leave temp files in the config dir."""
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config_dir = tmp_path / ".config" / "claude-maas"
    children = sorted(child.name for child in config_dir.iterdir())
    # Only api-key, config.json, and manifest.json should exist.
    assert "api-key" in children
    assert "config.json" in children
    # No tmp files.
    for name in children:
        assert not name.startswith("tmp"), f"leftover temp file: {name}"


# ---------------------------------------------------------------------------
# Flag handling
# ---------------------------------------------------------------------------


def test_setup_base_url_flag(run_setup, tmp_path):
    url = "https://maas.example.com/anthropic"
    result = run_setup("--base-url", url, stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["anthropic_base_url"] == url


def test_setup_model_flag(run_setup, tmp_path):
    result = run_setup("--model", "custom-glm", stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["model"] == "custom-glm"


def test_setup_context_tokens_flag(run_setup, tmp_path):
    result = run_setup("--context-tokens", "100000", stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["context_tokens"] == 100000


def test_setup_max_output_tokens_flag(run_setup, tmp_path):
    result = run_setup("--max-output-tokens", "8192", stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["max_output_tokens"] == 8192


def test_setup_all_flags_combined(run_setup, tmp_path):
    result = run_setup(
        "--base-url", "https://maas.example.com/anthropic",
        "--model", "my-model",
        "--context-tokens", "50000",
        "--max-output-tokens", "4096",
        stdin="mykey\n",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["anthropic_base_url"] == "https://maas.example.com/anthropic"
    assert data["model"] == "my-model"
    assert data["context_tokens"] == 50000
    assert data["max_output_tokens"] == 4096


# ---------------------------------------------------------------------------
# Default base URL ends in /anthropic not /anthropic/v1
# ---------------------------------------------------------------------------


def test_default_base_url_ends_in_anthropic_not_v1(run_setup, tmp_path):
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    url = data["anthropic_base_url"]
    assert url.endswith("/anthropic")
    assert not url.endswith("/anthropic/v1")
    assert not url.endswith("/v1")


# ---------------------------------------------------------------------------
# URL validation: reject credentials, fragments, query strings, non-HTTPS
# ---------------------------------------------------------------------------


def test_setup_rejects_url_with_credentials(run_setup):
    result = run_setup(
        "--base-url", "https://user:pass@maas.example.com/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode != 0


def test_setup_rejects_url_with_fragment(run_setup):
    result = run_setup(
        "--base-url", "https://maas.example.com/anthropic#frag",
        stdin="mykey\n",
    )
    assert result.returncode != 0


def test_setup_rejects_url_with_query_string(run_setup):
    result = run_setup(
        "--base-url", "https://maas.example.com/anthropic?foo=bar",
        stdin="mykey\n",
    )
    assert result.returncode != 0


def test_setup_rejects_http_non_localhost(run_setup):
    result = run_setup(
        "--base-url", "http://maas.example.com/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode != 0


def test_setup_rejects_ftp(run_setup):
    result = run_setup(
        "--base-url", "ftp://maas.example.com/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode != 0


def test_setup_allows_localhost_http(run_setup, tmp_path):
    """Non-HTTPS is allowed when the host is localhost."""
    result = run_setup(
        "--base-url", "http://localhost:8080/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["anthropic_base_url"] == "http://localhost:8080/anthropic"


def test_setup_allows_127_0_0_1_http(run_setup, tmp_path):
    """Non-HTTPS is allowed when the host is 127.0.0.1."""
    result = run_setup(
        "--base-url", "http://127.0.0.1:9000/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert data["anthropic_base_url"] == "http://127.0.0.1:9000/anthropic"


def test_setup_rejects_http_with_non_localhost_host(run_setup):
    """HTTP with a non-localhost host must be rejected even if it looks internal."""
    result = run_setup(
        "--base-url", "http://10.0.0.1/anthropic",
        stdin="mykey\n",
    )
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_setup_writes_manifest(run_setup, tmp_path):
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    manifest = tmp_path / ".config" / "claude-maas" / "manifest.json"
    assert manifest.is_file()
    assert manifest.stat().st_mode & 0o777 == 0o600
    data = json.loads(manifest.read_text())
    # Manifest should record intended launcher paths.
    assert "launchers" in data or "paths" in data


def test_manifest_does_not_contain_key(run_setup, tmp_path):
    result = run_setup(stdin="super-secret-xyz123\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    manifest = tmp_path / ".config" / "claude-maas" / "manifest.json"
    content = manifest.read_text()
    assert "super-secret-xyz123" not in content


# ---------------------------------------------------------------------------
# Launcher installation into ~/.local/bin
# ---------------------------------------------------------------------------


def test_setup_creates_local_bin(run_setup, tmp_path):
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    local_bin = tmp_path / ".local" / "bin"
    # The installer should create ~/.local/bin (even if launchers are absent).
    assert local_bin.is_dir()


def test_setup_does_not_fail_when_launchers_absent(run_setup, tmp_path):
    """The installer must not fail if source launcher files do not exist yet."""
    # In this test environment, client/claude-maas and client/claude-select
    # may or may not exist. The installer must succeed regardless.
    result = run_setup(stdin="mykey\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# D1 write protection (PRD CLIENT_CONFIG_PROTECTION §2 D1)
# ---------------------------------------------------------------------------


def test_setup_refuses_port_mismatch_without_force(run_setup, tmp_path):
    """D1: If existing config points at a different port, refuse (exit 2)
    unless --force is passed. This is the gate that would have prevented
    the 2026-08-20 port-38123 incident."""
    # First install on port 3000.
    r1 = run_setup("--base-url", "http://127.0.0.1:3000", stdin="key1\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"

    # Re-install on port 38123 — must be refused.
    r2 = run_setup("--base-url", "http://127.0.0.1:38123", stdin="key2\n")
    assert r2.returncode == 2, \
        f"expected exit 2 (refused), got {r2.returncode}\nstderr: {r2.stderr}"
    assert "REFUSING" in r2.stderr

    # Original config must be untouched.
    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert "3000" in data["anthropic_base_url"], \
        f"config was clobbered: {data['anthropic_base_url']}"


def test_setup_force_overrides_port_mismatch(run_setup, tmp_path):
    """D1: --force overrides the write protection."""
    # First install on port 3000.
    r1 = run_setup("--base-url", "http://127.0.0.1:3000", stdin="key1\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"

    # Re-install on port 38123 with --force — should succeed.
    r2 = run_setup("--base-url", "http://127.0.0.1:38123", "--force", stdin="key2\n")
    assert r2.returncode == 0, \
        f"expected exit 0 with --force, got {r2.returncode}\nstderr: {r2.stderr}"

    config = tmp_path / ".config" / "claude-maas" / "config.json"
    data = json.loads(config.read_text())
    assert "38123" in data["anthropic_base_url"], \
        f"config not updated with --force: {data['anthropic_base_url']}"


def test_setup_same_port_not_refused(run_setup, tmp_path):
    """D1: Re-install with the same port must not be refused (idempotent)."""
    r1 = run_setup("--base-url", "http://127.0.0.1:3000", stdin="key1\n")
    assert r1.returncode == 0, f"stderr: {r1.stderr}"

    r2 = run_setup("--base-url", "http://127.0.0.1:3000", stdin="key2\n")
    assert r2.returncode == 0, \
        f"same-port re-install should succeed, got {r2.returncode}\nstderr: {r2.stderr}"
