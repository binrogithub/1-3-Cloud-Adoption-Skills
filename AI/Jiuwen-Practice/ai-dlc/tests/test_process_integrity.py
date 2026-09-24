"""process-integrity — tests.

V1 a rewritten requirement bumps the session generation (new session
name, wholesale-rewrite prompt); V2 write attempts the frames carry
that never landed are named in the record; V3 the exec-gate ruff
verdict counts only diagnostics on lines the change touched.

Run:  python3 -m pytest tests/test_process_integrity.py -v
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/pi-test-specs")
os.environ.setdefault("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")

spec = importlib.util.spec_from_file_location(
    "plan_pi", _BIN / "bin" / "plan.py")
plan = importlib.util.module_from_spec(spec)
sys.modules["plan_pi"] = plan
spec.loader.exec_module(plan)
_rs = importlib.util.spec_from_file_location("report_pi", _BIN / "bin" / "report.py")
report = importlib.util.module_from_spec(_rs)
sys.modules["report_pi"] = report
_rs.loader.exec_module(report)

NAMES = ("tokens.css", "tokens.json", "components.md", "pages.md",
         "assets.md")


def _fake_design_session(files_to_write, capture):
    def fake(change, prompt, repo, task_dir, mode, timeout,
             generation=1):
        capture["generation"] = generation
        capture["prompt"] = prompt
        d = repo / "design"
        d.mkdir(exist_ok=True)
        for name, text in files_to_write.items():
            (d / name).write_text(text, encoding="utf-8")
        return {"timed_out": False, "round_complete": True,
                "interrupted": False,
                "session_name": "design-c1-001"}, []
    return fake


def _rig(tmp_path, prior_req="alpha-requirement", new_req=None):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    skill = tmp_path / "tpl" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: t\n---\nb\n")
    import hashlib
    (td / "proposal.md").write_text(
        new_req if new_req is not None else prior_req, encoding="utf-8")
    prior_sha = hashlib.sha256(
        prior_req.encode()).hexdigest()
    report.save_json(td / "state.json", {
        "task_id": "c1", "route": "inline", "stage": "WORK",
        "design_selection": {"chosen": str(skill),
                             "skill_name": "t",
                             "skill_sha256": "x"},
        "design_spec": {"requirement_sha": prior_sha,
                        "generation": 1, "all_written": True}})
    return repo, td


class TestV1Generations:
    def test_same_requirement_keeps_generation(self, tmp_path,
                                               monkeypatch):
        repo, td = _rig(tmp_path)
        cap = {}
        monkeypatch.setattr(plan, "run_design_session",
                            _fake_design_session(
                                {n: "content\n" for n in NAMES}, cap))
        assert plan.cmd_design_specify("c1", repo, td) == 0
        assert cap["generation"] == 1
        assert "REWRITE" not in cap["prompt"]

    def test_rewritten_requirement_bumps(self, tmp_path, monkeypatch):
        repo, td = _rig(tmp_path, prior_req="old text",
                        new_req="completely different requirement")
        cap = {}
        monkeypatch.setattr(plan, "run_design_session",
                            _fake_design_session(
                                {n: "content\n" for n in NAMES}, cap))
        assert plan.cmd_design_specify("c1", repo, td) == 0
        assert cap["generation"] == 2
        assert "REWRITE" in cap["prompt"]
        st = report.load_json(td / "state.json", {})
        assert st["design_spec"]["generation"] == 2
        assert st["design_spec"]["requirement_sha"]


class TestV2UnlandedWrites:
    def test_frame_write_that_never_landed_is_named(self, tmp_path,
                                                    monkeypatch):
        repo, td = _rig(tmp_path)
        # session writes NOTHING on disk but its frames claim a write
        frames = [json.dumps({
            "event": "chat.tool_call",
            "payload": {"tool_call": {
                "name": "write_file",
                "arguments": json.dumps({
                    "path": str(repo / "design" / "pages.md"),
                    "content": "x"}),
                "tool_call_id": "w1"}}})]

        def fake(change, prompt, repo_, td_, mode, timeout,
                 generation=1):
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "session_name": "s"}, frames

        monkeypatch.setattr(plan, "run_design_session", fake)
        rc = plan.cmd_design_specify("c1", repo, td)
        assert rc == plan.EXIT_INCONCLUSIVE
        st = report.load_json(td / "state.json", {})
        unlanded = st["design_spec"]["unlanded_writes"]
        assert any("pages.md" in u for u in unlanded), unlanded


class TestV3ChangedLineRuff:
    def _repo_with_debt(self, tmp_path, new_line=None):
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        f = repo / "mod.py"
        # pre-existing debt on line 1-2 (unused import), untouched
        f.write_text("import os\nimport sys\nX = 1\n",
                     encoding="utf-8")
        for cmd in (["init", "-q"],
                    ["config", "user.name", "t"],
                    ["config", "user.email", "t@t"],
                    ["add", "-A"],
                    ["commit", "-q", "-m", "base"]):
            subprocess.run(["git", "-C", str(repo)] + cmd,
                           capture_output=True, check=True)
        if new_line:
            f.write_text("import os\nimport sys\nX = 1\n"
                         + new_line, encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-A"],
                           capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-q", "-m", "feat"],
                capture_output=True, check=True)
        return repo

    def test_untouched_debt_passes_with_touched_clean(self, tmp_path):
        repo = self._repo_with_debt(
            tmp_path, new_line="Y = X + 1  # clean line\n")
        os.environ.pop("AI_DLC_EXEC_RUFF_WHOLEFILE", None)
        gate = report.run_execution_gate(
            repo, ["mod.py"], base="HEAD~1")
        ruff = next(t for t in gate["tools"] if t["name"] == "ruff")
        assert ruff["status"] == "pass", ruff["output_tail"]
        assert "baseline_debt_ignored" in \
            "\n".join(ruff["output_tail"])

    def test_new_debt_on_changed_line_fails(self, tmp_path):
        repo = self._repo_with_debt(
            tmp_path, new_line="import json\n")
        os.environ.pop("AI_DLC_EXEC_RUFF_WHOLEFILE", None)
        gate = report.run_execution_gate(
            repo, ["mod.py"], base="HEAD~1")
        ruff = next(t for t in gate["tools"] if t["name"] == "ruff")
        assert ruff["status"] == "fail"
        assert "changed-line findings" in \
            "\n".join(ruff["output_tail"])

    def test_wholefile_switch_restores_strict(self, tmp_path):
        repo = self._repo_with_debt(
            tmp_path, new_line="Y = 2\n")
        os.environ["AI_DLC_EXEC_RUFF_WHOLEFILE"] = "1"
        try:
            gate = report.run_execution_gate(
                repo, ["mod.py"], base="HEAD~1")
        finally:
            del os.environ["AI_DLC_EXEC_RUFF_WHOLEFILE"]
        ruff = next(t for t in gate["tools"] if t["name"] == "ruff")
        assert ruff["status"] == "fail"


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/pi-test-specs", ignore_errors=True)
