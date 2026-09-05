"""Tests for the plane git safe.directory boundary (G1-G4) and the
boundary-failure classification in bin/plan.py.

Covers the Requirements/Scenarios in
openspec/changes/plane-git-boundary-and-rollback-anchor/specs/plane-git-safe-directory/spec.md
against throwaway git repos under tmp_path, so no real .ai-dlc state is
touched.

Run:  python3 -m pytest -q tests/test_plane_git_boundary.py
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_boundary", _BIN / "bin" / "plan.py")


# ── G1: git_run() helper ──────────────────────────────────────────────

def test_git_run_argv_has_safe_directory_before_C(tmp_path):
    """git_run must place `-c safe.directory=<repo>` before `-C` in argv."""
    captured = {}

    def fake_run(cmd, cwd=None, timeout=None):
        captured["cmd"] = list(cmd)
        class _P:
            returncode = 0
            stdout = ""
            stderr = ""
        return _P()

    repo = tmp_path / "repo"
    repo.mkdir()
    orig = plan.run
    plan.run = fake_run
    try:
        plan.git_run(["status", "--porcelain", "-uall"], repo)
    finally:
        plan.run = orig
    cmd = captured["cmd"]
    assert cmd[0] == "git"
    # the safe.directory override must precede the -C path scoping
    assert "-c" in cmd and "-C" in cmd
    assert cmd.index("-c") < cmd.index("-C")
    sd = cmd[cmd.index("-c") + 1]
    assert sd == f"safe.directory={repo}"
    assert cmd[cmd.index("-C") + 1] == str(repo)
    # the caller's args come after the path
    assert cmd[-3:] == ["status", "--porcelain", "-uall"]


def test_git_run_passes_through_cwd_and_timeout(tmp_path):
    captured = {}

    def fake_run(cmd, cwd=None, timeout=None):
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        class _P:
            returncode = 0
            stdout = ""
            stderr = ""
        return _P()

    repo = tmp_path / "repo"
    repo.mkdir()
    orig = plan.run
    plan.run = fake_run
    try:
        plan.git_run(["status"], repo, cwd=tmp_path, timeout=12)
    finally:
        plan.run = orig
    assert captured["cwd"] == tmp_path
    assert captured["timeout"] == 12


def _have_git() -> bool:
    return subprocess.run(
        ["git", "--version"], capture_output=True, text=True
    ).returncode == 0


def _can_chown() -> bool:
    # need root (or CAP_CHOWN) to chown to an unrelated uid
    return hasattr(os, "geteuid") and os.geteuid() == 0


@pytest.mark.skipif(not (_have_git() and _can_chown()),
                    reason="needs git + root to chown a repo to a foreign uid")
def test_git_run_succeeds_on_foreign_owned_repo_where_raw_run_fails(tmp_path):
    """On a repo owned by a different uid, raw run() fails with
    dubious-ownership while git_run() succeeds (CVE-2022-24765)."""
    repo = tmp_path / "foreign"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f.txt").write_text("x\n")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"],
                   check=True, env=env)
    # hand the tree to an unrelated uid so git's ownership check misfires
    FOREIGN = 65534  # nobody/nogroup
    subprocess.run(["chown", "-R", f"{FOREIGN}:{FOREIGN}", str(repo)],
                   check=True)

    raw = plan.run(["git", "-C", str(repo), "status", "--porcelain", "-uall"])
    # if the environment globally allows dubious ownership (e.g. a wildcard
    # safe.directory in system config we couldn't suppress), raw may still
    # succeed — in that case the contrast this test asserts cannot be shown,
    # so skip rather than fail.
    if raw.returncode == 0:
        pytest.skip("environment does not reproduce dubious-ownership refusal")
    assert "dubious ownership" in (raw.stderr or "").lower()

    via = plan.git_run(["status", "--porcelain", "-uall"], repo)
    assert via.returncode == 0, via.stderr


# ── G2: git_status_paths routes through git_run ───────────────────────

def test_git_status_paths_healthy_returns_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    (repo / "a.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True, env=env)
    # an uncommitted modification is what status --porcelain reports
    (repo / "a.txt").write_text("y\n")
    (repo / "new.txt").write_text("z\n")  # untracked, -uall shows it
    paths = plan.git_status_paths(repo)
    assert paths is not None
    assert "a.txt" in paths
    assert "new.txt" in paths


def test_git_status_paths_uses_git_run(tmp_path, monkeypatch):
    """git_status_paths must build its git call through git_run, not a
    hand-written run(['git','-C',...])."""
    called = {}

    def fake_git_run(args, repo, cwd=None, timeout=None):
        called["args"] = list(args)
        called["repo"] = repo

        class _P:
            returncode = 0
            stdout = ""
            stderr = ""
        return _P()

    monkeypatch.setattr(plan, "git_run", fake_git_run)
    repo = tmp_path / "repo"
    repo.mkdir()
    plan.git_status_paths(repo)
    assert called["args"] == ["status", "--porcelain", "-uall"]
    assert called["repo"] == repo


# ── G3: cmd_sweep routes through git_run ──────────────────────────────

def test_cmd_sweep_uses_git_run_for_lsfiles_and_checkout(tmp_path, monkeypatch):
    """cmd_sweep's two direct git calls (ls-files, checkout --) must go
    through git_run. We drive sweep far enough to hit the ls-files call by
    stubbing the helpers it depends on."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "openspec").mkdir()

    seen = []

    def fake_git_run(args, r, cwd=None, timeout=None):
        seen.append(list(args))

        class _P:
            returncode = 0
            stdout = ""
            stderr = ""
        return _P()

    monkeypatch.setattr(plan, "git_run", fake_git_run)
    monkeypatch.setattr(plan, "plane_root", lambda r: repo)
    monkeypatch.setattr(plan, "default_task_dir",
                        lambda r, c: repo / ".ai-dlc" / c)
    # a baseline file so sweep proceeds to the ls-files call
    td = repo / ".ai-dlc" / "c" / "task"
    td.mkdir(parents=True)
    bf = td / "0.pre-boundary.json"
    bf.write_text("[]")
    monkeypatch.setattr(plan, "earliest_baseline_file", lambda d: bf)
    monkeypatch.setattr(plan, "load_json", lambda p, default=None: [])
    # git_status_paths returns no current paths -> no per-component work,
    # but ls-files is still invoked
    monkeypatch.setattr(plan, "git_status_paths", lambda r: [])
    monkeypatch.setattr(plan, "emit", lambda obj, code: code)

    plan.cmd_sweep("c", repo, td, False, False, None)
    assert any(args[:1] == ["ls-files"] for args in seen), seen


