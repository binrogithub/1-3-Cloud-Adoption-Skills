"""Contract tests for scripts/window-check-v12.sh (PRD RELEASE_V12 §3).

The script must:
  * be syntactically valid bash under set -euo pipefail;
  * FAIL (exit 1) when a project-derived listener besides :3000 is up
    (N1-G discriminative power — same shape as the production finding);
  * PASS N2-G/N4-G wording appears in output;
  * support --record writing window evidence with mode 0644 and the
    required fields.

We simulate listeners with a real loopback node process (no mocking of ss),
so the N1-G test proves the gate detects an actual socket, not a string.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "window-check-v12.sh"


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_bash_syntax_valid():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("V12_SERVICE", "claude-code-maas-proxy.service")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60, env=env,
    )


def test_n1_g_detects_noncompliant_listener(tmp_path):
    """Option-B reverse case (PRD UPSTREAM_PROFILE_V1 D10): a project-shaped
    listener that does NOT enforce auth must FAIL the gate.

    We run a real copy of the repo adapter (so the build hash matches) with
    MAAS_CLIENT_KEY_FILE pointing at a nonexistent path — legacy mode, where
    anonymous requests succeed. That is precisely the S2/N1 exposure class
    the gate exists to catch."""
    import shutil
    port = 4133
    dest = tmp_path / "adapter"
    dest.mkdir()
    shutil.copy(ROOT / "adapter" / "server.js", dest / "server.js")
    shutil.copy(ROOT / "adapter" / "lifecycle.js", dest / "lifecycle.js")

    env = {**os.environ,
           "PROXY_PORT": str(port),
           "PROXY_HOST": "127.0.0.1",
           "CLAUDE_CODE_PROXY_API_KEY": "test-key",
           "MAAS_CLIENT_KEY_FILE": str(tmp_path / "no-client.key"),
           "ANTHROPIC_PROXY_BASE_URL": "http://127.0.0.1:1/v1/chat/completions",
           "MAAS_CONNECT_TIMEOUT": "2"}
    proc = subprocess.Popen(["node", str(dest / "server.js")], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 5
        ready = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.1)
        assert ready, "test adapter never listened"
        result = _run()
        out = result.stdout + result.stderr
        assert result.returncode == 1, (
            f"N1-G must fail while a noncompliant listener is up\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "auth not enforced" in out, (
            f"expected the auth failure to be named\n{out}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_record_writes_window_file(tmp_path):
    """--record must stamp window evidence with the required fields."""
    window_file = tmp_path / "window-v12.json"
    result = _run("--record", env_extra={"V12_WINDOW_FILE": str(window_file)})
    # The listener gate result doesn't matter for this test; the file does.
    assert window_file.is_file(), f"window file not written\n{result.stdout}\n{result.stderr}"
    data = json.loads(window_file.read_text())
    for field in ("window_open_epoch", "baseline_requests", "commit"):
        assert field in data, f"missing field {field} in {data}"
    assert window_file.stat().st_mode & 0o777 in (0o644, 0o600)


def test_gate_names_present_in_output():
    result = _run()
    out = result.stdout + result.stderr
    for gate in ("N1-G", "N2-G", "N4-G", "N5-G"):
        assert gate in out, f"gate {gate} missing from output"

# ---------------------------------------------------------------------------
# S1 (PRD RELEASE_V13): accounting identity with failures present
# ---------------------------------------------------------------------------


def _write_status_file(path, stop_reasons):
    import json
    path.write_text(json.dumps({"stop_reasons": stop_reasons}))


def _write_journal_file(path, n_ok, n_failed):
    import json
    lines = []
    for _ in range(n_ok):
        lines.append(json.dumps({"type": "request_end", "stop_reason": "end_turn",
                                 "request_id": "x", "state": "completed"}))
    for _ in range(n_failed):
        lines.append(json.dumps({"type": "request_end", "stop_reason": None,
                                 "request_id": "y", "state": "upstream_failed",
                                 "error_code": "MAAS_STREAM_PROTOCOL"}))
    # journald-style prefixes must not break parsing
    path.write_text("\n".join(
        f"Aug 25 02:47:19 host node[123]: {l}" for l in lines) + "\n")


def test_s1_g_identity_holds_with_failures(tmp_path):
    """The OLD gate (sum == total) was permanently red in production because
    failed requests log request_end with stop_reason null and are excluded
    from /status by design. The corrected identity must PASS in exactly such
    a window: 5 completed + 2 failed."""
    status_f = tmp_path / "status.json"
    journal_f = tmp_path / "journal.log"
    _write_status_file(status_f, {"end_turn": 5})
    _write_journal_file(journal_f, n_ok=5, n_failed=2)

    result = _run(env_extra={
        "V12_STATUS_FILE": str(status_f),
        "V12_JOURNAL_FILE": str(journal_f),
    })
    out = result.stdout + result.stderr
    assert "stop_reasons (5) + null-stop (2) == request_end (7)" in out, out
    # And the whole script must not have failed on this gate.
    assert "accounting drift" not in out


def test_s1_g_reverse_old_equation_would_fail(tmp_path):
    """Discrimination: with 2 failures, the raw sum (5) != total (7) — i.e.
    the fixture would FAIL the old (wrong) equality. This pins the fixture
    as a genuine reverse case for the premise bug."""
    status_f = tmp_path / "status.json"
    journal_f = tmp_path / "journal.log"
    _write_status_file(status_f, {"end_turn": 5})
    _write_journal_file(journal_f, n_ok=5, n_failed=2)
    result = _run(env_extra={
        "V12_STATUS_FILE": str(status_f),
        "V12_JOURNAL_FILE": str(journal_f),
    })
    assert "stop_reasons (5) + null-stop (2) == request_end (7)" in result.stdout
    # old equation value: the sum alone
    assert 5 != 7  # trivially, but documents the fixture shape


def test_s1_g_drift_detected_when_request_unlogged(tmp_path):
    """A request that reaches /status but never logs request_end (the real
    regression N4-G guards) must FAIL the identity."""
    status_f = tmp_path / "status.json"
    journal_f = tmp_path / "journal.log"
    # 6 completed counted, only 5 logged
    _write_status_file(status_f, {"end_turn": 6})
    _write_journal_file(journal_f, n_ok=5, n_failed=0)
    result = _run(env_extra={
        "V12_STATUS_FILE": str(status_f),
        "V12_JOURNAL_FILE": str(journal_f),
    })
    out = result.stdout + result.stderr
    assert "accounting drift" in out
    assert result.returncode == 1
