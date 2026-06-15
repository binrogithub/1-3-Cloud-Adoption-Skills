import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENT_REPORT = str(ROOT / "scripts" / "dream_agent_report.py")


def _run(args, env=None):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, env=env, check=False)


def _trajectory(path: Path) -> Path:
    path.write_text(
        json.dumps({"role": "user", "text": "I prefer spaces; let's go with postgres"}) + "\n",
        encoding="utf-8",
    )
    return path


def test_agent_report_writes_without_nested_llm(tmp_path):
    memory = tmp_path / "memory"
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(
        json.dumps({"session_id": "s1", "role": "user", "text": "Always keep default dreaming report non-nested"}) + "\n",
        encoding="utf-8",
    )

    proc = _run([
        "python3",
        str(ROOT / "scripts" / "dream_agent_report.py"),
        "--memory-dir",
        str(memory),
        "--repo-root",
        str(repo),
        "--trajectory",
        str(trajectory),
    ])

    assert proc.returncode == 0, proc.stderr
    report_path = Path(proc.stdout.strip())
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "# Dreaming Summary Report" in report
    assert "- mode: `host-agent-entry`" in report
    assert "Always keep default dreaming report non-nested" in report
    assert "nested LLM" not in report
    # Signal Scan section is present when a trajectory exists; no steering by default.
    assert "## Signal Scan" in report
    assert "## Steering Instructions" not in report


def test_agent_report_renders_steering_and_signal_scan(tmp_path):
    memory = tmp_path / "memory"
    repo = tmp_path / "repo"
    repo.mkdir()
    trajectory = tmp_path / "trajectory.jsonl"
    trajectory.write_text(
        "\n".join(
            json.dumps(rec)
            for rec in (
                {"session_id": "s1", "role": "user", "text": "Actually no, that's wrong, use spaces"},
                {"session_id": "s2", "role": "user", "text": "I prefer black formatting from now on"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    proc = _run([
        "python3",
        str(ROOT / "scripts" / "dream_agent_report.py"),
        "--memory-dir", str(memory),
        "--repo-root", str(repo),
        "--trajectory", str(trajectory),
        "--instructions", "focus on coding-style preferences; ignore one-off debugging notes",
    ])

    assert proc.returncode == 0, proc.stderr
    report = Path(proc.stdout.strip()).read_text(encoding="utf-8")
    assert "## Steering Instructions" in report
    assert "focus on coding-style preferences" in report
    assert "## Signal Scan" in report
    assert "corrections=" in report
    assert "[corrections]" in report


def test_agent_report_redacts_and_clamps_instructions(tmp_path):
    memory = tmp_path / "memory"
    repo = tmp_path / "repo"
    repo.mkdir()
    long_tail = "x" * 5000
    proc = _run([
        "python3",
        str(ROOT / "scripts" / "dream_agent_report.py"),
        "--memory-dir", str(memory),
        "--repo-root", str(repo),
        "--instructions", f"token=supersecretvalue keep going {long_tail}",
    ])

    assert proc.returncode == 0, proc.stderr
    report = Path(proc.stdout.strip()).read_text(encoding="utf-8")
    assert "## Steering Instructions" in report
    assert "supersecretvalue" not in report
    assert "[REDACTED]" in report
    # 4096-char clamp means the full 5000-char tail cannot survive verbatim.
    assert ("x" * 5000) not in report


def test_project_root_mode_writes_shareable_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "mem"
    traj = _trajectory(tmp_path / "t.jsonl")

    proc = _run([
        "python3", AGENT_REPORT,
        "--output-mode", "project-root",
        "--repo-root", str(repo),
        "--memory-dir", str(mem),
        "--trajectory", str(traj),
    ])
    assert proc.returncode == 0, proc.stderr

    base = repo / ".maas-dreaming"
    report_path = Path(proc.stdout.strip())
    assert report_path.parent == base / "inbox"
    assert report_path.exists()

    index = (base / "DREAMS.md").read_text(encoding="utf-8")
    assert report_path.name in index
    assert "signals:" in index

    pointer = (base / "POINTER.suggested.md").read_text(encoding="utf-8")
    assert ".maas-dreaming/DREAMS.md" in pointer
    # Governance: the tool emits a suggestion, it does not write a CLAUDE.md.
    assert not (repo / "CLAUDE.md").exists()


def test_out_dir_overrides_mode_and_targets_cwd_style_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "memory"
    traj = _trajectory(tmp_path / "t.jsonl")

    proc = _run([
        "python3", AGENT_REPORT,
        "--out-dir", str(out),
        "--repo-root", str(repo),
        "--memory-dir", str(tmp_path / "mem"),
        "--trajectory", str(traj),
    ])
    assert proc.returncode == 0, proc.stderr
    assert Path(proc.stdout.strip()).parent == out / "inbox"
    assert (out / "DREAMS.md").exists()
    assert (out / "POINTER.suggested.md").exists()


def test_native_default_has_no_pointer(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mem = tmp_path / "mem"
    traj = _trajectory(tmp_path / "t.jsonl")

    proc = _run([
        "python3", AGENT_REPORT,
        "--repo-root", str(repo),
        "--memory-dir", str(mem),
        "--trajectory", str(traj),
    ])
    assert proc.returncode == 0, proc.stderr
    # Native mode gets an index (improvement) but no team pointer.
    assert (mem / "DREAMS.md").exists()
    assert not (mem / "POINTER.suggested.md").exists()


def test_index_preserves_prior_entries_and_retention_prunes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    mem = tmp_path / "mem"
    traj = _trajectory(tmp_path / "t.jsonl")

    names = []
    for _ in range(3):
        proc = _run([
            "python3", AGENT_REPORT,
            "--out-dir", str(out),
            "--repo-root", str(repo),
            "--memory-dir", str(mem),
            "--trajectory", str(traj),
            "--keep", "2",
        ])
        assert proc.returncode == 0, proc.stderr
        names.append(Path(proc.stdout.strip()).name)

    report_files = sorted((out / "inbox").glob("dream-agent-*.report.md"))
    assert len(report_files) == 2  # retention kept newest 2

    index_lines = [l for l in (out / "DREAMS.md").read_text(encoding="utf-8").splitlines()
                   if l.startswith("- [")]
    assert len(index_lines) == 2
    # Newest first, oldest pruned.
    assert names[2] in index_lines[0]
    assert names[0] not in (out / "DREAMS.md").read_text(encoding="utf-8")
