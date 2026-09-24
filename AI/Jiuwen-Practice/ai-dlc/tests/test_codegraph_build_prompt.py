"""Acceptance tests for the non-interactive discipline preamble in the
codegraph build prompt (PRD
docs/prd-codegraph-build-noninteractive-incremental.md §02/§05).

_codegraph_build_core constructs a build_prompt that embeds the pinned
understand/SKILL.md wholesale.  SKILL.md §7's "existing graph + unchanged
commit hash" branch asks the user a three-way question and waits for an
answer — but a jiuwenswarm session dispatch has no human to answer it.
These tests assert the prompt string now carries an explicit non-interactive
preamble, so the dispatched role knows not to block and knows an existing
on-disk graph may be reusable.

The test monkeypatches run_codegraph_session (same style as
test_codegraph_subagent_prompt.py / test_codegraph_brief.py) to capture
the prompt string and asserts on its content — no real pin or session.

Run:  python3 -m pytest tests/test_codegraph_build_prompt.py -v
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


plan = _load("plan_cgbp_test_mod", _BIN / "plan.py")
report = _load("report_cgbp_test_mod", _BIN / "report.py")


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


def _capture_build_prompt(tmp_path, monkeypatch) -> str:
    """Run _codegraph_build_core with run_codegraph_session mocked so it
    records the prompt string passed to it, and return that prompt."""
    repo = tmp_path / "repo"
    _seed_repo(repo)
    _fake_pin(monkeypatch, tmp_path)

    captured = {}

    def fake_session(change, prompt, repo, task_dir, mode, timeout):
        captured["prompt"] = prompt
        return ({"session_name": "test", "round_complete": True,
                 "interrupted": False, "timed_out": False,
                 "client_rc": 0}, [])

    monkeypatch.setattr(plan, "run_codegraph_session", fake_session)
    plan._codegraph_build_core(repo)
    assert "prompt" in captured, "run_codegraph_session was not called"
    return captured["prompt"]


# ═══ non-interactive preamble ═══════════════════════════════════════

class TestBuildPromptNonInteractivePreamble:
    """PRD §02/§05: the build prompt must tell the dispatched role that
    this is an unattended dispatch, that it must not wait for a human
    answer, and that an existing .ua/knowledge-graph.json may be reused."""

    def test_states_unattended_automated_dispatch(self, tmp_path,
                                                   monkeypatch):
        """(a) The prompt identifies this as an unattended/automated/
        non-interactive session dispatch."""
        prompt = _capture_build_prompt(tmp_path, monkeypatch)
        lower = prompt.lower()
        assert "unattended" in lower or "automated" in lower \
            or "non-interactive" in lower or "noninteractive" in lower, \
            "prompt does not state this is an unattended/automated dispatch"

    def test_instructs_not_to_wait_or_ask_user(self, tmp_path,
                                                monkeypatch):
        """(b) The prompt instructs the role not to wait for or ask the
        user a question."""
        prompt = _capture_build_prompt(tmp_path, monkeypatch)
        lower = prompt.lower()
        assert "do not wait" in lower or "must not wait" in lower \
            or "do not ask" in lower, \
            "prompt does not tell the role not to wait/ask the user"

    def test_mentions_existing_reusable_graph(self, tmp_path, monkeypatch):
        """(c) The prompt mentions that .ua/knowledge-graph.json may
        already exist and should be treated as reusable."""
        prompt = _capture_build_prompt(tmp_path, monkeypatch)
        assert ".ua/knowledge-graph.json" in prompt, \
            "prompt does not mention .ua/knowledge-graph.json"
        lower = prompt.lower()
        assert "reus" in lower, \
            "prompt does not describe the existing graph as reusable"

    def test_preamble_precedes_skill_text(self, tmp_path, monkeypatch):
        """The non-interactive preamble appears before the embedded
        SKILL.md body, so the role reads the run context first."""
        prompt = _capture_build_prompt(tmp_path, monkeypatch)
        preamble_idx = prompt.lower().find("unattended")
        skill_idx = prompt.find("--- SKILL.md ---")
        assert preamble_idx != -1 and skill_idx != -1, \
            "preamble marker or SKILL.md delimiter not found"
        assert preamble_idx < skill_idx, \
            "non-interactive preamble must come before the embedded SKILL.md"
