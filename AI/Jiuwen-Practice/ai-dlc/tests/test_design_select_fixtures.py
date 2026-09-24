#!/usr/bin/env python3
"""Run design-select fixtures against the current implementation.
Records red/green results.  Run: python3 tests/test_design_select_fixtures.py
"""
import json, os, sys, math, re
from pathlib import Path

# import plan.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import plan

OPENDESIGN_ROOT = plan.OPENDESIGN_ROOT
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "design-select"


def _tokenize_legacy(text):
    """Legacy tokenizer for backward compat."""
    return plan._tokenize_query(text)


def run_fixture(fixture: dict) -> dict:
    """Run one fixture and return result dict."""
    change = fixture["change"]
    proposal = fixture.get("proposal", "")
    surface_class = fixture.get("surface_class", "web")

    # Build change_kw using new _extract_change_keywords logic
    query_text = change.replace("-", " ").replace("_", " ") + " " + proposal
    query_tokens = plan._tokenize_query(query_text) - plan._negated_tokens(query_text)
    query_text_for_phrase = plan._strip_negated_clauses(query_text)
    change_kw = {
        "surface_hint": surface_class if surface_class else None,
        "query_tokens": query_tokens,
        "keywords": set(t for t in query_tokens if re.match(r"^[a-z]{3,}$", t)),
        "text": query_text_for_phrase.lower(),
    }

    # Build index + IDF
    root = Path(OPENDESIGN_ROOT)
    candidates = plan._scan_design_candidates(root)
    index = plan._build_design_index(root)
    idf = index["idf"]

    # L1 filter + L2 score
    eligible, filtered = plan._filter_candidates(candidates, change_kw.get("surface_hint"))
    scored = sorted(
        ((plan._score_candidate(c, change_kw, idf), c) for c in eligible),
        key=lambda x: (x[0], plan._tiebreak_key(x[1])),
        reverse=True)

    top1 = scored[0] if scored else None
    shortlist = [c["dir"] for s, c in scored[:12]]
    expect_top1 = fixture.get("expect_top1")
    expect_in_sl = fixture.get("expect_in_shortlist") or []

    result = {
        "fixture": fixture["change"],
        "top1": {"dir": top1[1]["dir"], "score": round(top1[0], 1),
                 "kind": top1[1]["kind"]} if top1 else None,
        "shortlist": shortlist,
        "eligible": len(eligible),
        "filtered_from": len(candidates),
    }

    # Check expect_top1
    if expect_top1:
        top1_dir = top1[1]["dir"] if top1 else None
        matched = (top1_dir == expect_top1.split("/")[-1] or
                   (top1 and expect_top1 in top1[1]["path"]))
        result["expect_top1_match"] = matched
        if not matched:
            for rank, (s, c) in enumerate(scored, 1):
                if expect_top1 in c["path"] or c["dir"] == expect_top1.split("/")[-1]:
                    result["expected_rank"] = rank
                    result["expected_score"] = round(s, 1)
                    break
            else:
                result["expected_rank"] = None

    # Check expect_in_shortlist
    if expect_in_sl:
        for exp in expect_in_sl:
            exp_dir = exp.split("/")[-1]
            in_sl = any(exp in s or s == exp_dir for s in shortlist)
            result.setdefault("shortlist_hits", {})[exp] = in_sl

    # Check no-tie
    if fixture.get("assert_no_tie"):
        top_score = top1[0] if top1 else 0
        tie_count = sum(1 for s, c in scored if s == top_score)
        result["tie_count"] = tie_count
        result["no_tie_pass"] = tie_count == 1

    # Check margin below threshold: (top1 - top2) / max(top1, 1) < threshold
    if fixture.get("assert_margin_below") is not None:
        threshold = fixture["assert_margin_below"]
        if top1 and len(scored) >= 2:
            top1_score = top1[0]
            top2_score = scored[1][0]
            margin = (top1_score - top2_score) / max(top1_score, 1.0)
        else:
            margin = 0.0  # no runner-up → no margin to assert
        result["margin"] = round(margin, 4)
        result["margin_below_pass"] = margin < threshold

    # Check assert_raw_top1_is_flagged: the pure L1+L2 top1 (before any
    # gate) must be the given candidate that _needs_arbitration flags
    # (via audience/tone or standalone scope).  This nails down the
    # PRD's evidence so a silent upstream change to the candidate pool
    # or scoring weights is caught rather than leaving a dead gate in
    # the code.
    raw_flagged = fixture.get("assert_raw_top1_is_flagged")
    if raw_flagged:
        top1_dir = top1[1]["dir"] if top1 else None
        matched = (top1_dir == raw_flagged.split("/")[-1] or
                   (top1 and raw_flagged in top1[1]["path"]))
        result["raw_top1_flagged_match"] = matched
        if not matched:
            for rank, (s, c) in enumerate(scored, 1):
                if raw_flagged in c["path"] or c["dir"] == raw_flagged.split("/")[-1]:
                    result["raw_flagged_rank"] = rank
                    result["raw_flagged_score"] = round(s, 1)
                    break
            else:
                result["raw_flagged_rank"] = None

    # Check assert_design_system_excludes: the pure L1+L2 design-system
    # selection (no gate) must not pick any of the named systems.  This
    # nails down the negation fix's real failure case (country-b-restaurant
    # picking 'Dashboard' solely because 'dashboard' was a negated token
    # counted as positive signal).
    ds_excludes = fixture.get("assert_design_system_excludes")
    if ds_excludes:
        systems = [c for c in candidates if c["kind"] == "system"]
        ds = plan._select_design_system(systems, change_kw, idf)
        ds_name = ds["name"] if ds else None
        result["design_system_excludes_pass"] = \
            ds_name not in ds_excludes
        result["design_system_picked"] = ds_name

    # Check assert_not_dashboard_family: the pure L1+L2 raw top1 (before
    # any gate) must not be a dashboard-family directory — nails down the
    # negation-coverage fix so a negated '不是仪表盘' clause can no longer
    # push a dashboard candidate to the top via leftover phrase signal.
    if fixture.get("assert_not_dashboard_family"):
        DASHBOARD_FAMILY = {
            "dashboard", "live-dashboard",
            "flowai-live-dashboard-template", "github-dashboard",
            "social-media-dashboard",
            "trading-analysis-dashboard-template",
            "social-media-matrix-tracker-template",
        }
        top1_dir = top1[1]["dir"] if top1 else None
        result["not_dashboard_family_pass"] = top1_dir not in DASHBOARD_FAMILY
        result["not_dashboard_family_top1"] = top1_dir

    return result