# ── G4: boundary failure classification ───────────────────────────────

def test_git_status_paths_failure_captures_stderr(tmp_path):
    """On a git error, git_status_paths returns None AND records the
    captured stderr in _GIT_STATUS_LAST_ERROR for the caller to read."""
    repo = tmp_path / "not-a-git-repo"
    repo.mkdir()
    plan._GIT_STATUS_LAST_ERROR = ""
    paths = plan.git_status_paths(repo)
    assert paths is None
    # git status on a non-repo prints a specific stderr; the slot must
    # carry it, not stay empty
    assert plan._GIT_STATUS_LAST_ERROR != ""
    assert "not a git repository" in plan._GIT_STATUS_LAST_ERROR.lower()


def test_git_status_paths_success_clears_last_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    plan._GIT_STATUS_LAST_ERROR = "stale"
    assert plan.git_status_paths(repo) is not None
    assert plan._GIT_STATUS_LAST_ERROR == ""


def test_run_role_boundary_failure_distinguishes_missing_from_git_error(
        tmp_path, monkeypatch):
    """_run_role's baseline-snapshot failure path must keep
    'boundary': 'unknown' as the outcome label while distinguishing
    'target not readable' from 'git reported a specific error' in the
    returned structure (INV-33)."""
    existing = tmp_path / "exists"
    existing.mkdir()
    missing = tmp_path / "does-not-exist"  # not a directory

    def fake_prepare(change, role, package_file, workspace=None):
        # repo is the tree when ws is None; we swap it per-case below
        return ({"repo": str(_cur_tree[0])}, _cur_tree[0], "prompt", "lang")

    _cur_tree = [existing]

    monkeypatch.setattr(plan, "prepare", fake_prepare)
    monkeypatch.setattr(plan, "masked_surface_refusal", lambda p: None)
    monkeypatch.setattr(plan, "now_iso", lambda: "2026-09-05T00:00:00Z")

    def fake_status(tree):
        # both cases fail (return None); the distinguishing detail is the
        # stderr slot, which the branch reads
        if tree.is_dir():
            plan._GIT_STATUS_LAST_ERROR = "fatal: not a git repository"
        else:
            plan._GIT_STATUS_LAST_ERROR = ""
        return None

    monkeypatch.setattr(plan, "git_status_paths", fake_status)

    # case 1: existing dir, git itself errored -> git_error field present
    _cur_tree[0] = existing
    res, code = plan._run_role("c", "role", Path("/pkg"), Path("/td"),
                               "mode", 10, None)
    assert res["boundary"] == "unknown"
    assert "git_error" in res
    assert res["git_error"] == "fatal: not a git repository"

    # case 2: target not a directory -> no git_error field, a distinct
    # 'not readable' error message
    _cur_tree[0] = missing
    res2, code2 = plan._run_role("c", "role", Path("/pkg"), Path("/td"),
                                 "mode", 10, None)
    assert res2["boundary"] == "unknown"
    assert "git_error" not in res2
    assert "not readable" in res2["error"]
    # the two causes are distinguishable in the structure
    assert res != res2


