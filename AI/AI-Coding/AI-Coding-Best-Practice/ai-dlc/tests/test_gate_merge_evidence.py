"""Acceptance tests for Epic D — gate-merge.request.json evidence
enrichment in cmd_gate().

Three linked changes inside cmd_gate()'s `if request:` branch:
  1. summary gains failed_d3_checks, selection_degraded,
     selection_degraded_reason.
  2. question text: a distinct template when selection_degraded is true
     (names the degraded reason + files); the existing design_nonconforming
     path appends file names (capped at 10) and failed D3 check names.
  3. options unchanged — still the existing 4-way / 3-way choice.

Run:  python3 -m pytest tests/test_gate_merge_evidence.py -v
"""
import importlib.util
import json
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


report = _load("report_test_mod_gate_evidence", _BIN / "bin" / "report.py")

DEGRADED_REASON = (
    "degraded — arbiter session replied but named no shortlist path; "
    "using top-scored candidate (score 27.9)")


def _seed_task(tmp_path: Path) -> Path:
    """Create a minimal task_dir with a gates/ subdirectory."""
    task_dir = tmp_path / "task"
    (task_dir / "gates").mkdir(parents=True, exist_ok=True)
    return task_dir


def _write_report(task_dir: Path, design: dict,
                  design_auto: dict | None = None):
    """Write a report.json with the given design block."""
    rep = {"outcome": "delivered", "delivered": True,
           "design": design}
    if design_auto is not None:
        rep["design_auto"] = design_auto
    report.save_json(task_dir / "report.json", rep)


def _gate_request(task_dir: Path, gate_id: str = "merge") -> dict:
    """Run cmd_gate in request mode and return the parsed request JSON."""
    rc = report.cmd_gate(
        task_dir, gate_id, decision=None, approver=None,
        rationale="", request=True, summary_file=None,
        gate_type="merge", question=None, options=None)
    assert rc == 0, "cmd_gate request mode should succeed"
    return json.loads((task_dir / "gates" / f"{gate_id}.request.json")
                      .read_text())


def _surface(files: list[str], applicable: bool = True) -> dict:
    return {"applicable": applicable,
            "surface_files": files[:50],
            "surface_files_total": len(files),
            "measured_files": len(files),
            "classes": ["web"] if applicable else []}


# ═══ selection_degraded question template ═════════════════════════════

class TestSelectionDegradedQuestion:
    """When selection_degraded is true, the question must use a distinct
    template that names the degraded reason and lists files — not the
    generic 'design %s: surface has %d web/deck files' template."""

    def test_degraded_question_contains_reason(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(["index.html", "style.css"]),
            "d3_checks": {"checks": {"tokens_used": False}, "all_pass": False}
        })
        req = _gate_request(task_dir)
        assert "selection degraded" in req["question"]
        assert DEGRADED_REASON in req["question"]
        assert "index.html" in req["question"]

    def test_degraded_question_differs_from_nonconforming(self, tmp_path):
        """A degraded result and a plain nonconforming result must NOT
        produce the identical question string."""
        # degraded fixture
        task_d = _seed_task(tmp_path / "degraded")
        _write_report(task_d, {
            "design_state": "design_nonconforming",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False}, "all_pass": False}
        })
        req_d = _gate_request(task_d)

        # plain nonconforming fixture (no degraded)
        task_n = _seed_task(tmp_path / "plain")
        _write_report(task_n, {
            "design_state": "design_nonconforming",
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False}, "all_pass": False}
        }, design_auto={"rc": 1})
        req_n = _gate_request(task_n)

        assert req_d["question"] != req_n["question"], (
            "degraded and plain nonconforming questions must differ")

    def test_degraded_question_file_truncation(self, tmp_path):
        """When surface_files exceeds 10, the question lists 10 and
        appends 'and N more'."""
        task_dir = _seed_task(tmp_path)
        files = [f"page{i}.html" for i in range(15)]
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(files),
            "d3_checks": {"checks": {}, "all_pass": False}
        })
        req = _gate_request(task_dir)
        assert "and 5 more" in req["question"]
        assert "page0.html" in req["question"]
        assert "page9.html" in req["question"]


# ═══ design_nonconforming evidence enrichment ═════════════════════════

