"""Acceptance tests for codegraph brief auto-dispatch before author dispatch.

Covers docs/prd-codegraph-author-autodispatch.md:
  - report.codegraph_auto_due: the full PRD §02 decision table
  - report.codegraph_auto_dispatch: pre-record-before-subprocess discipline
  - plan._maybe_auto_codegraph: the shared hook cmd_phase/cmd_dispatch call
  - plan._run_role: appends the impact-brief pointer sentence when the
    file exists, leaves the prompt untouched when it does not

cmd_phase/cmd_dispatch themselves are not driven end-to-end here (that
needs the full package/graph/gateway machinery) — _maybe_auto_codegraph
is tested directly, which is the one thing both call sites share, per
the PRD's own "avoid two judgment copies drifting apart" rationale.

Run:  python3 -m pytest tests/test_codegraph_autodispatch.py -v
"""
import importlib.util
import json
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


plan = _load("plan_cgad_test_mod", _BIN / "plan.py")
report = _load("report_cgad_test_mod", _BIN / "report.py")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return r.stdout


def _seed_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    return _git(repo, "rev-parse", "HEAD").strip()


def _state(task_dir: Path, repo: Path, base: str,
          change_id: str = "c1", route: str = "planned") -> Path:
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": route, "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso()}
    sp = task_dir / "state.json"
    report.save_json(sp, st)
    return sp


def _repo_with_pre_existing_change(tmp_path, route="planned"):
    repo = tmp_path / "repo"
    _seed_repo(repo)
    (repo / "existing.txt").write_text("old", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add existing")
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "existing.txt").write_text("edited", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "edit existing")
    task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
    _state(task_dir, repo, base, route=route)
    return repo, task_dir


class TestCodegraphAutoDue:
    """report.codegraph_auto_due: the full PRD §02 decision table."""

    def test_inline_route_not_due(self, tmp_path):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path,
                                                         route="inline")
        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert due is False
        assert why == "inline"

    def test_planned_applicable_never_attempted_is_due(self, tmp_path):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert due is True
        assert why == "due"

    def test_not_applicable_all_net_new(self, tmp_path):
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "brand_new.txt").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add brand new")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
        _state(task_dir, repo, base)
        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert due is False
        assert why in ("not_applicable", "surface_unmeasured")

    def test_already_attempted_via_state_json_not_due(self, tmp_path):
        """A manual `plan.py codegraph brief` run already recorded an
        outcome (any of the four codegraph_state values) — must not
        re-trigger, regardless of success/failure."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        state = report.load_json(task_dir / "state.json", {})
        state["codegraph_brief"] = {"written": False}  # e.g. incomplete
        report.save_json(task_dir / "state.json", state)
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert due is False
        assert why == "already_attempted"

    def test_already_attempted_via_planning_json_not_due(self, tmp_path):
        """An auto-dispatch pre-record (planning.json.codegraph_auto)
        already exists — must not re-trigger a second time."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        planning = {"codegraph_auto": {"state": "incomplete", "rc": None}}
        report.save_json(task_dir / "planning.json", planning)
        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert due is False
        assert why == "already_attempted"


