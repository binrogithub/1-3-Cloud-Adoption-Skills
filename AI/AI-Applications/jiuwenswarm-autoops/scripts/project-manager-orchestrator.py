#!/usr/bin/env python3
"""Create constrained, multi-role AutoOps recovery plans.

This is a project-owned adapter.  It never runs a shell command itself and only
emits an approved capability plan; a SwarmFlow asset or trusted caller advances
the individual steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from autoops_authorization import authorization_dir
from autoops_contract import autoops_plan

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "capability-registry.json"
WORKFLOW_REGISTRY = ROOT / "config" / "workflow-registry.json"
SERVICE_POLICY = ROOT / "config" / "authorization" / "service-policy.json"
TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def stable_task_id(request: str, target: str, service: str) -> str:
    """Give retries of one recovery request the same correlation identity."""
    material = "\x1f".join((request.strip(), target, service)).encode("utf-8")
    return "autoops-" + hashlib.sha256(material).hexdigest()[:32]


def fail(message: str) -> int:
    print(json.dumps({"status": "INPUT_ERROR", "error": message}))
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build one published multi-role service recovery plan.")
    parser.add_argument("--request", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--mode", choices=("inspect", "confirm", "auto"), default="inspect")
    parser.add_argument("--since-minutes", type=int, default=15)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--task-id")
    parser.add_argument("--authorization-id")
    args = parser.parse_args(argv)
    if not TARGET_RE.fullmatch(args.target):
        return fail("target does not match the published target schema")
    if not 1 <= args.since_minutes <= 60 or not 1 <= args.limit <= 200:
        return fail("since-minutes must be 1..60 and limit must be 1..200")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["capabilities"]
    workflow_registry = json.loads(WORKFLOW_REGISTRY.read_text(encoding="utf-8"))["workflows"]
    workflow = workflow_registry["service-recovery-v1"]
    policy = json.loads(SERVICE_POLICY.read_text(encoding="utf-8"))
    allowed_hosts = policy.get("allowed_hosts", [])
    # The public AutoOps contract uses `local` when the operator omits a host.
    # The demo recovery policy publishes one logical local fixture under its
    # execution identity, so resolve that alias before validating the plan.
    if args.target == "local" and args.target not in allowed_hosts and len(allowed_hosts) == 1:
        args.target = allowed_hosts[0]
    if args.target not in allowed_hosts:
        return fail("target is not published for the service recovery workflow")
    write = registry.get("host.ensure_service.v1", {})
    if args.service != write.get("service"):
        return fail("service recovery is not published for this service")
    task_id = args.task_id or stable_task_id(args.request, args.target, args.service)
    if args.mode == "auto":
        if not args.authorization_id:
            return fail("auto mode requires a trusted authorization-id")
        approval_path = authorization_dir() / f"{args.authorization_id}.json"
        try:
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return fail("auto mode requires an operator-created authorization record")
        if (approval.get("status") != "APPROVED" or approval.get("task_id") != task_id
                or approval.get("target") != args.target or approval.get("job") != write.get("job")):
            return fail("authorization scope does not match the published recovery action")
        try:
            if float(approval["expires_at"]) <= time.time():
                return fail("authorization has expired")
        except (KeyError, TypeError, ValueError):
            return fail("authorization expiry is invalid")
    steps = [
        {"step_id": "inspect-host", "role": "runbook-operator", "capability": "host.inspect.v1",
         "invocation_kind": "project_route", "effect": "read", "depends_on": [],
         "when": "always", "required": True, "expected_result": {"status": "SUCCEEDED"},
         "timeout_seconds": 300, "inputs": {"target": args.target}},
        {"step_id": "diagnose-logs", "role": "log-investigator", "capability": "logs.query.v1",
         "invocation_kind": "project_route", "effect": "read", "depends_on": ["inspect-host"],
         "when": "inspect-host.status == SUCCEEDED", "required": True,
         "expected_result": {"status": "SUCCEEDED", "diagnosis_status": "reported"},
         "timeout_seconds": 600,
         "inputs": {"target": args.target, "service": args.service,
                    "since_minutes": args.since_minutes, "limit": args.limit}},
    ]
    if args.mode != "inspect":
        steps.append({"step_id": "ensure-service", "role": "ansible-operator", "capability": "host.ensure_service.v1",
                      "invocation_kind": "project_route", "effect": "write",
                      "depends_on": ["inspect-host", "diagnose-logs"],
                      "when": "diagnose-logs.status == SUCCEEDED", "required": True,
                      "expected_result": {"status": "SUCCEEDED", "approval": "required" if args.mode == "confirm" else "preauthorized"},
                      "timeout_seconds": 900,
                      "approval": "required" if args.mode == "confirm" else "preauthorized",
                      "inputs": {"target": args.target, "service": args.service}})
        steps.append({"step_id": "verify-service", "role": "recovery-verifier", "capability": "service.verify.v1",
                      "invocation_kind": "project_route", "effect": "read", "depends_on": ["ensure-service"],
                      "when": "ensure-service.status == SUCCEEDED", "required": True,
                      "expected_result": {"status": "SUCCEEDED", "verification_status": "reported"},
                      "timeout_seconds": 600,
                      "inputs": {"target": args.target, "service": args.service}})
    status = "WAITING_APPROVAL" if args.mode == "confirm" else "PLANNED"
    payload = autoops_plan(task_id=task_id, plan_revision=1, goal=args.request,
                           scope={"target_ref": args.target, "service_ref": args.service},
                           steps=steps, status=status, template_id="service-recovery-v1",
                           mode=args.mode,
                           workflow_ref="service-recovery-v1", workflow_asset=workflow["asset"],
                           published_capabilities=set(registry))
    payload.update({"authorization_id": args.authorization_id,
                    "scope": {"target": args.target, "service": args.service},
                    "stop_conditions": ["evidence_insufficient", "policy_denied",
                                         "verification_failed", "external_result_unknown"],
                    "max_replans": 1})
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
