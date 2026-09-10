"""PRD v9 P2-3 — arbiter second opinion, tests.

When the 90s arbiter session fails (timeout or no shortlist path
named), one 45s second-opinion mini-session runs before degradation
is accepted: top-3 only, reply-is-the-pick. A pick there is
method=judged-2nd and NOT degraded; a second failure degrades exactly
as before, with the reason saying so.

Run:  python3 -m pytest tests/test_arbiter_second_opinion.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_so_mod", _BIN / "plan.py")
report = _load("report_so_mod", _BIN / "report.py")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr[:200]}")
    return r.stdout


def _setup(tmp_path: Path):
    """Standalone pricing-page wins L1+L2 (trigger phrase verbatim in
    the proposal) and trips the narrow-aesthetic gate, forcing the
    arbiter path; generic web-prototype is the unflagged fallback."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    (repo / "index.html").write_text("<html></html>")
    task_dir = repo / ".ai-dlc" / "tasks" / "c1"
    task_dir.mkdir(parents=True)
    report.save_json(task_dir / "state.json", {
        "task_id": "c1", "route": "inline", "base_sha": "x" * 40,
        "change_id": "c1", "repo": str(repo.resolve()),
        "stage": "WORK", "human_state": "Working"})
    (task_dir / "proposal.md").write_text(
        "Build a pricing page for a SaaS product.\n", encoding="utf-8")

    od_root = tmp_path / "opendesign"
    skills = od_root / "skills"
    skills.mkdir(parents=True)
    standalone = skills / "pricing-page"
    standalone.mkdir()
    (standalone / "SKILL.md").write_text(
        "---\nname: Pricing Page\nod.mode: template\nod.surface: web\n"
        "category: web\ntriggers:\n  - pricing page\n"
        "description: A standalone pricing page — plan tiers and FAQ.\n"
        "---\n# Pricing Page\n", encoding="utf-8")
    generic = skills / "web-prototype"
    generic.mkdir()
    (generic / "SKILL.md").write_text(
        "---\nname: Web Prototype\nod.mode: prototype\nod.surface: web\n"
        "category: web\ntriggers:\n  - website\n"
        "description: A generic multi-section website prototype.\n"
        "---\n# Web Prototype\n", encoding="utf-8")
    for i in range(8):
        d = skills / f"dummy-{i}"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: Dummy %d\nod.mode: prototype\nod.surface: web\n"
            "category: web\n---\n# Dummy %d\n" % (i, i), encoding="utf-8")
    for _d in skills.iterdir():
        (_d / "example.html").write_text("<html>x</html>",
                                     encoding="utf-8")
    return repo, task_dir, od_root, str(generic / "SKILL.md")


def _frames_reply(text: str) -> list:
    return [json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    })]


class TestSecondOpinion:
    def test_rescue_after_timeout(self, tmp_path, monkeypatch):
        """90s arbiter times out → the 45s second opinion names the
        generic path → judged-2nd, NOT degraded."""
        repo, td, od, generic_path = _setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))
        calls = []

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            calls.append((verb, timeout))
            if verb == "design-select-2nd":
                return {"timed_out": False, "round_complete": True,
                        "interrupted": False, "frames":
                        _frames_reply(generic_path + "\nbecause generic"),
                        "session_name": "s2"}, 0
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "frames": [],
                    "session_name": "s1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        state = report.load_json(td / "state.json", {})
        sel = state["design_selection"]
        assert sel["method"] == "judged-2nd", sel["method"]
        assert sel["degraded"] is False
        assert sel["chosen"] == generic_path
        assert sel["second_opinion"] == {
            "attempted": True, "session": "s2", "outcome": "picked",
            "pick": "web-prototype"}
        assert [c[0] for c in calls] == ["design-select",
                                         "design-select-2nd"]
        assert calls[1][1] == 45, "second opinion is the 45s mini-session"

    def test_both_fail_degrades_as_before(self, tmp_path, monkeypatch):
        repo, td, od, generic_path = _setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))

        def fake_timeout(change, verb, prompt, repo_, td_, mode, timeout):
            return {"timed_out": True, "round_complete": False,
                    "interrupted": False, "frames": [],
                    "session_name": "sx"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake_timeout)
        assert plan.cmd_design_select("c1", repo, td) == 0
        state = report.load_json(td / "state.json", {})
        sel = state["design_selection"]
        assert sel["method"] == "degraded"
        assert sel["degraded"] is True
        assert sel["chosen"] == generic_path  # unflagged fallback holds
        assert sel["second_opinion"]["outcome"] == "failed"
        assert "second opinion also failed" in sel["reason"]

    def test_first_try_judged_skips_second(self, tmp_path, monkeypatch):
        repo, td, od, generic_path = _setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))
        calls = []

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            calls.append(verb)
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _frames_reply(
                        generic_path + "\nbecause generic"),
                    "session_name": "s1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        state = report.load_json(td / "state.json", {})
        sel = state["design_selection"]
        assert sel["method"] == "judged"
        assert calls == ["design-select"], (
            "a successful first arbiter must not open a second session")
        assert sel["second_opinion"] == {"attempted": False}

    def test_rescue_after_no_path_reply(self, tmp_path, monkeypatch):
        """First session completes but names no shortlist path — the
        retry must still run (same failure class)."""
        repo, td, od, generic_path = _setup(tmp_path)
        monkeypatch.setattr(plan, "OPENDESIGN_ROOT", str(od))

        def fake(change, verb, prompt, repo_, td_, mode, timeout):
            if verb == "design-select-2nd":
                return {"timed_out": False, "round_complete": True,
                        "interrupted": False,
                        "frames": _frames_reply(
                            generic_path + "\npick this one"),
                        "session_name": "s2"}, 0
            return {"timed_out": False, "round_complete": True,
                    "interrupted": False,
                    "frames": _frames_reply("I cannot decide today"),
                    "session_name": "s1"}, 0

        monkeypatch.setattr(plan, "run_plane_session", fake)
        assert plan.cmd_design_select("c1", repo, td) == 0
        state = report.load_json(td / "state.json", {})
        sel = state["design_selection"]
        assert sel["method"] == "judged-2nd"
        assert sel["chosen"] == generic_path
