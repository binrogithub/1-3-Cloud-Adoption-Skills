"""PRD des5 残留① — D1.7 PAGE-SPECIFY, tests.

One ui-designer session turns the design-pages picks into per-page
specs under design/pages/<slug>.md; skill shas pinned per page; the
outcome gate is the mechanical existence check; without design_pages
it stops inconclusive with a remedy; the page count is capped.

Run:  python3 -m pytest tests/test_page_specify.py -v
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/pgspec-test-specs")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_ps", _BIN / "bin" / "plan.py")
report = _load("report_ps", _BIN / "bin" / "report.py")


def _setup(tmp_path: Path, n_pages: int = 2):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "index.html").write_text("<html></html>")
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    od = tmp_path / "od"
    pages = []
    for i, name in enumerate(["pricing", "blog", "contact",
                              "about"][:n_pages]):
        d = od / "design-templates" / f"{name}-tpl"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}-tpl\nod.mode: template\n"
            "od.surface: web\n---\nbody\n", encoding="utf-8")
        pages.append({"title": name.title(), "slug": name,
                      "query_tokens": [name],
                      "picks": [{"dir": f"{name}-tpl",
                                 "name": f"{name}-tpl",
                                 "path": str(d / "SKILL.md"),
                                 "score": 10.0,
                                 "matched_features": {}}]})
    report.save_json(td / "state.json", {
        "task_id": "c1", "route": "inline", "stage": "WORK",
        "design_pages": {"main": "web-prototype", "pages": pages}})
    return repo, td, pages


def _fake_session(files_to_write: dict):
    """A run_design_session fake that writes the given files into the
    repo and reports a complete round."""

    def fake(change, prompt, repo, task_dir, mode, timeout):
        for rel, text in files_to_write.items():
            f = repo / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        return {"timed_out": False, "round_complete": True,
                "interrupted": False, "session_name": "design-c1-001"}, \
            []
    return fake


class TestPageSpecify:
    def test_specs_written_and_pinned(self, tmp_path, monkeypatch):
        repo, td, pages = _setup(tmp_path)
        monkeypatch.setattr(plan, "run_design_session", _fake_session({
            "design/pages/pricing.md": "# Pricing spec\nreal content\n",
            "design/pages/blog.md": "# Blog spec\nreal content\n"}))
        assert plan.cmd_design_pages_specify("c1", repo, td) == 0
        st = report.load_json(td / "state.json", {})
        rec = st["design_page_specs"]
        assert rec["all_written"] is True
        assert [e["slug"] for e in rec["pages"]] == ["pricing", "blog"]
        assert all(e["skill_sha256"] for e in rec["pages"])
        assert (repo / "design" / "pages" / "pricing.md").is_file()

    def test_missing_file_is_inconclusive(self, tmp_path, monkeypatch):
        repo, td, pages = _setup(tmp_path)
        monkeypatch.setattr(plan, "run_design_session", _fake_session({
            "design/pages/pricing.md": "ok\n"}))  # blog.md never written
        assert plan.cmd_design_pages_specify(
            "c1", repo, td) == plan.EXIT_INCONCLUSIVE
        st = report.load_json(td / "state.json", {})
        assert st["design_page_specs"]["all_written"] is False

    def test_no_design_pages_stops_with_remedy(self, tmp_path, capsys):
        repo, td, pages = _setup(tmp_path)
        st = report.load_json(td / "state.json", {})
        del st["design_pages"]
        report.save_json(td / "state.json", st)
        rc = plan.cmd_design_pages_specify("c1", repo, td)
        out = json.loads(capsys.readouterr().out)
        assert rc == plan.EXIT_INCONCLUSIVE
        assert "design-pages" in out["remedy"]

    def test_timeout_no_record(self, tmp_path, monkeypatch):
        repo, td, pages = _setup(tmp_path)

        def fake(change, prompt, repo_, td_, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False}, []

        monkeypatch.setattr(plan, "run_design_session", fake)
        assert plan.cmd_design_pages_specify(
            "c1", repo, td) == plan.EXIT_INCONCLUSIVE
        st = report.load_json(td / "state.json", {})
        assert "design_page_specs" not in st

    def test_cap_three_pages(self, tmp_path, monkeypatch):
        repo, td, pages = _setup(tmp_path, n_pages=4)
        files = {f"design/pages/{p['slug']}.md": "spec\n"
                 for p in pages[:3]}
        captured = {}

        def fake(change, prompt, repo_, td_, mode, timeout):
            captured["prompt"] = prompt
            for rel, text in files.items():
                f = repo_ / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text, encoding="utf-8")
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "session_name": "design-c1-001"}, []

        monkeypatch.setattr(plan, "run_design_session", fake)
        assert plan.cmd_design_pages_specify("c1", repo, td) == 0
        st = report.load_json(td / "state.json", {})
        rec = st["design_page_specs"]
        assert len(rec["pages"]) == 3, "the run is capped at 3 pages"
        # the session was asked for exactly the capped three — the
        # fourth page never reaches the prompt
        for slug in ("pricing", "blog", "contact"):
            assert f"design/pages/{slug}.md" in captured["prompt"]
        assert "design/pages/about.md" not in captured["prompt"]


class TestSynonymsBatch2:
    def test_batch2_present_and_bounded(self):
        data = json.loads(
            (_BIN / "scripts" / "od-synonyms.json").read_text())
        t = data["templates"]
        for name in ("team-okrs", "meeting-notes", "weekly-update",
                     "x-research", "eng-runbook"):
            assert name in t, name
            assert 1 <= len(t[name]) <= 8
        # discipline: no batch2 entry may carry a competing family's
        # token (docs owns 文档/手册, kanban owns 看板, dashboard owns
        # 管理面板)
        for name in ("meeting-notes", "weekly-update", "x-research",
                     "eng-runbook"):
            joined = " ".join(t[name])
            for banned in ("文档", "手册", "看板", "管理面板", "仪表盘"):
                assert banned not in joined, (name, banned)


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/pgspec-test-specs", ignore_errors=True)
