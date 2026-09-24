#!/usr/bin/env python3
"""Run the published AutoOps diagnosis, recovery and verification flow."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from autoops_compensation import resolve_compensation

ROOT = Path(__file__).resolve().parents[1]


def run_json(command: list[str]) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=180)
    try:
        payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"status": "UNKNOWN", "error": completed.stderr.strip()[-1000:] or "adapter returned invalid JSON"}
    return completed.returncode, payload


def diagnosis_status(payload: dict[str, Any]) -> str:
    adapter = payload.get("adapter_result")
    return str(adapter.get("status", "")) if isinstance(adapter, dict) else str(payload.get("status", ""))


def run_pm_diagnosis(task_id: str, request: str, service: str, target: str) -> tuple[int, dict[str, Any]]:
    # Recovery is entered from an alert, whose text is not a routing contract.
    # Do not copy remediation words from the alert into this routing request:
    # ProjectManager would otherwise select E02/E01 and take the deterministic
    # single-log branch instead of producing the required trace_ready result.
    # The original request remains the flow's input and is not needed to choose
    # the fixed, read-only diagnosis route.
    diagnosis_request = f"调查 {service} 日志并分析根因；只读，不执行修改"
    return run_json([
        sys.executable, str(ROOT / "scripts" / "autoops-project-manager.py"),
        "--request", diagnosis_request, "--service", service, "--target", target,
        "--since-minutes", "1440", "--limit", "100", "--task-id", task_id,
    ])


def run_pm_recovery(task_id: str, incident_id: str, service: str, target: str,
                    preauthorization_id: str) -> tuple[int, dict[str, Any]]:
    return run_json([
        sys.executable, str(ROOT / "scripts" / "autoops-project-manager.py"),
        "--request", f"恢复 {service} 服务并确保健康", "--service", service, "--target", target,
        "--task-id", task_id, "--idempotency-key", f"{incident_id}:ensure-service",
        "--execute", "--preauthorization-id", preauthorization_id, "--incident-id", incident_id,
    ])


def run_verifier(task_id: str, service: str, target: str) -> tuple[int, dict[str, Any]]:
    return run_json([
        sys.executable, str(ROOT / "scripts" / "verify-service-recovery.py"),
        "--task-id", task_id, "--step-id", "verify-service", "--target", target, "--service", service,
    ])


def execute(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    diagnosis_code, diagnosis = run_pm_diagnosis(args.task_id, args.request, args.service, args.target)
    observed = diagnosis_status(diagnosis)
    result: dict[str, Any] = {"schema_version": 1, "task_id": args.task_id,
                              "incident_id": args.incident_id, "diagnosis": diagnosis}
    if diagnosis_code != 0 or observed not in {"trace_ready"}:
        result.update({"status": "WAITING_EVIDENCE", "decision": "stop",
                       "reason": "repair requires a complete current anomaly trace"})
        return 0, result
    if not args.preauthorization_id:
        result.update({"status": "WAITING_APPROVAL", "decision": "stop",
                       "reason": "a published preauthorization is required before repair"})
        return 0, result
    execution_code, execution = run_pm_recovery(
        args.task_id, args.incident_id, args.service, args.target, args.preauthorization_id,
    )
    result["execution"] = execution
    execution_status = str((execution.get("adapter_result") or {}).get("status", execution.get("status", ""))).upper()
    adapter = execution.get("adapter_result") if isinstance(execution, dict) else None
    error_code = str((adapter or {}).get("error_code", execution.get("error_code", ""))).upper()
    if execution_status == "RECONCILING" or error_code == "RESULT_UNKNOWN":
        result.update({"status": "RECONCILING", "decision": "reconcile",
                       "reason": "external execution result is unknown; query the original execution without resubmitting"})
        return 0, result
    if execution_code != 0 or execution_status != "SUCCEEDED":
        result.update({"status": "FAILED", "decision": "escalate",
                       "reason": "published recovery action did not succeed"})
        return 1, result
    verification_code, verification = run_verifier(args.task_id, args.service, args.target)
    result["verification"] = verification
    result["verification_status"] = verification.get("verification_status", "INCONCLUSIVE")
    if verification_code == 0 and result["verification_status"] == "PASSED":
        result.update({"status": "COMPLETED", "decision": "resolved"})
        return 0, result
    result["compensation"] = resolve_compensation("host.ensure_service.v1")
    result.update({"status": "FAILED", "decision": "escalate",
                   "reason": "recovery execution completed without independent verification"})
    return 1, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one bounded AutoOps recovery flow.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--target", default="local")
    parser.add_argument("--preauthorization-id")
    args = parser.parse_args(argv)
    try:
        code, result = execute(args)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAILED", "decision": "escalate", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