def main():
    fixtures = sorted(FIXTURE_DIR.glob("*.json"))
    results = []
    all_pass = True
    for fp in fixtures:
        fixture = json.loads(fp.read_text())
        r = run_fixture(fixture)
        r["fixture_file"] = fp.name
        results.append(r)

        # Determine pass/fail
        pass_ = True
        if "expect_top1_match" in r and not r["expect_top1_match"]:
            pass_ = False
        if "shortlist_hits" in r:
            if not all(r["shortlist_hits"].values()):
                pass_ = False
        if "no_tie_pass" in r and not r["no_tie_pass"]:
            pass_ = False
        if "margin_below_pass" in r and not r["margin_below_pass"]:
            pass_ = False
        if "raw_top1_flagged_match" in r and not r["raw_top1_flagged_match"]:
            pass_ = False
        if "design_system_excludes_pass" in r and not r["design_system_excludes_pass"]:
            pass_ = False
        if "not_dashboard_family_pass" in r and not r["not_dashboard_family_pass"]:
            pass_ = False
        r["pass"] = pass_
        if not pass_:
            all_pass = False

        status = "✅ PASS" if pass_ else "❌ FAIL"
        print(f"{status}  {fp.name}")
        if "margin" in r:
            print(f"   margin={r['margin']} (threshold "
                  f"{fixture.get('assert_margin_below')})")
        if not pass_:
            if r.get("top1"):
                print(f"   top1: {r['top1']['dir']} (score={r['top1']['score']})")
            if r.get("expected_rank"):
                print(f"   expected rank: {r['expected_rank']} (score={r.get('expected_score')})")
            if r.get("shortlist_hits"):
                for exp, hit in r["shortlist_hits"].items():
                    if not hit:
                        print(f"   '{exp}' NOT in shortlist: {r['shortlist']}")
            if r.get("tie_count", 0) > 1:
                print(f"   tie_count: {r['tie_count']}")
            if "raw_top1_flagged_match" in r and not r["raw_top1_flagged_match"]:
                if r.get("top1"):
                    print(f"   raw top1: {r['top1']['dir']} (score={r['top1']['score']})")
                if r.get("raw_flagged_rank"):
                    print(f"   expected flagged rank: {r['raw_flagged_rank']} "
                          f"(score={r.get('raw_flagged_score')})")
            if "design_system_excludes_pass" in r and not r["design_system_excludes_pass"]:
                print(f"   design_system picked: {r.get('design_system_picked')} "
                      f"(expected to exclude "
                      f"{fixture.get('assert_design_system_excludes')})")
            if "not_dashboard_family_pass" in r and not r["not_dashboard_family_pass"]:
                print(f"   raw top1 in dashboard family: "
                      f"{r.get('not_dashboard_family_top1')} "
                      f"(expected non-dashboard)")

    print(f"\n{'ALL PASS' if all_pass else 'SOME FAIL'}: {sum(r['pass'] for r in results)}/{len(results)}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
