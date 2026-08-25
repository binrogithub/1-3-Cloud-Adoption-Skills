"""WP-B tests (PRD RUNTIME_RESILIENCE_V1): stream-protocol-error auto-resume.

All B-gates are driven by a FAKE claude stub program — no real upstream
quota is consumed and no production failure is induced (project rule:
never fabricate production failures for sample size).

  B-G1  one protocol error -> waits the delay, retries with
        --resume <same uuid> -p continue (asserted via recorded argv).
  B-G2  persistent failure -> exactly MAAS_AUTO_CONTINUE_MAX retries, then
        abandons with non-zero.
  B-G3  marker text present in prose but isApiErrorMessage false -> no retry.
  B-G4  401/400/OVER_CAPACITY/abort -> no retry.
  B-G5  first retry succeeds -> audit record attempt:1 outcome:succeeded,
        counters increment.
"""
from __future__ import annotations

import importlib.util
import importlib.machinery
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "auto_continue.py"


def _load_module():
    loader = importlib.machinery.SourceFileLoader("auto_continue", str(MODULE))
    spec = importlib.util.spec_from_loader("auto_continue", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def ac():
    return _load_module()


# ---------------------------------------------------------------------------
# Fake claude stub
# ---------------------------------------------------------------------------

STUB_BODY = r'''#!/usr/bin/env python3
import json, os, sys, pathlib

# The stub receives its behavior via CLAUDE_STUB_PLAN: a JSON list, one
# entry per invocation. Each entry:
#   {"rc": 0, "error": "stream" | "none" | "401" | "400" | "503" | "abort" | "prose"}
# rc is the process exit code; error selects what the LAST assistant record
# in the session JSONL looks like.
plan = json.loads(os.environ.get("CLAUDE_STUB_PLAN", "[]"))
# Invocation index comes from the counter FILE (persisted across runs),
# not the env — the supervisor spawns a fresh process per attempt.
_counter_path = pathlib.Path(os.environ["CLAUDE_STUB_COUNTER"])
invocations_done = int(_counter_path.read_text() or "0") if _counter_path.exists() else 0

argv = sys.argv[1:]
# Extract --session-id or --resume value and -p prompt.
session_id = None
resume_id = None
prompt = None
i = 0
while i < len(argv):
    a = argv[i]
    if a == "--session-id" and i + 1 < len(argv):
        session_id = argv[i + 1]; i += 2; continue
    if a == "--resume" and i + 1 < len(argv):
        resume_id = argv[i + 1]; i += 2; continue
    if a == "-p" and i + 1 < len(argv):
        prompt = argv[i + 1]; i += 2; continue
    i += 1

# Record the invocation for the test to inspect.
rec = {"session_id": session_id, "resume": resume_id, "prompt": prompt, "argv": argv}
out = pathlib.Path(os.environ["CLAUDE_STUB_RECORD"])
out.write_text(out.read_text() + json.dumps(rec) + "\n" if out.exists() else json.dumps(rec) + "\n")

entry = plan[min(invocations_done, len(plan) - 1)] if plan else {"rc": 0, "error": "none"}

# Write the session JSONL into a fake projects dir under CLAUDE_STUB_HOME.
sid = session_id or resume_id or "unknown-session"
projects = pathlib.Path(os.environ["CLAUDE_STUB_HOME"]) / "projects" / "p"
projects.mkdir(parents=True, exist_ok=True)
jsonl = projects / f"{sid}.jsonl"
lines = []
if jsonl.exists():
    lines = [l for l in jsonl.read_text().splitlines() if l.strip()]
err = entry.get("error", "none")
if err == "stream":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"stop_reason": "stop_sequence",
                        "content": [{"type": "text",
                                     "text": "API Error: stream protocol error"}]}}
elif err == "prose":
    last = {"type": "assistant", "isApiErrorMessage": False,
            "message": {"stop_reason": "end_turn",
                        "content": [{"type": "text",
                                     "text": "The adapter sometimes returns API Error: stream protocol error, which we handled."}]}}
elif err == "401":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"stop_reason": "stop_sequence",
                        "content": [{"type": "text",
                                     "text": "API Error: 401 authentication_error: invalid or missing API key"}]}}
elif err == "400":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"stop_reason": "stop_sequence",
                        "content": [{"type": "text",
                                     "text": "API Error: 400 invalid_request_error"}]}}
elif err == "503":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"stop_reason": "stop_sequence",
                        "content": [{"type": "text",
                                     "text": "API Error: 503 adapter at capacity"}]}}
elif err == "abort":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"stop_reason": "stop_sequence",
                        "content": [{"type": "text",
                                     "text": "API Error: Request was aborted"}]}}
else:
    last = {"type": "assistant", "isApiErrorMessage": False,
            "message": {"stop_reason": "end_turn",
                        "content": [{"type": "text", "text": "All done."}]}}
lines.append(json.dumps({"type": "user", "message": {"content": prompt or ""}}))
lines.append(json.dumps(last))
jsonl.write_text("\n".join(lines) + "\n")

# Persist the invocation counter for the next stub run.
_counter_path.write_text(str(invocations_done + 1))

sys.exit(entry.get("rc", 0))
'''


@pytest.fixture()
def stub_env(tmp_path, monkeypatch):
    """Install the fake claude stub and return (env, records_path, home)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude-maas"
    stub.write_text(STUB_BODY)
    stub.chmod(0o755)

    home = tmp_path / "stubhome"
    home.mkdir()
    records = tmp_path / "records.jsonl"
    counter = tmp_path / "counter"
    counter.write_text("0")

    audit = tmp_path / "audit.jsonl"

    env = {
        "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path / "realhome"),
        "CLAUDE_STUB_RECORD": str(records),
        "CLAUDE_STUB_HOME": str(home),
        "CLAUDE_STUB_COUNTER": str(counter),
        "MAAS_AUTO_CONTINUE_DELAY": "0",
        "MAAS_AUTO_CONTINUE_MAX": "2",
    }
    (tmp_path / "realhome").mkdir()
    return {"env": env, "records": records, "home": home,
            "counter": counter, "audit": audit, "tmp_path": tmp_path}


def _run(ac, stub_env, plan, monkeypatch=None):
    """Drive the supervisor with the fake stub and a given plan."""
    env = dict(stub_env["env"])
    env["CLAUDE_STUB_PLAN"] = json.dumps(plan)
    full = {**os.environ, **env}
    for k in list(full):
        if k.startswith("ANTHROPIC_"):
            full.pop(k)
    # Run a tiny driver script that imports the module and supervises.
    driver = stub_env["tmp_path"] / "driver.py"
    driver.write_text(
        "import importlib.util, importlib.machinery, json, pathlib, sys\n"
        f"loader = importlib.machinery.SourceFileLoader('ac', {str(MODULE)!r})\n"
        "spec = importlib.util.spec_from_loader('ac', loader)\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "loader.exec_module(mod)\n"
        "stub = pathlib.Path(sys.argv[1])\n"
        "cfg = pathlib.Path(sys.argv[2])\n"
        "audit = pathlib.Path(sys.argv[3])\n"
        "def build(sid, is_resume, prompt):\n"
        "    argv = [str(stub)]\n"
        "    if is_resume:\n"
        "        argv += ['--resume', sid, '-p', prompt]\n"
        "    else:\n"
        "        argv += ['--session-id', sid, '-p', 'do the task']\n"
        "    return argv\n"
        "res = mod.run_with_auto_continue(\n"
        "    build,\n"
        "    claude_config_dir=cfg,\n"
        "    audit_path=audit,\n"
        "    sleep=lambda s: None,\n"
        ")\n"
        "print(json.dumps(res))\n"
        "print('COUNTERS', json.dumps(mod.counters()))\n"
    )
    proc = subprocess.run(
        [sys.executable, str(driver), str(stub_env["env"]["PATH"]).split(":")[0] + "/claude-maas",
         str(stub_env["home"]), str(stub_env["audit"])],
        env=full, capture_output=True, text=True, timeout=60,
    )
    return proc




def _driver_result(proc) -> dict:
    """Parse the driver's JSON result line (first line; COUNTERS is second)."""
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"driver produced no JSON result\nstdout: {proc.stdout}\nstderr: {proc.stderr}")

