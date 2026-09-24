"""Acceptance tests for Epic C — D0 SELECT degraded annotation in
design_validation().

When state.json.design_selection.degraded is true (arbiter replied but
named no shortlist path, session timed out, etc.), design_validation()
must layer selection_degraded + selection_degraded_reason onto its
return dict for every branch that reads design_selection — but NOT for
the three early-exit branches (design_unmeasured, design_not_applicable,
design_declined) that fire before design_selection is relevant.

The set of design_state values (all eight) stays exactly as they were;
the two new keys are optional, backward compatible.

Run:  python3 -m pytest tests/test_design_validation_degraded.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest

# ── load report.py as a module ──────────────────────────────────────
_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


report = _load("report_test_mod_degraded", _BIN / "bin" / "report.py")

DEGRADED_REASON = (
    "degraded — arbiter session replied but named no shortlist path; "
    "using top-scored candidate (score 27.9)")


def _state_with_degraded(task_dir: Path, repo: Path, base: str,
                         change_id: str = "c1") -> dict:
    """Write a state.json with design_selection.degraded=true."""
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": "inline", "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso(),
          "design_selection": {"chosen": "x", "skill_sha256": "s",
                               "degraded": True,
                               "reason": DEGRADED_REASON}}
    report.save_json(task_dir / "state.json", st)
    return st


def _state_without_degraded(task_dir: Path, repo: Path, base: str,
                            change_id: str = "c1") -> dict:
    """Write a state.json with design_selection but degraded=false."""
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": "inline", "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso(),
          "design_selection": {"chosen": "x", "skill_sha256": "s",
                                "degraded": False,
                                "reason": "normal selection"}}
    report.save_json(task_dir / "state.json", st)
    return st


def _seed_repo(repo: Path) -> str:
    import subprocess
    repo.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["config", "user.name", "test"],
                 ["config", "user.email", "test@test"],
                 ["commit", "-q", "--allow-empty", "-m", "seed"]):
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def _write_design_artifacts(repo: Path):
    """Create the five D1 SPECIFY design artifacts."""
    design_dir = repo / "design"
    design_dir.mkdir(exist_ok=True)
    (design_dir / "tokens.css").write_text(":root{--c:#fff;}\n")
    (design_dir / "tokens.json").write_text('{"c":"#fff"}\n')
    (design_dir / "components.md").write_text("## Btn\n")
    (design_dir / "pages.md").write_text("# Home\n")
    (design_dir / "assets.md").write_text("# A\n")


# ═══ Annotated branches ══════════════════════════════════════════════

class TestDegradedAnnotation:
    """Epic C: degraded selection is surfaced on every branch that reads
    design_selection."""

    def test_design_verified_with_degraded(self, tmp_path):
        """design_verified AND selection_degraded both true — the most
        insidious real scenario (D3 all pass, but the selection itself
        was unreliable).  This is the add-maas-website situation made
        explicit."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")
        _write_design_artifacts(repo)

        # D3 verify all pass: write design_verification with all checks
        # true
        st = report.load_json(task_dir / "state.json", {})
        st["design_verification"] = {
            "checks": {"tokens_used": True, "tokens_json_valid": True,
                       "skill_sha_match": True, "no_placeholder": True,
                       "design_artifacts_exist": True,
                       "components_conform": True},
            "ts": report.now_iso()}
        report.save_json(task_dir / "state.json", st)

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_verified"
        assert dv["selection_degraded"] is True
        assert dv["selection_degraded_reason"] == DEGRADED_REASON

    def test_design_nonconforming_with_degraded(self, tmp_path):
        """design_nonconforming + degraded — both surfaced."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")
        _write_design_artifacts(repo)

        # D3 verify with a failing check
        st = report.load_json(task_dir / "state.json", {})
        st["design_verification"] = {
            "checks": {"tokens_used": False, "tokens_json_valid": True,
                       "skill_sha_match": True, "no_placeholder": True,
                       "design_artifacts_exist": True,
                       "components_conform": True},
            "ts": report.now_iso()}
        report.save_json(task_dir / "state.json", st)

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_nonconforming"
        assert dv["selection_degraded"] is True
        assert dv["selection_degraded_reason"] == DEGRADED_REASON

    def test_design_nonconforming_no_d3_with_degraded(self, tmp_path):
        """Artifacts exist but D3 hasn't run — still annotated."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")
        _write_design_artifacts(repo)

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_nonconforming"
        assert dv["selection_degraded"] is True

    def test_design_unspecified_with_degraded(self, tmp_path):
        """No artifacts, no signed record — design_unspecified + degraded."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_unspecified"
        assert dv["selection_degraded"] is True
        assert dv["selection_degraded_reason"] == DEGRADED_REASON


# ═══ Excepted branches — no annotation ═══════════════════════════════

class TestExceptedBranchesNoAnnotation:
    """The three early-exit branches fire before design_selection is
    relevant and must NOT carry the degraded annotation, even when
    design_selection.degraded is true in state."""

    def test_design_unmeasured_not_annotated(self, tmp_path):
        """design_unmeasured: surface is empty — returns before
        design_selection is ever consulted."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)

        dv = report.design_validation(task_dir, repo, st, [])
        assert dv["design_state"] == "design_unmeasured"
        assert "selection_degraded" not in dv
        assert "selection_degraded_reason" not in dv

    def test_design_not_applicable_not_annotated(self, tmp_path):
        """design_not_applicable: surface measured but no web/deck file
        — returns before design_selection is consulted."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        # a .py file — measured but not a design surface
        (repo / "app.py").write_text("print('hi')")

        dv = report.design_validation(task_dir, repo, st, ["app.py"])
        assert dv["design_state"] == "design_not_applicable"
        assert "selection_degraded" not in dv
        assert "selection_degraded_reason" not in dv

    def test_design_declined_not_annotated(self, tmp_path):
        """design_declined: a person recorded a skip — returns before
        design_selection is consulted."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")

        # record a skip in planning.json
        report.save_json(task_dir / "planning.json", {
            "design_decision": {"skip": True, "why": "not needed",
                                "decided_by": "tester",
                                "ts": report.now_iso()}})

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_declined"
        assert "selection_degraded" not in dv
        assert "selection_degraded_reason" not in dv


