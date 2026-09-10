"""des5-fixes (PRD des5) — tests.

F1 synonym phrase escalation (8×idf, below native trigger phrase 12,
no token double-count); F2 session reply parsing accepts the unique
dir name; F3 design-pages --task-dir + spec-meta section filtering;
F4 fill dry-run counter.

Run:  python3 -m pytest tests/test_des5_fixes.py -v
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

os.environ.setdefault("AI_DLC_SPECS", "/tmp/des5fix-test-specs")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_d5", _BIN / "bin" / "plan.py")
report = _load("report_d5", _BIN / "bin" / "report.py")


def _reply_frames(text: str) -> list:
    return [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    })]


class TestF1SynonymPhrase:
    def test_phrase_carrier_beats_native_trigger_competitor(self):
        """The des5 devdocs shape: a competitor's native trigger on
        帮助中心 (12×4 tokens + 5×4 rule-2 tokens = 68 uniform) must
        lose to a carrier bridging TWO verbatim phrases (8×4 + 8×5)
        plus a single-token synonym."""
        carrier = {"name": "docs-x", "dir": "docs-x", "triggers": [],
                   "description": "",
                   "synonyms": ["帮助中心", "开发者指南", "文档"]}
        competitor = {"name": "faq-x", "dir": "faq-x",
                      "triggers": ["帮助中心"], "description": ""}
        kw = {"query_tokens": plan._tokenize_query(
            "帮助中心 开发者指南 文档"),
              "text": "帮助中心 开发者指南 文档"}
        c = plan._score_candidate(carrier, kw, None)
        f = plan._score_candidate(competitor, kw, None)
        assert c > f, f"phrase carrier must win: {c} vs {f}"

    def test_phrase_not_double_counted(self):
        """"api 文档" verbatim scores exactly 8×2 tokens — the token
        rule (4×) must not re-score the phrase's tokens."""
        cand = {"name": "d", "dir": "d", "triggers": [],
                "description": "", "synonyms": ["api 文档"]}
        kw = {"query_tokens": {"api", "文档"}, "text": "api 文档"}
        assert plan._score_candidate(cand, kw, None) == 16.0

    def test_single_token_synonym_unchanged(self):
        cand = {"name": "d", "dir": "d", "triggers": [],
                "description": "", "synonyms": ["alpha"]}
        kw = {"query_tokens": {"alpha"}, "text": "alpha beta"}
        # single token → token rule only (4.0), no phrase escalation
        assert plan._score_candidate(cand, kw, None) == 4.0


class TestF2NamedPick:
    SHORT = [
        {"path": "/od/design-templates/waitlist-page/SKILL.md",
         "dir": "waitlist-page"},
        {"path": "/od/design-templates/waitlist-page-pro/SKILL.md",
         "dir": "waitlist-page-pro"},
        {"path": "/od/skills/docs-page/SKILL.md", "dir": "docs-page"},
    ]

    def test_full_path_wins(self):
        r = plan._session_named_pick(
            "use /od/skills/docs-page/SKILL.md because docs", self.SHORT)
        assert r["dir"] == "docs-page"

    def test_name_only_accepted(self):
        r = plan._session_named_pick(
            "I would choose docs-page for this one.", self.SHORT)
        assert r["dir"] == "docs-page"

    def test_suffix_name_not_swallowed(self):
        """waitlist-page must not match a reply naming
        waitlist-page-pro."""
        r = plan._session_named_pick("go with waitlist-page-pro", self.SHORT)
        assert r["dir"] == "waitlist-page-pro"
        r2 = plan._session_named_pick(
            "waitlist-page-pro fits best", self.SHORT)
        assert r2 is None or r2["dir"] == "waitlist-page-pro"

    def test_no_match_returns_none(self):
        assert plan._session_named_pick("cannot decide", self.SHORT) is None


