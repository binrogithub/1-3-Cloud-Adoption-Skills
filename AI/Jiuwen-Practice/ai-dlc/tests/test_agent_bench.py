"""Acceptance tests for the agent-bench role (G2,
PRD docs/prd-browser-verify-and-agent-bench.md).

Covers:
  - agent_bench_pin_state: four branches (healthy, root missing, pin
    missing, digest mismatch) — same {ok, why, remedy, exit_code} shape
    understand_anything_pin_state uses (PRD §06, spec agent-bench-role).
  - cmd_bench: pin unavailable → agent_bench_state='unavailable', exit 0,
    no session dispatched; a judged-complete dispatch writes a signed
    result record including the pinned Harbor version and tree_sha256
    (INV-40); the bench subcommand has no --change argument (spec
    agent-bench-role: "accepts no --change").

Run:  python3 -m pytest tests/test_agent_bench.py -v
"""
import argparse
import importlib.util
import json
import os
import stat
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


plan = _load("plan_ab_test_mod", _BIN / "plan.py")
report = _load("report_ab_test_mod", _BIN / "report.py")


def _make_venv(root: Path) -> Path:
    """Stand up a minimal venv tree with an executable harbor entry point."""
    venv_bin = root / "venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    harbor = venv_bin / "harbor"
    harbor.write_text("#!/usr/bin/env python3\nimport harbor\n", encoding="utf-8")
    harbor.chmod(harbor.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # a lib file so the digest has real content
    (root / "venv" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "venv" / "lib" / "harbor.py").write_text(
        "VERSION = '0.1.0'\n", encoding="utf-8")
    return root


def _write_valid_pin(root: Path, tag: str = "0.1.0") -> dict:
    """Write a pin whose tree_sha256 matches the standing venv, using the
    real digest function so the pin and the check can never drift."""
    pin = {"tag": tag, "sha": None,
           "tree_sha256": plan.agent_bench_tree_digest(root),
           "sparse_paths": ["venv"],
           "installed_at": "2026-09-06T00:00:00Z",
           "size_bytes": 100}
    report.save_json(root / ".aidlc-pin.json", pin)
    return pin


# ── agent_bench_pin_state ─────────────────────────────────────────────


class TestAgentBenchPinState:
    def test_healthy_pin_is_ok(self, tmp_path, monkeypatch):
        root = tmp_path / "agent-bench"
        _make_venv(root)
        _write_valid_pin(root)
        monkeypatch.setattr(plan, "AGENT_BENCH_ROOT", root)

        state = plan.agent_bench_pin_state()

        assert state["ok"] is True
        assert state["root"] == str(root)
        assert state["pin"]["tag"] == "0.1.0"
        assert state["pin"]["tree_sha256"]

    def test_root_missing_is_not_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(plan, "AGENT_BENCH_ROOT",
                            tmp_path / "no_such_root")

        state = plan.agent_bench_pin_state()

        assert state["ok"] is False
        assert "why" in state and "remedy" in state
        assert "exit_code" in state
        assert "install-agent-bench" in state["remedy"]

    def test_pin_missing_is_not_ok(self, tmp_path, monkeypatch):
        root = tmp_path / "agent-bench"
        _make_venv(root)
        # no pin written
        monkeypatch.setattr(plan, "AGENT_BENCH_ROOT", root)

        state = plan.agent_bench_pin_state()

        assert state["ok"] is False
        assert "why" in state and "remedy" in state
        assert "exit_code" in state
        assert "no pin stands" in state["why"]

    def test_digest_mismatch_is_not_ok(self, tmp_path, monkeypatch):
        root = tmp_path / "agent-bench"
        _make_venv(root)
        # pin with a wrong digest — simulates a venv modified after pinning
        pin = {"tag": "0.1.0", "sha": None,
               "tree_sha256": "0" * 64,
               "sparse_paths": ["venv"],
               "installed_at": "2026-09-06T00:00:00Z",
               "size_bytes": 100}
        report.save_json(root / ".aidlc-pin.json", pin)
        monkeypatch.setattr(plan, "AGENT_BENCH_ROOT", root)

        state = plan.agent_bench_pin_state()

        assert state["ok"] is False
        assert "why" in state and "remedy" in state
        assert "exit_code" in state
        assert state.get("pinned_tree_sha256") == "0" * 64
        assert state.get("measured_tree_sha256") != "0" * 64
        assert "no longer matches" in state["why"]


# ── cmd_bench ─────────────────────────────────────────────────────────


def _stub_healthy_pin(monkeypatch, tmp_path) -> dict:
    """Point AGENT_BENCH_ROOT at a tmp root with a valid venv + pin and
    redirect bench history/runs dirs to tmp paths. Returns the pin."""
    root = tmp_path / "agent-bench"
    _make_venv(root)
    pin = _write_valid_pin(root)
    monkeypatch.setattr(plan, "AGENT_BENCH_ROOT", root)
    history = tmp_path / "bench-history"
    runs = tmp_path / "bench-runs"
    history.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(plan, "BENCH_HISTORY_DIR", history)
    monkeypatch.setattr(plan, "BENCH_RUNS_DIR", runs)
    return pin


class TestCmdBenchUnavailable:
    def test_unavailable_pin_returns_zero_and_never_dispatches(
            self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(plan, "AGENT_BENCH_ROOT",
                            tmp_path / "no_such_pin")

        def _must_not_run(*a, **kw):
            raise AssertionError("run_agent_bench_session must not be "
                                  "reached when the pin is unavailable")
        monkeypatch.setattr(plan, "run_agent_bench_session", _must_not_run)

        rc = plan.cmd_bench()
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["agent_bench_state"] == "unavailable"
        assert out["pin_state"]["ok"] is False


class TestCmdBenchComplete:
    def test_judged_complete_writes_signed_record_with_version_and_sha(
            self, tmp_path, monkeypatch, capsys):
        pin = _stub_healthy_pin(monkeypatch, tmp_path)

        def fake_session(prompt, repo, task_dir, mode, timeout):
            return ({"dispatch": "agent-bench", "mode": mode,
                     "repo": str(repo), "client": "jiuwenswarm",
                     "client_rc": 0, "timed_out": False,
                     "evidence": str(task_dir / "evidence" / "x.jsonl"),
                     "session_name": "agent-bench-001",
                     "started_at": "2026-09-06T00:00:00Z",
                     "ended_at": "2026-09-06T00:05:00Z",
                     "elapsed_seconds": 300.0,
                     "round_complete": True, "interrupted": False,
                     "envelope_note": "frames"}, [])
        monkeypatch.setattr(plan, "run_agent_bench_session", fake_session)

        rc = plan.cmd_bench(dataset="terminal-bench@2.0", model="claude",
                            n_concurrent=1)
        out = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert out["agent_bench_state"] == "complete"
        assert "result_file" in out

        record = json.loads(Path(out["result_file"]).read_text())
        # INV-40: the signed record must name the version and tree_sha256
        assert record["harbor_version"] == pin["tag"]
        assert record["tree_sha256"] == pin["tree_sha256"]
        assert record["dataset"] == "terminal-bench@2.0"
        assert record["model"] == "claude"
        assert record["n_concurrent"] == 1
        assert record["timestamp"]

    def test_incomplete_dispatch_writes_no_record(
            self, tmp_path, monkeypatch, capsys):
        _stub_healthy_pin(monkeypatch, tmp_path)
        history = plan.BENCH_HISTORY_DIR

        def fake_session(prompt, repo, task_dir, mode, timeout):
            return ({"dispatch": "agent-bench", "round_complete": False,
                     "interrupted": False, "timed_out": False,
                     "client_rc": 0}, [])
        monkeypatch.setattr(plan, "run_agent_bench_session", fake_session)

        rc = plan.cmd_bench()
        out = json.loads(capsys.readouterr().out)

        assert rc != 0
        assert out["agent_bench_state"] == "incomplete"
        assert "result_file" not in out
        assert list(history.glob("*.json")) == []


class TestBenchSubparserHasNoChange:
    def test_no_change_argument_on_bench_subcommand(self):
        """Spec agent-bench-role: 'it SHALL accept no --change argument'
        and shall not read/write any path under .ai-dlc/tasks/."""
        ap = argparse.ArgumentParser()
        sub = ap.add_subparsers(dest="cmd", required=True)
        plan._build_subparsers(sub)
        # find the bench subparser among the registered parsers
        bench_parser = None
        for action in ap._actions:
            if isinstance(action, argparse._SubParsersAction):
                bench_parser = action.choices.get("bench")
        assert bench_parser is not None, "no 'bench' subcommand registered"
        opt_strings = []
        for a in bench_parser._actions:
            opt_strings.extend(a.option_strings)
        assert "--change" not in opt_strings
        assert "--repo" not in opt_strings
        # the options that must exist
        assert "--dataset" in opt_strings
        assert "--model" in opt_strings
        assert "--n-concurrent" in opt_strings
