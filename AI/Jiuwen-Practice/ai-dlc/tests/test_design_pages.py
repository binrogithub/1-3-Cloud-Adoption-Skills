"""PRD v9 P2-2 — D1.6 PAGES per-page matching + materialize --page,
tests.

Each design/pages.md `## ` section matches its own top-N secondary
templates (deterministic, D0 main template excluded); per-page
material lands under design-material/pages/<slug>/ with a manifest
naming the page, and standing material is never overwritten.

Run:  python3 -m pytest tests/test_design_pages.py -v
"""
import importlib.util
import json
import os
from pathlib import Path

import os as _os
_os.environ.setdefault("AI_DLC_NO_MATERIALIZE_DISPATCH", "1")

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/pages-test-specs")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tpl(od: Path, name: str, desc: str, trigger: str) -> Path:
    d = od / "design-templates" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\nod.mode: template\nod.surface: web\n"
        f"category: web\ndescription: {desc}\ntriggers:\n"
        f"  - \"{trigger}\"\n---\nbody\n")
    return d


def _setup(tmp_path: Path) -> tuple:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "index.html").write_text("<html></html>")
    td = repo / ".ai-dlc" / "tasks" / "c1"
    td.mkdir(parents=True)
    od = tmp_path / "od"
    main = _tpl(od, "web-prototype",
                "A generic multi-section website prototype.", "website")
    _tpl(od, "pricing-page",
         "A standalone pricing page with plan tiers.", "pricing page")
    _tpl(od, "blog-post", "A long-form blog article page.", "blog")
    for i in range(6):
        _tpl(od, f"dummy-{i}", f"dummy {i}", "nothing")
    (td / "state.json").write_text(json.dumps(
        {"design_selection": {"chosen": str(main / "SKILL.md"),
                              "skill_name": "Web Prototype"}}))
    (repo / "design").mkdir()
    (repo / "design" / "pages.md").write_text(
        "# Pages\n\n"
        "## Pricing\nplan tiers and faq for the saas product\n\n"
        "## Blog\nlong-form articles archive\n\n"
        "### deep heading folds into the body\n")
    for _d in od.rglob("SKILL.md"):
        (_d.parent / "example.html").write_text("<html>x</html>", encoding="utf-8")
    return repo, td, od


class TestDesignPages:
    def test_per_page_matching(self, tmp_path, monkeypatch, capsys):
        repo, td, od = _setup(tmp_path)
        plan = _load("plan_pages", _BIN / "bin" / "plan.py")
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))
        rc = plan.cmd_design_pages("c1", repo, td)
        assert rc == 0, capsys.readouterr().out
        state = json.loads((td / "state.json").read_text())
        rec = state["design_pages"]
        assert rec["main"] == "web-prototype"
        assert [p["slug"] for p in rec["pages"]] == ["pricing", "blog"]
        pricing = rec["pages"][0]["picks"][0]
        blog = rec["pages"][1]["picks"][0]
        assert pricing["dir"] == "pricing-page", pricing
        assert blog["dir"] == "blog-post", blog
        for pg in rec["pages"]:
            for pick in pg["picks"]:
                assert pick["dir"] != "web-prototype", \
                    "the D0 main template must not appear as secondary"

    def test_missing_pages_md_stops_with_remedy(self, tmp_path, capsys):
        repo, td, _od = _setup(tmp_path)
        (repo / "design" / "pages.md").unlink()
        plan = _load("plan_pages2", _BIN / "bin" / "plan.py")
        rc = plan.cmd_design_pages("c1", repo, td)
        out = json.loads(capsys.readouterr().out)
        assert rc == plan.EXIT_INCONCLUSIVE
        assert "design-specify" in out["remedy"]

    def test_no_sections_stops(self, tmp_path, capsys):
        repo, td, _od = _setup(tmp_path)
        (repo / "design" / "pages.md").write_text("# only a title\n")
        plan = _load("plan_pages3", _BIN / "bin" / "plan.py")
        rc = plan.cmd_design_pages("c1", repo, td)
        out = json.loads(capsys.readouterr().out)
        assert rc == plan.EXIT_INCONCLUSIVE
        assert "no `## ` page sections" in out["stopped"]


class TestMaterializePage:
    def _od_with_assets(self, tmp_path: Path) -> Path:
        od = tmp_path / "od2"
        d = od / "design-templates" / "pricing-page"
        (d / "assets").mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: pricing-page\nod.mode: template\n"
            "od.surface: web\n---\nbody\n")
        (d / "assets" / "tier.svg").write_text("<svg/>")
        (d / "example.html").write_text("<html>p</html>")
        return od

    def test_page_materialize_and_coexistence(self, tmp_path):
        repo, td, _od = _setup(tmp_path)
        od = self._od_with_assets(tmp_path)
        plan = _load("plan_pmat1", _BIN / "bin" / "plan.py")
        assert plan.cmd_design_materialize(
            "c1", repo, "pricing-page", od, page="pricing") == 0
        dest = plan.plane_tree(repo) / "changes" / "c1" \
            / "design-material" / "pages" / "pricing"
        man = json.loads((dest / "manifest.json").read_text())
        assert man["page"] == "pricing"
        assert any(f["path"].endswith("tier.svg") for f in man["files"])
        # re-run refuses: standing material is never overwritten
        assert plan.cmd_design_materialize(
            "c1", repo, "pricing-page", od, page="pricing") \
            == plan.EXIT_PACKAGE_INVALID
        # the main materialization coexists alongside the page's
        assert plan.cmd_design_materialize(
            "c1", repo, "pricing-page", od) == 0
        main_man = json.loads(
            (plan.plane_tree(repo) / "changes" / "c1" / "design-material"
             / "manifest.json").read_text())
        assert main_man["page"] is None

    def test_page_slug_validated(self, tmp_path):
        repo, td, _od = _setup(tmp_path)
        od = self._od_with_assets(tmp_path)
        plan = _load("plan_pmat2", _BIN / "bin" / "plan.py")
        for bad in ("../evil", "Upper", "slash/inside"):
            assert plan.cmd_design_materialize(
                "c1", repo, "pricing-page", od, page=bad) \
                == plan.EXIT_PACKAGE_INVALID, bad


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/pages-test-specs", ignore_errors=True)
