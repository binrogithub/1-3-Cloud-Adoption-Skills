"""Safety tests for the workflow fan-out runner (scripts/workflow).

These tests verify the workflow delegation contract from Task 6 of the
approved implementation plan:

  * Overlapping / non-disjoint scopes are rejected *before* any worker starts
    (``invalid_manifest`` with zero delegate calls).
  * When the fraction of failed items exceeds 30%% the run aborts with
    ``reclassify_premium``.
  * Concurrency has a hard cap (default 3, configurable but never above
    ``MAX_CONCURRENCY`` which is at most 8).
  * The per-item results array is in input order regardless of completion order.
  * An aggregate verification timeout is enforced.
  * Per-item result files are recorded under
    ``~/.claude-hybrid/workflows/<run-id>/<item-id>.json`` with mode 0600.
  * A successful fanout returns ``status == "success"`` with per-item results.
  * The fallback path is never invoked (audit ``fallback`` is always false).
  * ``suborchestrate`` mode passes the whole brief to a single bounded delegate
    call.
  * Audit JSONL records ``route == "maas"``, ``model == "glm-5.2"`` and
    ``fallback is False``.

The runner is imported as a Python module via importlib so we can unit-test its
pure functions and inject a fake delegate instead of spawning a real subprocess.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "scripts" / "workflow"
SCHEMA_PATH = ROOT / "assets" / "manifest-schema.json"

MODEL = "glm-5.2"


# ---------------------------------------------------------------------------
# Module loading fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def workflow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Load scripts/workflow as a Python module.

    The script is a ``#!/usr/bin/env python3`` file that is also valid as a
    module. We load it via importlib so the tests can call ``run``,
    ``bounded_concurrency`` etc. directly. A fresh import each test avoids state
    leakage. The workflow directory is pointed into tmp_path so tests never
    touch the real HOME.
    """
    if not WORKFLOW_PATH.exists():
        pytest.fail("scripts/workflow does not exist yet")
    # The script has no .py extension, so we must supply a SourceFileLoader
    # explicitly — spec_from_file_location cannot infer one otherwise.
    loader = importlib.machinery.SourceFileLoader(
        "workflow_under_test", str(WORKFLOW_PATH)
    )
    spec = importlib.util.spec_from_loader("workflow_under_test", loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["workflow_under_test"] = mod
    spec.loader.exec_module(mod)
    # Point workflow + audit dirs into tmp_path so tests never touch real HOME.
    hybrid_dir = tmp_path / ".claude-hybrid"
    monkeypatch.setattr(mod, "HYBRID_DIR", hybrid_dir)
    monkeypatch.setattr(mod, "WORKFLOWS_DIR", hybrid_dir / "workflows")
    monkeypatch.setattr(mod, "AUDIT_FILE", hybrid_dir / "route-audit.jsonl")
    yield mod
    sys.modules.pop("workflow_under_test", None)


@pytest.fixture()
def schema() -> dict:
    if not SCHEMA_PATH.exists():
        pytest.fail("assets/manifest-schema.json does not exist yet")
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Fake delegate
# ---------------------------------------------------------------------------


class FakeDelegate:
    """A stand-in for the single-task delegate runner.

    Records every call and can be configured to fail specific items (by index)
    or to introduce a per-item delay so completion order differs from input
    order. Each ``__call__`` returns a dict mimicking what the real delegate
    runner produces::

        {
          "status": "success" | "needs_escalation" | ...,
          "model": "glm-5.2",
          "summary": str,
          "files_changed": list[str],
          "tokens": {"in": int, "out": int},
          "duration_s": float,
        }
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._fail_indices: set[int] = set()
        self._delay_indices: dict[int, float] = {}
        self._fail_mode: str = "index"  # index | count
        self._fail_count: int = 0
        self._calls_made: int = 0

    # --- configuration -----------------------------------------------------

    def fail_items(self, count: int, *, total: int | None = None) -> None:
        """Configure the delegate to fail ``count`` items out of ``total``.

        With ``total`` given, the first ``count`` items (by input index) fail.
        Without ``total``, the first ``count`` calls fail regardless of index.
        """
        self._fail_mode = "count"
        self._fail_count = count
        self._calls_made = 0

    def fail_indices(self, indices: set[int]) -> None:
        """Fail exactly the items at the given 0-based input indices."""
        self._fail_mode = "index"
        self._fail_indices = set(indices)

    def delay_item(self, index: int, seconds: float) -> None:
        """Make item ``index`` sleep for ``seconds`` before completing.

        Used to force non-input completion order so we can verify deterministic
        result ordering.
        """
        self._delay_indices[index] = seconds

    # --- the callable ------------------------------------------------------

    def __call__(self, brief: dict, *, model: str, max_turns: int,
                 timeout: float, cwd: str | None = None,
                 run_id: str | None = None, item_id: str | None = None,
                 item_index: int = -1) -> dict:
        call = {
            "brief": brief,
            "model": model,
            "max_turns": max_turns,
            "timeout": timeout,
            "cwd": cwd,
            "run_id": run_id,
            "item_id": item_id,
            "item_index": item_index,
        }
        self.calls.append(call)

        # Optional delay to scramble completion order.
        delay = self._delay_indices.get(item_index, 0.0)
        if delay > 0:
            import time
            time.sleep(delay)

        # Decide success/failure.
        fail = False
        if self._fail_mode == "index":
            fail = item_index in self._fail_indices
        elif self._fail_mode == "count":
            if self._calls_made < self._fail_count:
                fail = True
            self._calls_made += 1

        if fail:
            return {
                "status": "needs_escalation",
                "model": model,
                "summary": "delegate failed",
                "files_changed": [],
                "tokens": {"in": 10, "out": 0},
                "duration_s": 0.01,
            }
        return {
            "status": "success",
            "model": model,
            "summary": f"done: {brief.get('goal', '')}",
            "files_changed": brief.get("scope", []),
            "tokens": {"in": 100, "out": 50},
            "duration_s": 0.01,
        }


@pytest.fixture()
def delegate(workflow):
    """A FakeDelegate wired into the workflow module as the delegate callable."""
    fd = FakeDelegate()
    workflow.set_delegate_factory(lambda **kw: fd)
    return fd


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _item(goal: str, scope: list[str], **extra) -> dict:
    item = {
        "task_type": "code_generation",
        "goal": goal,
        "scope": scope,
        "acceptance": "true",
    }
    item.update(extra)
    return item


def fanout(items: list[dict], **overrides) -> dict:
    """Return a valid fanout manifest with optional overrides."""
    manifest = {
        "mode": "fanout",
        "run_id": "run-test-0001",
        "items": items,
        "concurrency": 3,
    }
    manifest.update(overrides)
    return manifest


def fanout_five() -> dict:
    """Five items with disjoint scopes — the canonical 5-item fanout."""
    return fanout(items=[
        _item("task-0", ["src/a.py"]),
        _item("task-1", ["src/b.py"]),
        _item("task-2", ["src/c.py"]),
        _item("task-3", ["src/d.py"]),
        _item("task-4", ["src/e.py"]),
    ])


def suborchestrate(**overrides) -> dict:
    manifest = {
        "mode": "suborchestrate",
        "run_id": "run-sub-0001",
        "brief": {
            "task_type": "docs",
            "goal": "orchestrate the whole feature",
            "scope": ["src/"],
            "acceptance": "true",
        },
        "max_turns": 20,
    }
    manifest.update(overrides)
    return manifest


# ---------------------------------------------------------------------------
# Disjoint scope enforcement
# ---------------------------------------------------------------------------


def test_overlapping_scopes_are_rejected_before_workers_start(workflow, delegate):
    manifest = fanout(items=[{"scope": ["src/a.py"]}, {"scope": ["src/a.py"]}])
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_disjoint_scopes_are_accepted(workflow, delegate):
    manifest = fanout(items=[
        _item("t0", ["src/a.py"]),
        _item("t1", ["src/b.py", "tests/test_b.py"]),
        _item("t2", ["src/c.py"]),
    ])
    result = workflow.run(manifest)
    assert result["status"] != "invalid_manifest"
    assert len(delegate.calls) == 3


def test_partial_overlap_in_subpath_is_rejected(workflow, delegate):
    """Any single path appearing in two items' scope must be rejected."""
    manifest = fanout(items=[
        _item("t0", ["src/a.py", "src/shared.py"]),
        _item("t1", ["src/b.py"]),
        _item("t2", ["src/shared.py", "src/c.py"]),
    ])
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_empty_scope_items_do_not_conflict(workflow, delegate):
    """Two read-only items with empty scopes are not a scope conflict."""
    manifest = fanout(items=[
        _item("t0", [], task_type="docs"),
        _item("t1", [], task_type="docs"),
    ])
    result = workflow.run(manifest)
    assert result["status"] != "invalid_manifest"
    assert len(delegate.calls) == 2


# ---------------------------------------------------------------------------
# Remainder > 30% aborts
# ---------------------------------------------------------------------------


def test_remainder_over_thirty_percent_aborts(workflow, delegate):
    delegate.fail_items(2, total=5)
    result = workflow.run(fanout_five())
    assert result["status"] == "reclassify_premium"


def test_remainder_at_thirty_percent_succeeds(workflow, delegate):
    """Exactly 30% failure (e.g. 3 of 10) must NOT abort — the threshold is
    strictly greater than 30%."""
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(10)]
    delegate.fail_indices({0, 1, 2})  # 3 of 10 == 30%
    result = workflow.run(fanout(items=items))
    assert result["status"] == "success"


