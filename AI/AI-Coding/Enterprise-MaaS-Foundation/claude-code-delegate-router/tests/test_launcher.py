"""Tests for the claude-maas isolated launcher and claude-select selector.

These tests verify the child-process environment contract from the PRD:

  * Only the documented MaaS env vars are exported to the child.
  * ANTHROPIC_API_KEY, CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX are unset.
  * The api-key file is read as data, never sourced/eval'd as shell.
  * --version, doctor, and mcp subcommands do not receive an inserted --model.
  * Normal interactive/print invocations get --model glm-5.2 inserted.
  * The launcher fails clearly on a missing or too-wide key file.
  * The launcher locates the real claude without resolving to itself.
  * claude-select native/maas/status behave correctly and never leak the key.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "client"
LAUNCHER = CLIENT_DIR / "claude-maas"
SELECTOR = CLIENT_DIR / "claude-select"
FAKE_CLAUDE = ROOT / "tests" / "helpers" / "fake-claude-launcher"

MODEL = "glm-5.2"
BASE_URL = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
KEY_VALUE = "test-secret-key"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """A fake HOME with a valid 0600 api-key and 0600 config.json."""
    config_dir = tmp_path / ".config" / "claude-maas"
    config_dir.mkdir(parents=True)
    config_dir.chmod(0o700)

    key_file = config_dir / "api-key"
    key_file.write_text(f"{KEY_VALUE}\n")
    key_file.chmod(0o600)

    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "anthropic_base_url": BASE_URL,
                "model": MODEL,
                "context_tokens": 190000,
                "max_output_tokens": 32768,
            }
        )
        + "\n"
    )
    config_file.chmod(0o600)

    # Isolated CLAUDE_CONFIG_DIR (~/.claude-maas) — empty but present.
    (tmp_path / ".claude-maas").mkdir()
    (tmp_path / ".claude-maas").chmod(0o700)

    return tmp_path


@pytest.fixture()
def key_file(fake_home: Path) -> Path:
    return fake_home / ".config" / "claude-maas" / "api-key"


@pytest.fixture()
def config_file(fake_home: Path) -> Path:
    return fake_home / ".config" / "claude-maas" / "config.json"


@pytest.fixture()
def bin_dir(tmp_path: Path) -> Path:
    """A directory for symlinks/copies of launchers and the fake claude."""
    d = tmp_path / "bin"
    d.mkdir()
    return d


@pytest.fixture()
def parent_env(fake_home: Path, bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Environment for the *parent* launcher process.

    Crucially this contains NO ANTHROPIC_* vars (proving the wrapper does not
    rely on inherited provider config) and a PATH that exposes the fake claude
    plus the launchers under test.
    """
    env: dict[str, str] = {
        "HOME": str(fake_home),
        "PATH": str(bin_dir) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
    }
    # Copy through a minimal set of non-provider vars python/bash need.
    for name in ("LANG", "LC_ALL", "TERM"):
        if name in os.environ:
            env[name] = os.environ[name]

    # Deliberately do NOT set any ANTHROPIC_* or CLAUDE_CODE_USE_* vars.
    return env


