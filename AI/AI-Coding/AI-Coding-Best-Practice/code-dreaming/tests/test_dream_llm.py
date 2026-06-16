import json
import os
import stat
import subprocess
from pathlib import Path

from scripts.dream_llm import Candidate, default_memory_dir, dream_prompt_path, parse_candidates, render_prompt, write_artifacts
from scripts.dream_sources import load_trajectory


ROOT = Path(__file__).resolve().parent.parent


def _fake_claude(path: Path, body: str, exit_code: int = 0) -> Path:
    script = path / "claude-glm"
    script.write_text(
        f"""#!/usr/bin/env bash
cat >/dev/null
printf '%s\\n' {json.dumps(body)}
exit {exit_code}
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _run(args, env=None):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, env=env, check=False)


def test_prompt_treats_repo_root_as_dream_target(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = load_trajectory(memory_dir=memory, repo_root=repo)

    prompt = render_prompt(dream_prompt_path(), memory, repo, trajectory, max_days=7)

    assert "The current shell working directory is irrelevant to validation" in prompt
    assert f"Repo root: {repo}" in prompt


def test_llm_runner_writes_verified_report_and_review_only_patch(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "MEMORY.md").write_text("# Project memory\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(json.dumps({"session_id": "s1", "time": "2026-06-14", "role": "user", "text": "Always run pytest for dream changes"}) + "\n", encoding="utf-8")
    first_id = load_trajectory(trajectory, memory, repo).records[0].evidence_id
    fake = _fake_claude(tmp_path, f"Candidate: section=Rules | Always run pytest for dream changes | verified: {first_id}")

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--trajectory",
        str(trajectory),
        "--claude-bin",
        str(fake),
    ])

    assert proc.returncode == 0, proc.stderr
    reports = sorted((memory / "inbox").glob("dream-llm-*.report.md"))
    assert reports
    report = reports[-1].read_text(encoding="utf-8")
    assert "trajectory_adapter: `jsonl`" in report
    assert "verified_count: 1" in report
    run_patches = sorted((memory / "inbox").glob("memory-md.20*.proposed.patch"))
    assert len(run_patches) == 1
    assert f"proposed_patch_paths: `{run_patches[0]}`" in report
    assert "cumulative_patch_path:" in report
    patch = (memory / "inbox" / "memory-md.proposed.patch").read_text(encoding="utf-8")
    assert patch == run_patches[0].read_text(encoding="utf-8")
    assert "## Rules" in patch
    assert "## Architecture decisions" not in patch
    assert "## Discovered durable knowledge" not in patch
    assert "## Patterns" not in patch
    assert "## Gotchas" not in patch
    assert "Always run pytest" in patch
    cumulative_patch = (memory / "inbox" / "memory-md.cumulative.proposed.patch").read_text(encoding="utf-8")
    cumulative_md = (memory / "inbox" / "memory-md.cumulative.proposed.md").read_text(encoding="utf-8")
    assert "Always run pytest" in cumulative_patch
    assert "Always run pytest" in cumulative_md
    assert (memory / "MEMORY.md").read_text(encoding="utf-8") == "# Project memory\n"


def test_write_artifacts_keeps_same_second_runs_distinct(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (memory / "MEMORY.md").write_text("# Project memory\n", encoding="utf-8")
    trajectory = load_trajectory(memory_dir=memory, repo_root=repo)

    first = write_artifacts(
        memory,
        repo,
        trajectory,
        "Candidate: section=Rules | First | repo-verified: README.md",
        [Candidate("Rules", "First [repo-verified: README.md]", "repo-verified", [])],
    )
    second = write_artifacts(
        memory,
        repo,
        trajectory,
        "Candidate: section=Rules | Second | repo-verified: README.md",
        [Candidate("Rules", "Second [repo-verified: README.md]", "repo-verified", [])],
    )

    assert first != second
    run_patches = sorted((memory / "inbox").glob("memory-md.20*.proposed.patch"))
    assert len(run_patches) == 2
    assert "First" in run_patches[0].read_text(encoding="utf-8")
    assert "Second" in run_patches[1].read_text(encoding="utf-8")
    assert (memory / "inbox" / "memory-md.proposed.patch").read_text(encoding="utf-8") == run_patches[1].read_text(encoding="utf-8")
    cumulative_patch = (memory / "inbox" / "memory-md.cumulative.proposed.patch").read_text(encoding="utf-8")
    cumulative_md = (memory / "inbox" / "memory-md.cumulative.proposed.md").read_text(encoding="utf-8")
    assert "First" in cumulative_patch
    assert "Second" in cumulative_patch
    assert "First" in cumulative_md
    assert "Second" in cumulative_md
    assert "First" not in (memory / "inbox" / "memory-md.proposed.patch").read_text(encoding="utf-8")


def test_no_trajectory_marks_candidate_unverified(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    fake = _fake_claude(tmp_path, "Candidate: section=Discovered durable knowledge | yesterday use local adapter | verified: ev-missing")

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--claude-bin",
        str(fake),
    ])

    assert proc.returncode == 0, proc.stderr
    report = sorted((memory / "inbox").glob("dream-llm-*.report.md"))[-1].read_text(encoding="utf-8")
    assert "unverified_count: 1" in report
    assert "[unverified: no trajectory evidence available]" in report
    assert "yesterday" not in (memory / "inbox" / "memory-md.proposed.patch").read_text(encoding="utf-8").lower()


def test_external_runner_requires_explicit_llm_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--repo-root",
        str(repo),
    ])

    assert proc.returncode == 2
    assert "requires --claude-bin" in proc.stderr


def test_missing_memory_dir_is_clear_error(tmp_path):
    fake = _fake_claude(tmp_path, "Summary only.")
    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(tmp_path / "missing"),
        "--repo-root",
        str(tmp_path),
        "--claude-bin",
        str(fake),
    ])

    assert proc.returncode == 2
    assert "memory dir does not exist" in proc.stderr


def test_default_memory_dir_is_created_for_report(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    env = {**os.environ, "HOME": str(tmp_path)}
    repo = tmp_path / "repo"
    repo.mkdir()
    fake = _fake_claude(tmp_path, "Summary only. No durable memory candidates.")

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--repo-root",
        str(repo),
        "--claude-bin",
        str(fake),
    ], env=env)

    memory = default_memory_dir(repo)
    assert proc.returncode == 0, proc.stderr
    assert memory.exists()
    assert sorted((memory / "inbox").glob("dream-llm-*.report.md"))


def test_missing_llm_binary_is_clear_error(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--claude-bin",
        "definitely-not-claude-glm",
    ])

    assert proc.returncode == 1
    assert "LLM binary not found" in proc.stderr


def test_llm_runner_uses_explicit_command_without_provider_assumption(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(json.dumps({"session_id": "s1", "role": "user", "text": "Keep dream reports review-only"}) + "\n", encoding="utf-8")
    fake = tmp_path / "host-agent"
    fake.write_text(
        f"""#!/usr/bin/env bash
cat >/dev/null
printf '%s\\n' {json.dumps("Candidate: section=Rules | Keep dream reports review-only | unverified: synthetic test")}
""",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--trajectory",
        str(trajectory),
        "--claude-bin",
        str(fake),
    ], env=env)

    assert proc.returncode == 0, proc.stderr
    report = sorted((memory / "inbox").glob("dream-llm-*.report.md"))[-1].read_text(encoding="utf-8")
    assert "Keep dream reports review-only" in report


def test_parse_candidates_invalid_verified_ids_become_unverified(tmp_path):
    result = load_trajectory(memory_dir=tmp_path, repo_root=tmp_path)

    candidates = parse_candidates("Candidate: section=Rules | today keep reports review-only | verified: ev-doesnotexist", result)

    assert candidates[0].status == "unverified"
    assert "[unverified:" in candidates[0].text


def test_parse_candidates_keeps_repo_verified_evidence(tmp_path):
    result = load_trajectory(memory_dir=tmp_path, repo_root=tmp_path)

    candidates = parse_candidates(
        "Candidate: section=Rules | Run `python3 -m pytest -q` before merging dream changes. | repo-verified: README.md (line 5)",
        result,
    )

    assert candidates[0].status == "repo-verified"
    assert candidates[0].evidence_ids == []
    assert "repo-verified: README.md (line 5)" in candidates[0].text
    assert "repo-(line 5)" not in candidates[0].text


def test_global_candidate_writes_separate_review_patch(tmp_path):
    memory = tmp_path / "project" / "memory"
    memory.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(json.dumps({"session_id": "s1", "role": "user", "text": "Across projects, always keep memory patches review-only"}) + "\n", encoding="utf-8")
    first_id = load_trajectory(trajectory, memory, repo).records[0].evidence_id
    fake = _fake_claude(tmp_path, f"Candidate: section=Rules | global=true | Across projects, always keep memory patches review-only | verified: {first_id}")

    proc = _run([
        str(ROOT / "bin" / "dream-llm.sh"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--trajectory",
        str(trajectory),
        "--claude-bin",
        str(fake),
    ])

    assert proc.returncode == 0, proc.stderr
    global_patch = (memory / "inbox" / "global-memory.proposed.patch").read_text(encoding="utf-8")
    assert "b/global/MEMORY.md" in global_patch
    assert "Across projects" in global_patch
    project_patch = (memory / "inbox" / "memory-md.proposed.patch").read_text(encoding="utf-8")
    assert "Across projects" not in project_patch
    report = sorted((memory / "inbox").glob("dream-llm-*.report.md"))[-1].read_text(encoding="utf-8")
    assert "scope=global" in report


def test_summary_only_llm_output_does_not_become_memory_candidate(tmp_path):
    result = load_trajectory(memory_dir=tmp_path, repo_root=tmp_path)
    output = """
Analysis of trajectory evidence:
All facts are derivable from the repo.

Proposed durable memory entries: None

Summary:
- Consolidated: 0 new entries
- Skipped: no durable user statements found.
"""

    assert parse_candidates(output, result) == []


def test_dream_prompt_prefers_renamed_maas_code_mirror():
    path = dream_prompt_path()

    assert "upstream/maas-code" in path.as_posix()
    assert path.name == "dream.txt"


def test_parse_real_claude_markdown_proposed_memory_entries(tmp_path):
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(json.dumps({"session_id": "s1", "text": "Always run pytest before merging dream changes"}) + "\n", encoding="utf-8")
    result = load_trajectory(trajectory, repo_root=tmp_path)
    ev = result.records[0].evidence_id
    output = f"""
## Proposed MEMORY.md entries

### ## Rules

1. **Always run `python3 -m pytest -q` before merging dream changes.**
   - verified: [{ev}] — explicit user statement

### ## Architecture decisions

- 2026-06-15: Directory dream should use a manifest so repeated runs send only changed files to the LLM. [verified: {ev}]

## Summary

- Consolidated: 2
"""

    candidates = parse_candidates(output, result)

    assert len(candidates) == 2
    assert candidates[0].section == "Rules"
    assert candidates[0].status == "verified"
    assert candidates[0].evidence_ids == [ev]
    assert candidates[1].section == "Architecture decisions"
