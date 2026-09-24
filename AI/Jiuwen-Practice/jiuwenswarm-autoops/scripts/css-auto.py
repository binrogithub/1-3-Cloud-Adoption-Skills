#!/usr/bin/env python3
"""Bounded CSS AutoOps command boundary.

The command is useful in observe/recommend mode even when the Huawei SDK is
not installed. A fixture can be supplied for deterministic tests; real writes
are intentionally not implemented at this boundary and remain an E01 action.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from css_config import effective_policy, load_credentials, load_profile, safe_profile_summary
from css_cloud import CssCloudError, ces_metric_samples, ces_metrics, cluster_snapshot
from css_metrics import normalize_snapshot
from css_policy import evaluate
from css_business_verification import verify_observation


def output(value: dict, code: int = 0) -> int:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return code


def fixture(path: str | None) -> dict:
    if not path:
        return {}
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("fixture must be a regular file")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("fixture must be a JSON object")
    return value


def action_status(operation_id: str | None) -> dict:
    if not operation_id:
        return {"status": "INPUT_ERROR", "error_code": "OPERATION_ID_REQUIRED"}
    path = Path(os.environ.get("AUTOOPS_CSS_ACTION_DB", ".runtime/css-actions.sqlite3"))
    if not path.exists():
        return {"status": "NOT_FOUND", "operation_id": operation_id}
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT operation_id,task_id,profile_id,direction,delta,status,cloud_request_id "
            "FROM css_actions WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None:
            return {"status": "NOT_FOUND", "operation_id": operation_id}
        payload = dict(row)
        action_state = payload.pop("status", None)
        return {"status": "FOUND", "action_status": action_state, **payload,
                "cloud_request_id": row["cloud_request_id"] or "not_returned"}
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or plan bounded Huawei Cloud CSS AutoOps.")
    parser.add_argument("command", choices=("inspect", "plan", "verify", "status"))
    parser.add_argument("--profile-id")
    parser.add_argument("--config-dir", default=None)
    parser.add_argument("--policy-id", default=None)
    parser.add_argument("--fixture", default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--operation-id", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            return output(action_status(args.operation_id))
        if not args.profile_id:
            return output({"status": "INPUT_ERROR", "error_code": "PROFILE_ID_REQUIRED"}, 2)
        profile = load_profile(args.profile_id, args.config_dir)
        credentials = load_credentials(profile, args.config_dir)
        if args.policy_id:
            profile = dict(profile)
            profile["policy_ref"] = args.policy_id
        policy = effective_policy(profile, args.config_dir)
        base = {"profile": safe_profile_summary(profile), "policy_revision": policy["revision"],
                "credential_id": credentials.get("credential_id", "default")}
        if args.command in {"inspect", "plan", "verify"}:
            raw = fixture(args.fixture)
            if not raw:
                try:
                    topology = cluster_snapshot(profile, credentials)
                    values = ces_metric_samples(profile, credentials)
                    metric_names = {
                        "disk_usage_pct": "disk_util", "jvm_heap_max": "max_jvm_heap_usage",
                        "cpu_max": "max_cpu_usage", "search_rate": "SearchRate",
                        "search_latency": "SearchLatency", "indexing_rate": "IndexingRate",
                        "indexing_latency": "IndexingLatency",
                    }
                    metric_samples = {
                        target: dict(values.get(source, {}))
                        for target, source in metric_names.items()
                    }
                    raw = {"source": "huaweicloud-css-ces", "observed_at": topology["observed_at"],
                           "metrics": {
                               "cluster_status": 0 if topology["cluster_healthy"] else 3,
                               **{name: sample.get("value") for name, sample in metric_samples.items()},
                           }, "metric_samples": metric_samples, "topology": topology}
                except CssCloudError as exc:
                    return output({**base, "status": "UNAVAILABLE", "error_code": "CSS_DATASOURCE_UNAVAILABLE",
                                   "error": str(exc)}, 1)
            snapshot = normalize_snapshot(raw, source=raw.get("source", "fixture"),
                                          window_minutes=int(raw.get("window_minutes", 10)))
            if args.command == "inspect":
                return output({**base, "status": "READY" if snapshot["quality"] == "ok" else "DEGRADED",
                               "snapshot": snapshot})
            if args.command == "plan":
                decision = evaluate(snapshot, policy)
                return output({**base, "status": decision["status"], "decision": decision,
                               "snapshot_quality": snapshot["quality"],
                               "evidence_refs": snapshot["evidence_refs"]})
            topology = snapshot["topology"]
            verification = verify_observation({
                "engine": topology.get("engine", {}),
                "business": {"status": topology.get("business_verification_status", "UNVERIFIED")},
            }, {"require_engine_health": False, "require_business": True})
            capacity_ready = snapshot["quality"] == "ok" and topology.get("cluster_healthy") is True
            business_status = str(topology.get("business_verification_status", verification.get("business_verification_status", "UNVERIFIED"))).upper()
            final_status = "SUCCEEDED" if capacity_ready and business_status in {"VERIFIED", "PASSED", "SUCCEEDED"} else (
                "CAPACITY_READY" if capacity_ready else "UNVERIFIED")
            return output({**base, "status": final_status,
                           "task_id": args.task_id, "capacity_change_status": topology.get("capacity_change_status", "UNKNOWN"),
                           "business_verification_status": business_status,
                           "verification_status": final_status,
                           "verification": verification,
                           "evidence_refs": snapshot["evidence_refs"]})
        return output({**base, "status": "NOT_IMPLEMENTED", "task_id": args.task_id,
                       "error_code": "NO_OPERATION_RECORD"}, 1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return output({"status": "INPUT_ERROR", "error": str(exc)}, 2)


if __name__ == "__main__":
    raise SystemExit(main())
