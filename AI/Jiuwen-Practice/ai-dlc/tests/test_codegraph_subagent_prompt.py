"""Acceptance tests for the subagent_type listing in codegraph prompts.

Verifies that when UNDERSTAND_ANYTHING_ROOT points at a tree with
agents/*.md files, the build_prompt and brief_prompt text constructed
inside _codegraph_build_core / cmd_codegraph_brief actually contains the
subagent_type names (filename stems).  Also verifies graceful omission
when the agents directory is absent or empty.

Run:  python3 -m pytest tests/test_codegraph_subagent_prompt.py -v
"""
import importlib.util
import json
import os
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


plan = _load("plan_cgsap_test_mod", _BIN / "plan.py")
report = _load("report_cgsap_test_mod", _BIN / "report.py")


# ── helpers ─────────────────────────────────────────────────────────

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


def _fake_pin_with_agents(monkeypatch, tmp_path,
                          agent_names: list[str] | None = None) -> Path:
    """Monkeypatch UNDERSTAND_ANYTHING_ROOT to a tmp path with a valid
    pin, a minimal skill tree, and optionally agents/*.md files."""
    ua_root = tmp_path / "ua_root"
    plugin = ua_root / "understand-anything-plugin"
    (plugin / "skills" / "understand").mkdir(parents=True, exist_ok=True)
    (plugin / "skills" / "understand-diff").mkdir(parents=True, exist_ok=True)
    (plugin / "skills" / "understand" / "SKILL.md").write_text(
        "# understand\nBuild the graph.\n", encoding="utf-8")
    (plugin / "skills" / "understand-diff" / "SKILL.md").write_text(
        "# understand-diff\nAnalyze the diff.\n", encoding="utf-8")
    if agent_names is not None:
        agents_dir = plugin / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name in agent_names:
            (agents_dir / f"{name}.md").write_text(
                f"---\nname: {name}\ndescription: test\n---\nbody\n",
                encoding="utf-8")
    # write a valid pin — use the real digest function so the pin check passes
    digest = plan.understand_anything_tree_digest(ua_root)
    pin = {"tag": "v2.9.0", "sha": "abc123",
           "sparse_paths": ["understand-anything-plugin"],
           "installed_at": "2026-09-04T00:00:00+00:00",
           "size_bytes": 100,
           "tree_sha256": digest}
    report.save_json(ua_root / ".aidlc-pin.json", pin)
    monkeypatch.setattr(plan, "UNDERSTAND_ANYTHING_ROOT", ua_root)
    return ua_root


# ═══ _registered_subagent_types ═════════════════════════════════════

class TestRegisteredSubagentTypes:
    """_registered_subagent_types reads agents/*.md stems from the pinned
    tree, or returns [] when absent/unreadable."""

    def test_returns_agent_stems(self, tmp_path, monkeypatch):
        names = ["project-scanner", "file-analyzer", "graph-reviewer"]
        _fake_pin_with_agents(monkeypatch, tmp_path, agent_names=names)
        result = plan._registered_subagent_types()
        assert result == sorted(names)

    def test_empty_when_no_agents_dir(self, tmp_path, monkeypatch):
        _fake_pin_with_agents(monkeypatch, tmp_path, agent_names=None)
        assert plan._registered_subagent_types() == []

    def test_empty_when_root_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(plan, "UNDERSTAND_ANYTHING_ROOT",
                            tmp_path / "nonexistent")
        assert plan._registered_subagent_types() == []


# ═══ build_prompt contains subagent types ═══════════════════════════

