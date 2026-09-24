"""Acceptance tests for the codegraph role, Phase B (`plan.py codegraph brief`).

Covers the four codegraph_state outcomes cmd_codegraph_brief can report:
  - not_applicable   — all target files are net-new (PRD §07 reverse gate)
  - unavailable       — no codegraph tool installed (PRD §07: must not block)
  - build_failed      — the configured tool exists but exits non-zero
  - brief_written / brief_incomplete — the session dispatch path (mocked)

Does not touch author-prompt wiring — that is explicitly out of scope
(see docs/prd-codegraph-role.md and the Phase B delegation notes).

Run:  python3 -m pytest tests/test_codegraph_brief.py -v
"""
import importlib.util
import json
import os
import stat
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


plan = _load("plan_cgb_test_mod", _BIN / "plan.py")
report = _load("report_cgb_test_mod", _BIN / "report.py")


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


def _repo_with_pre_existing_change(tmp_path):
    """A repo where base_sha has existing.txt, then a later commit edits
    it — codegraph_surface is applicable against this pair."""
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
    _state(task_dir, repo, base)
    return repo, task_dir


def _fake_pin(monkeypatch, tmp_path) -> Path:
    """Monkeypatch UNDERSTAND_ANYTHING_ROOT to a tmp path with a valid
    pin and a minimal skill tree so understand_anything_pin_state passes."""
    ua_root = tmp_path / "ua_root"
    plugin = ua_root / "understand-anything-plugin"
    (plugin / "skills" / "understand").mkdir(parents=True, exist_ok=True)
    (plugin / "skills" / "understand-diff").mkdir(parents=True, exist_ok=True)
    (plugin / "skills" / "understand" / "SKILL.md").write_text(
        "# understand\nBuild the graph.\n", encoding="utf-8")
    (plugin / "skills" / "understand-diff" / "SKILL.md").write_text(
        "# understand-diff\nAnalyze the diff.\n", encoding="utf-8")
    # write a valid pin — use the real digest function so the pin and the
    # check never drift (the helper must not re-derive the digest inline,
    # lest it desync from understand_anything_tree_digest's definition).
    pin = {"tag": "v2.9.0", "sha": "abc123",
           "sparse_paths": ["understand-anything-plugin"],
           "installed_at": "2026-09-04T00:00:00+00:00",
           "size_bytes": 100,
           "tree_sha256": plan.understand_anything_tree_digest(ua_root)}
    report.save_json(ua_root / ".aidlc-pin.json", pin)
    monkeypatch.setattr(plan, "UNDERSTAND_ANYTHING_ROOT", ua_root)
    return ua_root


