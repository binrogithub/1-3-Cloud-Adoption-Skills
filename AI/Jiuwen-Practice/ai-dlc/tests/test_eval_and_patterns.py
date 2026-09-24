"""P1-3 eval harness + P1-4 patterns dashboard — tests.

The eval harness materialises fixtures as fresh git repos, dispatches
one session per task, judges deterministically, and writes comparable
results tagged with the plane's git sha (Anthropic: a small fixed set
run before and after a change beats a large one run once). The
patterns dashboard aggregates decision patterns over a task's own
records — never conversation contents.

Run:  python3 -m pytest tests/test_eval_and_patterns.py -v
"""
import importlib.util
import json
import stat
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_patterns_t", _BIN / "bin" / "report.py")
evalmod = _load("eval_harness_t", _BIN / "bin" / "eval.py")


# ── P1-3: the set and the harness ──────────────────────────────────

def test_set_parses_and_is_well_formed():
    tasks = json.loads((_BIN / "evals" / "set.json").read_text(
        encoding="utf-8"))["tasks"]
    assert len(tasks) >= 8
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids))
    for t in tasks:
        assert t["prompt"].strip() and t["checks"]
        for c in t["checks"]:
            assert c["kind"] in ("exists", "contains", "command")


def test_checks_engine(tmp_path):
    task = {
        "id": "t", "files": {"a.txt": "hello accent\n"},
        "checks": [
            {"kind": "exists", "path": "a.txt"},
            {"kind": "contains", "path": "a.txt", "pattern": "accent"},
            {"kind": "contains", "path": "a.txt", "pattern": "absent"},
            {"kind": "command", "cmd": ["python3", "-c", "raise SystemExit(1)"],
             "expect_rc": 1},
        ]}
    d = evalmod.materialise(task, tmp_path)
    results = evalmod.run_checks(task, d)
    assert [r["ok"] for r in results] == [True, True, False, True]


def test_materialise_creates_a_git_repo(tmp_path):
    task = {"id": "t2", "files": {"x/y.txt": "z\n"}, "checks": []}
    d = evalmod.materialise(task, tmp_path)
    assert (d / ".git").is_dir() and (d / "x" / "y.txt").is_file()


def test_run_set_with_stub_client(tmp_path, monkeypatch, capsys):
    # a stub client that exits 0 and does no work: the harness must
    # still invoke it per task, judge mechanically, and write a results
    # file carrying the plane git sha — pass_rate 0 is the honest floor
    stub = tmp_path / "stub-client"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("AI_DLC_EVAL_CLIENT", str(stub))
    monkeypatch.setattr(evalmod, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(evalmod, "CLIENT", str(stub))
    assert evalmod.run_set("fix-json") == 0
    capsys.readouterr()
    files = sorted((tmp_path / "results").glob("run-*.json"))
    assert len(files) == 1
    out = json.loads(files[0].read_text(encoding="utf-8"))
    assert out["plane_git"]
    assert out["summary"]["total"] == 1
    assert out["tasks"][0]["client_rc"] == 0
    assert out["tasks"][0]["passed"] is False   # the stub did no work


def test_compare_names_regressions_and_improvements(tmp_path):
    def run(path, passed_a, passed_b):
        path.write_text(json.dumps({"plane_git": "x", "summary": {},
            "tasks": [
                {"id": "one", "passed": passed_a, "elapsed_seconds": 1},
                {"id": "two", "passed": passed_b, "elapsed_seconds": 2}]})
            + "\n", encoding="utf-8")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    run(a, True, False)
    run(b, False, True)
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert evalmod.compare(str(a), str(b)) == 0
    out = json.loads(buf.getvalue())
    assert out["regressions"] == ["one"]
    assert out["improvements"] == ["two"]


# ── P1-4: the patterns dashboard ───────────────────────────────────

def _task_dir(tmp_path: Path) -> Path:
    td = tmp_path / ".ai-dlc" / "tasks" / "t13"
    td.mkdir(parents=True)
    report.save_json(td / "planning.json", {
        "review": {"reviewers": {
            "correctness": {"outcome": 0, "elapsed_seconds": 12.0},
            "security": {"outcome": 0, "elapsed_seconds": 8.0},
            "operability": {"outcome": 17, "elapsed_seconds": 4.0}}},
        "codegraph_auto": {"rc": 0, "elapsed_seconds": 40.0}})
    report.save_json(td / "report.json", {
        "execution_gate": {"state": "pass"}, "delivered": True,
        "outcome": "completed", "landed_files": 4})
    report.save_json(td / "checkpoints.json",
                     {"checkpoints": [{"seq": 1}, {"seq": 2}]})
    (td / "events.jsonl").write_text(
        "\n".join(["{\"event\": \"CHECKPOINT_RECORDED\"}"] * 3
                  + ["{\"event\": \"EXECUTION_GATE\"}", "not json"]),
        encoding="utf-8")
    return td


def test_patterns_aggregates_roles_and_states(tmp_path, capsys):
    td = _task_dir(tmp_path)
    assert report.cmd_patterns(td) == 0
    out = json.loads(capsys.readouterr().out)
    roles = {r["role"]: r for r in out["roles"]}
    assert roles["review-correctness"]["success_rate"] == 1.0
    assert roles["review-operability"]["ok"] == 0
    assert roles["codegraph"]["elapsed_mean_s"] == 40.0
    assert out["execution_gate"] == "pass"
    assert out["delivered"] is True
    assert out["checkpoints"] == 2
    assert out["events"]["CHECKPOINT_RECORDED"] == 3


def test_patterns_on_an_empty_task_dir(tmp_path, capsys):
    td = tmp_path / "empty"
    td.mkdir()
    assert report.cmd_patterns(td) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["roles"] == []
    assert out["checkpoints"] == 0
