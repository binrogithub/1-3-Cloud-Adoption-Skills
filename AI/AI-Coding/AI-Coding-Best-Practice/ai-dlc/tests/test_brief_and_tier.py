"""P0-2 brief schema + P0-3 effort tiering — tests.

P0-2: every dispatch brief names Objective / Expected output / Tools /
Boundary as line markers; dispatch_role refuses a brief missing one
before a session opens (CrewAI's Task makes description +
expected_output + agent mandatory for the same reason; Anthropic's
dispatch briefs name the same four).

P0-3: the effort tier travels with the ROUTE decision — shape, crew
and budget ceiling recorded at init and echoed by next (the anti-15x
rule: multi-agent token burn is chosen, never defaulted into).

Run:  python3 -m pytest tests/test_brief_and_tier.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_brief_tier", _BIN / "bin" / "plan.py")
report = _load("report_brief_tier", _BIN / "bin" / "report.py")


FULL_BRIEF = """Objective: write the proposal artifact.
Expected output: exactly your own artifact file.
Tools: the openspec-author skill via the openspec CLI.
Boundary: write only inside your artifact path.
"""


# ── P0-2: the four elements ────────────────────────────────────────

def test_full_brief_passes():
    assert plan.brief_missing_sections(FULL_BRIEF) == []


@pytest.mark.parametrize("marker", plan.BRIEF_SECTION_MARKERS)
def test_each_missing_marker_is_named(marker):
    prompt = "\n".join(line for line in FULL_BRIEF.splitlines()
                       if not line.startswith(marker)) + "\n"
    assert plan.brief_missing_sections(prompt) == [marker]


def test_dispatch_role_refuses_incomplete_brief(tmp_path, monkeypatch):
    # the refusal fires before anything is paid for: the client is
    # never invoked, so a stubbed subprocess that fails the test on
    # contact proves the ordering
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)

    def _no_client(cmd, **kw):
        raise AssertionError("the client was invoked on an "
                              "incomplete brief")
    monkeypatch.setattr(plan.subprocess, "run", _no_client)
    out, code = plan.dispatch_role("c1", "proposal", {}, tmp_path,
                                   "Write the proposal.", tmp_path,
                                   "code.normal", 60)
    assert code == plan.EXIT_ROLE_REJECTED
    assert out["refused"] == "brief"
    assert "Objective:" in out["missing"]
    assert out["stopped"].startswith("before dispatch")


def test_assemble_prompt_carries_the_four():
    pkg = {"requirement": "r", "change_id": "c1", "capability": "cap",
           "repo": "/tmp/x"}
    prompt = plan.assemble_prompt(pkg, "proposal", "en")
    assert plan.brief_missing_sections(prompt) == []


def test_reviewer_prompt_carries_the_four():
    p = plan.reviewer_prompt("c1", "correctness",
                             {"stance": "s", "accepts": "a",
                              "refuses": "r"}, "review/c1/x/finding.md")
    assert plan.brief_missing_sections(p) == []


def test_revision_prompt_carries_the_four():
    p = plan.revision_prompt("c1", [{"axis": "a", "text": "t"}],
                             "review/c1/answers.md", None)
    assert plan.brief_missing_sections(p) == []


# ── P0-3: effort tiers ─────────────────────────────────────────────

def test_route_tier_inline():
    t = report.route_tier("inline")
    assert t["tier"] == "tier-1-inline"
    assert "3-10 tool calls" in t["budget"]
    assert "tier-3" in t["tier_note"]


def test_route_tier_planned():
    t = report.route_tier("planned")
    assert t["tier"] == "tier-2-planned"
    assert "10-15 tool calls per role" in t["budget"]


def test_tier_three_is_never_auto_assigned():
    for route in ("inline", "planned"):
        assert report.route_tier(route)["tier"] != "tier-3-team"


def test_init_records_the_tier(tmp_path, capsys):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    task_dir = tmp_path / ".ai-dlc" / "tasks" / "t9"
    assert report.cmd_init(task_dir, tmp_path, "inline", "t9",
                           None) == 0
    capsys.readouterr()
    st = json.loads((task_dir / "state.json").read_text(encoding="utf-8"))
    assert st["tier"]["tier"] == "tier-1-inline"
    assert st["tier"]["budget"]


def test_next_echoes_the_tier(tmp_path, capsys, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q",
                    "--allow-empty", "-m", "base"], check=True)
    task_dir = tmp_path / ".ai-dlc" / "tasks" / "t10"
    assert report.cmd_init(task_dir, tmp_path, "planned", "t10",
                           "c10") == 0
    capsys.readouterr()
    assert report.cmd_next(task_dir, tmp_path) in (0, 1)
    out = json.loads(capsys.readouterr().out)
    assert out["tier"] == "tier-2-planned"
    assert out["tier_budget"]
