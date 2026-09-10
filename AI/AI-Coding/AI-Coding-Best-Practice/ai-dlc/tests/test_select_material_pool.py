"""select-material-pool — tests.

P1 a named answer survives an unclosed round (arbiter + second
opinion); P2 stub candidates never enter the pool nor the fallback.

Run:  python3 -m pytest tests/test_select_material_pool.py -v
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
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_smp", _BIN / "bin" / "plan.py")
report = _load("report_smp", _BIN / "bin" / "report.py")


def _od(tmp_path: Path):
    od = tmp_path / "od"
    skills = od / "skills"
    skills.mkdir(parents=True)
    # a real design candidate: SKILL.md + example.html
    rich = skills / "rich-tpl"
    rich.mkdir()
    (rich / "SKILL.md").write_text(
        "---\nname: Rich\nod.mode: prototype\nod.surface: web\n"
        "category: web\ntriggers:\n  - website\n---\n# Rich\n",
        encoding="utf-8")
    (rich / "example.html").write_text("<html>rich</html>",
                                       encoding="utf-8")
    # a standalone-flagged rich candidate (forces the arbiter path)
    narrow = skills / "narrow-tpl"
    narrow.mkdir()
    (narrow / "SKILL.md").write_text(
        "---\nname: Narrow\nod.mode: template\nod.surface: web\n"
        "category: web\ntriggers:\n  - website\n"
        "description: standalone narrow audience page\n"
        "audience: founders\n---\n# Narrow\n", encoding="utf-8")
    (narrow / "example.html").write_text("<html>n</html>",
                                         encoding="utf-8")
    # a capability stub: SKILL.md only (the frontend-dev shape)
    stub = skills / "stub-skill"
    stub.mkdir()
    (stub / "SKILL.md").write_text(
        "---\nname: Stub\nod.mode: prototype\n"
        "triggers:\n  - hero page\n---\n# Stub\n", encoding="utf-8")
    return od, rich, narrow, stub


def _repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "index.html").write_text("<html></html>", encoding="utf-8")
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    report.save_json(td / "state.json", {
        "task_id": "c1", "route": "inline", "stage": "WORK"})
    (td / "proposal.md").write_text(
        "Build a website page for a SaaS product.\n", encoding="utf-8")
    return repo, td


def _reply_frames(text):
    return [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    })]


class TestP1NamedAnswerSurvives:
    def test_timed_out_arbiter_that_named_is_judged(self, tmp_path,
                                                    monkeypatch):
        od, rich, narrow, stub = _od(tmp_path)
        repo, td = _repo(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))
        rich_path = str(rich / "SKILL.md")

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False,
                    "frames": _reply_frames(
                        rich_path + "\nbecause rich"),
                    "session_name": "s1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        sel = report.load_json(td / "state.json",
                               {})["design_selection"]
        assert sel["method"] == "judged", sel["reason"]
        assert sel["degraded"] is False
        assert sel["chosen"] == rich_path
        assert sel["round_incomplete_judged"] is True

    def test_second_opinion_named_despite_timeout(self, tmp_path,
                                                  monkeypatch):
        od, rich, narrow, stub = _od(tmp_path)
        repo, td = _repo(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))
        rich_path = str(rich / "SKILL.md")

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            if verb == "design-select":
                return {"timed_out": True, "round_complete": False,
                        "interrupted": False, "frames": [],
                        "session_name": "s1"}, 0
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False,
                    "frames": _reply_frames("rich-tpl\npick it"),
                    "session_name": "s2"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        sel = report.load_json(td / "state.json",
                               {})["design_selection"]
        assert sel["method"] == "judged-2nd", sel["reason"]
        assert sel["chosen"] == rich_path
        assert sel["degraded"] is False

    def test_unnamed_timeout_still_degrades(self, tmp_path,
                                            monkeypatch):
        od, rich, narrow, stub = _od(tmp_path)
        repo, td = _repo(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "frames": [],
                    "session_name": "sx"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        sel = report.load_json(td / "state.json",
                               {})["design_selection"]
        assert sel["method"] == "degraded"
        assert sel["chosen"] != str(stub / "SKILL.md")


class TestP2MaterialPool:
    def test_stub_filtered_from_pool(self, tmp_path):
        od, rich, narrow, stub = _od(tmp_path)
        cands = plan._scan_design_candidates(od)
        eligible, filtered = plan._filter_candidates(cands, "web")
        dirs = {c["dir"] for c in eligible}
        assert "rich-tpl" in dirs and "narrow-tpl" in dirs
        assert "stub-skill" not in dirs

    def test_fallback_skips_stub(self, tmp_path, monkeypatch):
        """Scored list headed by a stub: the degraded fallback must
        step past it to the first material-bearing candidate."""
        stub = {"dir": "stub-skill", "name": "Stub",
                "has_example_html": False}
        rich = {"dir": "rich-tpl", "name": "Rich",
                "has_example_html": True}
        pick = plan._first_unflagged([(9.0, stub), (8.0, rich)], stub)
        assert pick["dir"] == "rich-tpl"
