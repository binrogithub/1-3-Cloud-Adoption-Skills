"""P0-1② evidence-constrained review — tests for the three-record
contract (Finding with Evidence / Concern / Nothing found) and the
synthesis's per-citation confirmed:/refuted: verdict, plus P0-1①'s
concurrency default.

The false-consensus failure this constrains: an unconstrained
adversarial round optimises for agreement rather than correctness
(arXiv 2608.18167 measured it worst-of-class; the evidence-grounded
constraint best-of-class, via prompt alone).

Run:  python3 -m pytest tests/test_review_evidence.py -v
"""
import importlib.util
import sys
from pathlib import Path

# ── load plan.py as a module ────────────────────────────────────────
_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_review_evidence", _BIN / "bin" / "plan.py")


def _finding(axis: str, body: str) -> str:
    return f"Axis: {axis}\n\n{body}\n"


def test_finding_with_path_line_evidence_passes(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Finding\nthe gate reads HEAD before the diff.\n"
        "Evidence: bin/report.py:2055 — the conjunction reads "
        "merge_approved before the exec gate\n"), encoding="utf-8")
    v = plan.judge_finding_file(f, "correctness")
    assert v == {"ok": True, "kind": "finding"}


def test_finding_with_diff_hunk_evidence_passes(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Finding\nthe hunk below is the regression.\n"
        "Evidence: @@ -2055,3 +2055,4 @@ delivered = bool(...)\n"),
        encoding="utf-8")
    assert plan.judge_finding_file(f, "correctness")["ok"] is True


def test_finding_without_evidence_is_refused(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Finding\nit feels fragile around the merge gate.\n"),
        encoding="utf-8")
    v = plan.judge_finding_file(f, "correctness")
    assert v["ok"] is False
    assert "no code evidence" in v["why"]


def test_concern_with_examined_passes_as_concern(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Concern\nI suspect the timeout is too tight for slow "
        "suites, but no code line shows it.\n"
        "## Examined\n- the timeout constant and both call sites\n"),
        encoding="utf-8")
    v = plan.judge_finding_file(f, "correctness")
    assert v == {"ok": True, "kind": "concern"}


def test_concern_without_examined_fails(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness", "## Concern\na feeling with no ground.\n"),
        encoding="utf-8")
    v = plan.judge_finding_file(f, "correctness")
    assert v["ok"] is False
    assert v["kind"] == "concern"


def test_finding_plus_concern_is_refused(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Finding\none thing.\nEvidence: a.py:1 — it is there\n"
        "## Concern\nand another.\n"), encoding="utf-8")
    v = plan.judge_finding_file(f, "correctness")
    assert v["ok"] is False
    assert "exactly one" in v["why"]


def test_nothing_found_still_works(tmp_path):
    f = tmp_path / "finding.md"
    f.write_text(_finding(
        "correctness",
        "## Nothing found\n\n## Examined\n- the whole gate path\n"),
        encoding="utf-8")
    assert plan.judge_finding_file(f, "correctness")["kind"] == "nothing"


SYNTHESIS_OK = """# Synthesis

## Group — the delivery conjunction
- [correctness] — confirmed: bin/report.py:2071 — the gate joins the
  conjunction exactly as the finding's Evidence line claims

## Opposing [correctness] vs [security]
- [correctness] increases wall-clock honesty
- [security] reduces dispatch freedom

## No opposing pairs
(absent — the pair above stands)
"""


def test_synthesis_citation_with_verdict_passes(tmp_path):
    s = tmp_path / "synthesis.md"
    s.write_text(SYNTHESIS_OK, encoding="utf-8")
    v = plan.judge_synthesis_file(s, ["correctness"])
    unverified = [b for b in v["breaches"]
                  if b["kind"] == "unverified-citation"]
    assert unverified == []
    assert v["groups"][0]["verdicts"] == [
        {"finding": "correctness", "verdict": "confirmed"}]


def test_synthesis_citation_without_verdict_is_a_breach(tmp_path):
    s = tmp_path / "synthesis.md"
    s.write_text(SYNTHESIS_OK.replace(
        "— confirmed: bin/report.py:2071 — the gate joins the\n  "
        "conjunction exactly as the finding's Evidence line claims",
        "— the gate indeed joins the conjunction"), encoding="utf-8")
    v = plan.judge_synthesis_file(s, ["correctness"])
    kinds = [b["kind"] for b in v["breaches"]]
    assert "unverified-citation" in kinds


def test_synthesis_refuted_verdict_is_recorded(tmp_path):
    s = tmp_path / "synthesis.md"
    s.write_text(SYNTHESIS_OK.replace(
        "confirmed: bin/report.py:2071",
        "refuted: bin/report.py:2090"), encoding="utf-8")
    v = plan.judge_synthesis_file(s, ["correctness"])
    assert v["groups"][0]["verdicts"] == [
        {"finding": "correctness", "verdict": "refuted"}]


def test_reviewer_prompt_states_the_three_records_and_evidence():
    p = plan.reviewer_prompt("c1", "correctness",
                             {"stance": "s", "accepts": "a",
                              "refuses": "r"}, "review/c1/x/finding.md")
    assert "Evidence: <path>:<line>" in p
    assert plan.REVIEW_CONCERN_HEADING in p
    assert "refused by the round's judge" in p


def test_concurrency_default_is_four():
    # P0-1①: reviewers dispatch concurrently; 4 is the standing default
    # (Anthropic's retrospection runs 3-5 subagents at once)
    assert plan.REVIEW_CONCURRENCY_DEFAULT == 4
