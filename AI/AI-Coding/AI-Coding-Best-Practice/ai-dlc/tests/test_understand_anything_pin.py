"""Acceptance tests for the Understand-Anything pin digest (PRD
docs/prd-codegraph-pin-digest-runtime-artifacts.md).

`understand_anything_tree_digest` must measure only git-tracked files'
on-disk bytes — untracked runtime artifacts (node_modules, dist, …)
that the analysis pipeline lazily installs under understand-anything-plugin/
must not enter the digest, while genuine tampering of a tracked source
file must still be detected (I3/INV-10 preserved, INV-19 added).

Run:  python3 -m pytest tests/test_understand_anything_pin.py -v
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_uap_test_mod", _BIN / "plan.py")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return r.stdout


@pytest.fixture
def ua_root(tmp_path) -> Path:
    """A temp git repo with an understand-anything-plugin/ subtree holding
    two committed source files plus an UNTRACKED node_modules/foo.js (the
    runtime-artifact stand-in)."""
    root = tmp_path / "ua_root"
    plugin = root / "understand-anything-plugin"
    plugin.mkdir(parents=True)
    (plugin / "skills").mkdir()
    (plugin / "skills" / "SKILL.md").write_text("# understand\n", encoding="utf-8")
    (plugin / "manifest.json").write_text('{"v":1}\n', encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "source")
    # untracked runtime artifact — written but NEVER git-added
    nm = plugin / "node_modules"
    nm.mkdir()
    (nm / "foo.js").write_text("module.exports = {};\n", encoding="utf-8")
    return root


def test_untracked_runtime_artifact_change_is_invisible(ua_root):
    """PRD §06 case 2 (regression): editing an untracked node_modules file
    must not move the digest. Against the pre-fix rglob walk this fails."""
    before = plan.understand_anything_tree_digest(ua_root)
    (ua_root / "understand-anything-plugin" / "node_modules" / "foo.js").write_text(
        "// mutated at runtime\nmodule.exports = {};\n", encoding="utf-8")
    after = plan.understand_anything_tree_digest(ua_root)
    assert before == after


def test_tracked_source_edit_is_detected(ua_root):
    """PRD §06 case 3: tampering a tracked file's on-disk bytes must move
    the digest — confirms the fix did not overcorrect into ignoring all
    change (I3/INV-10 preserved)."""
    before = plan.understand_anything_tree_digest(ua_root)
    (ua_root / "understand-anything-plugin" / "manifest.json").write_text(
        '{"v":2}\n', encoding="utf-8")
    after = plan.understand_anything_tree_digest(ua_root)
    assert before != after


def test_new_untracked_file_is_invisible(ua_root):
    """PRD §06 case 4: a brand-new untracked file landing under the subtree
    (another runtime-artifact drift shape) must not move the digest."""
    before = plan.understand_anything_tree_digest(ua_root)
    (ua_root / "understand-anything-plugin" / "dist").mkdir()
    (ua_root / "understand-anything-plugin" / "dist" / "bundle.js").write_text(
        "built();\n", encoding="utf-8")
    after = plan.understand_anything_tree_digest(ua_root)
    assert before == after


def test_tracked_source_deletion_is_detected(ua_root):
    """PRD §06 case 5: deleting a tracked source file (git rm + working
    tree) must move the digest — deletions are detected, not just edits."""
    before = plan.understand_anything_tree_digest(ua_root)
    _git(ua_root, "rm", "-q",
         "understand-anything-plugin/manifest.json")
    after = plan.understand_anything_tree_digest(ua_root)
    assert before != after