# ═══ Regression: no degraded field → no annotation ═══════════════════

class TestRegressionNoDegradedField:
    """When design_selection.degraded is missing or false, the return
    dict must NOT contain selection_degraded keys — backward compatible
    with callers that don't know about them."""

    def test_degraded_false_no_annotation(self, tmp_path):
        """degraded=false → no selection_degraded keys."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_without_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")
        _write_design_artifacts(repo)

        # D3 all pass
        st = report.load_json(task_dir / "state.json", {})
        st["design_verification"] = {
            "checks": {"tokens_used": True, "tokens_json_valid": True,
                       "skill_sha_match": True, "no_placeholder": True,
                       "design_artifacts_exist": True,
                       "components_conform": True},
            "ts": report.now_iso()}
        report.save_json(task_dir / "state.json", st)

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert dv["design_state"] == "design_verified"
        assert "selection_degraded" not in dv
        assert "selection_degraded_reason" not in dv

    def test_no_design_selection_no_annotation(self, tmp_path):
        """No design_selection at all → no selection_degraded keys."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        task_dir.mkdir(parents=True, exist_ok=True)
        st = {"task_id": "c1", "route": "inline", "base_sha": base,
              "change_id": "c1", "repo": str(repo.resolve()),
              "stage": "WORK", "human_state": "Working",
              "started_at": report.now_iso()}
        report.save_json(task_dir / "state.json", st)
        (repo / "index.html").write_text("<html></html>")

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        assert "selection_degraded" not in dv
        assert "selection_degraded_reason" not in dv

    def test_design_state_values_unchanged(self, tmp_path):
        """The set of possible design_state values is exactly the eight
        original states — no new states introduced."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        task_dir = repo / ".ai-dlc" / "tasks" / "c1"
        st = _state_with_degraded(task_dir, repo, base)
        (repo / "index.html").write_text("<html></html>")
        _write_design_artifacts(repo)

        st = report.load_json(task_dir / "state.json", {})
        st["design_verification"] = {
            "checks": {"tokens_used": True, "tokens_json_valid": True,
                       "skill_sha_match": True, "no_placeholder": True,
                       "design_artifacts_exist": True,
                       "components_conform": True},
            "ts": report.now_iso()}
        report.save_json(task_dir / "state.json", st)

        dv = report.design_validation(task_dir, repo, st, ["index.html"])
        expected_states = {
            "design_unspecified", "design_nonconforming",
            "design_verified", "design_declined",
            "design_not_applicable", "design_unmeasured",
            "design_applied", "design_unverified"}
        assert dv["design_state"] in expected_states
