"""G2 — route_doctor_advisory + cmd_next wiring.

route_doctor_advisory runs a lightweight, read-only subset of
install.sh --doctor (toolchain files present+executable, config parses,
gateway client reachable) and returns None when healthy or a single
advisory string naming the first failure. cmd_next adds it under an
`advisory` key only when non-None; the check never blocks, never
changes the exit code, and writes nothing (INV-21/INV-22).

Run:  python3 -m pytest -q tests/test_route_doctor_advisory.py
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


report = _load("report", _BIN / "report.py")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "test")
    _git(r, "commit", "--allow-empty", "-q", "-m", "init")
    return r


@pytest.fixture
def healthy_root(tmp_path: Path, monkeypatch) -> Path:
    """A self-contained toolchain root that passes all three checks."""
    root = tmp_path / "toolchain"
    (root / "bin").mkdir(parents=True)
    (root / "config").mkdir()
    for f in ("plan.py", "report.py"):
        p = root / "bin" / f
        p.write_text("#!/usr/bin/env python3\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    (root / "config" / "collapsed.config.yaml").write_text(
        "execution:\n  planning_threshold_files: 4\n")
    client = tmp_path / "gw-client"
    client.write_text("#!/bin/sh\n")
    client.chmod(client.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(report, "_TOOLCHAIN_ROOT", root)
    monkeypatch.setenv("AI_DLC_CLIENT", str(client))
    return root


# ── route_doctor_advisory: the three checks ────────────────────────────

def test_healthy_returns_none(healthy_root, repo):
    assert report.route_doctor_advisory(repo) is None


def test_missing_plan_py_is_reported(healthy_root, repo):
    (healthy_root / "bin" / "plan.py").unlink()
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "bin/plan.py" in adv
    assert "missing" in adv
    assert "install.sh" in adv  # a copy-pasteable repair command


def test_non_executable_plan_py_is_reported(healthy_root, repo):
    p = healthy_root / "bin" / "plan.py"
    p.chmod(p.stat().st_mode & ~stat.S_IXUSR)
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "bin/plan.py" in adv
    assert "executable" in adv


def test_missing_config_is_reported(healthy_root, repo):
    (healthy_root / "config" / "collapsed.config.yaml").unlink()
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "collapsed.config.yaml" in adv
    assert "missing" in adv


def test_empty_config_is_reported(healthy_root, repo):
    (healthy_root / "config" / "collapsed.config.yaml").write_text("")
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "collapsed.config.yaml" in adv
    assert "empty" in adv


def test_missing_gateway_client_is_reported(healthy_root, repo,
                                            monkeypatch):
    monkeypatch.setenv("AI_DLC_CLIENT", str(healthy_root / "no-such-client"))
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "gateway client" in adv
    assert "AI_DLC_CLIENT" in adv


def test_first_failure_wins(healthy_root, repo, monkeypatch):
    """When plan.py is missing AND the client is missing, the toolchain
    check (1) fires first — the gateway probe (3) never runs."""
    (healthy_root / "bin" / "plan.py").unlink()
    monkeypatch.setenv("AI_DLC_CLIENT", str(healthy_root / "no-such-client"))
    adv = report.route_doctor_advisory(repo)
    assert adv is not None
    assert "bin/plan.py" in adv
    assert "gateway" not in adv


# ── cmd_next wiring ────────────────────────────────────────────────────

def _work_task_dir(repo: Path) -> Path:
    td = repo / ".ai-dlc" / "tasks" / "c1-planning"
    td.mkdir(parents=True)
    (td / "state.json").write_text(json.dumps({
        "change_id": "c1", "route": "inline", "stage": "WORK",
    }))
    return td


def test_cmd_next_has_no_advisory_key_when_healthy(repo, monkeypatch,
                                                   capsys):
    monkeypatch.setattr(report, "route_doctor_advisory",
                        lambda r: None)
    td = _work_task_dir(repo)
    capsys.readouterr()
    rc = report.cmd_next(td, repo)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "advisory" not in out
    # the existing fields are still computed
    assert out["stage"] == "WORK"
    assert "do" in out


def test_cmd_next_carries_advisory_without_changing_exit_code(repo,
                                                              monkeypatch,
                                                              capsys):
    msg = ("bin/plan.py is missing — re-run the installer")
    monkeypatch.setattr(report, "route_doctor_advisory", lambda r: msg)
    td = _work_task_dir(repo)
    capsys.readouterr()
    rc = report.cmd_next(td, repo)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0  # exit code unchanged
    assert out["advisory"] == msg
    # other fields are still computed and unchanged in shape
    assert out["stage"] == "WORK"
    assert "do" in out


def test_cmd_next_advisory_does_not_block_failure_exit_code(repo,
                                                            monkeypatch,
                                                            capsys):
    """A failing health check must not turn a non-zero next into zero
    or vice versa — next's exit code follows the task state alone."""
    monkeypatch.setattr(report, "route_doctor_advisory",
                        lambda r: "gateway down")
    # no state.json → next returns 0 with an init hint; advisory still
    # attaches, exit code stays 0
    td = repo / ".ai-dlc" / "tasks" / "empty-planning"
    td.mkdir(parents=True)
    capsys.readouterr()
    rc = report.cmd_next(td, repo)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["advisory"] == "gateway down"


def test_route_doctor_advisory_is_read_only(healthy_root, repo, tmp_path):
    """INV-22: the check creates, modifies, or deletes no file."""
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")
              if p.is_file()}
    report.route_doctor_advisory(repo)
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")
             if p.is_file()}
    assert before == after
