"""Tests for client/claude-maas-run (WP-B §B8 headless wrapper).

The wrapper must be a thin CLI over the SAME supervisor module — not a
second implementation. We drive it with a fake claude-maas stub and verify:

  * first attempt: --session-id + prompt on stdin;
  * retry: --resume <same id> -p continue;
  * exit code reflects ok/abandon;
  * the supervisor module is imported from scripts/auto_continue.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "client" / "claude-maas-run"
MODULE = ROOT / "scripts" / "auto_continue.py"

STUB = r'''#!/usr/bin/env python3
import json, os, sys, pathlib
plan = json.loads(os.environ.get("CLAUDE_STUB_PLAN", "[]"))
cnt = pathlib.Path(os.environ["CLAUDE_STUB_COUNTER"])
done = int(cnt.read_text() or "0") if cnt.exists() else 0
argv = sys.argv[1:]
session_id = resume_id = prompt = None
i = 0
while i < len(argv):
    a = argv[i]
    if a == "--session-id" and i + 1 < len(argv): session_id = argv[i+1]; i += 2; continue
    if a == "--resume" and i + 1 < len(argv): resume_id = argv[i+1]; i += 2; continue
    if a == "-p" and i + 1 < len(argv): prompt = argv[i+1]; i += 2; continue
    i += 1
rec = pathlib.Path(os.environ["CLAUDE_STUB_RECORD"])
line = json.dumps({"session_id": session_id, "resume": resume_id,
                   "prompt": prompt, "stdin_prompt": None})
rec.write_text((rec.read_text() if rec.exists() else "") + line + "\n")
entry = plan[min(done, len(plan) - 1)] if plan else {"rc": 0, "error": "none"}
sid = session_id or resume_id or "s"
projects = pathlib.Path(os.environ["CLAUDE_STUB_HOME"]) / "projects" / "p"
projects.mkdir(parents=True, exist_ok=True)
jsonl = projects / f"{sid}.jsonl"
lines = [l for l in (jsonl.read_text().splitlines() if jsonl.exists() else []) if l.strip()]
if entry.get("error") == "stream":
    last = {"type": "assistant", "isApiErrorMessage": True,
            "message": {"content": [{"type": "text",
                                     "text": "API Error: stream protocol error"}]}}
else:
    last = {"type": "assistant", "isApiErrorMessage": False,
            "message": {"content": [{"type": "text", "text": "done"}]}}
lines.append(json.dumps(last))
jsonl.write_text("\n".join(lines) + "\n")
cnt.write_text(str(done + 1))
sys.exit(entry.get("rc", 0))
'''


@pytest.fixture()
def env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude-maas"
    stub.write_text(STUB)
    stub.chmod(0o755)
    home = tmp_path / "stubhome"
    home.mkdir()
    rec = tmp_path / "records.jsonl"
    cnt = tmp_path / "counter"
    cnt.write_text("0")
    e = dict(os.environ)
    e.update({
        "PATH": f"{bindir}:{e.get('PATH', '')}",
        "HOME": str(tmp_path),
        # The wrapper reads CLAUDE_CONFIG_DIR to find session JSONLs;
        # point it at the stub's fake projects tree.
        "CLAUDE_CONFIG_DIR": str(home),
        "CLAUDE_STUB_RECORD": str(rec),
        "CLAUDE_STUB_HOME": str(home),
        "CLAUDE_STUB_COUNTER": str(cnt),
        "MAAS_AUTO_CONTINUE_DELAY": "0",
        "MAAS_AUTO_CONTINUE_MAX": "2",
    })
    for k in list(e):
        if k.startswith("ANTHROPIC_"):
            e.pop(k)
    return {"env": e, "records": rec, "tmp_path": tmp_path,
            "bindir": str(bindir)}


def _run(env, plan, prompt="do the thing"):
    e = dict(env["env"])
    e["CLAUDE_STUB_PLAN"] = json.dumps(plan)
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--client-bin",
         str(Path(env["bindir"]) / "claude-maas"), prompt],
        env=e, capture_output=True, text=True, timeout=60,
    )


def test_wrapper_retries_via_resume_same_session(env):
    proc = _run(env, [
        {"rc": 1, "error": "stream"},
        {"rc": 0, "error": "none"},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[0])
    assert result["ok"] is True
    assert result["attempts"] == 2
    recs = [json.loads(l) for l in env["records"].read_text().splitlines() if l.strip()]
    assert len(recs) == 2
    assert recs[0]["session_id"] == recs[1]["resume"]
    assert recs[1]["prompt"] == "continue"
    for r in recs:
        assert "--continue" not in json.dumps(r)


def test_wrapper_abandons_after_budget(env):
    proc = _run(env, [{"rc": 1, "error": "stream"}] * 4)
    assert proc.returncode == 1
    result = json.loads(proc.stdout.strip().splitlines()[0])
    assert result["outcome"] == "abandoned"
    assert result["attempts"] == 3


def test_wrapper_uses_shared_supervisor():
    """The wrapper must import scripts/auto_continue.py — no reimplementation."""
    src = WRAPPER.read_text()
    assert "auto_continue.py" in src
    assert MODULE.is_file()
    # And the module exposes the API the wrapper calls.
    text = MODULE.read_text()
    assert "def run_with_auto_continue(" in text


def test_wrapper_disable_env(env):
    e = dict(env["env"])
    e["MAAS_AUTO_CONTINUE"] = "0"
    e["CLAUDE_STUB_PLAN"] = json.dumps([{"rc": 1, "error": "stream"}] * 3)
    proc = subprocess.run(
        [sys.executable, str(WRAPPER), "--client-bin",
         str(Path(env["bindir"]) / "claude-maas"), "task"],
        env=e, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout.strip().splitlines()[0])
    assert result["attempts"] == 1