class TestCodegraphAutoDispatch:
    """report.codegraph_auto_dispatch: pre-record-before-subprocess (J2)."""

    def test_pre_record_survives_a_subprocess_exception(
            self, tmp_path, monkeypatch):
        """codegraph_auto_dispatch catches a raising subprocess.run
        (mirrors J2: the pre-record is the fence) and returns gracefully
        with rc=-1 rather than propagating — scheduling, not gating,
        must never crash the caller (cmd_phase/cmd_dispatch)."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        state = report.load_json(task_dir / "state.json", {})

        def _boom(*a, **kw):
            raise RuntimeError("simulated kill mid-subprocess")

        monkeypatch.setattr(report.subprocess, "run", _boom)

        rec = report.codegraph_auto_dispatch(task_dir, repo, state, "c1")
        assert rec["rc"] == -1

        planning = report.load_json(task_dir / "planning.json", {})
        assert isinstance(planning.get("codegraph_auto"), dict)
        # the final record reflects the caught failure (state complete,
        # rc=-1) — the PRE-record (state incomplete, rc None) is what
        # J2 guarantees survives an actual process kill, which a caught
        # Python exception is not; see the next test for the true kill
        # simulation via os.kill-style abrupt termination being out of
        # reach for a unit test — this test instead confirms the
        # exception path degrades cleanly rather than propagating.
        assert planning["codegraph_auto"]["state"] == "complete"
        assert planning["codegraph_auto"]["rc"] == -1

    def test_pre_record_exists_before_subprocess_is_even_called(
            self, tmp_path, monkeypatch):
        """The actual J2 guarantee: the pre-record (state=incomplete,
        rc=None) is on disk BEFORE subprocess.run is invoked — checked
        from inside the mocked subprocess.run itself, so a real crash of
        the child process (which a unit test cannot simulate directly)
        would still leave this fact recorded."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        state = report.load_json(task_dir / "state.json", {})
        seen = {}

        def _check_pre_record(*a, **kw):
            planning = report.load_json(task_dir / "planning.json", {})
            seen["pre"] = planning.get("codegraph_auto")
            class _FakeProc:
                returncode = 0
                stdout = json.dumps({"codegraph_state": "brief_written"})
                stderr = ""
            return _FakeProc()

        monkeypatch.setattr(report.subprocess, "run", _check_pre_record)
        report.codegraph_auto_dispatch(task_dir, repo, state, "c1")

        assert seen["pre"]["state"] == "incomplete"
        assert seen["pre"]["rc"] is None

    def test_successful_dispatch_records_outcome(self, tmp_path,
                                                  monkeypatch):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        state = report.load_json(task_dir / "state.json", {})

        class _FakeProc:
            returncode = 0
            stdout = json.dumps({"session_name": "codegraph-c1-001",
                                 "codegraph_state": "brief_written"})
            stderr = ""

        monkeypatch.setattr(report.subprocess, "run",
                            lambda *a, **kw: _FakeProc())

        rec = report.codegraph_auto_dispatch(task_dir, repo, state, "c1")
        assert rec["rc"] == 0
        assert rec["outcome"] == "brief_written"
        assert rec["session"] == "codegraph-c1-001"

        planning = report.load_json(task_dir / "planning.json", {})
        assert planning["codegraph_auto"]["state"] == "complete"


