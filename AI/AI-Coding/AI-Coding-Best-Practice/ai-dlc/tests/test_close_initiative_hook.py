"""G1 — phase-chain close hook: `plan.py close` advances the owning
initiative after a successful merge + archive, reusing the Phase A
`initiative advance` function. A change id in no manifest leaves close
byte-identical to pre-change (PRD §06 regression case).

Run:  python3 -m pytest -q tests/test_close_initiative_hook.py
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


report = _load("report", _BIN / "report.py")
initiative = _load("initiative", _BIN / "initiative.py")
plan = _load("plan", _BIN / "plan.py")


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


def _approved_task_dir(repo: Path, change: str) -> Path:
    td = repo / ".ai-dlc" / "tasks" / f"{change}-planning"
    (td / "gates").mkdir(parents=True)
    (td / "gates" / "gate-merge.answer.json").write_text(json.dumps({
        "decision": "approve", "approver": "robin",
        "rationale": "looks good", "ts": "2026-09-05T00:00:00Z",
    }))
    return td


def _stub_archive_success(monkeypatch):
    """Make cmd_close reach its success tail without a real plane
    dispatch. classify_target → writable; cmd_archive_dispatch → ok."""
    monkeypatch.setattr(plan, "classify_target",
                        lambda repo, grants=None: {"class": "writable"})
    monkeypatch.setattr(plan, "cmd_archive_dispatch",
                        lambda *a, **k: ({"status": "archived"}, 0))


def test_close_advances_registered_initiative(repo, monkeypatch, capsys):
    initiative.cmd_register("demo", repo, ["phase1", "phase2"])
    td = _approved_task_dir(repo, "phase1")
    _stub_archive_success(monkeypatch)

    calls = []
    real_advance = initiative.cmd_advance

    def _spy(change_id, r):
        calls.append(change_id)
        return real_advance(change_id, r)

    monkeypatch.setattr(plan, "init_advance", _spy)
    capsys.readouterr()

    rc = plan.cmd_close("phase1", repo, td, None, False)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["closed"] is True

    # advance was invoked exactly once with the closed change id
    assert calls == ["phase1"]
    # the hook's result is surfaced (the phase was advanced)
    assert out["initiative_advance"]["advanced"] is True
    assert out["initiative_advance"]["delivered"] == "phase1"

    # the manifest itself moved: phase1 delivered, phase2 queued
    m = json.loads((repo / ".ai-dlc" / "initiatives" / "demo.json")
                   .read_text())
    assert m["phases"][0]["status"] == "delivered"
    assert m["phases"][1]["status"] == "queued"


def test_close_on_unregistered_change_is_byte_identical(repo, monkeypatch,
                                                        capsys):
    """A change id in no manifest must leave close's output byte-identical
    to pre-change — no initiative_advance key, advance never called."""
    td = _approved_task_dir(repo, "orphan-change")
    _stub_archive_success(monkeypatch)

    monkeypatch.setattr(plan, "init_advance",
                        lambda *a, **k: pytest.fail("advance must not be "
                                                    "called for an "
                                                    "unregistered change"))
    capsys.readouterr()

    rc = plan.cmd_close("orphan-change", repo, td, None, False)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["closed"] is True
    # the defining regression property: no new key
    assert "initiative_advance" not in out


def test_close_does_not_advance_when_archive_fails(repo, monkeypatch,
                                                   capsys):
    """INV-20 / spec: archive non-zero → no lookup, no advancement."""
    initiative.cmd_register("demo", repo, ["phase1", "phase2"])
    td = _approved_task_dir(repo, "phase1")
    monkeypatch.setattr(plan, "classify_target",
                        lambda repo, grants=None: {"class": "writable"})
    monkeypatch.setattr(plan, "cmd_archive_dispatch",
                        lambda *a, **k: ({"status": "failed",
                                          "why": "simulated"}, 27))
    monkeypatch.setattr(plan, "init_advance",
                        lambda *a, **k: pytest.fail("advance must not run "
                                                    "when archive fails"))
    capsys.readouterr()

    rc = plan.cmd_close("phase1", repo, td, None, False)
    assert rc == 27
    # phase1 stays pending — the hook never fired
    m = json.loads((repo / ".ai-dlc" / "initiatives" / "demo.json")
                   .read_text())
    assert m["phases"][0]["status"] == "pending"


def test_close_does_not_advance_without_approval(repo, monkeypatch, capsys):
    """Spec: close's existing early-return path (no approval) → no
    advancement."""
    initiative.cmd_register("demo", repo, ["phase1", "phase2"])
    td = repo / ".ai-dlc" / "tasks" / "phase1-planning"
    (td / "gates").mkdir(parents=True)  # no answer file
    _stub_archive_success(monkeypatch)
    monkeypatch.setattr(plan, "init_advance",
                        lambda *a, **k: pytest.fail("advance must not run "
                                                    "without approval"))
    capsys.readouterr()

    rc = plan.cmd_close("phase1", repo, td, None, False)
    # EXIT_INCONCLUSIVE — the gate carries no approval
    assert rc != 0
    m = json.loads((repo / ".ai-dlc" / "initiatives" / "demo.json")
                   .read_text())
    assert m["phases"][0]["status"] == "pending"


def test_advancement_failure_does_not_break_close(repo, monkeypatch, capsys):
    """Spec: advancement failure is reported but close's exit status and
    already-written merge/archive result are unaffected."""
    initiative.cmd_register("demo", repo, ["phase1", "phase2"])
    td = _approved_task_dir(repo, "phase1")
    _stub_archive_success(monkeypatch)

    def _boom(*a, **k):
        raise RuntimeError("simulated advancement failure")

    monkeypatch.setattr(plan, "init_advance", _boom)
    capsys.readouterr()

    rc = plan.cmd_close("phase1", repo, td, None, False)
    assert rc == 0  # close still succeeds
    out = json.loads(capsys.readouterr().out)
    assert out["closed"] is True
    # the failure is surfaced, not swallowed
    assert out["initiative_advance"]["advanced"] is False
    assert "simulated advancement failure" in \
        out["initiative_advance"]["error"]