class TestCodegraphBriefNotApplicable:
    def test_all_net_new_is_a_noop(self, tmp_path, capsys):
        """No pre-existing files → not_applicable, no session dispatch,
        no codegraph/ directory created."""
        repo = tmp_path / "repo"
        base = _seed_repo(repo)
        (repo / "brand_new.txt").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add brand new")
        task_dir = repo / ".ai-dlc" / "tasks" / "c1-planning"
        _state(task_dir, repo, base)

        rc = plan.cmd_codegraph_brief("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["codegraph_state"] == "not_applicable"
        assert not (repo / "codegraph").exists()


class TestCodegraphBriefUnavailable:
    def test_no_pin_installed_is_not_an_error(self, tmp_path, monkeypatch,
                                              capsys):
        """PRD §07: pin not installed must be a normal, non-blocking
        outcome, not a failure — the common case in this environment."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        monkeypatch.setattr(plan, "UNDERSTAND_ANYTHING_ROOT",
                            tmp_path / "no_such_pin")

        rc = plan.cmd_codegraph_brief("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["codegraph_state"] == "unavailable"
        assert out["applicable"] is True
        assert not (repo / "codegraph").exists()


class TestCodegraphBriefBuildFailed:
    def test_build_session_fails(self, tmp_path, monkeypatch, capsys):
        """The pin is valid but the build session dispatch does not write
        .ua/knowledge-graph.json → build_failed, brief skipped, task not
        blocked."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        _fake_pin(monkeypatch, tmp_path)

        # build session runs but does not write the graph file
        def fake_codegraph_session(change, prompt, repo, task_dir, mode,
                                   timeout):
            return ({"session_name": f"codegraph-{change}-001",
                    "round_complete": True, "interrupted": False,
                    "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session",
                            fake_codegraph_session)

        rc = plan.cmd_codegraph_brief("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["codegraph_state"] == "build_failed"
        assert not (repo / "codegraph").exists()

        events = (task_dir / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "CODEGRAPH_UNAVAILABLE" in kinds


class TestCodegraphBriefWritten:
    def test_session_writes_brief(self, tmp_path, monkeypatch, capsys):
        """Pin valid, build succeeds, brief session dispatch (mocked)
        writes codegraph/impact-brief.md → brief_written, state.json and
        events.jsonl recorded."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        _fake_pin(monkeypatch, tmp_path)

        call_count = {"n": 0}

        def fake_codegraph_session(change, prompt, repo, task_dir, mode,
                                   timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # build call — write the graph file
                ua_dir = repo / ".ua"
                ua_dir.mkdir(exist_ok=True)
                (ua_dir / "knowledge-graph.json").write_text(
                    '{"nodes": [], "edges": []}', encoding="utf-8")
            else:
                # brief call — write the brief
                brief_dir = repo / "codegraph"
                brief_dir.mkdir(exist_ok=True)
                (brief_dir / "impact-brief.md").write_text(
                    f"# Codegraph impact brief — {change}\n\n"
                    "## Scope queried\n  existing.txt\n\n"
                    "## Callers\nnone found\n\n"
                    "## Callees / dependencies\nnone found\n\n"
                    "## Cross-module coupling flagged\nnone found\n")
            return ({"session_name": f"codegraph-{change}-{call_count['n']:03d}",
                    "round_complete": True, "interrupted": False,
                    "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session",
                            fake_codegraph_session)

        rc = plan.cmd_codegraph_brief("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["codegraph_state"] == "brief_written"
        assert out["brief_written"] is True

        brief_path = repo / "codegraph" / "impact-brief.md"
        assert brief_path.is_file()
        assert brief_path.stat().st_size > 0

        state = report.load_json(task_dir / "state.json", {})
        assert state["codegraph_brief"]["written"] is True
        assert state["codegraph_brief"]["pre_existing_files"] == \
            ["existing.txt"]

        events = (task_dir / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "CODEGRAPH_BRIEF_WRITTEN" in kinds

    def test_session_runs_but_file_missing_is_incomplete(self, tmp_path,
                                                          monkeypatch,
                                                          capsys):
        """The brief session dispatch completes but never writes the
        file → brief_incomplete, non-zero exit, recorded honestly."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        _fake_pin(monkeypatch, tmp_path)

        call_count = {"n": 0}

        def fake_codegraph_session(change, prompt, repo, task_dir, mode,
                                   timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # build call — write the graph file
                ua_dir = repo / ".ua"
                ua_dir.mkdir(exist_ok=True)
                (ua_dir / "knowledge-graph.json").write_text(
                    '{"nodes": [], "edges": []}', encoding="utf-8")
            return ({"session_name": f"codegraph-{change}-{call_count['n']:03d}",
                    "round_complete": True, "interrupted": False,
                    "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session",
                            fake_codegraph_session)

        rc = plan.cmd_codegraph_brief("c1", repo, task_dir)
        out = json.loads(capsys.readouterr().out)

        assert rc != 0
        assert out["codegraph_state"] == "brief_incomplete"
        assert out["brief_written"] is False

        state = report.load_json(task_dir / "state.json", {})
        assert state["codegraph_brief"]["written"] is False

        events = (task_dir / "events.jsonl").read_text().splitlines()
        kinds = [json.loads(e)["event"] for e in events]
        assert "CODEGRAPH_BRIEF_INCOMPLETE" in kinds


class TestProductExcludes:
    def test_codegraph_excluded_from_delivery(self):
        """codegraph/** and .ua/** must be in product_excludes so the
        brief and the knowledge graph never count toward
        landed_files/landed_bytes."""
        cfg_path = _BIN.parent / "config" / "collapsed.config.yaml"
        text = cfg_path.read_text(encoding="utf-8")
        assert "codegraph/**" in text
        assert ".ua/**" in text