class TestBuildPromptSubagentListing:
    """_codegraph_build_core's build_prompt must list registered
    subagent_type names when agents are present, and omit the sentence
    gracefully when they are not."""

    def test_build_prompt_names_subagents(self, tmp_path, monkeypatch):
        """When agents/*.md exist, the build prompt dispatched to
        run_codegraph_session contains each subagent_type name."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        agent_names = ["project-scanner", "file-analyzer",
                       "architecture-analyzer"]
        _fake_pin_with_agents(monkeypatch, tmp_path,
                              agent_names=agent_names)

        captured = {}

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            captured["prompt"] = prompt
            return ({"session_name": "test", "round_complete": True,
                     "interrupted": False, "timed_out": False,
                     "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session", fake_session)
        plan._codegraph_build_core(repo)

        prompt = captured["prompt"]
        for name in agent_names:
            assert name in prompt, \
                f"subagent_type '{name}' missing from build prompt"

    def test_build_prompt_omits_sentence_when_no_agents(self, tmp_path,
                                                         monkeypatch):
        """When no agents/ directory exists, the build prompt has no
        subagent listing sentence — graceful omission, no error."""
        repo = tmp_path / "repo"
        _seed_repo(repo)
        _fake_pin_with_agents(monkeypatch, tmp_path, agent_names=None)

        captured = {}

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            captured["prompt"] = prompt
            return ({"session_name": "test", "round_complete": True,
                     "interrupted": False, "timed_out": False,
                     "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session", fake_session)
        plan._codegraph_build_core(repo)

        prompt = captured["prompt"]
        assert "subagent_type" not in prompt
        assert "registered with jiuwenswarm" not in prompt


# ═══ brief_prompt contains subagent types ═══════════════════════════

class TestBriefPromptSubagentListing:
    """cmd_codegraph_brief's brief_prompt must also list registered
    subagent_type names (graph-reviewer is relevant to diff analysis)."""

    def test_brief_prompt_names_subagents(self, tmp_path, monkeypatch,
                                          capsys):
        """When agents/*.md exist, the brief prompt dispatched to the
        second run_codegraph_session call contains each subagent_type."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        agent_names = ["project-scanner", "file-analyzer",
                       "graph-reviewer", "assemble-reviewer"]
        _fake_pin_with_agents(monkeypatch, tmp_path,
                              agent_names=agent_names)

        prompts = []
        call_count = {"n": 0}

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            call_count["n"] += 1
            prompts.append(prompt)
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
                    "# Codegraph impact brief\n")
            return ({"session_name": f"test-{call_count['n']}",
                     "round_complete": True, "interrupted": False,
                     "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session", fake_session)
        plan.cmd_codegraph_brief("c1", repo, task_dir)
        capsys.readouterr()  # swallow stdout

        # the brief prompt is the second call
        assert len(prompts) == 2
        brief_prompt = prompts[1]
        for name in agent_names:
            assert name in brief_prompt, \
                f"subagent_type '{name}' missing from brief prompt"

    def test_brief_prompt_omits_sentence_when_no_agents(self, tmp_path,
                                                        monkeypatch,
                                                        capsys):
        """When no agents/ directory exists, the brief prompt has no
        subagent listing sentence."""
        repo, task_dir = _repo_with_pre_existing_change(tmp_path)
        _fake_pin_with_agents(monkeypatch, tmp_path, agent_names=None)

        prompts = []
        call_count = {"n": 0}

        def fake_session(change, prompt, repo, task_dir, mode, timeout):
            call_count["n"] += 1
            prompts.append(prompt)
            if call_count["n"] == 1:
                ua_dir = repo / ".ua"
                ua_dir.mkdir(exist_ok=True)
                (ua_dir / "knowledge-graph.json").write_text(
                    '{"nodes": [], "edges": []}', encoding="utf-8")
            else:
                brief_dir = repo / "codegraph"
                brief_dir.mkdir(exist_ok=True)
                (brief_dir / "impact-brief.md").write_text(
                    "# Codegraph impact brief\n")
            return ({"session_name": f"test-{call_count['n']}",
                     "round_complete": True, "interrupted": False,
                     "timed_out": False, "client_rc": 0}, [])

        monkeypatch.setattr(plan, "run_codegraph_session", fake_session)
        plan.cmd_codegraph_brief("c1", repo, task_dir)
        capsys.readouterr()

        assert len(prompts) == 2
        brief_prompt = prompts[1]
        assert "subagent_type" not in brief_prompt
        assert "registered with jiuwenswarm" not in brief_prompt
