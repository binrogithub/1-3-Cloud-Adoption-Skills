"""Tests for bin/initiative.py — plan.py initiative register/advance/status.

Exercises every Requirement/Scenario in
openspec/changes/phase-chain-automation/specs/phase-chain-automation/spec.md
against a throwaway git repo under tmp_path, so no real .ai-dlc state is
touched.

Run:  python3 -m pytest -q tests/test_initiative.py
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


def _manifest(repo: Path, initiative_id: str) -> dict:
    return json.loads(
        (repo / ".ai-dlc" / "initiatives" / f"{initiative_id}.json")
        .read_text(encoding="utf-8"))


# ── register / status round trip ─────────────────────────────────────

def test_register_then_status_shows_pending_phases(repo, capsys):
    rc = initiative.cmd_register("demo-init", repo, ["c1", "c2", "c3"],
                                 title="Demo", created_by="robin")
    assert rc == 0
    capsys.readouterr()

    rc = initiative.cmd_status("demo-init", repo)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["initiative_id"] == "demo-init"
    assert [p["status"] for p in out["phases"]] == ["pending"] * 3
    assert [p["change_id"] for p in out["phases"]] == ["c1", "c2", "c3"]
    assert [p["seq"] for p in out["phases"]] == [1, 2, 3]


def test_register_extends_only_the_new_tail(repo):
    initiative.cmd_register("demo-init", repo, ["c1", "c2"])
    before = _manifest(repo, "demo-init")

    rc = initiative.cmd_register("demo-init", repo, ["c1", "c2", "c3"])
    assert rc == 0
    after = _manifest(repo, "demo-init")

    assert after["phases"][0] == before["phases"][0]
    assert after["phases"][1] == before["phases"][1]
    assert [p["change_id"] for p in after["phases"]] == ["c1", "c2", "c3"]
    assert after["phases"][2]["status"] == "pending"


def test_register_rejects_duplicate_change_id_across_initiatives(repo):
    initiative.cmd_register("init-a", repo, ["shared-id"])
    rc = initiative.cmd_register("init-b", repo, ["shared-id"])
    assert rc == 1
    assert not (repo / ".ai-dlc" / "initiatives" / "init-b.json").exists()


def test_register_rejects_duplicate_change_id_within_same_call(repo):
    rc = initiative.cmd_register("init-c", repo, ["x", "x"])
    assert rc == 1
    assert not (repo / ".ai-dlc" / "initiatives" / "init-c.json").exists()


# ── advance: no-op for unregistered changes (INV-6) ────────────────────

def test_advance_on_change_in_no_manifest_is_a_noop(repo):
    rc = initiative.cmd_advance("never-registered", repo)
    assert rc == 0
    assert not (repo / ".ai-dlc" / "initiatives").exists()


# ── advance: the next phase is pending → queue it cleanly ─────────────

def test_advance_queues_next_pending_phase_with_clean_state(repo):
    initiative.cmd_register("demo-init", repo, ["phase1", "phase2"])

    rc = initiative.cmd_advance("phase1", repo)
    assert rc == 0

    m = _manifest(repo, "demo-init")
    assert m["phases"][0]["status"] == "delivered"
    assert m["phases"][1]["status"] == "queued"

    # The next phase's task skeleton exists and was created through the
    # same cmd_init report.py uses — its state carries no planning.json
    # or any field copied from phase1.
    task_dir = repo / ".ai-dlc" / "tasks" / "phase2-planning"
    state = json.loads((task_dir / "state.json").read_text())
    assert state["change_id"] == "phase2"
    assert state["route"] == "planned"
    assert state["stage"] == "WORK"
    assert not (task_dir / "planning.json").exists()

    # events.jsonl carries the visible event.
    events = (repo / ".ai-dlc" / "events.jsonl").read_text().splitlines()
    kinds = [json.loads(e)["event"] for e in events]
    assert "INITIATIVE_PHASE_QUEUED" in kinds


def test_advance_does_not_copy_prior_phase_planning_state(repo):
    """A prior phase's design_decision (skip, etc.) must never leak into
    the next phase's fresh task skeleton."""
    initiative.cmd_register("demo-init", repo, ["phase1", "phase2"])

    # Simulate phase1 having recorded a design skip decision in its own
    # (separately-created) planning dir, the way a real WORK stage would.
    p1_dir = repo / ".ai-dlc" / "tasks" / "phase1-planning"
    p1_dir.mkdir(parents=True)
    (p1_dir / "planning.json").write_text(json.dumps({
        "design_decision": {"skip": True, "decided_by": "robin",
                            "why": "not a new page surface"},
    }))

    initiative.cmd_advance("phase1", repo)

    p2_dir = repo / ".ai-dlc" / "tasks" / "phase2-planning"
    assert not (p2_dir / "planning.json").exists()


# ── advance: last phase → initiative complete ──────────────────────────

def test_advance_on_last_phase_marks_initiative_complete(repo):
    initiative.cmd_register("demo-init", repo, ["only-phase"])
    rc = initiative.cmd_advance("only-phase", repo)
    assert rc == 0
    m = _manifest(repo, "demo-init")
    assert m["status"] == "complete"
    assert m["phases"][0]["status"] == "delivered"

    events = (repo / ".ai-dlc" / "events.jsonl").read_text().splitlines()
    kinds = [json.loads(e)["event"] for e in events]
    assert "INITIATIVE_COMPLETE" in kinds


# ── advance: blocked next phase is left untouched ──────────────────────

def test_advance_leaves_blocked_next_phase_untouched(repo):
    initiative.cmd_register("demo-init", repo, ["phase1", "phase2"])
    m = _manifest(repo, "demo-init")
    m["phases"][1]["status"] = "blocked"
    report.save_json(
        repo / ".ai-dlc" / "initiatives" / "demo-init.json", m)

    rc = initiative.cmd_advance("phase1", repo)
    assert rc == 0

    after = _manifest(repo, "demo-init")
    assert after["phases"][0]["status"] == "delivered"
    assert after["phases"][1]["status"] == "blocked"
    assert not (repo / ".ai-dlc" / "tasks" / "phase2-planning").exists()


# ── advance failure isolation (INV-4) ───────────────────────────────────

def test_advance_failure_does_not_affect_the_delivered_phase(repo, monkeypatch):
    initiative.cmd_register("demo-init", repo, ["phase1", "phase2"])

    def _boom(*a, **k):
        raise RuntimeError("simulated task-skeleton creation failure")

    monkeypatch.setattr(initiative, "cmd_init", _boom)

    rc = initiative.cmd_advance("phase1", repo)
    assert rc == 1

    m = _manifest(repo, "demo-init")
    assert m["phases"][0]["status"] == "delivered"
    assert m["phases"][1]["status"] == "pending"


# ── close is untouched by this change (Phase A scope boundary) ─────────

def test_close_subcommand_wiring_is_unmodified():
    """Phase A never wires advance into plan.py close — cmd_close's
    signature and behavior must be exactly what it was before this
    change."""
    plan = _load("plan", _BIN / "plan.py")
    import inspect
    sig = inspect.signature(plan.cmd_close)
    assert list(sig.parameters) == [
        "change", "repo", "task_dir", "branch", "skip_specs",
        "keep_task_branch", "mode", "timeout",
    ]