# ── G5: dt1_gates.sh rollback-anchor SKIP state ───────────────────────

_DT1 = _BIN / "tests" / "collapse" / "dt1_gates.sh"

# the exact anchor-check block from dt1_gates.sh (G5), extracted so it can
# be run against a fixture repo without the rest of the gate
_ANCHOR_BLOCK = r'''if ! git rev-parse -q --verify v0.8.0 >/dev/null 2>&1; then
  echo "SKIP: v0.8.0 anchor not carried by this repo's history (republished copy) — see SKILL.md"
elif ! git cat-file -e v0.8.0:bin/oracle.py 2>/dev/null; then
  echo "FAIL: v0.8.0:bin/oracle.py missing — deletion has no rollback anchor"
  exit 1
fi
'''


def _run_anchor_block(cwd: Path):
    return subprocess.run(
        ["bash", "-c", _ANCHOR_BLOCK], cwd=cwd,
        capture_output=True, text=True,
    )


def test_dt1_gates_skip_when_tag_absent(tmp_path):
    """A repo whose history does not carry v0.8.0 at all -> SKIP line,
    exit 0 (a republished copy, not a broken anchor)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"],
                   check=True, env=env)
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "i"],
                   check=True, env=env)
    r = _run_anchor_block(repo)
    assert r.returncode == 0
    assert "SKIP" in r.stdout
    assert "v0.8.0" in r.stdout
    assert "republished copy" in r.stdout


def test_dt1_gates_fail_when_tag_present_but_file_missing(tmp_path):
    """Tag v0.8.0 exists but does not contain bin/oracle.py -> FAIL,
    exit 1 (a genuinely broken anchor — unchanged behavior)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"],
                   check=True, env=env)
    (repo / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "i"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "tag", "v0.8.0"],
                   check=True, env=env)
    r = _run_anchor_block(repo)
    assert r.returncode == 1
    assert "FAIL" in r.stdout
    assert "rollback anchor" in r.stdout


def test_dt1_gates_pass_when_tag_and_file_present(tmp_path):
    """Tag v0.8.0 exists and contains bin/oracle.py -> no SKIP, no FAIL,
    exit 0 (the anchor is genuinely satisfied)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"],
                   check=True, env=env)
    (repo / "bin").mkdir()
    (repo / "bin" / "oracle.py").write_text("# oracle\n")
    subprocess.run(["git", "-C", str(repo), "add", "bin/oracle.py"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "i"],
                   check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "tag", "v0.8.0"],
                   check=True, env=env)
    r = _run_anchor_block(repo)
    assert r.returncode == 0
    assert "SKIP" not in r.stdout
    assert "FAIL" not in r.stdout


@pytest.mark.skipif(not _have_git(), reason="needs git")
def test_dt1_gates_in_this_repo_emits_skip_and_exits_zero():
    """Acceptance (§12): in this repo, which carries no v0.8.0 tag, the
    full dt1_gates.sh must emit a SKIP line and exit 0 (where it
    previously exited 1)."""
    r = subprocess.run(["bash", str(_DT1)], capture_output=True, text=True,
                       cwd=str(_BIN))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SKIP" in r.stdout
    assert "v0.8.0" in r.stdout
    assert "republished copy" in r.stdout
