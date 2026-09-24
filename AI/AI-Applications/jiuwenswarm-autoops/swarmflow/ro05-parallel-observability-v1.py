"""RO-05 parallel read-only observability workflow.

The workflow uses JiuwenSwarm native experts and project-owned terminal
routes. E05 logs and E04 metrics are independent and run concurrently. E06
history is added at most once when E05 returns anomaly evidence, which is the
only plan revision this workflow permits. No write capability is exposed.
"""
from __future__ import annotations

import asyncio
import json
import re
import shlex
import uuid
from collections.abc import Mapping
from typing import Any


META = {
    "name": "ro05-parallel-observability-v1",
    "description": "Parallel E05/E04 evidence collection with one evidence-triggered E06 replan.",
    "whenToUse": "Read-only application diagnosis where logs and metrics are independent evidence sources.",
    "phases": [
        {"title": "parallel_evidence", "detail": "E05 logs and E04 metrics run concurrently"},
        {"title": "replan", "detail": "E06 history is added once only when E05 finds an anomaly"},
        {"title": "approval", "detail": "human acknowledgement gate; no write step"},
    ],
    "budget": {"max_steps": 3, "max_parallel_read_steps": 3, "max_replans": 1},
}

SERVICE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
FAILURE_STATUSES = {"FAILED", "ERROR", "BLOCKED", "INVALID"}


def normalize_args(args: Any) -> dict[str, Any]:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as exc:
            raise ValueError("workflow args must be a JSON object") from exc
    if not isinstance(args, Mapping):
        raise ValueError("workflow args must be an object or JSON object string")
    return dict(args)


def _status(result: Any) -> str:
    if not isinstance(result, Mapping):
        return "INVALID"
    for key in ("diagnosis_status", "execution_status", "status"):
        if result.get(key):
            return str(result[key]).upper()
    return "UNKNOWN"


def _valid_result(result: Any, task_id: str, capability: str) -> bool:
    if not isinstance(result, Mapping):
        return False
    if result.get("task_id") != task_id or result.get("capability") != capability:
        return False
    return _status(result) not in FAILURE_STATUSES and _status(result) != "UNKNOWN"


def _failure(phase_name: str, results: Mapping[str, Any], error_code: str = "REQUIRED_STEP_FAILED") -> dict[str, Any]:
    return {
        "status": "FAILED",
        "failed_phase": phase_name,
        "error_code": error_code,
        "results": dict(results),
    }


ANOMALY_TERMS = ("error", "exception", "fatal", "panic", "failed", "failure", "timeout",
                 "traceback", "崩溃", "异常")


def _mapping_value(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, Mapping) else None
    return None


