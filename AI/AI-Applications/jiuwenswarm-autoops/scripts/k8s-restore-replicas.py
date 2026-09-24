#!/usr/bin/env python3
"""Restore one published Deployment through the E01 Rundeck boundary."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("AUTOOPS_KUBERNETES_WORKLOADS_FILE",
                            str(ROOT / "config" / "kubernetes" / "workloads.json")))


def emit(payload: dict[str, Any], code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def published_job(cluster_name: str, workload_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cluster = config["clusters"][cluster_name]
        workload = cluster["workloads"][workload_id]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None, "PUBLISHED_WORKLOAD_NOT_FOUND"
    if cluster.get("enabled") is not True:
        return None, "CLUSTER_NOT_ENABLED"
    job = workload.get("restore_job")
    if workload.get("kind") != "Deployment" or not isinstance(job, str) or not job:
        return None, "RESTORE_ACTION_NOT_PUBLISHED"
    return {"cluster": cluster, "workload": workload, "job": job}, None


def inspect(cluster: str, workload: str) -> tuple[int, dict[str, Any]]:
    command = [sys.executable, str(ROOT / "scripts" / "k8s-inspect.py"),
               "--cluster", cluster, "--workload", workload]
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                               capture_output=True, check=False, timeout=90)
    try:
        payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {
            "status": "unavailable", "error_code": "INSPECT_NO_JSON"
        }
    except json.JSONDecodeError:
        payload = {"status": "unavailable", "error_code": "INSPECT_INVALID_JSON",
                   "error": completed.stderr.strip()[-1000:]}
    return completed.returncode, payload


def runbook(job: str, target: str, task_id: str, idempotency_key: str) -> tuple[int, dict[str, Any]]:
    environment = os.environ.copy()
    environment["AUTOOPS_AUTHENTICATED_ROLE"] = "runbook-operator"
    command = [sys.executable, str(ROOT / "scripts" / "runbook-execute.py"),
               "--task-id", task_id, "--idempotency-key", idempotency_key,
               "--job", job, "--target", target]
    completed = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                               capture_output=True, check=False, timeout=180)
    try:
        payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {
            "status": "UNKNOWN", "error_code": "RUNBOOK_NO_JSON"
        }
    except json.JSONDecodeError:
        payload = {"status": "UNKNOWN", "error_code": "RUNBOOK_INVALID_JSON",
                   "error": completed.stderr.strip()[-1000:]}
    return completed.returncode, payload


def business_verification_config(workload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the explicitly published business probe, if this workload has one."""
    verification = workload.get("business_verification")
    if not isinstance(verification, dict) or not isinstance(verification.get("health_url"), str) \
            or not verification["health_url"].strip():
        return None
    return verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore a published Kubernetes Deployment replica baseline.")
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    args = parser.parse_args(argv)
    if os.environ.get("AUTOOPS_AUTHENTICATED_ROLE") != "kubernetes-operator":
        return emit({"status": "PERMISSION_DENIED", "error_code": "ROLE_REQUIRED",
                     "required_role": "kubernetes-operator"}, 2)
    published, error_code = published_job(args.cluster, args.workload)
    if error_code:
        return emit({"status": "UNAVAILABLE" if error_code == "CLUSTER_NOT_ENABLED" else "INPUT_ERROR",
                     "error_code": error_code, "cluster": args.cluster, "workload": args.workload},
                    1 if error_code == "CLUSTER_NOT_ENABLED" else 2)
    code, observation = inspect(args.cluster, args.workload)
    if code != 0 or observation.get("status") != "ok":
        return emit({"status": "UNKNOWN", "error_code": "PRECONDITION_INSPECTION_FAILED",
                     "observation": observation}, 1)
    conflicts = observation.get("hpa_conflicts", [])
    if conflicts:
        return emit({"status": "WAITING", "error_code": "HPA_CONFLICT", "changed": False,
                     "observation": observation}, 0)
    deployment = observation.get("deployment", {})
    desired = deployment.get("desired_replicas")
    baseline = published["workload"].get("baseline_replicas")
    if not isinstance(desired, int) or not isinstance(baseline, int):
        return emit({"status": "UNKNOWN", "error_code": "REPLICA_STATE_UNAVAILABLE",
                     "observation": observation}, 1)
    if desired >= baseline:
        return emit({"status": "NO_CHANGE", "changed": False, "baseline_replicas": baseline,
                     "observed_replicas": desired, "resource_verification_status": "PASSED",
                     "business_verification_status": "UNVERIFIED"
                     if business_verification_config(published["workload"]) is None else "PENDING",
                     "observation": observation}, 0)
    runbook_code, result = runbook(published["job"], args.target, args.task_id, args.idempotency_key)
    payload: dict[str, Any] = {"status": result.get("status", "UNKNOWN"),
                               "changed": None, "baseline_replicas": baseline,
                               "observed_replicas": desired, "job": published["job"],
                               "target": args.target, "observation": observation,
                               "runbook_result": result}
    if runbook_code == 0 and str(result.get("status", "")).upper() in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
        verify_code, verification = inspect(args.cluster, args.workload)
        payload["verification_observation"] = verification
        after_deployment = verification.get("deployment", {}) if isinstance(verification, dict) else {}
        after_desired = after_deployment.get("desired_replicas")
        after_ready = after_deployment.get("ready_replicas")
        if verify_code != 0 or verification.get("status") != "ok":
            payload["status"] = "FAILED"
            payload["resource_verification_status"] = "FAILED"
            payload["verification_status"] = "FAILED"  # legacy field
            payload["error_code"] = "POSTCONDITION_INSPECTION_FAILED"
            return emit(payload, 1)
        if not isinstance(after_desired, int) or not isinstance(after_ready, int) \
                or after_desired < baseline or after_ready < baseline:
            payload["status"] = "FAILED"
            payload["resource_verification_status"] = "FAILED"
            payload["verification_status"] = "FAILED"  # legacy field
            payload["error_code"] = "POSTCONDITION_NOT_MET"
            return emit(payload, 1)
        payload["resource_verification_status"] = "PASSED"
        payload["verification_status"] = "PASSED"  # legacy field means resource postcondition
        payload["business_verification_status"] = "UNVERIFIED" \
            if business_verification_config(published["workload"]) is None else "PENDING"
        payload["verified_replicas"] = {"desired": after_desired, "ready": after_ready}
    recap = result.get("ansible_recap")
    if isinstance(recap, dict):
        payload["changed"] = recap.get("result") == "CHANGED"
        payload["ansible_recap"] = recap
    return emit(payload, runbook_code)


if __name__ == "__main__":
    raise SystemExit(main())