def _records(stub_env) -> list[dict]:
    if not stub_env["records"].exists():
        return []
    out = []
    for line in stub_env["records"].read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# Detection unit tests (B3)
# ---------------------------------------------------------------------------


def test_detection_requires_both_conditions(ac, tmp_path):
    jsonl = tmp_path / "s.jsonl"
    # Marker text but isApiErrorMessage false -> NOT detected.
    jsonl.write_text(json.dumps({"type": "assistant", "isApiErrorMessage": False,
        "message": {"content": [{"type": "text", "text": "API Error: stream protocol error"}]}}) + "\n")
    assert ac.detect_stream_protocol_error(jsonl) is False

    # isApiErrorMessage true but different text -> NOT detected.
    jsonl.write_text(json.dumps({"type": "assistant", "isApiErrorMessage": True,
        "message": {"content": [{"type": "text", "text": "API Error: 401 auth"}]}}) + "\n")
    assert ac.detect_stream_protocol_error(jsonl) is False

    # Both conditions -> detected.
    jsonl.write_text(json.dumps({"type": "assistant", "isApiErrorMessage": True,
        "message": {"content": [{"type": "text", "text": "API Error: stream protocol error"}]}}) + "\n")
    assert ac.detect_stream_protocol_error(jsonl) is True


def test_detection_uses_last_assistant_only(ac, tmp_path):
    jsonl = tmp_path / "s.jsonl"
    lines = [
        json.dumps({"type": "assistant", "isApiErrorMessage": True,
                    "message": {"content": [{"type": "text", "text": "API Error: stream protocol error"}]}}),
        json.dumps({"type": "assistant", "isApiErrorMessage": False,
                    "message": {"content": [{"type": "text", "text": "recovered and finished"}]}}),
    ]
    jsonl.write_text("\n".join(lines) + "\n")
    assert ac.detect_stream_protocol_error(jsonl) is False