def test_remainder_under_thirty_percent_succeeds(workflow, delegate):
    delegate.fail_indices({0})  # 1 of 5 == 20%
    result = workflow.run(fanout_five())
    assert result["status"] == "success"


def test_all_failures_abort(workflow, delegate):
    delegate.fail_items(5, total=5)
    result = workflow.run(fanout_five())
    assert result["status"] == "reclassify_premium"


def test_reclassify_result_includes_failed_fraction(workflow, delegate):
    delegate.fail_items(2, total=5)
    result = workflow.run(fanout_five())
    assert result["status"] == "reclassify_premium"
    assert "failed" in result
    assert "total" in result
    assert result["failed"] == 2
    assert result["total"] == 5


# ---------------------------------------------------------------------------
# Concurrency hard cap
# ---------------------------------------------------------------------------


def test_concurrency_default_is_three(workflow):
    assert workflow.DEFAULT_CONCURRENCY == 3


def test_concurrency_has_hard_cap(workflow):
    assert workflow.MAX_CONCURRENCY <= 8
    assert workflow.MAX_CONCURRENCY >= 3


def test_bounded_concurrency_clamps_to_max(workflow):
    assert workflow.bounded_concurrency(99) == workflow.MAX_CONCURRENCY
    assert workflow.bounded_concurrency(workflow.MAX_CONCURRENCY) == workflow.MAX_CONCURRENCY


