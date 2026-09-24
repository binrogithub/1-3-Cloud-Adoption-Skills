"""P2-3 dispatch-doctor — tests.

The deterministic half of the tool-description repair loop: replay the
session archives, count --help fumbling per tool and commands repeated
3+ times, emit revision suggestions for human review. Command shapes
only — the conversation is never read.

Run:  python3 -m pytest tests/test_dispatch_doctor.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_doctor_t", _BIN / "bin" / "report.py")


def _session(root: Path, name: str, lines: list[str]) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "history.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def test_help_fumbling_counted_per_tool(tmp_path, capsys):
    _session(tmp_path, "s1", [
        '{"content": "python3 bin/plan.py --help"}',
        '{"content": "python3 bin/plan.py --help"}',
        '{"content": "python3 bin/plan.py --help"}',
        '{"content": "bin/report.py --help"}',
    ])
    assert report.cmd_dispatch_doctor(tmp_path, None, 50) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["help_fumbling"]["plan.py"] == 3
    assert out["help_fumbling"]["report.py"] == 1


def test_suggestions_name_the_worst_offender(tmp_path, capsys):
    _session(tmp_path, "s1", [
        '{"content": "bin/plan.py --help"}',
        '{"content": "bin/plan.py --help"}',
    ])
    report.cmd_dispatch_doctor(tmp_path, None, 50)
    out = json.loads(capsys.readouterr().out)
    assert out["suggestions"][0]["tool"] == "plan.py"
    assert "copy-paste" in out["suggestions"][0]["suggestion"]


def test_repeated_commands_flagged(tmp_path, capsys):
    _session(tmp_path, "s1", [
        '{"tool_call": {"command": "bin/plan.py validate --change c"}}',
        '{"tool_call": {"command": "bin/plan.py validate --change c"}}',
        '{"tool_call": {"command": "bin/plan.py validate --change c"}}',
        '{"tool_call": {"command": "echo ok"}',
    ])
    report.cmd_dispatch_doctor(tmp_path, None, 50)
    out = json.loads(capsys.readouterr().out)
    assert out["repeated_commands"] == {
        "bin/plan.py validate --change c": 3}


def test_write_dumps_suggestions_for_human_review(tmp_path):
    _session(tmp_path, "s1", [
        '{"content": "bin/plan.py --help"}',
        '{"content": "bin/plan.py --help"}',
    ])
    out_file = tmp_path / "suggestions.json"
    assert report.cmd_dispatch_doctor(tmp_path, out_file, 50) == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["suggestions"] and data["files_scanned"] == 1


def test_empty_archives_are_normal(tmp_path, capsys):
    assert report.cmd_dispatch_doctor(tmp_path, None, 50) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["files_scanned"] == 0
    assert out["help_fumbling"] == {}