@pytest.fixture()
def launch(fake_home: Path, bin_dir: Path, parent_env: dict[str, str]):
    """Return a callable that runs claude-maas with args and parses captured JSON.

    The fake claude is placed on PATH as ``claude``. The real launcher script
    is placed on PATH as ``claude-maas`` (and ``claude-select``).
    """
    # Put fake claude on PATH.
    fake_link = bin_dir / "claude"
    fake_link.symlink_to(FAKE_CLAUDE)

    # Put launchers on PATH.
    maas_link = bin_dir / "claude-maas"
    maas_link.symlink_to(LAUNCHER)
    select_link = bin_dir / "claude-select"
    select_link.symlink_to(SELECTOR)

    def _run(*args: str, env_override: dict[str, str] | None = None) -> dict:
        env = dict(parent_env)
        if env_override:
            env.update(env_override)
        result = subprocess.run(
            ["claude-maas", *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"claude-maas {args!r} exited {result.returncode}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return json.loads(result.stdout)

    return _run


@pytest.fixture()
def run_select(fake_home: Path, bin_dir: Path, parent_env: dict[str, str]):
    """Return a callable that runs claude-select with args and returns CompletedProcess."""
    fake_link = bin_dir / "claude"
    fake_link.symlink_to(FAKE_CLAUDE)

    maas_link = bin_dir / "claude-maas"
    maas_link.symlink_to(LAUNCHER)
    select_link = bin_dir / "claude-select"
    select_link.symlink_to(SELECTOR)

    def _run(*args: str, env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = dict(parent_env)
        if env_override:
            env.update(env_override)
        return subprocess.run(
            ["claude-select", *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return _run


# ---------------------------------------------------------------------------
# Environment injection
# ---------------------------------------------------------------------------


def test_launcher_injects_only_child_maas_environment(launch, parent_env):
    captured = launch("-p", "OK")
    env = captured["env"]
    assert env["ANTHROPIC_BASE_URL"].endswith("/anthropic")
    assert env["ANTHROPIC_AUTH_TOKEN"] == KEY_VALUE
    assert "ANTHROPIC_API_KEY" not in env
    assert env["ANTHROPIC_MODEL"] == MODEL
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == MODEL
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == MODEL
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == MODEL
    assert env["CLAUDE_CONFIG_DIR"].endswith("/.claude-maas")
    assert env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "190000"
    # Parent must not have had any ANTHROPIC_ vars to begin with.
    assert not any(name.startswith("ANTHROPIC_") for name in parent_env)


def test_launcher_unsets_bedrock_and_vertex(launch):
    captured = launch("-p", "OK")
    env = captured["env"]
    assert "CLAUDE_CODE_USE_BEDROCK" not in env
    assert "CLAUDE_CODE_USE_VERTEX" not in env


def test_launcher_does_not_inherit_bedrock_or_vertex(launch, parent_env):
    """Even if the parent has bedrock/vertex set, the child must not."""
    captured = launch(
        "-p",
        "OK",
        env_override={
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "CLAUDE_CODE_USE_VERTEX": "1",
        },
    )
    env = captured["env"]
    assert "CLAUDE_CODE_USE_BEDROCK" not in env
    assert "CLAUDE_CODE_USE_VERTEX" not in env


def test_launcher_base_url_has_no_trailing_v1(launch):
    captured = launch("-p", "OK")
    assert captured["env"]["ANTHROPIC_BASE_URL"] == BASE_URL
    assert not captured["env"]["ANTHROPIC_BASE_URL"].endswith("/v1")


# ---------------------------------------------------------------------------
# Key file safety
# ---------------------------------------------------------------------------


def test_launcher_does_not_source_key_file_as_shell(launch, key_file):
    key_file.write_text("$(touch /tmp/must-not-exist)\n")
    key_file.chmod(0o600)
    # If the wrapper sourced/eval'd the key file, /tmp/must-not-exist would
    # be created. The fake claude still runs (it ignores the bogus token).
    launch("--version")
    assert not Path("/tmp/must-not-exist").exists()


def test_launcher_reads_only_first_line_of_key(launch, key_file):
    key_file.write_text("real-key\nleftover-line\n")
    key_file.chmod(0o600)
    captured = launch("-p", "OK")
    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == "real-key"


def test_launcher_fails_on_missing_key_file(launch, key_file):
    key_file.unlink()
    with pytest.raises(AssertionError) as exc_info:
        launch("-p", "OK")
    assert "api-key" in str(exc_info.value).lower() or "key" in str(exc_info.value).lower()


def test_launcher_fails_on_world_readable_key_file(launch, key_file):
    key_file.chmod(0o644)  # too wide
    with pytest.raises(AssertionError):
        launch("-p", "OK")


def test_launcher_fails_on_group_readable_key_file(launch, key_file):
    key_file.chmod(0o640)  # group readable — too wide
    with pytest.raises(AssertionError):
        launch("-p", "OK")


def test_launcher_fails_on_missing_config_file(launch, config_file):
    config_file.unlink()
    with pytest.raises(AssertionError):
        launch("-p", "OK")


def test_launcher_fails_on_world_readable_config_dir(launch, fake_home):
    config_dir = fake_home / ".config" / "claude-maas"
    config_dir.chmod(0o755)  # too wide
    with pytest.raises(AssertionError):
        launch("-p", "OK")


# ---------------------------------------------------------------------------
# --model insertion semantics
# ---------------------------------------------------------------------------


def test_version_does_not_get_inserted_model(launch):
    captured = launch("--version")
    assert "--model" not in captured["argv"]
    assert "glm-5.2" not in captured["argv"]


def test_doctor_subcommand_does_not_get_inserted_model(launch):
    captured = launch("doctor")
    assert "--model" not in captured["argv"]


def test_mcp_subcommand_does_not_get_inserted_model(launch):
    captured = launch("mcp", "list")
    assert "--model" not in captured["argv"]
    assert captured["argv"] == ["mcp", "list"]


def test_print_invocation_gets_inserted_model(launch):
    captured = launch("-p", "do something")
    assert "--model" in captured["argv"]
    model_idx = captured["argv"].index("--model")
    assert captured["argv"][model_idx + 1] == MODEL


def test_interactive_invocation_gets_inserted_model(launch):
    # No subcommand args at all -> interactive mode -> model inserted.
    captured = launch()
    assert "--model" in captured["argv"]
    model_idx = captured["argv"].index("--model")
    assert captured["argv"][model_idx + 1] == MODEL


def test_model_flag_inserted_before_user_args(launch):
    """The wrapper should insert --model before any user-supplied args so the
    official CLI sees it as the active model override."""
    captured = launch("-p", "hello")
    argv = captured["argv"]
    model_idx = argv.index("--model")
    # --model should come before -p (the first user arg).
    assert model_idx == 0


# ---------------------------------------------------------------------------
# Self-resolution avoidance
# ---------------------------------------------------------------------------


def test_launcher_does_not_resolve_to_itself(launch):
    """The launcher must exec the real claude, not recursively exec itself.

    We verify this indirectly: the fake claude ran and produced JSON with the
    user's args present. If the launcher had exec'd itself, we would get
    infinite recursion or a second copy of the wrapper's env-setup output
    rather than clean JSON.
    """
    captured = launch("-p", "OK")
    # The user's -p and OK must be present in argv (alongside inserted --model).
    assert "-p" in captured["argv"]
    assert "OK" in captured["argv"]


def test_launcher_locates_claude_on_path(launch):
    captured = launch("-p", "OK")
    # The fake claude ran and captured env — proves it was found and exec'd.
    assert "ANTHROPIC_AUTH_TOKEN" in captured["env"]


# ---------------------------------------------------------------------------
# No service started / no HTTP listener
# ---------------------------------------------------------------------------


def test_launcher_starts_no_service(launch):
    """The launcher must exec claude and exit; it must not daemonize or listen."""
    captured = launch("-p", "OK")
    # The fake claude exited 0 and produced JSON — the launcher did exec, not
    # fork+exit leaving a background service.
    assert "env" in captured


# ---------------------------------------------------------------------------
# claude-select
# ---------------------------------------------------------------------------


def test_select_native_execs_claude(run_select):
    result = run_select("native", "-p", "OK")
    assert result.returncode == 0
    captured = json.loads(result.stdout)
    assert captured["argv"] == ["-p", "OK"]


def test_select_maas_execs_claude_maas(run_select):
    result = run_select("maas", "-p", "OK")
    assert result.returncode == 0
    captured = json.loads(result.stdout)
    # claude-maas inserts --model for normal invocations.
    assert "--model" in captured["argv"]
    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == KEY_VALUE


def test_select_status_prints_host_model_and_fingerprint(run_select):
    result = run_select("status")
    assert result.returncode == 0
    out = result.stdout
    # Must include the endpoint host.
    assert "modelarts-maas.com" in out
    # Must include the model.
    assert MODEL in out
    # Must include a fingerprint (hash-like, hex).
    assert "fingerprint" in out.lower() or "sha" in out.lower() or "key" in out.lower()


def test_select_status_does_not_leak_key(run_select):
    result = run_select("status")
    assert result.returncode == 0
    assert KEY_VALUE not in result.stdout
    assert KEY_VALUE not in result.stderr


def test_select_status_fingerprint_is_stable(run_select):
    r1 = run_select("status")
    r2 = run_select("status")
    assert r1.stdout == r2.stdout


def test_select_unknown_subcommand_fails(run_select):
    result = run_select("bogus")
    assert result.returncode != 0


def test_select_no_subcommand_fails(run_select):
    result = run_select()
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Secret never appears in argv
# ---------------------------------------------------------------------------


def test_key_never_appears_in_argv(launch):
    captured = launch("-p", "OK")
    for arg in captured["argv"]:
        assert KEY_VALUE not in arg


# ---------------------------------------------------------------------------
# resolve-binary diagnostic (PRD §FR-5)
# ---------------------------------------------------------------------------


def test_resolve_binary_prints_path_and_digest(fake_home, bin_dir, parent_env):
    """`claude-maas resolve-binary` must print the official CLI path and a
    SHA-256 digest, and must NOT print the API key."""
    (bin_dir / "claude").symlink_to(FAKE_CLAUDE)
    (bin_dir / "claude-maas").symlink_to(LAUNCHER)
    result = subprocess.run(
        ["claude-maas", "resolve-binary"],
        env=parent_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    parts = result.stdout.strip().split("\t")
    assert len(parts) == 2, f"expected path<TAB>digest, got: {result.stdout!r}"
    path_str, digest = parts
    assert path_str, "binary path must be non-empty"
    assert len(digest) == 64 or digest == "unknown", (
        f"digest must be sha256 hex or 'unknown', got: {digest!r}"
    )
    assert KEY_VALUE not in result.stdout
    assert KEY_VALUE not in result.stderr


def test_resolve_binary_does_not_load_key(fake_home, bin_dir, parent_env, key_file):
    """resolve-binary must succeed even if the key file is missing."""
    key_file.unlink()
    (bin_dir / "claude").symlink_to(FAKE_CLAUDE)
    (bin_dir / "claude-maas").symlink_to(LAUNCHER)
    result = subprocess.run(
        ["claude-maas", "resolve-binary"],
        env=parent_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"resolve-binary must not require the key file\nstderr: {result.stderr}"
    )