class TestF2SelectIntegration:
    """A name-only arbiter reply is a judged pick, not a degrade."""

    def _setup(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config",
                        "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(repo), "config",
                        "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q",
                        "--allow-empty", "-m", "seed"], check=True)
        (repo / "index.html").write_text("<html></html>")
        td = repo / ".ai-dlc" / "tasks" / "c1"
        td.mkdir(parents=True)
        report.save_json(td / "state.json", {
            "task_id": "c1", "route": "inline", "stage": "WORK"})
        (td / "proposal.md").write_text(
            "Build a pricing page for a SaaS product.\n", encoding="utf-8")
        od = tmp_path / "od"
        skills = od / "skills"
        skills.mkdir(parents=True)
        for d, name, trig, desc in (
                ("pricing-page", "Pricing Page", "pricing page",
                 "A standalone pricing page — plan tiers and FAQ."),
                ("web-prototype", "Web Prototype", "website",
                 "A generic multi-section website prototype.")):
            (skills / d).mkdir()
            (skills / d / "SKILL.md").write_text(
                f"---\nname: {name}\nod.mode: "
                f"{'template' if d == 'pricing-page' else 'prototype'}"
                f"\nod.surface: web\ncategory: web\ntriggers:\n"
                f"  - {trig}\ndescription: {desc}\n---\n# {name}\n",
                encoding="utf-8")
        for i in range(8):
            (skills / f"dummy-{i}").mkdir()
            (skills / f"dummy-{i}" / "SKILL.md").write_text(
                "---\nname: D%d\nod.mode: prototype\nod.surface: web\n"
                "category: web\n---\n# D%d\n" % (i, i), encoding="utf-8")
        for _d in (od).rglob("SKILL.md"):
            (_d.parent / "example.html").write_text("<html>x</html>", encoding="utf-8")
        return repo, td, od

    def test_name_only_first_reply_is_judged(self, tmp_path, monkeypatch):
        repo, td, od = self._setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _reply_frames(
                        "web-prototype\ngeneric fits"),
                    "session_name": "s1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        sel = report.load_json(td / "state.json", {})["design_selection"]
        assert sel["method"] == "judged", sel["reason"]
        assert sel["degraded"] is False
        assert sel["skill_name"] == "Web Prototype"

    def test_name_only_second_opinion_rescues(self, tmp_path, monkeypatch):
        repo, td, od = self._setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            if verb == "design-select":
                return {"timed_out": True, "round_complete": False,
                        "interrupted": False, "frames": [],
                        "session_name": "s1"}, 0
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _reply_frames("web-prototype"),
                    "session_name": "s2"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        sel = report.load_json(td / "state.json", {})["design_selection"]
        assert sel["method"] == "judged-2nd"
        assert sel["second_opinion"]["pick"] == "web-prototype"


class TestF3PagesParsing:
    def _md(self, tmp_path, text):
        f = tmp_path / "pages.md"
        f.write_text(text, encoding="utf-8")
        return f

    def test_page_prefix_sections_preferred_and_stripped(self, tmp_path):
        f = self._md(tmp_path, (
            "# Pages\n\n"
            "## Page: Pricing\nplan tiers\n\n"
            "## Responsive Behavior Summary\nbreakpoints\n\n"
            "## Accent Usage Audit\nusages\n\n"
            "## Page: Blog\narticles\n"))
        pages, dropped = plan._parse_pages_md(f)
        assert [p["slug"] for p in pages] == ["pricing", "blog"]
        assert pages[0]["title"] == "Pricing"
        assert dropped == 2

    def test_meta_blacklist_without_prefix(self, tmp_path):
        f = self._md(tmp_path, (
            "# Pages\n\n## Pricing\nplan tiers\n\n"
            "## Interaction Flow\nclicks\n"))
        pages, dropped = plan._parse_pages_md(f)
        assert [p["slug"] for p in pages] == ["pricing"]
        assert dropped == 1

    def test_all_meta_falls_back_to_all_sections(self, tmp_path):
        f = self._md(tmp_path, "# Pages\n\n## Audit One\nx\n\n## Audit Two\ny\n")
        pages, dropped = plan._parse_pages_md(f)
        assert len(pages) == 2 and dropped == 0

    def test_fullwidth_prefix_colon(self, tmp_path):
        f = self._md(tmp_path, "# Pages\n\n## Page：定价\n套餐\n\n## 审计 Audit\nx\n")
        pages, dropped = plan._parse_pages_md(f)
        assert len(pages) == 1 and dropped == 1

    def test_cli_has_task_dir_flag(self, capsys):
        old = sys.argv
        try:
            sys.argv = ["plan.py", "design-pages", "--help"]
            import contextlib
            with contextlib.suppress(SystemExit):
                plan.main()
            out = capsys.readouterr().out
            assert "--task-dir" in out
        finally:
            sys.argv = old


class TestF4DryRunCounter:
    def test_dry_run_counts(self, tmp_path, capsys):
        root = tmp_path / "od"
        d = root / "design-templates" / "waitlist-x"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: waitlist-x\ndescription: Pre-launch capture.\n"
            "triggers:\n  - \"waitlist page\"\n---\nbody\n")
        fill = _load("fill_d5", _BIN / "scripts" / "fill-od-intent.py")
        old = sys.argv
        try:
            sys.argv = ["fill-od-intent.py", "--root", str(root),
                        "--dry-run"]
            assert fill.main() == 0
        finally:
            sys.argv = old
        assert "would write 1 sidecars" in capsys.readouterr().out


def teardown_module(_):
    import shutil
    shutil.rmtree("/tmp/des5fix-test-specs", ignore_errors=True)