def test_bounded_concurrency_clamps_to_min_one(workflow):
    assert workflow.bounded_concurrency(0) == 1
    assert workflow.bounded_concurrency(-5) == 1


def test_bounded_concurrency_respects_requested(workflow):
    if workflow.MAX_CONCURRENCY > 4:
        assert workflow.bounded_concurrency(4) == 4
    assert workflow.bounded_concurrency(1) == 1
    assert workflow.bounded_concurrency(2) == 2


def test_manifest_concurrency_above_cap_is_clamped(workflow, delegate):
    manifest = fanout_five()
    manifest["concurrency"] = 999
    result = workflow.run(manifest)
    assert result["status"] == "success"
    # All items still ran (concurrency was clamped, not rejected).
    assert len(delegate.calls) == 5


def test_concurrency_never_exceeds_hard_cap(workflow, delegate, monkeypatch):
    """Track the peak number of concurrent in-flight delegate calls."""
    import threading

    peak = {"value": 0, "current": 0}
    lock = threading.Lock()
    real_delegate = delegate

    def counting_delegate(brief, **kw):
        with lock:
            peak["current"] += 1
            peak["value"] = max(peak["value"], peak["current"])
        try:
            return real_delegate(brief, **kw)
        finally:
            with lock:
                peak["current"] -= 1

    workflow.set_delegate_factory(lambda **kw: counting_delegate)

    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(8)]
    manifest = fanout(items=items, concurrency=999)
    result = workflow.run(manifest)
    assert result["status"] == "success"
    assert peak["value"] <= workflow.MAX_CONCURRENCY


# ---------------------------------------------------------------------------
# Deterministic item result order
# ---------------------------------------------------------------------------


def test_results_are_in_input_order_regardless_of_completion(workflow, delegate):
    """Item 0 is delayed so it finishes last, but results[0] must still
    correspond to item 0."""
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(5)]
    delegate.delay_item(0, 0.15)
    result = workflow.run(fanout(items=items, concurrency=3))
    assert result["status"] == "success"
    results = result["results"]
    assert len(results) == 5
    for i, r in enumerate(results):
        assert f"task-{i}" in r["summary"]


