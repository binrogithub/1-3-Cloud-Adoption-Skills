"""Workflow path-traversal tests (PRD SECURITY_HARDENING V1 §D5 / G5).

run_id and item_id become directory and file names under
~/.claude-hybrid/workflows/. Anything outside [A-Za-z0-9][A-Za-z0-9._-]{0,63}
must be rejected as invalid_manifest with zero filesystem side effects.
"""
from __future__ import annotations

import importlib.util
import importlib.machinery
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "scripts" / "workflow"


def _load():
    loader = importlib.machinery.SourceFileLoader("wf_test", str(WORKFLOW))
    spec = importlib.util.spec_from_loader("wf_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


BAD_RUN_IDS = [
    "../evil",
    "..",
    "a/b",
    "a\\b",
    "./x",
    ".hidden",
    " leading-space",
    "trailing-space ",
    "tab\tid",
    "newline\nid",
    "nul\x00byte",
    "semi;colon",
    "pipe|char",
    "star*char",
    "x" * 65,  # too long
    "",
]

BAD_ITEM_IDS = [
    "../evil",
    "..",
    "a/b",
    ".hidden",
    "nul\x00byte",
    "x" * 65,
]


def _manifest(run_id="ok-run", item_id=None):
    item = {"task_type": "docs", "goal": "do it"}
    if item_id is not None:
        item["item_id"] = item_id
    return {"mode": "fanout", "run_id": run_id, "items": [item]}


def test_bad_run_ids_rejected():
    wf = _load()
    for rid in BAD_RUN_IDS:
        errors = wf._validate_manifest(_manifest(run_id=rid))
        assert errors, f"run_id {rid!r} was accepted"
        assert any("run_id" in e for e in errors), f"run_id {rid!r} error missing: {errors}"


def test_bad_item_ids_rejected():
    wf = _load()
    for iid in BAD_ITEM_IDS:
        errors = wf._validate_manifest(_manifest(item_id=iid))
        assert errors, f"item_id {iid!r} was accepted"
        assert any("item_id" in e for e in errors), f"item_id {iid!r} error missing: {errors}"


def test_good_ids_accepted():
    wf = _load()
    assert wf._validate_manifest(_manifest()) == []
    assert wf._validate_manifest(_manifest(run_id="Run_2026.v1-beta", item_id="item.000-a")) == []
    assert wf._validate_manifest({"mode": "suborchestrate", "run_id": "sub1", "brief": {"task_type": "docs", "goal": "x"}}) == []


def test_run_returns_invalid_manifest_no_fs_side_effects(tmp_path, monkeypatch):
    """End-to-end: a traversal run_id must not create anything on disk."""
    wf = _load()
    monkeypatch.setattr(wf, "WORKFLOWS_DIR", tmp_path / "workflows")

    def _boom(*a, **k):  # any delegate call would be a failure of the gate
        raise AssertionError("delegate must not run for an invalid manifest")

    monkeypatch.setattr(wf, "_get_delegate", _boom)

    result = wf.run(_manifest(run_id="../../escape"))
    assert result["status"] == "invalid_manifest"
    assert not (tmp_path / "workflows").exists() or list((tmp_path / "workflows").iterdir()) == []


def test_write_item_result_refuses_unsafe_id(tmp_path):
    """Defense in depth: the writer itself refuses non-filename ids."""
    wf = _load()
    for iid in ("../evil", "a/b", "", None):
        try:
            wf._write_item_result(tmp_path, iid, {"x": 1})
        except ValueError:
            continue
        raise AssertionError(f"unsafe item_id {iid!r} was written")


def test_schema_declares_the_pattern():
    """The schema and the code must agree on the charset."""
    import json
    schema = json.loads((ROOT / "assets" / "manifest-schema.json").read_text())
    pat = schema["properties"]["run_id"].get("pattern")
    assert pat and pat.startswith("^[A-Za-z0-9]"), "run_id pattern missing from schema"
    brief = schema["$defs"]["brief"]["properties"]
    assert brief["item_id"].get("pattern") == pat
