#!/usr/bin/env python3
"""Scheduling gates for the nightly dream entry point.

This helper is intentionally independent from scripts/dream.py: it decides
whether cron should spawn work, records a small lock under the memory root, and
updates a completion stamp after a successful run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ported adapter for MiMo-Code's session/auto-dream.ts scheduling gates.
# Keep the default intervals aligned with:
#   vendor/mimo-code/opencode/src/session/auto-dream.ts
STAMP_FILE = ".dream-last-run.json"
LOCK_FILE = ".dream-run.lock"
PENDING_FILE = ".dream-pending"
DEFAULT_INTERVAL_DAYS = 7.0
DEFAULT_LOCK_TTL_SECONDS = 6 * 60 * 60.0
MIMO_MIN_SPAWN_GAP_SECONDS = 10.0
DEFAULT_THROTTLE_SECONDS = MIMO_MIN_SPAWN_GAP_SECONDS


def _claude_project_key(path: Path) -> str:
    return "-" + "-".join(part for part in path.resolve().parts if part != "/")


def resolve_native_memory_dir(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    projects_root = Path.home() / ".claude" / "projects"
    for candidate in (start, *start.parents):
        memory_dir = projects_root / _claude_project_key(candidate) / "memory"
        if memory_dir.exists():
            return memory_dir
    return projects_root / _claude_project_key(start) / "memory"


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def iso_utc(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def is_pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def memory_file_mtimes(memory_dir: Path) -> list[float]:
    if not memory_dir.exists():
        return []
    ignored = {STAMP_FILE, LOCK_FILE, PENDING_FILE}
    mtimes: list[float] = []
    for path in memory_dir.rglob("*"):
        if not path.is_file() or path.name in ignored:
            continue
        try:
            mtimes.append(path.stat().st_mtime)
        except OSError:
            continue
    return mtimes


def earliest_memory_timestamp(memory_dir: Path) -> float | None:
    mtimes = memory_file_mtimes(memory_dir)
    if mtimes:
        return min(mtimes)
    try:
        return memory_dir.stat().st_mtime
    except OSError:
        return None


def last_run_timestamp(memory_dir: Path) -> float | None:
    data = read_json(memory_dir / STAMP_FILE)
    value = data.get("completed_at_epoch")
    return float(value) if isinstance(value, (int, float)) else None


@dataclass(frozen=True)
class Decision:
    should_run: bool
    reason: str


def scheduling_decision(memory_dir: Path, interval_days: float, force: bool = False,
                        now: float | None = None) -> Decision:
    now = time.time() if now is None else now
    interval_seconds = max(0.0, interval_days) * 24 * 60 * 60

    if force:
        return Decision(True, "force bypass enabled")

    last_run = last_run_timestamp(memory_dir)
    if last_run is not None and now - last_run < interval_seconds:
        age_days = max(0.0, (now - last_run) / 86400)
        return Decision(False, f"too-recent: last dream was {age_days:.2f} days ago")

    if last_run is None:
        first_seen = earliest_memory_timestamp(memory_dir)
        if first_seen is not None and now - first_seen < interval_seconds:
            age_days = max(0.0, (now - first_seen) / 86400)
            return Decision(False, f"too-young: project memory is {age_days:.2f} days old")

    return Decision(True, "eligible")


def acquire_lock(memory_dir: Path, owner_pid: int | None, now: float | None = None,
                 throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
                 lock_ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS) -> Decision:
    now = time.time() if now is None else now
    lock_path = memory_dir / LOCK_FILE
    lock = read_json(lock_path)
    created_at = lock.get("created_at_epoch")
    age = now - float(created_at) if isinstance(created_at, (int, float)) else None
    pid = lock.get("owner_pid")
    pid = int(pid) if isinstance(pid, int) or (isinstance(pid, str) and pid.isdigit()) else None

    if age is not None and age < throttle_seconds:
        return Decision(False, "locked: another dream was spawned recently")
    if age is not None and age < lock_ttl_seconds and is_pid_alive(pid):
        return Decision(False, f"locked: dream already running with pid {pid}")

    write_json(lock_path, {
        "created_at": iso_utc(now),
        "created_at_epoch": now,
        "owner_pid": owner_pid,
    })
    return Decision(True, "lock acquired")


def release_lock(memory_dir: Path, owner_pid: int | None = None) -> None:
    lock_path = memory_dir / LOCK_FILE
    lock = read_json(lock_path)
    existing_pid = lock.get("owner_pid")
    if owner_pid is not None and existing_pid not in {owner_pid, str(owner_pid)}:
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def record_stamp(memory_dir: Path, repo_root: Path, interval_days: float,
                 now: float | None = None) -> None:
    now = time.time() if now is None else now
    write_json(memory_dir / STAMP_FILE, {
        "completed_at": iso_utc(now),
        "completed_at_epoch": now,
        "interval_days": interval_days,
        "repo_root": str(repo_root.resolve()),
        "tool": "maas-dreaming",
    })


def pending_path(memory_dir: Path) -> Path:
    return memory_dir / PENDING_FILE


def write_pending(memory_dir: Path, repo_root: Path, now: float | None = None) -> Path:
    """Mark a dream as due for the next host-agent session. No LLM is spawned."""
    now = time.time() if now is None else now
    path = pending_path(memory_dir)
    write_json(path, {
        "requested_at": iso_utc(now),
        "requested_at_epoch": now,
        "repo_root": str(repo_root.resolve()),
        "tool": "maas-dreaming",
    })
    return path


def clear_pending(memory_dir: Path) -> bool:
    path = pending_path(memory_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def is_pending(memory_dir: Path) -> bool:
    return pending_path(memory_dir).exists()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Decide whether a scheduled dream should run.")
    p.add_argument("command", choices=(
        "check", "stamp", "release", "pending", "pending-status", "clear-pending",
    ))
    p.add_argument("--memory-dir", help="Memory root. Default resolves like scripts/dream.py.")
    p.add_argument("--repo-root", default=".", help="Repo root used for native memory resolution.")
    p.add_argument("--interval-days", type=float,
                   default=float(os.environ.get("MCE_DREAM_INTERVAL_DAYS", DEFAULT_INTERVAL_DAYS)))
    p.add_argument("--force", action="store_true", default=parse_bool(os.environ.get("MCE_FORCE")))
    p.add_argument("--owner-pid", type=int, default=None)
    p.add_argument("--throttle-seconds", type=float, default=DEFAULT_THROTTLE_SECONDS)
    p.add_argument("--lock-ttl-seconds", type=float, default=DEFAULT_LOCK_TTL_SECONDS)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    memory_dir = Path(args.memory_dir).expanduser() if args.memory_dir else resolve_native_memory_dir(repo_root)

    if args.command == "check":
        decision = scheduling_decision(memory_dir, args.interval_days, args.force)
        if not decision.should_run:
            print(f"skip: {decision.reason}; memory_root={memory_dir}")
            return 2
        lock = acquire_lock(memory_dir, args.owner_pid, throttle_seconds=args.throttle_seconds,
                            lock_ttl_seconds=args.lock_ttl_seconds)
        if not lock.should_run:
            print(f"skip: {lock.reason}; memory_root={memory_dir}")
            return 2
        print(f"run: {decision.reason}; memory_root={memory_dir}")
        return 0

    if args.command == "stamp":
        record_stamp(memory_dir, repo_root, args.interval_days)
        release_lock(memory_dir, args.owner_pid)
        print(f"stamped: {memory_dir / STAMP_FILE}")
        return 0

    if args.command == "pending":
        decision = scheduling_decision(memory_dir, args.interval_days, args.force)
        if not decision.should_run:
            print(f"skip: {decision.reason}; memory_root={memory_dir}")
            return 2
        path = write_pending(memory_dir, repo_root)
        print(f"pending: {path}")
        return 0

    if args.command == "pending-status":
        if is_pending(memory_dir):
            print(f"pending: {pending_path(memory_dir)}")
            return 0
        print(f"clean: no dream pending; memory_root={memory_dir}")
        return 1

    if args.command == "clear-pending":
        removed = clear_pending(memory_dir)
        record_stamp(memory_dir, repo_root, args.interval_days)
        print(f"cleared: pending_removed={str(removed).lower()}; stamped {memory_dir / STAMP_FILE}")
        return 0

    release_lock(memory_dir, args.owner_pid)
    print(f"released: {memory_dir / LOCK_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
