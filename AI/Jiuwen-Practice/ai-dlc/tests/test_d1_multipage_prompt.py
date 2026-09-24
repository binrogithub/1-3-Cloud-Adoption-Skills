"""d1-multi-page-prompt — tests.

The D1 specify prompt must demand one `## Page:` section per
proposal-named page (des5b: a four-page proposal was flattened into a
single-page pages.md, leaving D1.6/D1.7 with one page to match).

Run:  python3 -m pytest tests/test_d1_multipage_prompt.py -v
"""
import importlib.util
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_mp", _BIN / "bin" / "plan.py")
report = _load("report_mp", _BIN / "bin" / "report.py")

ARTIFACTS = ("tokens.css", "tokens.json", "components.md",
             "pages.md", "assets.md")


def _setup(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    skill = tmp_path / "tpl" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: web-prototype\n---\nbody\n")
    report.save_json(td / "state.json", {
        "task_id": "c1", "route": "inline", "stage": "WORK",
        "design_selection": {"chosen": str(skill),
                             "skill_name": "web-prototype",
                             "skill_sha256": "x"}})
    return repo, td


def test_specify_prompt_demands_page_sections(tmp_path, monkeypatch):
    repo, td = _setup(tmp_path)
    captured = {}

    def fake(change, prompt, repo_, td_, mode, timeout, generation=1):
        captured["prompt"] = prompt
        d = repo_ / "design"
        d.mkdir(exist_ok=True)
        for name in ARTIFACTS:
            (d / name).write_text("real content\n")
        return {"timed_out": False, "round_complete": True,
                "interrupted": False,
                "session_name": "design-c1-001"}, []

    monkeypatch.setattr(plan, "run_design_session", fake)
    assert plan.cmd_design_specify("c1", repo, td) == 0
    p = captured["prompt"]
    assert "## Page: <name>" in p, (
        "the prompt must name the Page: section convention")
    assert "per named page" in p, (
        "the prompt must require one section per proposal-named page")
    # the five-artifact contract line still stands
    assert "design/pages.md" in p