# ---------------------------------------------------------------------------
# B-G1: retry uses --resume <same uuid> -p continue
# ---------------------------------------------------------------------------


def test_b_g1_retry_resumes_same_session(stub_env):
    proc = _run(None, stub_env, [
        {"rc": 1, "error": "stream"},
        {"rc": 0, "error": "none"},
    ])
    result = _driver_result(proc)
    assert result["ok"] is True
    assert result["attempts"] == 2
    recs = _records(stub_env)
    assert len(recs) == 2
    first, second = recs
    # First invocation: --session-id, no --resume.
    assert first["session_id"] is not None
    assert first["resume"] is None
    # Retry: --resume with the SAME id, prompt continue.
    assert second["resume"] == first["session_id"]
    assert second["prompt"] == "continue"
    # --continue must never appear.
    for r in recs:
        assert "--continue" not in r["argv"]
        assert "-c" not in r["argv"]


# ---------------------------------------------------------------------------
# B-G2: exactly 2 retries then abandon
# ---------------------------------------------------------------------------


def test_b_g2_persistent_failure_abandons_after_two_retries(stub_env):
    proc = _run(None, stub_env, [{"rc": 1, "error": "stream"}] * 5)
    result = _driver_result(proc)
    assert result["ok"] is False
    assert result["outcome"] == "abandoned"
    assert result["attempts"] == 3  # initial + 2 retries
    assert len(_records(stub_env)) == 3


# ---------------------------------------------------------------------------
# B-G3: prose mention does not trigger
# ---------------------------------------------------------------------------


def test_b_g3_prose_mention_does_not_retry(stub_env):
    proc = _run(None, stub_env, [{"rc": 0, "error": "prose"}])
    result = _driver_result(proc)
    assert result["attempts"] == 1
    assert len(_records(stub_env)) == 1


# ---------------------------------------------------------------------------
# B-G4: terminal errors never retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("err", ["401", "400", "503", "abort"])
def test_b_g4_terminal_errors_do_not_retry(stub_env, err):
    proc = _run(None, stub_env, [{"rc": 1, "error": err}] * 3)
    result = _driver_result(proc)
    assert result["attempts"] == 1
    assert len(_records(stub_env)) == 1


# ---------------------------------------------------------------------------
# B-G5: audit + counters on success-after-retry
# ---------------------------------------------------------------------------


def test_b_g5_audit_written_on_retry_success(stub_env):
    proc = _run(None, stub_env, [
        {"rc": 1, "error": "stream"},
        {"rc": 0, "error": "none"},
    ])
    assert proc.returncode == 0
    audit_path = stub_env["audit"]
    assert audit_path.exists(), "no audit record written"
    lines = [json.loads(l) for l in audit_path.read_text().splitlines() if l.strip()]
    # The retry decision and the final success outcome are both recorded.
    kinds = {r.get("outcome") for r in lines if r.get("type") == "auto_continue"}
    assert "retrying" in kinds, f"retry decision not audited: {lines}"
    assert "succeeded" in kinds, f"final success not audited: {lines}"
    for r in lines:
        assert r.get("trigger") == "stream_protocol_error"
        assert r.get("session_id")
    # Counters: attempted +1, succeeded +1 (driver prints them).
    counters_line = [l for l in proc.stdout.splitlines() if l.startswith("COUNTERS")]
    assert counters_line, f"counters missing from driver output: {proc.stdout}"
    counters = json.loads(counters_line[0].split(" ", 1)[1])
    assert counters["attempted"] >= 1
    assert counters["succeeded"] >= 1


def test_env_disable(stub_env):
    env = dict(stub_env["env"])
    env["MAAS_AUTO_CONTINUE"] = "0"
    stub_env["env"] = env
    proc = _run(None, stub_env, [{"rc": 1, "error": "stream"}] * 3)
    result = _driver_result(proc)
    assert result["attempts"] == 1
    assert len(_records(stub_env)) == 1
