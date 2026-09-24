"""Acceptance tests for the codegraph role, Phase A (deterministic pieces).

Covers:
  - report.codegraph_surface: applicability by prior existence at base_sha
  - plan.py codegraph-scope: the measurement subcommand
  - plan.py codegraph build: missing-binary structured error (no traceback)

Phase B (the LLM-dispatched brief role) is a separate future change and is
NOT tested here.

Run:  python3 -m pytest tests/test_codegraph_role.py -v
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ── load plan.py and report.py as modules ───────────────────────────
_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_cg_test_mod", _BIN / "plan.py")
report = _load("report_cg_test_mod", _BIN / "report.py")


# ── helpers ─────────────────────────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return r.stdout


def _seed_repo(repo: Path) -> str:
    """Init a git repo with one empty seed commit; return the seed SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    return _git(repo, "rev-parse", "HEAD").strip()


def _state(task_dir: Path, repo: Path, base: str,
           change_id: str = "c1", route: str = "inline") -> Path:
    """Write a minimal state.json for a task."""
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": route, "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso()}
    sp = task_dir / "state.json"
    report.save_json(sp, st)
    return sp


# ═══ codegraph_surface ═════════════════════════════════════════════

class TestCodegraphSurface:
    """report.codegraph_surface: a file counts only if it already existed
    at base_sha. Net-new files do not count."""

    def test_net_new_file_not_applicable(self, tmp_path):
        """A file added AFTER base_sha does not count — nothing
        pre-existing to query a graph about."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        # add a file after base_sha and commit it so it's in the tree
        (repo / "new.txt").write_text("new", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add new file")
        surface = report.codegraph_surface(["new.txt"], repo, base)
        assert surface["applicable"] is False
        assert surface["pre_existing_files"] == []
        assert surface["pre_existing_files_total"] == 0
        assert surface["measured_files"] == 1

    def test_pre_existing_file_applicable(self, tmp_path):
        """A file that existed at base_sha counts."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        # create a file at base_sha
        (repo / "existing.txt").write_text("old", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add existing file")
        # now base_sha is the seed; existing.txt was added after it, so
        # re-capture base as the commit that has existing.txt
        base_with_file = _git(repo, "rev-parse", "HEAD").strip()
        # make a further change so there's a diff
        (repo / "existing.txt").write_text("edited", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "edit existing file")
        surface = report.codegraph_surface(["existing.txt"], repo,
                                           base_with_file)
        assert surface["applicable"] is True
        assert surface["pre_existing_files"] == ["existing.txt"]
        assert surface["pre_existing_files_total"] == 1
        assert surface["measured_files"] == 1

    def test_mixed_files(self, tmp_path):
        """One pre-existing + one net-new → applicable, only the
        pre-existing one in the list."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        (repo / "old.txt").write_text("old", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "old file")
        base = _git(repo, "rev-parse", "HEAD").strip()
        (repo / "new.txt").write_text("new", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "new file")
        surface = report.codegraph_surface(["old.txt", "new.txt"], repo, base)
        assert surface["applicable"] is True
        assert surface["pre_existing_files"] == ["old.txt"]
        assert surface["pre_existing_files_total"] == 1
        assert surface["measured_files"] == 2

    def test_no_base_sha(self, tmp_path):
        """Without base_sha there is no base to check against — nothing
        is pre-existing, applicability is false."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        (repo / "x.txt").write_text("x", encoding="utf-8")
        surface = report.codegraph_surface(["x.txt"], repo, None)
        assert surface["applicable"] is False
        assert surface["pre_existing_files_total"] == 0

    def test_cap_at_fifty(self, tmp_path):
        """The pre_existing_files list is capped at 50; the _total count
        reflects the true number."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        for i in range(60):
            (repo / f"f{i:03d}.txt").write_text(str(i), encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "many files")
        base = _git(repo, "rev-parse", "HEAD").strip()
        files = [f"f{i:03d}.txt" for i in range(60)]
        surface = report.codegraph_surface(files, repo, base)
        assert surface["applicable"] is True
        assert len(surface["pre_existing_files"]) == 50
        assert surface["pre_existing_files_total"] == 60
        assert surface["measured_files"] == 60


# ═══ codegraph-scope subcommand ════════════════════════════════════

class TestCodegraphScope:
    """plan.py codegraph-scope: prints correct JSON for both cases."""

    def test_scope_not_applicable_net_new(self, tmp_path, capsys):
        """All files net-new relative to base_sha → applicable false."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        # add a file after base and commit so change_surface sees it in
        # the diff (base..HEAD)
        (repo / "brand_new.txt").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add brand new")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
        _state(task_dir, repo, base)
        rc = plan.cmd_codegraph_scope("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["applicable"] is False
        assert out["pre_existing_files"] == []
        assert out["pre_existing_files_total"] == 0

    def test_scope_applicable_pre_existing(self, tmp_path, capsys):
        """A file that existed at base_sha → applicable true with the
        right pre_existing_files list."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        (repo / "existing.txt").write_text("old", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add existing")
        base = _git(repo, "rev-parse", "HEAD").strip()
        # edit the existing file so there's a diff
        (repo / "existing.txt").write_text("edited", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "edit existing")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
        _state(task_dir, repo, base)
        rc = plan.cmd_codegraph_scope("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["applicable"] is True
        assert out["pre_existing_files"] == ["existing.txt"]
        assert out["pre_existing_files_total"] == 1


# ═══ codegraph build: missing pin ═══════════════════════════════════

class TestCodegraphBuild:
    """plan.py codegraph build with a missing/unset pin exits non-zero
    with a structured error, not a traceback."""

    def test_missing_pin_structured_error(self, tmp_path, monkeypatch,
                                          capsys):
        """The pin does not exist → exit 1 with a JSON error naming the
        pin state, no traceback."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        monkeypatch.setattr(plan, "UNDERSTAND_ANYTHING_ROOT",
                            tmp_path / "nonexistent_ua")
        rc = plan.cmd_codegraph_build(repo)
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["error"] == "understand-anything pin not available"
        assert "pin_state" in out

    def test_missing_pin_no_traceback(self, tmp_path, monkeypatch):
        """Running via subprocess must not produce a Python traceback on
        a missing pin — just a clean non-zero exit + JSON."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        env = dict(os.environ,
                   AI_DLC_UNDERSTAND_ANYTHING_ROOT=str(tmp_path / "no_such_pin"))
        r = subprocess.run(
            [sys.executable, str(_BIN / "plan.py"),
             "codegraph", "build", "--repo", str(repo)],
            capture_output=True, text=True, env=env)
        assert r.returncode != 0
        assert "Traceback" not in r.stderr
        assert "Traceback" not in r.stdout
        out = json.loads(r.stdout)
        assert out["error"] == "understand-anything pin not available"
