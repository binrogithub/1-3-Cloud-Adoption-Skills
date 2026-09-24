"""P2-1 stall watch + nudge — tests.

The clock is the frames': a dispatch is suspected when its evidence
has produced no timestamped frame for the timeout — timestamps only,
content never parsed. A suspected stall lands in the task's EXISTING
event stream. The nudge surfaces merge gates unanswered past 48h.

Run:  python3 -m pytest tests/test_stallguard.py -v
"""
import importlib.util
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_stall_t", _BIN / "bin" / "report.py")


def _evidence(task_dir: Path, name: str, ts: float) -> None:
    ev = task_dir / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / name).write_text(json.dumps({"timestamp": ts}) + "\n",
                           encoding="utf-8")


def test_quiet_past_timeout_is_suspected(tmp_path, capsys):
    td = tmp_path / "t"
    td.mkdir()
    _evidence(td, "plan-author-1.jsonl", time.time() - 400)
    assert report.cmd_stallguard(td, 300) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["suspected"]) == 1
    assert out["suspected"][0]["evidence"] == "plan-author-1.jsonl"
    events = (td / "events.jsonl").read_text(encoding="utf-8")
    assert "STALL_SUSPECTED" in events


def test_fresh_frames_are_normal(tmp_path, capsys):
    td = tmp_path / "t"
    td.mkdir()
    _evidence(td, "plan-author-1.jsonl", time.time() - 10)
    assert report.cmd_stallguard(td, 300) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["suspected"] == []
    assert not (td / "events.jsonl").exists()


def test_no_evidence_is_not_an_error(tmp_path, capsys):
    td = tmp_path / "empty"
    td.mkdir()
    assert report.cmd_stallguard(td, 300) == 0
    assert json.loads(capsys.readouterr().out)["suspected"] == []


def test_content_is_never_parsed(tmp_path, capsys):
    # garbage payloads with live timestamps are still just frames
    td = tmp_path / "t"
    td.mkdir()
    ev = td / "evidence"
    ev.mkdir()
    (ev / "plan-x-1.jsonl").write_text(
        json.dumps({"timestamp": time.time() - 400,
                    "payload": "not for the guard to read"})
        + "\nnot json at all\n", encoding="utf-8")
    assert report.cmd_stallguard(td, 300) == 0
    assert len(json.loads(capsys.readouterr().out)["suspected"]) == 1


def _gate_task(root: Path, name: str, requested_at: str,
               answered: bool = False) -> Path:
    td = root / ".ai-dlc" / "tasks" / name
    td.mkdir(parents=True)
    report.save_json(td / "state.json", {
        "task_id": name, "route": "inline", "stage": "MERGE_GATE",
        "human_state": "Needs your decision"})
    report.save_json(td / "gates" / "gate-merge.request.json",
                     {"requested_at": requested_at})
    if answered:
        report.save_json(td / "gates" / "gate-merge.answer.json",
                         {"decision": "approve"})
    return td


def test_nudge_surfaces_old_unanswered_gates(tmp_path, capsys):
    old = (datetime.now(timezone.utc)
           - timedelta(hours=72)).isoformat().replace("+00:00", "Z")
    _gate_task(tmp_path, "stale", old)
    _gate_task(tmp_path, "answered", old, answered=True)
    _gate_task(tmp_path, "fresh",
               datetime.now(timezone.utc).isoformat())
    assert report.cmd_nudge(tmp_path, 48) == 0
    out = json.loads(capsys.readouterr().out)
    nudged = {w["task"] for w in out["nudged"]}
    assert nudged == {"stale"}
    ev = (tmp_path / ".ai-dlc" / "tasks" / "stale" / "events.jsonl") \
        .read_text(encoding="utf-8")
    assert "MERGE_GATE_NUDGED" in ev
