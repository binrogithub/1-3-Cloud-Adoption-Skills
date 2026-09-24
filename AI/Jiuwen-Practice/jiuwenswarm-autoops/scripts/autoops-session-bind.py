#!/usr/bin/env python3
"""Bind a native TUI session to the durable task it created."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from autoops_task_store import TaskStore

TASK_ID = re.compile(r"\bpm-[a-f0-9]{32}\b")


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def find_task_id(history: Path) -> str | None:
    try:
        text = history.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    matches = TASK_ID.findall(text)
    return matches[0] if matches else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind a TUI session to its AutoOps task.")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--actor-id", default="tui")
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args(argv)
    deadline = time.monotonic() + max(0, min(args.wait_seconds, 60))
    task_id = find_task_id(args.history)
    while task_id is None and time.monotonic() < deadline:
        time.sleep(0.25)
        task_id = find_task_id(args.history)
    if task_id is None:
        return emit({"status": "PENDING", "session_id": args.session_id})

    store = TaskStore(args.state_db)
    try:
        task = store.get(task_id)
        if task is None:
            return emit({"status": "NOT_FOUND", "task_id": task_id}, 1)
        try:
            task = store.bind_identity(task_id, actor_id=args.actor_id,
                                       session_id=args.session_id)
        except ValueError as exc:
            return emit({"status": "IDENTITY_CONFLICT", "task_id": task_id,
                         "error": str(exc)}, 1)
        return emit({"status": "BOUND", "task_id": task_id,
                     "actor_id": args.actor_id, "session_id": args.session_id,
                     "task_status": task["status"] if task else None})
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
