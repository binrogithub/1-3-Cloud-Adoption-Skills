"""P1-10 spec↔implementation alignment — tests.

The Requirement↔hunk mapping: every requirement should trace to at
least one hunk (two significant shared terms = a trace; one is a
coincidence), and a hunk answering to no requirement is named. Orphan
requirements surface in the merge gate's question. Visible information,
never a gate.

Run:  python3 -m pytest tests/test_spec_alignment.py -v
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report = _load("report_align_t", _BIN / "bin" / "report.py")


def _commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(repo), "commit", "-q", "-m", msg],
                   check=True)


def _repo_with_change(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "gate.py").write_text("value = 1\n", encoding="utf-8")
    _commit_all(repo, "base")
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    # the landed work: implements both requirements
    (repo / "gate.py").write_text(
        "value = 1\n\n\ndef checkpoint_turn(label):\n"
        "    \"\"\"Record a turn checkpoint with restore guard.\"\"\"\n"
        "    return ('checkpoint', label)\n", encoding="utf-8")
    (repo / "policy.py").write_text(
        "DENY_FIRST = True\n\n\ndef dispatch_policy_decide(role):\n"
        "    \"\"\"Deny first, allow second, default-deny.\"\"\"\n"
        "    return 'refuse'\n", encoding="utf-8")
    _commit_all(repo, "work")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    specs = tmp_path / "specs"
    (specs / "gate-cap").mkdir(parents=True)
    (specs / "gate-cap" / "spec.md").write_text(
        "## Purpose\n\nx\n\n"
        "## ADDED Requirements\n\n"
        "### Requirement: Turn checkpoints are recorded per dispatch\n\n"
        "The system SHALL record a checkpoint for every turn, with a\n"
        "restore guard.\n\n"
        "#### Scenario: Recording\n\n- **WHEN** a turn ends\n"
        "- **THEN** a checkpoint exists\n\n"
        "### Requirement: Dispatch policy denies by default\n\n"
        "A role outside the allowlist SHALL be refused by the policy.\n",
        encoding="utf-8")
    return repo, specs, base, head


def test_full_coverage_maps_both_directions(tmp_path):
    repo, specs, base, head = _repo_with_change(tmp_path)
    align = report.spec_alignment(repo, base, head, specs)
    assert align is not None
    assert align["requirements"] == 2
    assert align["orphan_requirements"] == []
    assert align["orphan_hunks"] == []
    by_req = {m["requirement"]: m for m in align["matrix"]}
    assert by_req["Turn checkpoints are recorded per dispatch"]["hunks"]
    assert by_req["Dispatch policy denies by default"]["hunks"]


def test_orphan_requirement_is_named(tmp_path):
    repo, specs, base, head = _repo_with_change(tmp_path)
    # a third requirement nothing implements — and whose vocabulary
    # genuinely does not overlap the landed diff
    (specs / "gate-cap" / "spec.md").write_text(
        (specs / "gate-cap" / "spec.md").read_text(encoding="utf-8")
        + "\n### Requirement: Nightly roster drift is detected\n\n"
          "A nightly scan SHALL detect roster drift and write a "
          "report.\n",
        encoding="utf-8")
    align = report.spec_alignment(repo, base, head, specs)
    assert align["orphan_requirements"] == [
        "Nightly roster drift is detected"]


def test_orphan_hunk_is_named(tmp_path):
    repo, specs, base, head = _repo_with_change(tmp_path)
    # a change no requirement mentions
    (repo / "readme_extra.txt").write_text(
        "changelog polish unrelated coverage\n", encoding="utf-8")
    _commit_all(repo, "unrelated")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    align = report.spec_alignment(repo, base, head, specs)
    assert any(h["file"] == "readme_extra.txt"
               for h in align["orphan_hunks"])


def test_nothing_to_align_returns_none(tmp_path):
    repo, specs, base, head = _repo_with_change(tmp_path)
    assert report.spec_alignment(repo, base, head,
                                 tmp_path / "missing") is None
    assert report.spec_alignment(repo, None, head, specs) is None


def test_gate_question_names_orphans(tmp_path, capsys):
    task_dir = tmp_path / ".ai-dlc" / "tasks" / "t14"
    task_dir.mkdir(parents=True)
    report.save_json(task_dir / "state.json", {
        "task_id": "t14", "route": "planned", "stage": "MERGE_GATE"})
    report.save_json(task_dir / "report.json", {
        "execution_gate": {"state": "pass"},
        "alignment": {"orphan_requirements": [
            "Nightly roster drift is detected"]}})
    report.cmd_gate(task_dir, "gate-merge", None, None, "", True, None,
                    "MERGE_GATE", None, None)
    req = json.loads((task_dir / "gates" / "gate-merge.request.json")
                     .read_text(encoding="utf-8"))
    assert "Spec alignment: 1 requirement(s)" in req["question"]
    assert "Nightly roster drift" in req["question"]


def test_single_token_requirement_still_traces(tmp_path):
    repo, specs, base, head = _repo_with_change(tmp_path)
    (specs / "cap2").mkdir()
    (specs / "cap2" / "spec.md").write_text(
        "### Requirement: Checkpointing\n\n"
        "Checkpointing SHALL happen.\n", encoding="utf-8")
    align = report.spec_alignment(repo, base, head, specs)
    by_req = {m["requirement"]: m for m in align["matrix"]}
    assert by_req["Checkpointing"]["hunks"]
