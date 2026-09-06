"""Acceptance tests for Epic B — design-surface contradiction in
route_check().

An inline route whose change touches the web/deck design surface must
stop the task regardless of file count — even a 1-file .html change
well under planning_threshold_files.  This is a second, independent
contradiction symmetric to the existing count-based check: same gate,
same exception path, same "contradiction stops the run" shape.

Run:  python3 -m pytest tests/test_route_design_surface.py -v
"""
import importlib.util
import subprocess
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


report = _load("report_test_mod_route_ds", _BIN / "bin" / "report.py")


def _seed_repo(repo: Path) -> str:
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


def _commit_files(repo: Path, files: dict[str, str], msg: str = "change"):
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", msg],
                   check=True)


def _make_state(task_dir: Path, repo: Path, base: str, route: str,
                change_id: str = "b1") -> dict:
    task_dir.mkdir(parents=True, exist_ok=True)
    st = {"task_id": change_id, "route": route, "base_sha": base,
          "change_id": change_id, "repo": str(repo.resolve()),
          "stage": "WORK", "human_state": "Working",
          "started_at": report.now_iso()}
    report.save_json(task_dir / "state.json", st)
    return st


# ═══ Design-surface contradiction ═════════════════════════════════════

class TestDesignSurfaceContradiction:
    """Epic B: inline route + design surface → stop, regardless of count."""

    def test_one_html_file_stops_inline(self, tmp_path):
        """A single .html file on an inline route stops the task even
        though measured_files (1) is well below the threshold (4)."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"index.html": "<h1>hi</h1>\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is not None, "1-file .html inline must stop"
        assert "design surface" in block["why"], block["why"]
        assert "file count" not in block["why"], block["why"]
        assert check["design_surface"]["applicable"] is True
        assert check["measured_files"] == 1

    def test_one_css_file_stops_inline(self, tmp_path):
        """A single .css file is also a design-surface hit."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"style.css": "body{color:red}\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is not None
        assert "design surface" in block["why"]

    def test_two_design_files_stops_inline(self, tmp_path):
        """Two design-surface files (under threshold) still stop."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"a.html": "<a></a>\n", "b.css": "a{}\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is not None
        assert "design surface" in block["why"]
        assert check["measured_files"] == 2

    def test_exception_suppresses_design_surface(self, tmp_path):
        """A recorded exception suppresses the design-surface contradiction
        just as it suppresses the count-based one."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"index.html": "<h1>hi</h1>\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        gates = task_dir / "gates"
        gates.mkdir(parents=True)
        report.save_json(gates / "gate-route.answer.json", {
            "decision": "exception",
            "reason": "single landing page tweak, design review not needed",
            "author": "tester", "ts": report.now_iso()})
        check, block = report.route_check(task_dir, repo, st)
        assert block is None, "exception must suppress the design-surface stop"
        assert "exception" in check

    def test_planned_route_unaffected(self, tmp_path):
        """A planned route over a .html file does not stop — the
        design-surface check only fires for inline."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"index.html": "<h1>hi</h1>\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="planned")
        check, block = report.route_check(task_dir, repo, st)
        assert block is None


# ═══ Regression: pure-code changes ═══════════════════════════════════

class TestPureCodeRegression:
    """Epic B regression: non-web/deck changes under threshold pass
    inline exactly as before — the new check does not fire."""

    def test_one_py_file_passes_inline(self, tmp_path):
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"main.py": "print('hi')\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is None, "1-file .py inline must pass"
        assert check["design_surface"]["applicable"] is False

    def test_three_go_files_pass_inline(self, tmp_path):
        """Three .go files (under threshold=4, no design surface) pass."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"a.go": "package x\n", "b.go": "package x\n",
                             "c.go": "package x\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is None
        assert check["measured_files"] == 3
        assert check["design_surface"]["applicable"] is False

    def test_mixed_code_and_design_stops_inline(self, tmp_path):
        """A change with both .py and .html files: the design-surface
        hit stops it even if total file count is under threshold."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        _commit_files(repo, {"main.py": "x=1\n", "page.html": "<p></p>\n"})
        task_dir = tmp_path / "task"
        st = _make_state(task_dir, repo, base, route="inline")
        check, block = report.route_check(task_dir, repo, st)
        assert block is not None
        assert "design surface" in block["why"]
        assert check["measured_files"] == 2
