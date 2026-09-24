#!/usr/bin/env python3
"""Read one persisted AutoOps task and its lifecycle events."""
from __future__ import annotations

import argparse
import json

from autoops_task_store import TaskStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read one AutoOps task status.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 500:
        print(json.dumps({"status": "INPUT_ERROR", "error": "limit must be from 1 through 500"}))
        return 2
    store = TaskStore()
    try:
        task = store.get(args.task_id)
        if task is None:
            print(json.dumps({"status": "NOT_FOUND", "task_id": args.task_id}, ensure_ascii=False))
            return 1
        print(json.dumps({"status": "FOUND", "task": task,
                          "events": store.events(args.task_id, args.limit)}, ensure_ascii=False))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
