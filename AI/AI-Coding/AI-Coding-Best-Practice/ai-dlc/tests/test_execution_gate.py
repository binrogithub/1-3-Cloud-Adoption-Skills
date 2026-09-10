"""P0-4 execution gate — tests for the third machine fact in deliver.

Covers: plan discovery (explicit not_applicable, never silent), pass and
fail verdicts, timeout handling, the --no-exec-gate refusal contract, and
the deliver integration (outcome exec_gate_failed, delivered false,
execution-gate.json persisted).

Run:  python3 -m pytest tests/test_execution_gate.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


# ── load report.py as a module ──────────────────────────────────────
_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_exec_gate", _BIN / "bin" / "report.py")


def _plan(name: str, rc: int) -> str:
    """A one-tool plan whose command exits rc deterministically."""
    return json.dumps([{
        "name": name,
        "cmd": [sys.executable, "-c", "import sys; sys.exit(%d)" % rc],
        "scope": "suite",
    }])


def test_gate_pass(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", _plan("t-pass", 0))
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "pass"
    assert gate["ran"] == 1
    assert gate["tools"][0]["status"] == "pass"
    assert gate["tools"][0]["rc"] == 0


def test_gate_fail(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", _plan("t-fail", 3))
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "fail"
    assert gate["tools"][0]["status"] == "fail"
    assert gate["tools"][0]["rc"] == 3


def test_gate_mixed_one_fail_fails_all(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    plan = json.dumps([
        {"name": "ok", "cmd": [sys.executable, "-c", "pass"],
         "scope": "suite"},
        {"name": "bad", "cmd": [sys.executable, "-c",
                                "import sys; sys.exit(1)"],
         "scope": "suite"},
    ])
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", plan)
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "fail"
    assert [t["status"] for t in gate["tools"]] == ["pass", "fail"]


def test_gate_timeout_is_fail(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    plan = json.dumps([{
        "name": "slow", "cmd": [sys.executable, "-c",
                                "import time; time.sleep(30)"],
        "scope": "suite"}])
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", plan)
    monkeypatch.setattr(report, "EXEC_GATE_TIMEOUT", 1)
    gate = report.run_execution_gate(tmp_path, ["a.py"])
    assert gate["state"] == "fail"
    assert gate["tools"][0]["rc"] is None
    assert "timed out" in gate["tools"][0]["output_tail"][-1]


def test_no_toolchain_is_explicit_not_silent(tmp_path, monkeypatch):
    # python files changed, but no tests/, no config, no tools on PATH:
    # every entry must be not_applicable with a reason — never missing.
    monkeypatch.delenv("AI_DLC_EXEC_TOOLS_JSON", raising=False)
    monkeypatch.setattr(report, "_tool_available", lambda tool: False)
    gate = report.run_execution_gate(tmp_path, ["only.py"])
    assert gate["state"] == "not_applicable"
    assert gate["ran"] == 0
    names = {t["name"] for t in gate["tools"]}
    assert names == {"pytest", "ruff", "mypy"}
    assert all(t["status"] == "not_applicable" and t.get("why")
               for t in gate["tools"])


def test_plan_scopes_lint_to_changed_files(tmp_path, monkeypatch):
    # ruff on PATH: its command carries only the changed python files
    monkeypatch.delenv("AI_DLC_EXEC_TOOLS_JSON", raising=False)
    monkeypatch.setattr(report, "_tool_available", lambda tool: True)
    plan = report.execution_tool_plan(tmp_path, ["src/a.py", "docs.md"])
    ruff = next(t for t in plan if t["name"] == "ruff")
    assert ruff["cmd"] == ["ruff", "check", "--select", "E,F",
                           "--ignore", "E501", "src/a.py"]
    assert ruff["scope"] == "changed-files"


def test_no_exec_gate_refuses_unnamed_actor(tmp_path):
    # a model may not self-sign a gate skip (the --no-design contract)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    rc = report.cmd_deliver(tmp_path, tmp_path, "completed",
                            no_exec_gate=True, no_exec_gate_by="model",
                            no_exec_gate_why="because")
    assert rc == 1


def test_deliver_integration_gate_fail_blocks(tmp_path, monkeypatch, capsys):
    # end to end: a landed change with a signed spec verdict whose tool
    # fails → exec_gate_failed, delivered false, execution-gate.json
    # persisted next to the report. The verdict is fabricated through
    # report.py's own signing path against tmp roots — the same shape
    # the real validate dispatch writes, per records_tool's contract.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    key_path = tmp_path / "verdict.key"
    key_path.write_bytes(b"test-key-material-not-secret")
    monkeypatch.setattr(report, "VERDICT_KEY_PATH", key_path)
    monkeypatch.setattr(report, "RECORDS_ROOT", tmp_path / "records")
    report.write_record("p0-4-test-change", "verdict", {
        "verb": "validate", "rc": 0, "change": "p0-4-test-change",
        "ts": "2026-09-07T00:00:00Z", "session": "test-stand-in"})
    task_dir = tmp_path / ".ai-dlc" / "tasks" / "t1"
    assert report.cmd_init(task_dir, tmp_path, "inline", "t1",
                           "p0-4-test-change") == 0
    capsys.readouterr()  # flush init's own JSON output before deliver
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.py"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q", "-m", "work"],
                   check=True)
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON", _plan("t-fail", 1))
    rc = report.cmd_deliver(task_dir, tmp_path, "completed")
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["spec"]["spec_valid"] is True
    assert rep["execution_gate"]["state"] == "fail"
    assert rep["outcome"] == "exec_gate_failed"
    assert rep["delivered"] is False
    persisted = json.loads((task_dir / "execution-gate.json")
                           .read_text(encoding="utf-8"))
    assert persisted["state"] == "fail"
    assert persisted["tools"][0]["name"] == "t-fail"


def test_close_refuses_on_failed_exec_gate(tmp_path):
    # 02-static-site finding: an approval predating a failing
    # re-delivery must not carry the close (plan.py cmd_close reads the
    # standing report; this test pins the contract from the report side)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "plan_close_t", _BIN / "bin" / "plan.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    td = tmp_path / "td"
    td.mkdir()
    report.save_json(td / "state.json", {"stage": "MERGE_GATE"})
    report.save_json(td / "report.json",
                     {"execution_gate": {"state": "fail"}})
    report.save_json(td / "gates" / "gate-merge.answer.json",
                     {"decision": "approve", "approver": "Robin",
                      "rationale": "predates the failure"})
    rc = plan.cmd_close("c", tmp_path, td, None, False)
    assert rc == plan.EXIT_INCONCLUSIVE


def test_close_refuses_on_spec_invalid(tmp_path):
    # 03-wordfreq finding: close's exec-gate guard has a twin
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "plan_close_spec_t", _BIN / "bin" / "plan.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    td = tmp_path / "td"
    td.mkdir()
    report.save_json(td / "state.json", {"stage": "MERGE_GATE"})
    report.save_json(td / "report.json", {
        "execution_gate": {"state": "pass"},
        "spec": {"spec_state": "spec_invalid"}})
    report.save_json(td / "gates" / "gate-merge.answer.json",
                     {"decision": "approve", "approver": "Robin",
                      "rationale": "predates the refusal"})
    rc = plan.cmd_close("c", tmp_path, td, None, False)
    assert rc == plan.EXIT_INCONCLUSIVE
