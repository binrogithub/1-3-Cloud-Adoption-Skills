import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import should_run  # noqa: E402


DAY = 24 * 60 * 60


def _cli(*args):
    return subprocess.run(
        ["python3", str(ROOT / "scripts" / "should_run.py"), *args],
        text=True, capture_output=True, check=False,
    )


def _memory_file(memory_dir: Path, name: str, mtime: float) -> Path:
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / name
    path.write_text("# memory\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_too_young_project_is_skipped(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"
    _memory_file(memory_dir, "episode.md", now - DAY)

    decision = should_run.scheduling_decision(memory_dir, interval_days=7, now=now)

    assert decision.should_run is False
    assert "too-young" in decision.reason


def test_too_recent_last_run_is_skipped(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"
    _memory_file(memory_dir, "episode.md", now - 20 * DAY)
    should_run.write_json(memory_dir / should_run.STAMP_FILE, {
        "completed_at_epoch": now - DAY,
    })

    decision = should_run.scheduling_decision(memory_dir, interval_days=7, now=now)

    assert decision.should_run is False
    assert "too-recent" in decision.reason


def test_old_project_without_stamp_is_eligible(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"
    _memory_file(memory_dir, "episode.md", now - 8 * DAY)

    decision = should_run.scheduling_decision(memory_dir, interval_days=7, now=now)

    assert decision == should_run.Decision(True, "eligible")


def test_force_bypasses_skip_gates(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"
    _memory_file(memory_dir, "episode.md", now - DAY)
    should_run.write_json(memory_dir / should_run.STAMP_FILE, {
        "completed_at_epoch": now - 60,
    })

    decision = should_run.scheduling_decision(memory_dir, interval_days=7,
                                              force=True, now=now)

    assert decision.should_run is True
    assert "force" in decision.reason


def test_missing_timestamp_path_runs(tmp_path):
    memory_dir = tmp_path / "missing-memory"

    decision = should_run.scheduling_decision(memory_dir, interval_days=7,
                                              now=2_000_000.0)

    assert decision.should_run is True
    assert decision.reason == "eligible"


def test_lock_throttles_duplicate_invocation(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"

    first = should_run.acquire_lock(memory_dir, owner_pid=12345, now=now,
                                    throttle_seconds=60)
    second = should_run.acquire_lock(memory_dir, owner_pid=12346, now=now + 5,
                                     throttle_seconds=60)

    assert first.should_run is True
    assert second.should_run is False
    assert "locked" in second.reason


def test_stamp_records_completion_under_memory_root(tmp_path):
    now = 2_000_000.0
    memory_dir = tmp_path / "memory"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    should_run.acquire_lock(memory_dir, owner_pid=os.getpid(), now=now)
    should_run.record_stamp(memory_dir, repo_root, interval_days=7, now=now)
    should_run.release_lock(memory_dir, owner_pid=os.getpid())
    stamp = should_run.read_json(memory_dir / should_run.STAMP_FILE)

    assert stamp["completed_at_epoch"] == now
    assert stamp["interval_days"] == 7
    assert stamp["repo_root"] == str(repo_root.resolve())
    assert not (memory_dir / should_run.LOCK_FILE).exists()


def test_pending_helpers_roundtrip(tmp_path):
    memory_dir = tmp_path / "memory"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    assert should_run.is_pending(memory_dir) is False
    path = should_run.write_pending(memory_dir, repo_root, now=2_000_000.0)
    assert path == memory_dir / should_run.PENDING_FILE
    assert should_run.is_pending(memory_dir) is True
    assert should_run.clear_pending(memory_dir) is True
    assert should_run.is_pending(memory_dir) is False
    # Clearing an absent flag is a no-op, not an error.
    assert should_run.clear_pending(memory_dir) is False


def _make_eligible(memory_dir: Path):
    memory_dir.mkdir(parents=True, exist_ok=True)
    episode = memory_dir / "episode.md"
    episode.write_text("# m\n", encoding="utf-8")
    old = 2_000_000.0  # far in the past relative to wall clock
    os.utime(episode, (old, old))


def test_cli_pending_lifecycle(tmp_path):
    memory_dir = tmp_path / "memory"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_eligible(memory_dir)
    common = ["--memory-dir", str(memory_dir), "--repo-root", str(repo_root)]

    # Eligible -> flag created, exit 0.
    created = _cli("pending", *common)
    assert created.returncode == 0, created.stderr
    assert (memory_dir / should_run.PENDING_FILE).exists()

    # Status reflects the flag (exit 0).
    status = _cli("pending-status", *common)
    assert status.returncode == 0, status.stdout

    # Clear removes the flag and records a completion stamp.
    cleared = _cli("clear-pending", *common)
    assert cleared.returncode == 0, cleared.stderr
    assert not (memory_dir / should_run.PENDING_FILE).exists()
    assert (memory_dir / should_run.STAMP_FILE).exists()

    # Status now reports clean (exit 1).
    assert _cli("pending-status", *common).returncode == 1

    # Too-recent after stamp -> pending skips (exit 2), no flag rewritten.
    skipped = _cli("pending", *common)
    assert skipped.returncode == 2
    assert not (memory_dir / should_run.PENDING_FILE).exists()


def test_cli_pending_force_bypasses_gate(tmp_path):
    memory_dir = tmp_path / "memory"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    common = ["--memory-dir", str(memory_dir), "--repo-root", str(repo_root)]

    # Freshly-created memory is too-young, so an unforced pending skips (exit 2).
    memory_dir.mkdir(parents=True)
    (memory_dir / "episode.md").write_text("# m\n", encoding="utf-8")
    assert _cli("pending", *common).returncode == 2
    assert not (memory_dir / should_run.PENDING_FILE).exists()

    # --force bypasses the schedule gate and writes the flag.
    forced = _cli("pending", "--force", *common)
    assert forced.returncode == 0, forced.stderr
    assert (memory_dir / should_run.PENDING_FILE).exists()
