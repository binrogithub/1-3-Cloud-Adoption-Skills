"""Red-green regression tests for the real ``tests/claude_e2e_probe.sh``.

These tests exercise the *tracked* probe directly (never a stub) by placing a
fake ``claude`` binary on PATH that produces a controlled JSON response and
optionally creates the tool-round-trip marker.  This proves the probe's data
channel and ``modelUsage`` validation, not merely verifier orchestration.

Contract under test (PRD_RELEASE_CLOSURE_V1 §FR-1, §FR-2, §FR-3, §G-RC1):

  * Claude JSON output reaches the Python validator (no stdin/heredoc clash).
  * ``modelUsage`` is parsed and the extracted model set must be exactly
    ``{glm-5.2}`` — raw substring matching is not accepted.
  * The tool marker must be created by the Claude tool call.
  * Empty / invalid JSON / missing modelUsage / mixed models / missing marker /
    non-zero Claude exit all produce a non-zero probe exit and a stable error
    code.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "claude_e2e_probe.sh"

MODEL = "glm-5.2"
BASE_URL = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
TOKEN = "test-maas-token-not-a-real-key"

# Stable error codes from PRD §7.
E_INVALID_JSON = "E2E_INVALID_JSON"
E_MODEL_USAGE_MISSING = "E2E_MODEL_USAGE_MISSING"
E_MODEL_MISMATCH = "E2E_MODEL_MISMATCH"
E_TOOL_MARKER_MISSING = "E2E_TOOL_MARKER_MISSING"

ALL_ERROR_CODES = {
    E_INVALID_JSON,
    E_MODEL_USAGE_MISSING,
    E_MODEL_MISMATCH,
    E_TOOL_MARKER_MISSING,
}


# ---------------------------------------------------------------------------
# Fake claude binary builder
# ---------------------------------------------------------------------------


def _write_fake_claude(
    bin_dir: Path,
    *,
    response_json: str | None,
    create_marker: bool,
    exit_code: int = 0,
) -> Path:
    """Install a fake ``claude`` on PATH.

    *response_json* is written to stdout (or nothing if ``None``).  When
    *create_marker* is true the fake binary extracts the marker path from the
    final prompt argument and touches it, simulating a real Bash tool call.
    """
    script = "#!/usr/bin/env bash\nset -euo pipefail\n"
    if create_marker:
        # The probe prompt is: Use the Bash tool to run: touch <MARKER_FILE>
        # Extract the path after "touch " from the last argument.
        script += (
            '_last="${!#}"\n'
            '_marker="${_last##*touch }"\n'
            'case "$_marker" in\n'
            '  */*) touch "$_marker" 2>/dev/null || true ;;\n'
            'esac\n'
        )
    if response_json is not None:
        # Use printf so no trailing newline issues; the probe reads via file.
        escaped = response_json.replace("\\", "\\\\").replace("'", "'\\''")
        script += f"printf '%s' '{escaped}'\n"
    script += f"exit {exit_code}\n"
    path = bin_dir / "claude"
    path.write_text(script)
    path.chmod(0o755)
    return path


def _run_probe(
    bin_dir: Path,
    tmp_path: Path,
    *,
    token: str = TOKEN,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the tracked probe with a controlled environment."""
    env: dict[str, str] = {
        "HOME": str(tmp_path),
        "PATH": str(bin_dir) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
        "ANTHROPIC_AUTH_TOKEN": token,
        "ANTHROPIC_BASE_URL": BASE_URL,
    }
    for name in ("LANG", "LC_ALL", "TERM"):
        if name in os.environ:
            env[name] = os.environ[name]
    # Never leak ANTHROPIC_API_KEY into the probe.
    env.pop("ANTHROPIC_API_KEY", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(PROBE)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _model_usage_json(models: set[str]) -> str:
    """Build a modelUsage JSON object containing exactly *models*."""
    usage = {m: {"inputTokens": 1, "outputTokens": 1} for m in models}
    return json.dumps({"modelUsage": usage})


# ---------------------------------------------------------------------------
# Positive case
# ---------------------------------------------------------------------------


def test_valid_json_and_tool_marker_pass(tmp_path):
    """Valid JSON with only glm-5.2 and a created marker must PASS."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=_model_usage_json({MODEL}),
        create_marker=True,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode == 0, (
        f"probe should PASS on valid input\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "model=glm-5.2 ok" in result.stdout
    assert "tool round trip ok" in result.stdout


# ---------------------------------------------------------------------------
# Negative matrix (PRD §G-RC1)
# ---------------------------------------------------------------------------


def test_empty_response_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(bin_dir, response_json="", create_marker=True)
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "empty response must FAIL"
    assert any(code in result.stderr for code in ALL_ERROR_CODES) or (
        "json" in result.stderr.lower()
    ), f"stderr should name a stable error code\nstderr: {result.stderr}"


def test_invalid_json_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir, response_json="not-json-at-all", create_marker=True
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "invalid JSON must FAIL"
    assert E_INVALID_JSON in result.stderr, (
        f"stderr should contain {E_INVALID_JSON}\nstderr: {result.stderr}"
    )


def test_missing_model_usage_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=json.dumps({"content": "ok but no modelUsage"}),
        create_marker=True,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "missing modelUsage must FAIL"
    assert E_MODEL_USAGE_MISSING in result.stderr, (
        f"stderr should contain {E_MODEL_USAGE_MISSING}\nstderr: {result.stderr}"
    )


def test_mixed_models_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=_model_usage_json({MODEL, "claude-sonnet-4"}),
        create_marker=True,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "mixed models must FAIL"
    assert E_MODEL_MISMATCH in result.stderr, (
        f"stderr should contain {E_MODEL_MISMATCH}\nstderr: {result.stderr}"
    )


def test_wrong_model_only_fails(tmp_path):
    """A response whose modelUsage contains only a non-glm-5.2 model must FAIL.

    This guards against substring matching: 'glm-5.2' does not appear anywhere,
    so a substring fallback would also fail — but the strict set check must be
    the real gate.
    """
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=_model_usage_json({"claude-sonnet-4"}),
        create_marker=True,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "wrong model must FAIL"
    assert E_MODEL_MISMATCH in result.stderr, (
        f"stderr should contain {E_MODEL_MISMATCH}\nstderr: {result.stderr}"
    )


def test_substring_match_not_accepted(tmp_path):
    """A response that contains the string 'glm-5.2' only inside a text field
    (not in modelUsage) must FAIL — substring matching is forbidden."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=json.dumps(
            {
                "content": [{"type": "text", "text": "I am glm-5.2"}],
                "modelUsage": {"claude-sonnet-4": {"inputTokens": 1}},
            }
        ),
        create_marker=True,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "substring match must not be accepted"
    assert E_MODEL_MISMATCH in result.stderr


