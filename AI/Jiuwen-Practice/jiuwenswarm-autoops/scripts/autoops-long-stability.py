#!/usr/bin/env python3
"""Run a bounded AutoOps watcher stability audit and persist evidence."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT / "scripts" / "autoops_watch.py"


def load_object(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"file must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_evidence(path: Path, payload: dict[str, object]) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink evidence path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def audit(args: argparse.Namespace) -> dict[str, object]:
    if args.mode not in {"fixture", "deployed"}:
        raise ValueError("mode must be fixture or deployed")
    if args.cycles is None and args.duration_seconds < 60:
        raise ValueError("duration_seconds must be at least 60 when cycles is omitted")
    if args.mode == "deployed":
        if args.cycles is not None or args.duration_seconds < 86400:
            raise ValueError("deployed mode requires wall-clock duration of at least 86400 seconds")
        if not shutil.which("systemctl"):
            raise ValueError("deployed mode requires systemctl")
        active = subprocess.run(["systemctl", "is-active", "--quiet", args.watch_service],
                                check=False, capture_output=True, text=True)
        if active.returncode != 0:
            raise ValueError(f"deployed watcher is not active: {args.watch_service}")
    if args.cycles is not None and not 1 <= args.cycles <= 100000:
        raise ValueError("cycles must be from 1 through 100000")
    if not 0 <= args.interval_seconds <= 3600:
        raise ValueError("interval_seconds must be from 0 through 3600")
    policy = load_object(args.policy)
    if policy.get("kind") != "MonitoringPolicy":
        raise ValueError("policy must be a MonitoringPolicy object")
    state_dir = args.state_dir
    events_file = args.events_file
    if events_file.is_symlink() or not events_file.is_file():
        raise ValueError(f"events file must be a regular file: {events_file}")
    state_dir.mkdir(parents=True, exist_ok=True)
    progress_file = state_dir / "stability-progress.jsonl"
    if progress_file.is_symlink():
        raise ValueError(f"refusing symlink progress path: {progress_file}")
    environment = os.environ.copy()
    environment["AUTOOPS_STATE_DB"] = str(args.state_db)
    started = time.time()
    offsets: list[int] = []
    cycle_results: list[dict[str, object]] = []
    requested_cycles = args.cycles
    deadline = started + args.duration_seconds
    cycle = 0
    while True:
        if requested_cycles is not None and cycle >= requested_cycles:
            break
        if requested_cycles is None and time.time() >= deadline:
            break
        if args.mode == "deployed":
            # The installed systemd watcher is the sole consumer. This audit
            # samples its durable state and never starts a second watcher.
            result = {"processed": None, "duplicates": None}
        else:
            completed = subprocess.run(
                [sys.executable, str(WATCHER), "--policy", str(args.policy),
                 "--state-dir", str(state_dir), "--events-file", str(events_file)],
                text=True, capture_output=True, env=environment, check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"watcher failed at cycle {cycle + 1}: {completed.stdout or completed.stderr}")
            result = json.loads(completed.stdout)
        state = load_object(state_dir / "state.json")
        if state.get("status") != "active":
            raise RuntimeError(f"watcher left active state at cycle {cycle + 1}: {state.get('status')}")
        offset = int(state.get("file_offset", 0))
        if offsets and offset < offsets[-1]:
            raise RuntimeError(f"event file offset moved backwards at cycle {cycle + 1}")
        offsets.append(offset)
        cycle_results.append({
            "cycle": cycle + 1,
            "processed": result.get("processed", 0),
            "duplicates": result.get("duplicates", 0),
            "offset": offset,
            "watermark": state.get("watermark"),
        })
        cycle += 1
        checkpoint = {
            "cycle": cycle,
            "processed": result.get("processed", 0),
            "duplicates": result.get("duplicates", 0),
            "offset": offset,
            "watermark": state.get("watermark"),
            "recorded_at": time.time(),
        }
        with progress_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(checkpoint, ensure_ascii=False), file=sys.stderr, flush=True)
        if requested_cycles is None and time.time() >= deadline:
            break
        if args.interval_seconds:
            time.sleep(args.interval_seconds)
    if not cycle:
        raise RuntimeError("stability audit completed zero cycles")
    finished = time.time()
    payload: dict[str, object] = {
        "schema_version": 1,
        "result": "PASS",
        "mode": ("accelerated" if args.mode == "fixture" and requested_cycles is not None
                  else ("duration" if args.mode == "fixture" else "deployed")),
        "cycles": cycle,
        "duration_seconds": round(finished - started, 3),
        "requested_duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "policy": str(args.policy),
        "events_file": str(events_file),
        "state_dir": str(state_dir),
        "state_db": str(args.state_db),
        "progress_file": str(progress_file),
        "offsets": offsets,
        "cycle_results": cycle_results,
        "tui_required": False,
        "consumer_service": args.watch_service if args.mode == "deployed" else None,
        "second_consumer_started": False,
        "secrets_persisted": False,
    }
    if args.evidence:
        write_evidence(args.evidence, payload)
        payload["evidence"] = str(args.evidence)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a bounded AutoOps watcher stability audit.")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--events-file", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--state-db", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, default=86400)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--cycles", type=int, help="Use bounded cycles for accelerated fixture validation.")
    parser.add_argument("--mode", choices=("fixture", "deployed"), default="fixture")
    parser.add_argument("--watch-service", default="jiuwenswarm-autoops-watch.service",
                        help="Active systemd watcher sampled by deployed mode")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