class TestMaybeAutoCodegraphHook:
    """plan._maybe_auto_codegraph: the shared hook cmd_phase/cmd_dispatch
    both call — dispatches when due, skips (with an event) when not,
    never raises regardless of outcome (scheduling, not gating)."""

    def test_dispatches_once_when_due(self, tmp_path, monkeypatch):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        calls = []
        monkeypatch.setattr(plan, "codegraph_auto_due",
                            lambda *a, **kw: (True, "due"))
        monkeypatch.setattr(
            plan, "codegraph_auto_dispatch",
            lambda *a, **kw: calls.append(a) or {"rc": 0})

        plan._maybe_auto_codegraph("c1", repo, task_dir)

        assert len(calls) == 1

    def test_skips_when_not_due(self, tmp_path, monkeypatch):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        calls = []
        monkeypatch.setattr(plan, "codegraph_auto_due",
                            lambda *a, **kw: (False, "inline"))
        monkeypatch.setattr(
            plan, "codegraph_auto_dispatch",
            lambda *a, **kw: calls.append(a))

        plan._maybe_auto_codegraph("c1", repo, task_dir)

        assert len(calls) == 0
        events = (task_dir / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "CODEGRAPH_AUTO_SKIPPED" in kinds


class TestWorktreeVisibility:
    """Regression for the worktree blind spot (PRD
    prd-codegraph-autodispatch-worktree-blindspot.md): under ai-dlc's
    standard worktree-first flow, real work happens in a linked worktree
    on the task branch, NOT in the --repo main checkout.  Before the fix
    _change_files_for_codegraph only looked at repo's own diff/status and
    always saw zero files → codegraph_auto_due returned
    (False, 'surface_unmeasured') and the auto-trigger never fired in real
    usage.  These cases build a real linked worktree via `git worktree add`
    and assert the file is now visible."""

    def _repo_base_with_existing_file(self, tmp_path):
        """A repo whose base_sha commit contains an existing tracked file
        (so codegraph_surface sees it as pre-existing → applicable)."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        (repo / "existing.txt").write_text("old", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add existing")
        base = _git(repo, "rev-parse", "HEAD").strip()
        task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
        _state(task_dir, repo, base)  # change_id=c1 → convention task/c1
        return repo, task_dir, base

    def test_uncommitted_edit_in_linked_worktree_is_visible(
            self, tmp_path):
        """The root reproduction: an uncommitted edit to an existing
        tracked file made ONLY inside the linked worktree (the main
        checkout is untouched) is now seen by _change_files_for_codegraph
        and codegraph_auto_due returns (True, 'due').  Against the
        unfixed code this returns (False, 'surface_unmeasured')."""
        repo, task_dir, base = self._repo_base_with_existing_file(tmp_path)
        wt = tmp_path / "wt-linked"
        _git(repo, "worktree", "add", str(wt), "-b", "task/c1")
        # uncommitted edit to an existing tracked file, ONLY in the worktree
        (wt / "existing.txt").write_text("edited in worktree",
                                         encoding="utf-8")

        files, base_sha = report._change_files_for_codegraph(repo, task_dir)
        assert "existing.txt" in files, (
            f"worktree uncommitted edit not visible: {files}")

        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert (due, why) == (True, "due"), (due, why)

    def test_committed_landing_on_task_branch_is_visible(self, tmp_path):
        """The concomitant fix (PRD §04 pt 2): a commit that has landed on
        the task branch inside the worktree (not yet merged) is visible via
        the diff-side (base..<resolved work sha>) — the old code diffed
        base..HEAD on the main checkout, which never sees task-branch
        commits, so this too returned surface_unmeasured before the fix."""
        repo, task_dir, base = self._repo_base_with_existing_file(tmp_path)
        wt = tmp_path / "wt-linked"
        _git(repo, "worktree", "add", str(wt), "-b", "task/c1")
        (wt / "existing.txt").write_text("committed in worktree",
                                         encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "edit existing on task branch")

        files, base_sha = report._change_files_for_codegraph(repo, task_dir)
        assert "existing.txt" in files, (
            f"task-branch commit not visible via diff: {files}")

        state = report.load_json(task_dir / "state.json", {})
        due, why = report.codegraph_auto_due(task_dir, repo, state)
        assert (due, why) == (True, "due"), (due, why)


class TestRunRolePromptAugmentation:
    """plan._run_role: appends the impact-brief pointer sentence to the
    prompt prepare() returns, purely based on file existence — never
    touches prepare()/dispatch_role() internals."""

    def test_appends_pointer_when_brief_exists(self, tmp_path, monkeypatch):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        brief_dir = repo / "codegraph"
        brief_dir.mkdir()
        (brief_dir / "impact-brief.md").write_text("# brief\n")

        captured = {}
        monkeypatch.setattr(
            plan, "prepare",
            lambda change, role, package_file, workspace=None:
                ({"id": "pkg"}, repo, "ORIGINAL PROMPT", "en"))
        monkeypatch.setattr(
            plan, "dispatch_role",
            lambda change, role, pkg, repo_, prompt, task_dir_, mode,
                   timeout, ws=None: captured.setdefault("prompt", prompt))

        plan._run_role("c1", "proposal", Path("pkg.json"), task_dir,
                       "code.normal", 600)

        assert "ORIGINAL PROMPT" in captured["prompt"]
        assert "codegraph/impact-brief.md" in captured["prompt"]

    def test_no_change_when_brief_absent(self, tmp_path, monkeypatch):
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)

        captured = {}
        monkeypatch.setattr(
            plan, "prepare",
            lambda change, role, package_file, workspace=None:
                ({"id": "pkg"}, repo, "ORIGINAL PROMPT", "en"))
        monkeypatch.setattr(
            plan, "dispatch_role",
            lambda change, role, pkg, repo_, prompt, task_dir_, mode,
                   timeout, ws=None: captured.setdefault("prompt", prompt))

        plan._run_role("c1", "proposal", Path("pkg.json"), task_dir,
                       "code.normal", 600)

        assert captured["prompt"] == "ORIGINAL PROMPT"