def test_results_indexed_by_input_position(workflow, delegate):
    items = [
        _item("alpha", ["src/a.py"]),
        _item("beta", ["src/b.py"]),
        _item("gamma", ["src/c.py"]),
    ]
    # Delay beta so it finishes after gamma.
    delegate.delay_item(1, 0.15)
    result = workflow.run(fanout(items=items, concurrency=3))
    assert result["status"] == "success"
    assert "alpha" in result["results"][0]["summary"]
    assert "beta" in result["results"][1]["summary"]
    assert "gamma" in result["results"][2]["summary"]


def test_failed_items_keep_input_position(workflow, delegate):
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(5)]
    delegate.fail_indices({1, 3})
    result = workflow.run(fanout(items=items))
    # 2 of 5 = 40% which is > 30%, so the run aborts.
    assert result["status"] == "reclassify_premium"
    # Even on abort, partial results (if any) must be in input order.
    if "results" in result and result["results"]:
        for r in result["results"]:
            assert "status" in r


def test_single_failure_position_preserved(workflow, delegate):
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(5)]
    delegate.fail_indices({2})  # 1/5 = 20% <= 30%
    result = workflow.run(fanout(items=items))
    assert result["status"] == "success"
    results = result["results"]
    assert results[2]["status"] == "needs_escalation"
    for i in (0, 1, 3, 4):
        assert results[i]["status"] == "success"


# ---------------------------------------------------------------------------
# Per-item result files
# ---------------------------------------------------------------------------


def test_per_item_files_recorded_with_mode_0600(workflow, delegate, tmp_path):
    manifest = fanout_five()
    result = workflow.run(manifest)
    assert result["status"] == "success"
    run_id = manifest["run_id"]
    wf_dir = workflow.WORKFLOWS_DIR / run_id
    assert wf_dir.is_dir()
    files = sorted(wf_dir.glob("*.json"))
    assert len(files) == 5
    for f in files:
        assert f.stat().st_mode & 0o777 == 0o600
        data = json.loads(f.read_text())
        assert "status" in data
        assert data["model"] == MODEL


def test_per_item_files_named_by_item_id(workflow, delegate):
    items = [
        _item("task-0", ["src/a.py"], item_id="item-aaa"),
        _item("task-1", ["src/b.py"], item_id="item-bbb"),
    ]
    manifest = fanout(items=items)
    result = workflow.run(manifest)
    assert result["status"] == "success"
    run_id = manifest["run_id"]
    wf_dir = workflow.WORKFLOWS_DIR / run_id
    assert (wf_dir / "item-aaa.json").exists()
    assert (wf_dir / "item-bbb.json").exists()


def test_per_item_files_use_stable_default_ids(workflow, delegate):
    """When items omit item_id, stable ids (e.g. item-000, item-001) are used."""
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(3)]
    manifest = fanout(items=items)
    result = workflow.run(manifest)
    assert result["status"] == "success"
    run_id = manifest["run_id"]
    wf_dir = workflow.WORKFLOWS_DIR / run_id
    # Stable zero-padded ids.
    assert (wf_dir / "item-000.json").exists()
    assert (wf_dir / "item-001.json").exists()
    assert (wf_dir / "item-002.json").exists()


def test_workflow_dir_mode_0700(workflow, delegate):
    manifest = fanout_five()
    workflow.run(manifest)
    run_id = manifest["run_id"]
    wf_dir = workflow.WORKFLOWS_DIR / run_id
    assert wf_dir.is_dir()
    assert wf_dir.stat().st_mode & 0o777 == 0o700


# ---------------------------------------------------------------------------
# Aggregate verification timeout
# ---------------------------------------------------------------------------


def test_aggregate_verification_timeout_enforced(workflow, delegate):
    """The manifest may specify an aggregate verification timeout; the runner
    must accept and propagate it (not hang indefinitely)."""
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(3)]
    manifest = fanout(items=items, verification_timeout=5.0)
    result = workflow.run(manifest)
    assert result["status"] == "success"
    assert "duration_s" in result


def test_per_item_timeout_propagated(workflow, delegate):
    items = [_item(f"task-{i}", [f"src/f{i}.py"]) for i in range(3)]
    manifest = fanout(items=items, item_timeout=10.0)
    result = workflow.run(manifest)
    assert result["status"] == "success"
    for call in delegate.calls:
        assert call["timeout"] == 10.0


# ---------------------------------------------------------------------------
# Successful fanout
# ---------------------------------------------------------------------------


def test_successful_fanout_returns_success_with_results(workflow, delegate):
    result = workflow.run(fanout_five())
    assert result["status"] == "success"
    assert "results" in result
    assert len(result["results"]) == 5
    for r in result["results"]:
        assert r["status"] == "success"
        assert r["model"] == MODEL