def _adapter_result(result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Find the project adapter payload returned by a native expert.

    Native experts return a small contract envelope.  The actual adapter JSON
    is normally in ``adapter_result``; accepting ``result`` as a compatibility
    shape keeps this workflow independent from model formatting.
    """
    for key in ("adapter_result", "result", "payload"):
        nested = _mapping_value(result.get(key))
        if nested is not None:
            return nested
    return None


def _log_entries_have_anomaly(payload: Mapping[str, Any]) -> bool:
    entries = payload.get("entries", payload.get("items", []))
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if isinstance(entry, Mapping):
            line = str(entry.get("line", entry.get("message", entry.get("source", ""))))
        else:
            line = str(entry)
        if any(term in line.casefold() for term in ANOMALY_TERMS):
            return True
    return False


def _is_anomaly(result: Mapping[str, Any], capability: str = "") -> bool:
    values = [result.get("diagnosis_status"), result.get("status"), result.get("execution_status")]
    if any(str(value).upper() in {"ANOMALY", "ANOMALY_DETECTED", "TRACE_READY"} for value in values if value):
        return True
    # A bounded log query can be PARTIAL solely because its limit was reached.
    # Inspect the returned evidence before deciding whether the conditional E06
    # replan is needed.  PARTIAL coverage remains PARTIAL in the final report.
    if capability == "logs.query.v2":
        payload = _adapter_result(result)
        return payload is not None and _log_entries_have_anomaly(payload)
    return False


def _command(request: str, service: str, target: str, since_minutes: int, limit: int, capability: str) -> str:
    if capability == "logs.query.v2":
        args = [
            "python3", "/root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py",
            "--request", request, "--service", service,
            "--target", target, "--since-minutes", str(since_minutes),
            "--limit", str(limit), "--machine-output",
        ]
    elif capability == "metrics.query.v1":
        args = [
            "python3", "/root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py",
            "--request", request, "--service", service,
            "--target", target, "--profile", "service_up",
            "--since-minutes", str(since_minutes), "--limit", str(limit),
        ]
    else:
        args = [
            "python3", "/root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py",
            "--request", request, "--service", service,
            "--target", target, "--since-minutes", str(since_minutes),
            "--limit", str(limit),
        ]
    return shlex.join(args)


async def _expert(*, agent, label: str, capability: str, task_id: str,
                  service: str, target: str, since_minutes: int, limit: int,
                  request: str) -> dict[str, Any]:
    command = _command(request, service, target, since_minutes, limit, capability)
    prompt = (
        f"You are the {label} in a read-only native AutoOps workflow.\n"
        f"Locked parent task_id: {task_id}; service: {service}; window: {since_minutes} minutes; "
        f"capability: {capability}.\n"
        "Make exactly one bash tool call using this exact project-owned command:\n\n"
        f"{command}\n\n"
        "Do not read skills or files, use other tools, change scope, or execute any write action. "
        "Return structured JSON with the locked task_id, this capability, status, and evidence_refs. "
        "For logs, status may be NO_ANOMALY, ANOMALY_DETECTED, or PARTIAL. "
        "For metrics/events, preserve the adapter result status and report missing data as PARTIAL."
    )
    result = await agent(
        prompt,
        label=label,
        schema={"type": "object", "required": ["task_id", "capability", "status", "evidence_refs"]},
        options={"timeout": 90},
    )
    return dict(result) if isinstance(result, Mapping) else {"result": result}


async def run(args: Any) -> dict[str, Any]:
    from swarmflow import agent, human, log, phase

    args = normalize_args(args)
    task_id = str(args.get("task_id") or "")
    service = str(args.get("service") or "autoops-demo")
    target = str(args.get("target") or "local")
    task = str(args.get("task") or "Diagnose the application with read-only logs and metrics")
    since_minutes = int(args.get("since_minutes", 1440))
    limit = int(args.get("limit", 20))
    require_human = bool(args.get("require_human", False))
    if not task_id:
        task_id = "autoops-ro05-" + uuid.uuid4().hex
    if (not SERVICE_PATTERN.fullmatch(service) or not SERVICE_PATTERN.fullmatch(target)
            or target != "local" or not 1 <= since_minutes <= 1440 or not 1 <= limit <= 200):
        return {"status": "INVALID", "error_code": "INVALID_WORKFLOW_SCOPE"}

    phase("parallel_evidence")
    log("Starting E05 log and E04 metric experts concurrently")
    initial_pairs = await asyncio.gather(
        _expert(agent=agent, label="log-investigator", capability="logs.query.v2",
                task_id=task_id, service=service, target=target,
                since_minutes=since_minutes, limit=limit,
                request="只读调查服务日志并判断是否有异常"),
        _expert(agent=agent, label="metrics-observer", capability="metrics.query.v1",
                task_id=task_id, service=service, target=target,
                since_minutes=since_minutes, limit=limit,
                request="只读检查服务健康指标"),
    )
    results: dict[str, Any] = {
        "log-investigator": initial_pairs[0],
        "metrics-observer": initial_pairs[1],
    }
    for label, capability in (("log-investigator", "logs.query.v2"),
                              ("metrics-observer", "metrics.query.v1")):
        if not _valid_result(results[label], task_id, capability):
            return _failure("parallel_evidence", results)

    plan_revision = 1
    replans = 0
    if _is_anomaly(results["log-investigator"], "logs.query.v2"):
        replans = 1
        plan_revision = 2
        phase("replan")
        log("E05 anomaly evidence supports one E06 history correlation replan")
        history = await _expert(
            agent=agent, label="event-investigator", capability="events.search.v1",
            task_id=task_id, service=service, target=target,
            since_minutes=since_minutes, limit=limit,
            request="只读查询服务最近发布、变更和审计事件；历史关联只能作为候选",
        )
        results["event-investigator"] = history
        if not _valid_result(history, task_id, "events.search.v1"):
            return _failure("replan", results)

    if require_human:
        phase("approval")
        approval = await human(
            "Read-only evidence collection is complete. No write action is included. Reply close to acknowledge.",
            label="ro05-readonly-approval", options={"timeout": 1800},
        )
        if str(approval).strip().lower() not in {"close", "closed", "done", "cancel", "cancelled", "取消"}:
            return {"status": "WAITING_FOR_HUMAN", "task_id": task_id, "plan_revision": plan_revision,
                    "replans": replans, "results": results}
    cancelled = require_human and str(approval).strip().lower() in {"cancel", "cancelled", "取消"}
    return {
        "status": "CANCELLED" if cancelled else "COMPLETED",
        "workflow": "ro05-parallel-observability-v1",
        "task_id": task_id,
        "plan_revision": plan_revision,
        "replans": replans,
        "budget": META["budget"],
        "phases_completed": ["parallel_evidence"] + (["replan"] if replans else []) + (["approval"] if require_human else []),
        "human_gate": "required" if require_human else "skipped_read_only",
        "results": results,
        "next_phase_blocked": ["recover", "verify"],
        "message": "Read-only evidence collection complete; no write operation was executed.",
    }
