"""Finding #1 (AB-lab E2E, 2026-09-08): the execution gate's pytest
detection missed flat layouts — a root-level test_*.py with no tests/
dir and no config measured not_applicable and the gate stood hollow.
The fix: root-level test files count as a pytest surface.

Run:  python3 -m pytest tests/test_exec_gate_flat_layout.py -v
"""
import importlib.util
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_flat_t", _BIN / "bin" / "report.py")


def _gate_for(tmp_path, files: dict):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    plan = report.execution_tool_plan(tmp_path, ["a.py"])
    return {t["name"]: t for t in plan}


def test_flat_root_test_file_is_detected(tmp_path):
    plan = _gate_for(tmp_path, {"test_tasks.py": "def test_x(): pass\n"})
    assert plan["pytest"].get("cmd"), "flat layout must dispatch pytest"


def test_flat_suffixed_test_file_is_detected(tmp_path):
    plan = _gate_for(tmp_path, {"tasks_test.py": "def test_x(): pass\n"})
    assert plan["pytest"].get("cmd")


def test_tests_dir_still_detected(tmp_path):
    plan = _gate_for(tmp_path,
                     {"tests/test_a.py": "def test_x(): pass\n"})
    assert plan["pytest"].get("cmd")


def test_no_test_surface_is_still_explicit(tmp_path):
    plan = _gate_for(tmp_path, {"app.py": "x = 1\n"})
    assert plan["pytest"]["status"] == "not_applicable"


def test_real_lab_shape_passes_the_gate(tmp_path):
    # the exact shape that measured not_applicable in the E2E
    plan = _gate_for(tmp_path, {
        "tasks.py": "class TaskList: pass\n",
        "test_tasks.py": "from tasks import TaskList\n"
                         "def test_ok():\n    assert TaskList()\n"})
    entry = plan["pytest"]
    cmd = entry.get("cmd") or []
    # dispatched with the interpreter's own pytest, never not_applicable
    assert isinstance(cmd, list) and len(cmd) >= 3
    assert cmd[1:3] == ["-m", "pytest"]
    assert entry.get("status") is None or entry.get("detect")