def test_successful_fanout_result_shape(workflow, delegate):
    result = workflow.run(fanout_five())
    assert result["status"] == "success"
    assert result["model"] == MODEL
    assert "run_id" in result
    assert "duration_s" in result
    assert isinstance(result["duration_s"], (int, float))
    assert "results" in result
    assert "failed" in result
    assert "total" in result
    assert result["failed"] == 0
    assert result["total"] == 5


def test_fanout_calls_delegate_once_per_item(workflow, delegate):
    workflow.run(fanout_five())
    assert len(delegate.calls) == 5
    for call in delegate.calls:
        assert call["model"] == MODEL


def test_fanout_model_is_always_glm_5_2(workflow, delegate):
    workflow.run(fanout_five())
    for call in delegate.calls:
        assert call["model"] == MODEL


# ---------------------------------------------------------------------------
# Fallback is never invoked
# ---------------------------------------------------------------------------


def test_fallback_never_invoked_on_success(workflow, delegate):
    result = workflow.run(fanout_five())
    assert result["status"] == "success"
    assert result.get("fallback") is False


def test_fallback_never_invoked_on_abort(workflow, delegate):
    delegate.fail_items(4, total=5)
    result = workflow.run(fanout_five())
    assert result["status"] == "reclassify_premium"
    assert result.get("fallback") is False


def test_fallback_never_invoked_on_invalid_manifest(workflow, delegate):
    manifest = fanout(items=[{"scope": ["x"]}, {"scope": ["x"]}])
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert result.get("fallback") is False


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@pytest.fixture()
def audit_lines(workflow, delegate, tmp_path):
    workflow.run(fanout_five())
    af = workflow.AUDIT_FILE
    if not af.exists():
        return []
    return [json.loads(line) for line in af.read_text().splitlines() if line.strip()]


def test_audit_file_has_mode_0600(workflow, delegate):
    workflow.run(fanout_five())
    af = workflow.AUDIT_FILE
    assert af.exists()
    assert af.stat().st_mode & 0o777 == 0o600


def test_audit_records_required_fields(audit_lines):
    assert len(audit_lines) >= 1
    for line in audit_lines:
        assert "ts" in line
        assert "run_id" in line
        assert line["route"] == "maas"
        assert line["model"] == MODEL
        assert "outcome" in line
        assert "duration_s" in line


def test_audit_fallback_is_always_false(audit_lines):
    for line in audit_lines:
        assert line["fallback"] is False


def test_audit_never_contains_fallback_true(workflow, delegate):
    delegate.fail_items(4, total=5)
    workflow.run(fanout_five())
    raw = workflow.AUDIT_FILE.read_text()
    assert '"fallback": true' not in raw
    assert '"fallback":true' not in raw


def test_audit_does_not_store_brief_text(workflow, delegate):
    secret = "SECRET-WORKFLOW-GOAL-XYZ"
    items = [_item(secret, ["src/a.py"])]
    workflow.run(fanout(items=items))
    raw = workflow.AUDIT_FILE.read_text()
    assert secret not in raw


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_schema_has_required_fields(schema):
    assert "mode" in schema.get("required", [])
    assert "run_id" in schema.get("required", [])
    # items/brief are conditionally required via allOf (fanout needs items,
    # suborchestrate needs brief). Verify the conditional requirements exist.
    all_of = schema.get("allOf", [])
    assert len(all_of) >= 2
    then_clauses = [c.get("then", {}).get("required", []) for c in all_of]
    flat = [r for clause in then_clauses for r in clause]
    assert "items" in flat
    assert "brief" in flat


def test_schema_mode_enum(schema):
    props = schema["properties"]
    enum = props["mode"]["enum"]
    assert "fanout" in enum
    assert "suborchestrate" in enum


def test_schema_concurrency_integer(schema):
    props = schema["properties"]
    cc = props["concurrency"]
    assert cc["type"] == "integer"
    assert cc["minimum"] >= 1


def test_workflow_validates_against_schema(workflow, delegate):
    """A manifest missing required fields is rejected as invalid_manifest."""
    result = workflow.run({"mode": "fanout", "run_id": "x"})  # no items
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_workflow_rejects_unknown_mode(workflow, delegate):
    result = workflow.run({"mode": "bogus", "run_id": "x", "items": []})
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


