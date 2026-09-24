#!/usr/bin/env python3
"""Control the AutoOps watcher without invoking an operational adapter.

This is the small control plane used by the launcher and system operators.
It changes only the persisted watcher lifecycle state or reads the task ledger;
it never collects logs, calls JiuwenSwarm, or runs a repair command.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoops_task_store import TaskStore
from autoops_watch import DEFAULT_STATE, change_status, health_snapshot, load_state, state_path
from autoops_runtime_config import resolve_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control the AutoOps watcher lifecycle.")
    parser.add_argument("--action", choices=("status", "progress", "budget", "follow", "health", "pause", "resume", "stop"),
                        default="status")
    runtime = resolve_runtime()
    parser.add_argument("--state-dir", type=Path,
                        default=Path(runtime["watch_state_dir"]))
    parser.add_argument("--state-db", type=Path,
                        help="Optional task ledger path; defaults to AUTOOPS_STATE_DB.")
    parser.add_argument("--events-file", type=Path,
                        help="Optional event stream used to calculate queue depth.")
    parser.add_argument("--task-id", help="Include one durable task and its events in status output.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--interval", type=int, default=5,
                        help="Follow polling interval in seconds, from 1 through 30.")
    parser.add_argument("--max-updates", type=int, default=0,
                        help="Stop follow after this many snapshots; zero means until terminal.")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 500:
        print(json.dumps({"status": "INPUT_ERROR", "error": "limit must be from 1 through 500"},
                         ensure_ascii=False))
        return 2
    if not 1 <= args.interval <= 30 or args.max_updates < 0:
        print(json.dumps({"status": "INPUT_ERROR", "error":
                          "interval must be 1-30 and max-updates must be non-negative"},
                         ensure_ascii=False))
        return 2

    try:
        if args.action == "follow":
            if not args.task_id:
                print(json.dumps({"status": "INPUT_ERROR", "error":
                                  "--task-id is required for follow"}, ensure_ascii=False))
                return 2
            if args.state_db:
                os.environ["AUTOOPS_STATE_DB"] = str(args.state_db)
            store = TaskStore()
            try:
                emitted = 0
                while True:
                    progress = store.progress(args.task_id)
                    if progress is None:
                        print(json.dumps({"status": "NOT_FOUND", "task_id": args.task_id}, ensure_ascii=False))
                        return 1
                    print(json.dumps({"status": "FOLLOW", "observed_at":
                                      datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                      "progress": progress}, ensure_ascii=False, sort_keys=True), flush=True)
                    emitted += 1
                    if progress["status"] in {"SUCCEEDED", "PARTIAL", "BLOCKED", "FAILED", "CANCELLED"} \
                            or (args.max_updates and emitted >= args.max_updates):
                        return 0
                    time.sleep(args.interval)
            finally:
                store.close()
        if args.action in {"status", "health"}:
            watcher = load_state(args.state_dir)
            events_file = args.events_file or Path(runtime["events_file"])
            watcher = {**watcher, "health": health_snapshot(watcher, events_file)}
        elif args.action in {"pause", "resume", "stop"}:
            target_status = {"pause": "paused", "resume": "active", "stop": "stopped"}[args.action]
            watcher = change_status(args.state_dir, target_status)
            watcher = {**load_state(args.state_dir), **watcher}
        else:
            watcher = {"status": "NOT_REQUESTED"}

        result: dict[str, Any] = {
            "status": "OK",
            "action": args.action,
            "watcher": {**watcher, "state_file": str(state_path(args.state_dir))},
        }
        if args.action == "health":
            result["health"] = watcher["health"]
        if args.action in {"progress", "budget"}:
            if not args.task_id:
                print(json.dumps({"status": "INPUT_ERROR", "error":
                                  f"--task-id is required for {args.action}"}, ensure_ascii=False))
                return 2
            if args.state_db:
                os.environ["AUTOOPS_STATE_DB"] = str(args.state_db)
            store = TaskStore()
            try:
                task = store.get(args.task_id)
                if task is None:
                    print(json.dumps({"status": "NOT_FOUND", "task_id": args.task_id}, ensure_ascii=False))
                    return 1
                result[args.action] = (store.progress(args.task_id) if args.action == "progress"
                                       else store.budget_status(args.task_id))
            finally:
                store.close()
        if args.task_id:
            if args.state_db:
                os.environ["AUTOOPS_STATE_DB"] = str(args.state_db)
            store = TaskStore()
            try:
                task = store.get(args.task_id)
                result["task"] = (None if task is None else
                                   {"task": task, "events": store.events(args.task_id, args.limit)})
            finally:
                store.close()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
