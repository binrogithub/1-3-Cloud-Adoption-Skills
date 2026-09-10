"""project-manager + coder roles — agent-side hats (tests a).

The PM prompt must carry the four-marker contract with manage-not-code
semantics; `plan.py wbs` validates the decomposition mechanically:
structure, per-package four-marker briefs, and the clean-tree proof
that the PM never coded.

Run:  python3 -m pytest tests/test_project_manager_role.py -v
"""
import json
import os
import subprocess
from pathlib import Path

# the spec tree the wbs reader resolves must be the test's own, not the
# host's live plane home — set before the modules load
_TMP_SPECS = os.environ.get("AI_DLC_SPECS")
os.environ["AI_DLC_SPECS"] = "/tmp/pm-role-test-specs"

import importlib.util  # noqa: E402
import shutil  # noqa: E402

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_pm_role", _BIN / "bin" / "plan.py")


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "mod.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo,
                   check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def _change_dir(repo: Path, change: str = "ch1") -> Path:
    d = plan.plane_tree(repo) / "changes" / change
    d.mkdir(parents=True, exist_ok=True)
    return d


BRIEF = ("Objective: implement the helper.\n"
         "Expected output: module + tests passing.\n"
         "Tools: the repo files read-write in the worktree.\n"
         "Boundary: only the named module and its test file.\n")


def _write_wbs(cdir: Path, repo: Path, change: str = "ch1",
               subtasks=None, packages=None, change_id=None, repo_str=None):
    wbs = {"change_id": change_id or change,
           "repo": repo_str or str(repo),
           "subtasks": subtasks if subtasks is not None else [
               {"id": "a", "title": "first", "package": "packages/a.json",
                "depends_on": []},
               {"id": "b", "title": "second", "package": "packages/b.json",
                "depends_on": ["a"]}]}
    (cdir / "wbs.json").write_text(json.dumps(wbs))
    pkgs = packages if packages is not None else {
        sid: {"requirement": "do " + sid, "change_id": change,
              "capability": "core", "repo": str(repo),
              "subtask_id": sid, "brief": BRIEF}
        for sid in ("a", "b")}
    pdir = cdir / "packages"
    pdir.mkdir(exist_ok=True)
    for sid, pkg in pkgs.items():
        (pdir / f"{sid}.json").write_text(json.dumps(pkg))


def setup_function(_):
    shutil.rmtree("/tmp/pm-role-test-specs", ignore_errors=True)


# ── the role-md contracts (PM/coder are agent-side hats) ───────────

def test_pm_role_md_carries_contract():
    md = (_BIN / "roles" / "project-manager.md").read_text()
    for marker in ("Objective", "Expected output", "Tools", "Boundary"):
        assert marker in md
    assert "\u4e0d\u7f16\u7801" in md and "\u4e0d\u6d4b\u8bd5" in md
    assert "wbs.json" in md and "plan.py wbs" in md
    assert "git status" in md


def test_coder_role_md_carries_contract():
    md = (_BIN / "roles" / "coder.md").read_text()
    for marker in ("Objective", "Expected output", "Tools", "Boundary"):
        assert marker in md
    assert "\u7f16\u7801\u4e0e\u6d4b\u8bd5\u4e00\u4f53" in md
    assert "validator" in md and "MERGE_GATE" in md


def test_roster_table_lists_every_role():
    md = (_BIN / "roles" / "README.md").read_text()
    for role in ("project-manager", "coder", "proposal", "specs",
                 "design", "tasks", "review-", "validate", "archiver",
                 "codegraph", "graph"):
        assert role in md, role


def test_other_roles_keep_the_artifact_contract():
    pkg = {"requirement": "add a helper", "change_id": "ch1",
           "capability": "core", "repo": "/tmp/somewhere"}
    prompt = plan.assemble_prompt(pkg, "proposal", "English")
    assert plan.brief_missing_sections(prompt) == []
    assert "write the proposal artifact" in prompt
    assert "you do not code" not in prompt


# ── wbs validation: the happy path ─────────────────────────────────

def test_wbs_valid_emits_topo_order(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    _write_wbs(cdir, repo)
    assert plan.cmd_wbs("ch1", repo) == 0


def test_wbs_missing_file(tmp_path):
    repo = _git_repo(tmp_path)
    _change_dir(repo)
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID


def test_wbs_wrong_change_id(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    _write_wbs(cdir, repo, change_id="other")
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID


def test_wbs_brief_missing_marker(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    pkgs = {"a": {"requirement": "r", "change_id": "ch1",
                  "capability": "core", "repo": str(repo),
                  "subtask_id": "a",
                  "brief": "Objective: x\nExpected output: y\n"
                           "Tools: z\n"},
            "b": {"requirement": "r", "change_id": "ch1",
                  "capability": "core", "repo": str(repo),
                  "subtask_id": "b", "brief": BRIEF}}
    _write_wbs(cdir, repo, packages=pkgs)
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID


def test_wbs_package_change_mismatch(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    pkgs = {"a": {"requirement": "r", "change_id": "WRONG",
                  "capability": "core", "repo": str(repo),
                  "subtask_id": "a", "brief": BRIEF},
            "b": {"requirement": "r", "change_id": "ch1",
                  "capability": "core", "repo": str(repo),
                  "subtask_id": "b", "brief": BRIEF}}
    _write_wbs(cdir, repo, packages=pkgs)
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID


def test_wbs_cycle(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    subs = [{"id": "a", "title": "x", "package": "packages/a.json",
             "depends_on": ["b"]},
            {"id": "b", "title": "y", "package": "packages/b.json",
             "depends_on": ["a"]}]
    _write_wbs(cdir, repo, subtasks=subs)
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID


def test_wbs_dirty_tree_proves_pm_coded(tmp_path):
    repo = _git_repo(tmp_path)
    cdir = _change_dir(repo)
    _write_wbs(cdir, repo)
    (repo / "smuggled.py").write_text("def cheat(): pass\n")
    assert plan.cmd_wbs("ch1", repo) == plan.EXIT_PACKAGE_INVALID
    (repo / "smuggled.py").unlink()


def teardown_module(_):
    if _TMP_SPECS:
        os.environ["AI_DLC_SPECS"] = _TMP_SPECS
    else:
        os.environ.pop("AI_DLC_SPECS", None)
    shutil.rmtree("/tmp/pm-role-test-specs", ignore_errors=True)