# ---------------------------------------------------------------------------
# Suborchestrate mode
# ---------------------------------------------------------------------------


def test_suborchestrate_calls_delegate_once_with_full_brief(workflow, delegate):
    manifest = suborchestrate()
    result = workflow.run(manifest)
    assert result["status"] == "success"
    assert len(delegate.calls) == 1
    call = delegate.calls[0]
    assert call["brief"] == manifest["brief"]
    assert call["model"] == MODEL


def test_suborchestrate_propagates_max_turns(workflow, delegate):
    manifest = suborchestrate(max_turns=15)
    workflow.run(manifest)
    assert delegate.calls[0]["max_turns"] == 15


def test_suborchestrate_failure_returns_needs_escalation(workflow, delegate):
    delegate.fail_items(1)
    manifest = suborchestrate()
    result = workflow.run(manifest)
    assert result["status"] == "needs_escalation"
    assert result.get("fallback") is False


def test_suborchestrate_does_not_check_disjoint_scope(workflow, delegate):
    """Suborchestrate passes a single brief; scope disjointness is a fanout
    concern only."""
    manifest = suborchestrate()
    manifest["brief"]["scope"] = ["src/a.py", "src/a.py"]
    result = workflow.run(manifest)
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------


VALID_STATUSES = {
    "success",
    "reclassify_premium",
    "invalid_manifest",
    "needs_escalation",
    "capacity_error",
}


def test_all_results_have_valid_status(workflow, delegate):
    for result in (
        workflow.run(fanout_five()),
        workflow.run({"mode": "fanout", "run_id": "x"}),
        workflow.run({"mode": "bogus", "run_id": "x", "items": []}),
    ):
        assert result["status"] in VALID_STATUSES, result["status"]


def test_invalid_manifest_does_not_create_workflow_dir(workflow, delegate):
    """When the manifest is invalid, no workflow directory or files are created."""
    manifest = fanout(items=[{"scope": ["x"]}, {"scope": ["x"]}],
                      run_id="run-invalid-0001")
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    wf_dir = workflow.WORKFLOWS_DIR / "run-invalid-0001"
    assert not wf_dir.exists()


def test_invalid_manifest_writes_no_audit(workflow, delegate):
    manifest = fanout(items=[{"scope": ["x"]}, {"scope": ["x"]}],
                      run_id="run-invalid-0002")
    workflow.run(manifest)
    af = workflow.AUDIT_FILE
    assert not af.exists() or af.read_text().strip() == ""


# ---------------------------------------------------------------------------
# Regression tests for code-review findings.
# ---------------------------------------------------------------------------


def test_fanout_strips_item_id_before_delegate(workflow, delegate):
    """item_id is a workflow-only field; delegate's schema has
    additionalProperties:false, so it must be stripped before passing."""
    manifest = fanout(items=[
        {"task_type": "docs", "goal": "g", "scope": ["a.py"], "item_id": "custom-aaa"},
    ], run_id="run-strip-0001")
    result = workflow.run(manifest)
    assert result["status"] == "success"
    assert len(delegate.calls) == 1
    # The brief passed to delegate must NOT contain item_id.
    assert "item_id" not in delegate.calls[0]["brief"]


def test_invalid_item_timeout_rejected(workflow, delegate):
    """Non-numeric item_timeout must return invalid_manifest, not crash."""
    manifest = fanout(items=[{"task_type": "docs", "goal": "g", "scope": ["a.py"]}],
                      run_id="run-bad-to-0001", item_timeout="abc")
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_invalid_max_turns_rejected(workflow, delegate):
    manifest = fanout(items=[{"task_type": "docs", "goal": "g", "scope": ["a.py"]}],
                      run_id="run-bad-mt-0001", max_turns="xyz")
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_verification_timeout_enforced_in_fanout(workflow, delegate):
    """verification_timeout must actually bound wall-clock time, not be a no-op."""
    import time as _time
    delegate.delay_item(0, 2.0)  # item 0 takes 2s
    manifest = fanout(items=[
        {"task_type": "docs", "goal": "g", "scope": ["a.py"]},
    ], run_id="run-vto-0001", verification_timeout=0.1)
    start = _time.monotonic()
    result = workflow.run(manifest)
    elapsed = _time.monotonic() - start
    # The run must complete well under the 2s the delegate would take,
    # because verification_timeout cuts it short.
    assert elapsed < 1.0, f"verification_timeout not enforced: {elapsed:.2f}s"
    assert result["status"] == "reclassify_premium"
