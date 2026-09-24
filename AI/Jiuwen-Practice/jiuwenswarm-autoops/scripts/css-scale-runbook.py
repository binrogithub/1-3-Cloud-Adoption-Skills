#!/usr/bin/env python3
"""The only project-owned CSS data-node mutation boundary.

This is an E01 Runbook adapter. It refuses all mutations unless the caller is
the authenticated runbook role, supplies a registered profile and explicitly
enables execution. The API response is always reported as SUBMITTED.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from css_capability import classify_api_error, validate_plan
from css_action_ledger import open_action_db, resource_key, transition_status
from css_cloud import CssCloudError, cluster_snapshot, scale_cluster
from css_config import effective_policy, load_credentials, load_profile, safe_profile_summary


def emit(value: dict, code: int = 0) -> int:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return code


def action_db() -> sqlite3.Connection:
    return open_action_db()


def task_event(task_id: str, event_type: str, payload: dict) -> None:
    try:
        from autoops_task_store import TaskStore
        store = TaskStore()
        try:
            if store.get(task_id) is not None:
                store.event(task_id, event_type, payload)
        finally:
            store.close()
    except Exception:
        # The action ledger remains authoritative if a caller does not have a
        # TaskStore task (for example, an isolated Runbook test).
        pass


def set_action_status(connection: sqlite3.Connection, operation_id: str,
                      target: str) -> None:
    row = connection.execute(
        "SELECT status FROM css_actions WHERE operation_id=?", (operation_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"CSS action is missing from ledger: {operation_id}")
    status = transition_status(row[0], target)
    connection.execute("UPDATE css_actions SET status=?, updated_at=? WHERE operation_id=?",
                       (status, datetime.now(timezone.utc).isoformat(), operation_id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed CSS ess data-node scaling action.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--direction", choices=("scale_out", "scale_in"), required=True)
    parser.add_argument("--delta", type=int, required=True)
    parser.add_argument("--config-dir")
    parser.add_argument("--target-nodes", type=int)
    parser.add_argument("--topology-file")
    parser.add_argument("--business-evidence-file")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    base = {"task_id": args.task_id, "operation_id": args.idempotency_key,
            "profile_id": args.profile_id, "direction": args.direction,
            "delta": args.delta, "node_type": "ess"}
    try:
        profile = load_profile(args.profile_id, args.config_dir)
        credentials = load_credentials(profile, args.config_dir)
        policy = effective_policy(profile, args.config_dir)
        stable_resource_key = resource_key(profile)
        base["profile"] = safe_profile_summary(profile)
        if args.delta < 1:
            return emit({**base, "status": "INPUT_ERROR", "error_code": "DELTA_INVALID"}, 2)
        step_key = "scale_out_step" if args.direction == "scale_out" else "scale_in_step"
        allow_key = "allow_scale_out" if args.direction == "scale_out" else "allow_scale_in"
        if not policy.get(allow_key, False):
            return emit({**base, "status": "BLOCKED",
                         "error_code": "POLICY_DIRECTION_DISABLED"}, 0)
        step_limit = int(policy[step_key])
        if args.direction == "scale_in":
            step_limit = min(step_limit, int(policy.get("max_scale_in_step", 1)))
        if args.delta > step_limit:
            return emit({**base, "status": "BLOCKED", "error_code": "STEP_LIMIT"}, 0)
        if not args.execute:
            return emit({**base, "status": "PENDING_CONFIRMATION",
                         "execution_mode": "dry-run",
                         "confirmation": "Only an operator-created E01 approval may execute this fixed Runbook."})
        if os.environ.get("AUTOOPS_AUTHENTICATED_ROLE") != "runbook-operator":
            return emit({**base, "status": "PERMISSION_DENIED",
                         "error_code": "RUNBOOK_ROLE_REQUIRED"}, 0)
        if os.environ.get("AUTOOPS_CSS_MUTATION_ENABLED") != "1":
            return emit({**base, "status": "BLOCKED",
                         "error_code": "CSS_MUTATION_DISABLED",
                         "error": "CSS mutation is disabled; use observe or recommend mode."}, 0)
        if args.target_nodes is None or not args.topology_file:
            return emit({**base, "status": "BLOCKED",
                         "error_code": "PRECHECK_EVIDENCE_REQUIRED",
                         "message": "An execute request requires the current topology and target node count."}, 0)
        business_evidence = None
        if args.direction == "scale_in":
            if not args.business_evidence_file:
                return emit({**base, "status": "BLOCKED",
                             "error_code": "BUSINESS_VERIFICATION_REQUIRED_FOR_SCALE_IN"}, 0)
            business_path = Path(args.business_evidence_file)
            if business_path.is_symlink() or not business_path.is_file():
                return emit({**base, "status": "BLOCKED",
                             "error_code": "BUSINESS_EVIDENCE_UNAVAILABLE"}, 0)
            business_evidence = json.loads(business_path.read_text(encoding="utf-8"))
            if not isinstance(business_evidence, dict) or business_evidence.get("status") != "PASSED":
                return emit({**base, "status": "BLOCKED",
                             "error_code": "BUSINESS_WINDOW_NOT_PASSED"}, 0)
            if (int(business_evidence.get("sample_count", 0)) < int(business_evidence.get("required_samples", 1))
                    or float(business_evidence.get("window_seconds", 0)) < float(business_evidence.get("required_window_seconds", 1))):
                return emit({**base, "status": "BLOCKED",
                             "error_code": "BUSINESS_WINDOW_INCOMPLETE"}, 0)
            samples = business_evidence.get("samples", [])
            if not samples or time.time() - float(samples[-1].get("observed_epoch", 0)) > 180:
                return emit({**base, "status": "BLOCKED",
                             "error_code": "BUSINESS_EVIDENCE_STALE"}, 0)
        topology_path = Path(args.topology_file)
        if topology_path.is_symlink() or not topology_path.is_file():
            return emit({**base, "status": "BLOCKED",
                         "error_code": "TOPOLOGY_EVIDENCE_UNAVAILABLE"}, 0)
        topology = json.loads(topology_path.read_text(encoding="utf-8"))
        if not isinstance(topology, dict):
            return emit({**base, "status": "BLOCKED",
                         "error_code": "TOPOLOGY_EVIDENCE_INVALID"}, 0)
        if policy.get("fresh_precheck_required", False):
            try:
                fresh_topology = cluster_snapshot(profile, credentials)
            except CssCloudError as exc:
                return emit({**base, "status": "UNAVAILABLE",
                             "error_code": "FRESH_TOPOLOGY_UNAVAILABLE",
                             "error": str(exc)}, 1)
            supplied_nodes = topology.get("data_node_count")
            if supplied_nodes is not None and supplied_nodes != fresh_topology.get("data_node_count"):
                return emit({**base, "status": "BLOCKED",
                             "error_code": "TOPOLOGY_CHANGED",
                             "reason_codes": ["TOPOLOGY_CHANGED"],
                             "supplied_nodes": supplied_nodes,
                             "current_nodes": fresh_topology.get("data_node_count")}, 0)
            topology = fresh_topology
        precheck = validate_plan(topology, policy, args.direction, args.delta, args.target_nodes)
        if precheck:
            status = "RECONCILING" if "ACTIVE_CLOUD_ACTION" in precheck else "BLOCKED"
            return emit({**base, "status": status, "reason_codes": precheck,
                         "error_code": precheck[0]}, 0)
        connection = action_db()
        # Make the active-action check and intent insert one SQLite transaction.
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT task_id,profile_id,direction,delta,status,cloud_request_id "
            "FROM css_actions WHERE operation_id=?", (args.idempotency_key,)
        ).fetchone()
        if existing:
            connection.close()
            if tuple(existing[1:4]) != (args.profile_id, args.direction, args.delta):
                return emit({**base, "status": "IDEMPOTENCY_CONFLICT",
                             "error_code": "IDEMPOTENCY_CONFLICT"}, 2)
            return emit({**base, "status": existing[4],
                         "cloud_request_id": existing[5], "reconciliation": True}, 0)
        active = connection.execute(
            "SELECT operation_id,status FROM css_actions WHERE (resource_key=? OR profile_id=?) "
            "AND status IN ('INTENT_RECORDED','SUBMITTED','RECONCILING','UNKNOWN','CAPACITY_READY','VERIFYING_BUSINESS','DEGRADED') "
            "AND operation_id<>? ORDER BY operation_id LIMIT 1",
            (stable_resource_key, args.profile_id, args.idempotency_key),
        ).fetchone()
        if active:
            connection.close()
            return emit({**base, "status": "RECONCILING",
                         "error_code": "ACTIVE_CLOUD_ACTION",
                         "active_operation_id": active[0],
                         "message": "An existing CSS action must be reconciled before a new write."}, 0)
        connection.execute(
            "INSERT INTO css_actions(operation_id,task_id,profile_id,direction,delta,status,cloud_request_id,"
            "resource_key,target_nodes,policy_revision,evidence_ref,intent_recorded_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (args.idempotency_key, args.task_id, args.profile_id, args.direction,
             args.delta, "INTENT_RECORDED", None, stable_resource_key, args.target_nodes,
             policy.get("revision"), topology_path.as_posix(),
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
        task_event(args.task_id, "css.action_intent_recorded", {
            "operation_id": args.idempotency_key, "profile_id": args.profile_id,
            "direction": args.direction, "delta": args.delta, "node_type": "ess",
        })
        try:
            response, request_id = scale_cluster(
                profile, credentials, args.direction, args.delta
            )
        except ImportError:
            set_action_status(connection, args.idempotency_key, "FAILED")
            connection.commit()
            connection.close()
            return emit({**base, "status": "UNAVAILABLE",
                         "error_code": "CSS_SDK_NOT_INSTALLED"}, 1)
        except Exception as exc:
            classification = classify_api_error(str(exc))
            set_action_status(connection, args.idempotency_key, classification["status"])
            connection.commit()
            connection.close()
            if isinstance(exc, CssCloudError):
                return emit({**base, "status": "UNAVAILABLE", "error": str(exc)}, 1)
            return emit({**base, "status": classification["status"],
                         "error_code": classification["error_code"],
                         "reason_code": classification["reason_code"],
                         "retry": classification["retry"], "error": str(exc)}, 0)
        # CSS's successful scale-out response exposes ``id`` as the cluster
        # ID, not as an operation/request ID.  Never report that value as a
        # cloud request identifier; the reconciliation ledger already tracks
        # the idempotency key when Huawei does not return one.
        set_action_status(connection, args.idempotency_key, "SUBMITTED")
        connection.execute("UPDATE css_actions SET cloud_request_id=? WHERE operation_id=?",
                           (request_id, args.idempotency_key))
        connection.commit()
        connection.close()
        task_event(args.task_id, "css.action_submitted", {
            "operation_id": args.idempotency_key, "cloud_request_id": request_id,
            "status": "SUBMITTED",
        })
        return emit({**base, "status": "SUBMITTED",
                     "cloud_request_id": request_id,
                     "cloud_request_id_status": "returned" if request_id else "not_returned",
                     "capacity_change_status": "RECONCILING",
                     "message": "CSS accepted the request; topology reconciliation is required."})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return emit({**base, "status": "INPUT_ERROR", "error": str(exc)}, 2)


if __name__ == "__main__":
    raise SystemExit(main())
