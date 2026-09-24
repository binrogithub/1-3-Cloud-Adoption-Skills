"""G3 — plan.py suggest: read-only candidate-route menu.

score_candidates reuses _extract_change_keywords' tokenizer against the
fixed candidate table; up to 4 ranked candidates, empty-list fallback on
all-zero, never executes or writes (INV-23/INV-24).

Run:  python3 -m pytest -q tests/test_suggest.py
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


# ── each candidate's trigger signal ranks it first ─────────────────────

@pytest.mark.parametrize("text,expected", [
    ("fix a typo in one file — a quick mechanical patch",
     "inline_quick_fix"),
    ("refactor the architecture across multiple modules",
     "planned_full_pipeline"),
    ("write a PRD and spec first before any implementation",
     "prd_spec_only"),
    ("design a new web page UI dashboard for the landing",
     "design_first"),
    ("deploy to production and ship the release",
     "deploy_extra_gate"),
])
def test_trigger_signal_ranks_candidate_first(repo, text, expected):
    cands = plan.score_candidates(text, repo)
    assert cands, f"expected non-empty candidates for {text!r}"
    assert cands[0]["name"] == expected
    for c in cands:
        assert {"name", "why", "first_command", "score"} <= set(c)


def test_unrecognizable_input_returns_empty(repo, capsys):
    rc = plan.cmd_suggest(repo, None, "xyzzy plugh grault frobozz")
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == []
    assert out["fallback"] is not None
    assert "next" in out["fallback"]  # points at plan.py next


def test_output_never_exceeds_four(repo):
    # an input that lights up every candidate
    text = ("fix typo refactor architecture modules prd spec design ui "
            "page dashboard deploy production release")
    cands = plan.score_candidates(text, repo)
    assert len(cands) <= 4
    # all five candidates score above zero, so the cap binds at exactly 4
    assert len(cands) == 4
    # ranked by score desc then declaration order — scores are positive
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)


def test_suggest_is_read_only(repo, tmp_path, capsys):
    """INV-23: no file under the repo is created or modified."""
    def _snapshot():
        return {str(p): p.stat().st_mtime_ns
                for p in tmp_path.rglob("*") if p.is_file()}
    before = _snapshot()
    plan.cmd_suggest(repo, None, "fix a typo quickly")
    after = _snapshot()
    assert set(after) == set(before), \
        "suggest created or deleted a file"
    for k in before:
        assert after[k] == before[k], f"suggest modified {k}"


def test_change_with_design_selection_reshapes_design_first(repo, capsys):
    """Spec --change scenario: an existing design_selection makes
    design_first's rationale reference the decision rather than propose
    it as new."""
    td = repo / ".ai-dlc" / "tasks" / "c1-planning"
    (td).mkdir(parents=True)
    (td / "state.json").write_text(json.dumps({
        "change_id": "c1", "route": "planned", "stage": "WORK",
        "design_selection": {"skill": {"name": "shadcn",
                                       "path": "/x/SKILL.md"}},
    }))

    rc = plan.cmd_suggest(repo, "c1", "build the web page UI")
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    names = [c["name"] for c in out["candidates"]]
    assert "design_first" in names
    df = next(c for c in out["candidates"] if c["name"] == "design_first")
    # references the existing decision, not a fresh proposal
    assert "already" in df["why"] or "continue" in df["why"]


def test_change_without_state_is_equivalent_to_no_change(repo, capsys):
    """A --change whose task dir has no state.json must not crash and
    must score on text alone."""
    rc = plan.cmd_suggest(repo, "never-initialized", "fix a typo")
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["candidates"][0]["name"] == "inline_quick_fix"


def test_cjk_triggers_are_reachable(repo):
    """The tokenizer's CJK bigrams must reach Chinese trigger phrases
    (梳理架构 / 部署 / 界面) — the design reused _tokenize_query for
    exactly this reason."""
    cands = plan.score_candidates("先梳理架构，多模块重构，再部署上线", repo)
    names = [c["name"] for c in cands]
    assert "planned_full_pipeline" in names
    assert "deploy_extra_gate" in names
