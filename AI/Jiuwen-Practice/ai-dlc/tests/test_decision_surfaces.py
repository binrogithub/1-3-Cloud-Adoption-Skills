"""P1-1 copy-paste commands + P1-6 anti-collusion surfaces — tests.

P1-1: the skill's first screen carries the four steps as complete,
copy-paste-ready commands — the measured failure was 1m56s of --help
fumbling that a ready command block eliminates.

P1-6: the merge gate's question carries the machine-facts-authority
reminder and the execution gate's state; the validate verdict records
which model actually served it (measured from usage frames) against
the configured intent — same-source collusion posture made visible
instead of assumed away.

Run:  python3 -m pytest tests/test_decision_surfaces.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_decision_surfaces", _BIN / "bin" / "plan.py")
report = _load("report_decision_surfaces", _BIN / "bin" / "report.py")

USAGE_FRAME = json.dumps({
    "event": "chat.usage_metadata",
    "payload": {"metadata": {"usage_metadata": {
        "model_name": "glm-5.2", "input_tokens": 10}}}})


# ── P1-6: the validator's model, measured ──────────────────────────

def test_frames_model_name_reads_usage_frame():
    assert plan.frames_model_name([USAGE_FRAME]) == "glm-5.2"


def test_frames_model_name_absent_is_none():
    assert plan.frames_model_name(["{}"]) is None


def test_validator_model_mismatch_warns(monkeypatch):
    monkeypatch.setenv("AI_DLC_VALIDATOR_MODEL", "glm-5.2x")
    st = plan.validator_model_state([USAGE_FRAME])
    assert st["configured"] == "glm-5.2x"
    assert st["actual"] == "glm-5.2"
    assert st["same_source_warning"] is True
    assert "did not take effect" in st["why"]


def test_validator_model_match_is_quiet(monkeypatch):
    monkeypatch.setenv("AI_DLC_VALIDATOR_MODEL", "glm-5.2")
    st = plan.validator_model_state([USAGE_FRAME])
    assert st["same_source_warning"] is False


def test_validator_model_unset_states_the_posture(monkeypatch):
    monkeypatch.delenv("AI_DLC_VALIDATOR_MODEL", raising=False)
    monkeypatch.setattr(plan, "config_scalar_global",
                        lambda key: None)
    st = plan.validator_model_state([USAGE_FRAME])
    assert st["configured"] is None
    assert "same-source" in st["why"]


# ── P1-6: the gate question carries authority + the exec gate ──────

def _mini_task(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    task_dir = tmp_path / ".ai-dlc" / "tasks" / "t11"
    task_dir.mkdir(parents=True)
    report.save_json(task_dir / "state.json", {
        "task_id": "t11", "route": "inline", "stage": "MERGE_GATE",
        "human_state": "Needs your decision"})
    report.save_json(task_dir / "report.json", {
        "execution_gate": {"state": "pass"}})
    return task_dir


def test_gate_question_carries_authority_and_exec_gate(tmp_path, capsys):
    task_dir = _mini_task(tmp_path)
    capsys.readouterr()
    assert report.cmd_gate(task_dir, "gate-merge", None, None, "",
                           True, None, "MERGE_GATE", None, None) in (0, 1)
    capsys.readouterr()
    req = json.loads((task_dir / "gates" / "gate-merge.request.json")
                     .read_text(encoding="utf-8"))
    assert "authoritative" in req["question"]
    assert "Execution gate: pass." in req["question"]


# ── P1-1: the copy-paste block on the first screen ─────────────────

def test_skill_first_screen_carries_copy_paste_commands():
    skill = (_BIN / "supervisor" / "skills" / "claude" / "ai-dlc"
             / "SKILL.md").read_text(encoding="utf-8")
    first_screen = skill.split("## Task flow (full)")[0]
    for needle in ("report.py init --task-dir $TD",
                   "plan.py validate --change <change-id>",
                   "report.py deliver --task-dir $TD",
                   "report.py gate --request --task-dir $TD",
                   "plan.py close --change <change-id>"):
        assert needle in first_screen, needle
    assert "copy-paste" in first_screen.lower()


def test_skill_states_the_authority_rule():
    skill = (_BIN / "supervisor" / "skills" / "claude" / "ai-dlc"
             / "SKILL.md").read_text(encoding="utf-8")
    assert "Machine facts outrank consensus" in skill


def test_deliver_report_carries_the_tier(tmp_path, capsys, monkeypatch):
    # 01-notes-cli: the gate reader sees the effort tier in the report
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    key = tmp_path / "verdict.key"
    key.write_bytes(b"k")
    monkeypatch.setattr(report, "VERDICT_KEY_PATH", key)
    monkeypatch.setattr(report, "RECORDS_ROOT", tmp_path / "records")
    report.write_record("tier-check", "verdict", {
        "verb": "validate", "rc": 0, "change": "tier-check",
        "ts": "2026-09-08T00:00:00Z", "session": "s"})
    td = tmp_path / ".ai-dlc" / "tasks" / "t15"
    report.cmd_init(td, tmp_path, "inline", "t15", "tier-check")
    capsys.readouterr()
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.py"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q", "-m", "w"],
                   check=True)
    monkeypatch.setenv("AI_DLC_EXEC_TOOLS_JSON",
                       json.dumps([{"name": "t", "cmd":
                                    [sys.executable, "-c", "pass"],
                                    "scope": "suite"}]))
    report.cmd_deliver(td, tmp_path, "completed")
    rep = json.loads(capsys.readouterr().out)
    assert rep["tier"]["tier"] == "tier-1-inline"
    assert rep["tier"]["budget"]
