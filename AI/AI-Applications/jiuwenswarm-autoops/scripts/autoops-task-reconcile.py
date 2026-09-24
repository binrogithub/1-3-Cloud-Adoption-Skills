#!/usr/bin/env python3
"""Reconcile one unknown Runbook execution without creating a new action."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from autoops_task_store import TaskStore

ROOT = Path(__file__).resolve().parents[1]


def output(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def reconciliation_context(store: TaskStore, task_id: str) -> dict | None:
    for event in reversed(store.events(task_id)):
        if event["event_type"] == "external.execution_unknown":
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                return payload
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the original Runbook execution only.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--execution-db", type=Path)
    args = parser.parse_args(argv)

    store = TaskStore(args.state_db)
    try:
        task = store.get(args.task_id)
        if task is None:
            return output({"status": "NOT_FOUND", "error_code": "TASK_NOT_FOUND",
                           "task_id": args.task_id}, 1)
        if task["status"] in {"SUCCEEDED", "FAILED", "PARTIAL", "BLOCKED", "CANCELLED"}:
            return output({"status": "ALREADY_TERMINAL", "task": task}, 0)
        context = reconciliation_context(store, args.task_id)
        if context is None:
            return output({"status": "RECONCILE_CONTEXT_MISSING",
                           "error_code": "RECONCILE_CONTEXT_MISSING",
                           "task_id": args.task_id}, 1)
        job = str(context.get("job") or "")
        target = str(context.get("target") or "")
        operation_id = str(context.get("operation_id") or task["payload"].get("operation_id") or "")
        if not job or not target or not operation_id:
            return output({"status": "RECONCILE_CONTEXT_INVALID",
                           "error_code": "RECONCILE_CONTEXT_INVALID",
                           "task_id": args.task_id}, 1)
    finally:
        store.close()

    environment = os.environ.copy()
    if args.execution_db:
        environment["AUTOOPS_EXECUTION_DB"] = str(args.execution_db)
    command = [sys.executable, str(ROOT / "scripts" / "runbook-execute.py"),
               "--task-id", args.task_id, "--idempotency-key", operation_id,
               "--job", job, "--target", target]
    completed = subprocess.run(command, cwd=ROOT, env=environment,
                               text=True, capture_output=True, check=False)
    try:
        adapter = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        adapter = {"status": "UNKNOWN", "error_code": "RESULT_UNKNOWN",
                   "error": completed.stderr.strip()[-1000:]}

    store = TaskStore(args.state_db)
    try:
        task_payload = {
            "status": adapter.get("status", "UNKNOWN"),
            "execution_status": adapter.get("status", "UNKNOWN"),
            "error_code": adapter.get("error_code"),
            "retry_class": adapter.get("retry_class"),
            "reconciliation": True,
            "adapter_result": adapter,
        }
        store.record_result(args.task_id, task_payload, completed.returncode,
                            event_type="external.execution_reconciled")
        task = store.get(args.task_id)
    finally:
        store.close()

    lifecycle = task["status"] if task else "UNKNOWN"
    result = {"status": lifecycle, "task_id": args.task_id,
              "operation_id": operation_id, "job": job, "target": target,
              "adapter_result": adapter,
              "next_action": "reconcile_existing_action_only"
              if lifecycle == "CANCEL_REQUESTED" else
              "query_existing_execution" if lifecycle == "RECONCILING" else "none"}
    return output(result, 0 if lifecycle in {"RECONCILING", "CANCEL_REQUESTED", "SUCCEEDED"} else 1)


if __name__ == "__main__":
    raise SystemExit(main())