class TestNonconformingEvidence:
    """The existing design_nonconforming (non-degraded) question path
    must append file names and failed D3 check names."""

    def test_question_includes_file_names(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "surface": _surface(["index.html", "style.css", "app.js"]),
            "d3_checks": {"checks": {"tokens_used": True},
                          "all_pass": True}
        }, design_auto={"rc": 1})
        req = _gate_request(task_dir)
        assert "index.html" in req["question"]
        assert "style.css" in req["question"]
        assert "app.js" in req["question"]

    def test_question_includes_failed_d3_check_names(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False,
                                      "no_placeholder": False,
                                      "skill_sha_match": True},
                          "all_pass": False}
        }, design_auto={"rc": 1})
        req = _gate_request(task_dir)
        assert "tokens_used" in req["question"]
        assert "no_placeholder" in req["question"]
        assert "skill_sha_match" not in req["question"].split(
            "Failed D3 checks:")[1].split("\n")[0] if \
            "Failed D3 checks:" in req["question"] else True

    def test_question_file_truncation(self, tmp_path):
        """File listing caps at 10 with 'and N more' suffix."""
        task_dir = _seed_task(tmp_path)
        files = [f"page{i}.html" for i in range(12)]
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "surface": _surface(files),
            "d3_checks": {"checks": {}, "all_pass": False}
        }, design_auto={"rc": 1})
        req = _gate_request(task_dir)
        assert "and 2 more" in req["question"]


# ═══ summary fields ═══════════════════════════════════════════════════

class TestSummaryFields:
    """The summary must carry failed_d3_checks and selection_degraded
    fields transplanted from the report's design block."""

    def test_summary_failed_d3_checks(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False,
                                      "no_placeholder": False,
                                      "skill_sha_match": True},
                          "all_pass": False}
        }, design_auto={"rc": 1})
        req = _gate_request(task_dir)
        assert req["summary"]["failed_d3_checks"] == [
            "tokens_used", "no_placeholder"]

    def test_summary_selection_degraded(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_verified",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": True},
                          "all_pass": True}
        })
        req = _gate_request(task_dir)
        assert req["summary"]["selection_degraded"] is True
        assert req["summary"]["selection_degraded_reason"] == DEGRADED_REASON

    def test_summary_no_degraded_no_key(self, tmp_path):
        """When selection_degraded is absent, the summary must not carry
        the key (backward compatible)."""
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False}, "all_pass": False}
        }, design_auto={"rc": 1})
        req = _gate_request(task_dir)
        assert "selection_degraded" not in req["summary"]
        assert "selection_degraded_reason" not in req["summary"]

    def test_summary_empty_failed_d3_checks(self, tmp_path):
        """When all D3 checks pass, failed_d3_checks is an empty list."""
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_verified",
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": True}, "all_pass": True}
        })
        req = _gate_request(task_dir)
        assert req["summary"]["failed_d3_checks"] == []


# ═══ Regression: pure-code path unaffected ═════════════════════════════

class TestRegressionPureCode:
    """A design_not_applicable (pure code) fixture must produce a question
    identical to the pre-Epic-D behavior — no evidence lines appended."""

    def test_pure_code_question_unchanged(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_not_applicable",
            "surface": _surface([], applicable=False)
        })
        req = _gate_request(task_dir)
        expected = ("Merge this delivery into the target branch? "
                    "(rationale required)")
        assert req["question"] == expected

    def test_pure_code_options_unchanged(self, tmp_path):
        """Pure code change gets the 3-way choice (no run_design_first)."""
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_not_applicable",
            "surface": _surface([], applicable=False)
        })
        req = _gate_request(task_dir)
        assert req["options"] == ["approve", "request_changes", "cancel"]

    def test_pure_code_summary_no_degraded(self, tmp_path):
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_not_applicable",
            "surface": _surface([], applicable=False)
        })
        req = _gate_request(task_dir)
        assert "selection_degraded" not in req["summary"]
        assert req["summary"]["failed_d3_checks"] == []


# ═══ Options unchanged ═════════════════════════════════════════════════

class TestOptionsUnchanged:
    """Epic D must not change the available actions — only the
    information the human sees."""

    def test_degraded_options_follow_design_warn(self, tmp_path):
        """When degraded and design_state is in warn states, options are
        the 4-way choice (same as before)."""
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_nonconforming",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": False}, "all_pass": False}
        })
        req = _gate_request(task_dir)
        assert req["options"] == ["run_design_first", "approve",
                                  "request_changes", "cancel"]

    def test_degraded_verified_options_3way(self, tmp_path):
        """When degraded but design_state is design_verified (not in warn
        states), options are the 3-way choice — options logic is
        unchanged by Epic D."""
        task_dir = _seed_task(tmp_path)
        _write_report(task_dir, {
            "design_state": "design_verified",
            "selection_degraded": True,
            "selection_degraded_reason": DEGRADED_REASON,
            "surface": _surface(["index.html"]),
            "d3_checks": {"checks": {"tokens_used": True}, "all_pass": True}
        })
        req = _gate_request(task_dir)
        assert req["options"] == ["approve", "request_changes", "cancel"]
