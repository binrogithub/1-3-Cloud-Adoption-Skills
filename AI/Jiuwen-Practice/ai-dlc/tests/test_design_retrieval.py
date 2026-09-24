"""design retrieval strengthening (PRD v9 P1-A) — tests.

Intent metadata is a scored axis (not just a tiebreak), near-duplicate
candidates collapse before the shortlist cut, and every selection
carries matched_features + locale_axis in its rubric.

Run:  python3 -m pytest tests/test_design_retrieval.py -v
"""
import importlib.util
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk(tdir: Path, name: str, desc: str, triggers=None, sidecar=None):
    d = tdir / name
    d.mkdir(parents=True)
    trig = "\n".join(f'  - "{t}"' for t in (triggers or []))
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n"
        f"triggers:\n{trig}\n---\nbody\n")
    (d / "example.html").write_text("<html></html>")
    if sidecar:
        (d / ".od-intent.json").write_text(sidecar)
    return d


def test_intent_metadata_scores_above_tiebreak(tmp_path):
    root = tmp_path
    tdir = root / "design-templates"
    _mk(tdir, "waitlist-a", "Pre-launch email capture landing",
        ["waitlist page"])
    _mk(tdir, "blog-b", "Long form articles",
        ["blog page"],
        sidecar='{"template": "blog-b", "intent_page_types": ["blog"],'
                ' "token_family": ["article"], "locale": ["en"],'
                ' "framework": ["html-css"], "co_appear": []}')
    plan = _load("plan_r1", _BIN / "bin" / "plan.py")
    kw = {"query_tokens": {"blog", "articles"}, "keywords": {"blog"},
          "surface_hint": "web", "text": "blog articles"}
    idf = {"blog": 2.0, "articles": 1.0}
    # both mention blog; the metadata carrier wins on the scored axis
    a = plan._score_candidate(
        next(c for c in plan._scan_design_candidates(root)
             if c["dir"] == "waitlist-a"), kw, idf)
    b = plan._score_candidate(
        next(c for c in plan._scan_design_candidates(root)
             if c["dir"] == "blog-b"), kw, idf)
    assert b > a


def test_locale_axis_prefers_zh_for_cjk_query(tmp_path):
    root = tmp_path
    tdir = root / "design-templates"
    _mk(tdir, "page-en", "generic page", ["page"])
    _mk(tdir, "page-zh", "generic page", ["page"],
        sidecar='{"template": "page-zh", "intent_page_types": ["page"],'
                ' "locale": ["zh"], "framework": ["html-css"],'
                ' "co_appear": []}')
    plan = _load("plan_r2", _BIN / "bin" / "plan.py")
    kw = {"query_tokens": {"页面", "page"}, "keywords": {"page"},
          "surface_hint": "web", "text": "页面 page"}
    idf = {"page": 2.0}
    en = plan._score_candidate(
        next(c for c in plan._scan_design_candidates(root)
             if c["dir"] == "page-en"), kw, idf)
    zh = plan._score_candidate(
        next(c for c in plan._scan_design_candidates(root)
             if c["dir"] == "page-zh"), kw, idf)
    assert zh > en


def test_dedup_collapses_near_duplicates():
    plan = _load("plan_r3", _BIN / "bin" / "plan.py")
    scored = [(10, {"dir": "waitlist-page"}),
              (9, {"dir": "waitlist-page-pro"}),
              (8, {"dir": "blog-post"})]
    kept, clusters = plan._dedup_scored(scored)
    assert [k[1]["dir"] for k in kept] == ["waitlist-page", "blog-post"]
    assert kept[0][1]["cluster_members"] == ["waitlist-page-pro"]
    assert set(clusters) == {"waitlist-page", "blog-post"}


def test_dedup_keeps_distinct_names():
    plan = _load("plan_r4", _BIN / "bin" / "plan.py")
    scored = [(10, {"dir": "pricing-table"}),
              (9, {"dir": "blog-post"})]
    kept, _ = plan._dedup_scored(scored)
    assert len(kept) == 2


def test_matched_features_names_the_hits():
    plan = _load("plan_r5", _BIN / "bin" / "plan.py")
    cand = {"name": "waitlist-page", "category": "marketing",
            "scenario": "launch", "triggers": ["waitlist page"],
            "intent_page_types": ["waitlist", "landing"],
            "token_family": ["email", "capture"]}
    feats = plan._matched_features(cand, {"waitlist", "email", "zzz"})
    assert feats["name"] == ["waitlist"]
    assert feats["intent_page_types"] == ["waitlist"]
    assert feats["token_family"] == ["email"]
    assert "zzz" not in str(feats)