def test_missing_marker_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=_model_usage_json({MODEL}),
        create_marker=False,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "missing marker must FAIL"
    assert E_TOOL_MARKER_MISSING in result.stderr, (
        f"stderr should contain {E_TOOL_MARKER_MISSING}\nstderr: {result.stderr}"
    )


def test_nonzero_claude_exit_fails(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir,
        response_json=_model_usage_json({MODEL}),
        create_marker=True,
        exit_code=2,
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode != 0, "non-zero Claude exit must FAIL"


# ---------------------------------------------------------------------------
# Security: response body never leaks to stdout
# ---------------------------------------------------------------------------


def test_response_body_not_printed_to_stdout(tmp_path):
    """The response JSON must never appear in the probe's stdout/stderr."""
    secret_body = _model_usage_json({MODEL})
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_fake_claude(
        bin_dir, response_json=secret_body, create_marker=True
    )
    result = _run_probe(bin_dir, tmp_path)
    assert result.returncode == 0
    # The modelUsage payload must not be echoed.
    assert "inputTokens" not in result.stdout
    assert "inputTokens" not in result.stderr


# ---------------------------------------------------------------------------
# Probe is the tracked script, not a stub
# ---------------------------------------------------------------------------


def test_probe_is_tracked_and_executable():
    """The test must run the real tracked probe, not a PATH stub."""
    assert PROBE.is_file(), "tests/claude_e2e_probe.sh must exist"
    assert PROBE.stat().st_mode & stat.S_IXUSR, "probe must be executable"
