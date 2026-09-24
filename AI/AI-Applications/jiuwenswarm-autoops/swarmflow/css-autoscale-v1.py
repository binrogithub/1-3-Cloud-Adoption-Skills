"""Native css_auto workflow for bounded CSS inspect/plan requests."""
from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any


META = {
    "name": "css-autoscale-v1",
    "description": "Native css_auto CSS traffic and bounded data-node plan workflow.",
    "whenToUse": "Inspect or plan a registered Huawei Cloud CSS cluster.",
    "phases": [
        {"title": "css_evidence", "detail": "css_auto reads registered CSS/CES evidence"},
        {"title": "css_plan", "detail": "css_auto returns a bounded hold or scaling plan"},
    ],
}


def normalize_args(args: Any) -> dict[str, Any]:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"request": args}
    if not isinstance(args, Mapping):
        raise ValueError("workflow args must be an object")
    return dict(args)


def _run_project_manager(command: list[str], timeout: int = 120) -> tuple[int, dict[str, Any]]:
    """Run the project-owned deterministic route in the workflow host."""
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True,
        timeout=timeout, env=os.environ.copy(),
    )
    output = completed.stdout.strip()
    try:
        value = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        return completed.returncode or 1, {
            "status": "FAILED", "error_code": "PROJECT_MANAGER_INVALID_OUTPUT",
            "error": "ProjectManager returned non-JSON output",
        }
    if not isinstance(value, Mapping):
        return completed.returncode or 1, {
            "status": "FAILED", "error_code": "PROJECT_MANAGER_INVALID_OUTPUT",
            "error": "ProjectManager returned a non-object result",
        }
    return completed.returncode, dict(value)


def _workflow_status(raw_status: Any) -> str:
    status = str(raw_status or "UNKNOWN").strip().upper()
    if status in {"READY", "DEGRADED", "HOLD", "PLANNED", "PLAN_READY", "COMPLETED",
                  "SUCCEEDED", "CAPACITY_READY", "UNVERIFIED", "PENDING_CONFIRMATION",
                  "WAITING_APPROVAL"}:
        return "COMPLETED" if status not in {"PENDING_CONFIRMATION", "WAITING_APPROVAL"} else "WAITING_APPROVAL"
    return status if status in {"INPUT_ERROR", "NOT_CONFIGURED", "UNAVAILABLE", "INCONCLUSIVE"} else "FAILED"


def _role_trace(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    routing = result.get("routing") if isinstance(result.get("routing"), Mapping) else {}
    roles = routing.get("selected_roles") if isinstance(routing.get("selected_roles"), list) else []
    capabilities = routing.get("selected_capabilities") if isinstance(routing.get("selected_capabilities"), list) else []
    plan = result.get("plan") if isinstance(result.get("plan"), Mapping) else {}
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    adapter = result.get("adapter_result") if isinstance(result.get("adapter_result"), Mapping) else {}
    execution_mode = str(result.get("execution_mode") or "")
    executed_capability = str(result.get("capability") or "")
    adapter_status = str(adapter.get("status") or "").upper()
    trace = [{"step_id": "project-manager-route", "role": "project-manager",
              "capability": "css.project-manager", "status": "SUCCEEDED"}]
    for index, role in enumerate(roles):
        capability = capabilities[index] if index < len(capabilities) else None
        item = {"step_id": f"role-{index + 1}", "role": role,
                "capability": capability, "status": "SELECTED"}
        if (capability == executed_capability and execution_mode == "inspect" and adapter):
            item["status"] = "EXECUTED" if adapter_status in {"READY", "COMPLETED"} else "ATTEMPTED"
            item["result_status"] = adapter_status or "UNKNOWN"
        trace.append(item)
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        item = {"step_id": step.get("step_id"), "role": step.get("role"),
                "capability": step.get("capability"), "status": "PLANNED"}
        if item not in trace:
            trace.append(item)
    return trace


async def run(args: Any):
    from swarmflow import phase

    scope = normalize_args(args)
    request = str(scope.get("request") or "查看 CSS 集群流量和 data 节点容量")
    profile = str(scope.get("css_profile") or "")
    config_dir = str(scope.get("css_config_dir") or "")
    if not profile:
        return {"status": "INPUT_ERROR", "error_code": "CSS_PROFILE_REQUIRED"}
    project_root = Path(__file__).resolve().parents[1]
    executable = os.environ.get("AUTOOPS_PYTHON_EXECUTABLE", "python3")
    command = [
        executable, str(project_root / "scripts" / "autoops-project-manager.py"),
        "--request", request, "--css-profile", profile, "--machine-output",
    ]
    if config_dir:
        command.extend(["--css-config-dir", config_dir])
    phase("css_evidence")
    code, result = _run_project_manager(command)
    raw_status = str(result.get("status", "UNKNOWN")).upper()
    workflow_status = _workflow_status(raw_status)
    plan = result.get("plan") if isinstance(result.get("plan"), Mapping) else {}
    steps = plan.get("steps", []) if isinstance(plan, Mapping) else []
    phase("css_plan")
    return {
        "status": workflow_status,
        "expert_role": "css_auto",
        "selected_roles": result.get("routing", {}).get("selected_roles", ["css_auto"]),
        "role_trace": _role_trace(result),
        "role_boundaries": {
            "runbook-operator": {"status": "GATED", "effect": "write",
                                  "reason": "requires operator authorization and explicit execute"},
            "recovery-verifier": {"status": "NOT_APPLICABLE", "effect": "read",
                                   "reason": "no CSS write operation was submitted"},
        },
        "cloud_writes": False,
        "project_manager_exit_code": code,
        "result": dict(result),
    }
