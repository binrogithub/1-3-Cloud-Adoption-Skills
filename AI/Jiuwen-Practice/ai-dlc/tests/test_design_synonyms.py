"""PRD v9 P2-1 — synonyms bridge axis, tests.

The synonyms sidecar key is a vocabulary bridge (zh query → en-only
template; generic words → specific page-type name). It scores 4×idf per
unique bridged token (never above a name hit at 5), merges through the
candidate scanner like every other od-intent key, dies with
AI_DLC_NO_INTENT_META, validates under metadata-validate, and reaches
the coder through fill-od-intent.py --synonyms (lowercased, deduped,
capped at 8).

Run:  python3 -m pytest tests/test_design_synonyms.py -v
"""
import json
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent

import importlib.util  # noqa: E402


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tpl(root: Path, sub: str, name: str, desc: str,
         synonyms: list[str] | None = None) -> Path:
    d = root / sub / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\nod.mode: template\nod.surface: web\n"
        f"category: web\ndescription: {desc}\n---\nbody\n")
    meta = {"template": name,
            "intent_page_types": [name],
            "token_family": [], "co_appear": [],
            "locale": ["en"], "framework": ["html-css"]}
    if synonyms is not None:
        meta["synonyms"] = synonyms
    (d / ".od-intent.json").write_text(json.dumps(meta))
    return d


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "od"
    _tpl(root, "design-templates", "docs-page",
         "Developer documentation page.", synonyms=[
             "开发者", "文档", "帮助中心", "手册", "指南",
             "教程", "知识库", "api 文档"])
    _tpl(root, "design-templates", "pm-spec-x",
         "A product spec template with Chinese prose 文档 开发者.")
    return root


class TestSynonymAxis:
    def test_carrier_wins_zh_query(self, tmp_path):
        """文档 开发者 页面 must reach the en-only docs-page through
        its curated synonyms, beating an equal-base candidate that
        merely carries the words in prose."""
        root = _tree(tmp_path)
        plan = _load("plan_syn1", _BIN / "bin" / "plan.py")
        cands = plan._scan_design_candidates(root)
        by = {c["dir"]: c for c in cands}
        kw = {"query_tokens": plan._tokenize_query("文档 开发者 页面"),
              "text": "文档 开发者 页面"}
        docs = plan._score_candidate(by["docs-page"], kw, None)
        spec = plan._score_candidate(by["pm-spec-x"], kw, None)
        assert docs > spec, (
            f"synonym carrier must win: docs={docs} spec={spec}")

    def test_synonym_scores_below_name_hit(self, tmp_path):
        """One bridged token is 4×idf — a name hit (5×idf, no idf table
        → uniform 1.0) must outrank it: the bridge never beats the
        fields the template actually carries."""
        plan = _load("plan_syn2", _BIN / "bin" / "plan.py")
        carrier = {"name": "zzz", "dir": "zzz", "triggers": [],
                   "description": "", "synonyms": ["alpha"]}
        named = {"name": "alpha-page", "dir": "alpha-page",
                 "triggers": [], "description": ""}
        kw = {"query_tokens": {"alpha"}, "text": "alpha"}
        assert plan._score_candidate(named, kw, None) > \
            plan._score_candidate(carrier, kw, None)

    def test_env_flag_kills_synonym_axis(self, tmp_path, monkeypatch):
        root = _tree(tmp_path)
        monkeypatch.setenv("AI_DLC_NO_INTENT_META", "1")
        plan = _load("plan_syn3", _BIN / "bin" / "plan.py")
        c = [x for x in plan._scan_design_candidates(root)
             if x["dir"] == "docs-page"][0]
        assert not c.get("synonyms")

    def test_matched_features_carries_synonyms(self):
        plan = _load("plan_syn4", _BIN / "bin" / "plan.py")
        cand = {"name": "docs-page", "dir": "docs-page",
                "synonyms": ["开发者", "文档"]}
        feats = plan._matched_features(cand, {"文档", "开发者"})
        assert feats.get("synonyms") == sorted({"文档", "开发者"})

    def test_metadata_validate_accepts_synonyms(self, tmp_path, capsys):
        root = _tree(tmp_path)
        plan = _load("plan_syn5", _BIN / "bin" / "plan.py")
        rc = plan.cmd_design_index(root, "metadata-validate")
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["invalid"] == 0


class TestFillerSynonyms:
    def test_fill_merges_curated_synonyms(self, tmp_path):
        """--synonyms writes the curated terms into the sidecar:
        lowercased, deduped, capped at 8; templates without an entry
        get no synonyms key."""
        root = tmp_path / "od"
        d = root / "design-templates" / "waitlist-x"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: waitlist-x\ndescription: Pre-launch capture.\n"
            "triggers:\n  - \"waitlist page\"\n---\nbody\n")
        synfile = tmp_path / "syn.json"
        synfile.write_text(json.dumps({"templates": {
            "waitlist-x": ["候补名单", "候补名单", "Early Access",
                           "a", "b", "c", "d", "e", "f", "g", "h"]}}))
        fill = _load("fill_syn", _BIN / "scripts" / "fill-od-intent.py")
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["fill-od-intent.py", "--root", str(root),
                        "--synonyms", str(synfile)]
            rc = fill.main()
        finally:
            sys.argv = old_argv
        assert rc == 0
        meta = json.loads((d / ".od-intent.json").read_text())
        assert meta["synonyms"][:3] == ["候补名单", "early access", "a"]
        assert len(meta["synonyms"]) == 8, "cap at 8"

    def test_fill_covers_both_roots_and_all_templates(self, tmp_path):
        """P2-1 batch 2: the default pass covers design-templates/ AND
        skills/, with no example.html requirement."""
        root = tmp_path / "od"
        for sub, name in (("design-templates", "tpl-no-example"),
                          ("skills", "skill-no-example")):
            d = root / sub / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: x\n---\nbody\n")
        fill = _load("fill_syn2", _BIN / "scripts" / "fill-od-intent.py")
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["fill-od-intent.py", "--root", str(root)]
            rc = fill.main()
        finally:
            sys.argv = old_argv
        assert rc == 0
        assert (root / "design-templates" / "tpl-no-example"
                / ".od-intent.json").is_file()
        assert (root / "skills" / "skill-no-example"
                / ".od-intent.json").is_file()
