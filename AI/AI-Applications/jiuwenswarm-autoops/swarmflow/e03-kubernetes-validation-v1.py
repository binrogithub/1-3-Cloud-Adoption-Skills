"""Read-only native E03 Kubernetes expert validation workflow.

This is a project-owned glue asset. JiuwenSwarm supplies the native workflow
engine and worker; the worker is constrained to the published E03 inspection
adapter and never receives a recovery or arbitrary kubectl route.
"""
import json
import shlex
from collections.abc import Mapping
from typing import Any


META = {
    "name": "e03-kubernetes-validation-v1",
    "description": "Native E03 Kubernetes operator validation: inspect only.",
    "whenToUse": "Validate native kubernetes-operator registration against a published read-only workload.",
    "phases": [
        {"title": "inspect", "detail": "kubernetes-operator: published E03 read-only inspect"},
    ],
}


INSPECT_SCHEMA = {
    "type": "object",
    "required": ["task_id", "selected_epic", "selected_role", "capability", "status"],
    "properties": {
        "task_id": {"type": "string"},
        "selected_epic": {"type": "string"},
        "selected_role": {"type": "string"},
        "capability": {"type": "string"},
        "status": {"type": "string"},
        "cluster": {"type": "string"},
        "workload": {"type": "string"},
    },
}


def _ok(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    # The validation proves native role registration and the published route;
    # a customer cluster may legitimately be unavailable in this read-only run.
    return (
        result.get("selected_epic") == "E03"
        and result.get("selected_role") == "kubernetes-operator"
        and result.get("capability") == "k8s.inspect.v1"
        and str(result.get("status", "")).upper() not in {"FAILED", "ERROR", "BLOCKED", "INVALID"}
    )


async def run(args: Any):
    from swarmflow import agent, phase

    if isinstance(args, str):
        try:
            scope = json.loads(args)
        except json.JSONDecodeError:
            scope = {"request": args}
    else:
        scope = dict(args or {}) if isinstance(args, Mapping) else {}
    request = str(scope.get("request") or scope.get("task") or
                  "检查本机 Kubernetes 集群和工作负载，只读盘点")
    cluster = str(scope.get("cluster") or "autoops-development")
    workload = str(scope.get("workload") or "staging/orders/order-api")
    target = str(scope.get("target") or "local")
    route = shlex.join([
        "python3",
        "/root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py",
        "--request", request,
        "--cluster", cluster,
        "--workload", workload,
        "--target", target,
    ])
    phase("inspect")
    result = await agent(
        "You are the E03 Kubernetes Operator. This is a published read-only validation. "
        "Make exactly one tool call: use the bash tool to run the following exact "
        "project-owned command, then return its JSON result through structured_output:\n\n"
        + route
        + "\n\nDo not read any Skill, AGENT, workflow, or other file. Do not use read_file, "
        "search_files, grep, glob, kubectl, Rundeck, Ansible, recovery, or any other "
        "tool. Do not run any command before or after the exact command above. The "
        "command is the only allowed operational boundary for this worker. Request: "
        + request,
        label="kubernetes-operator",
        schema=INSPECT_SCHEMA,
        options={"timeout": 120},
    )
    if not _ok(result):
        return {"status": "FAILED", "failed_phase": "inspect", "result": result}
    return {"status": "COMPLETED", "expert_role": "kubernetes-operator", "inspection": result}
