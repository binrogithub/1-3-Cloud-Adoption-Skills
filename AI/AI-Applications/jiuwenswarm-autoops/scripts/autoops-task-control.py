#!/usr/bin/env python3
"""Resume or cancel a durable AutoOps task without invoking an adapter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoops_task_store import TERMINAL_STATES, TaskStore


def output(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control one durable AutoOps task.")
    parser.add_argument("--action", choices=("status", "progress", "budget", "resume", "cancel"), required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--actor-id")
    parser.add_argument("--session-id")
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--reason", default="operator requested cancellation")
    args = parser.parse_args(argv)
    store = TaskStore(args.state_db)
    try:
        task_id = args.task_id
        if not task_id:
            candidates = store.find_by_identity(actor_id=args.actor_id, session_id=args.session_id)
            if not candidates:
                return output({"status": "NOT_FOUND", "error_code": "TASK_IDENTITY_NOT_FOUND",
                               "actor_id": args.actor_id, "session_id": args.session_id}, 1)
            if len(candidates) > 1:
                return output({"status": "AMBIGUOUS", "error_code": "TASK_IDENTITY_AMBIGUOUS",
                               "actor_id": args.actor_id, "session_id": args.session_id,
                               "candidates": [{"task_id": item["task_id"], "status": item["status"],
                                               "request": item["payload"].get("request"),
                                               "updated_at": item["updated_at"]}
                                              for item in candidates]}, 1)
            task_id = candidates[0]["task_id"]
        task = store.get(task_id)
        if task is None:
            return output({"status": "NOT_FOUND", "task_id": task_id}, 1)
        if args.action == "status":
            return output({"status": "FOUND", "task": task,
                           "events": store.events(task_id)})
        if args.action == "progress":
            return output({"status": "PROGRESS", "progress": store.progress(task_id)})
        if args.action == "budget":
            return output({"status": "BUDGET", "budget": store.budget_status(task_id)})
        if args.action == "cancel":
            task = store.request_cancel(task_id, args.reason)
            return output({"status": "CANCEL_REQUESTED" if task["status"] == "CANCEL_REQUESTED" else "CANCEL_NOT_REQUIRED",
                           "task": task, "next_action": "reconcile_existing_action_only"
                           if task["status"] == "CANCEL_REQUESTED" else "none"})
        if task["status"] == "CANCELLED":
            return output({"status": "CANNOT_RESUME", "error_code": "TASK_CANCELLED",
                           "task": task}, 1)
        if task["status"] == "CANCEL_REQUESTED":
            return output({"status": "CANNOT_RESUME", "error_code": "CANCEL_PENDING",
                           "task": task, "next_action": "reconcile_existing_action_only"}, 1)
        if task["status"] == "RECONCILING":
            return output({"status": "RECONCILE_REQUIRED", "task": task,
                           "next_action": "query_existing_execution"})
        if task["status"] in TERMINAL_STATES:
            return output({"status": "ALREADY_TERMINAL", "task": task,
                           "next_action": "none"})
        store.event(task_id, "task.resume_requested", {
            "task_id": task_id, "policy": "reuse_task_and_operation_id",
        })
        task = store.get(task_id)
        return output({"status": "RESUME_READY", "task": task,
                       "next_action": "continue_existing_plan"})
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
