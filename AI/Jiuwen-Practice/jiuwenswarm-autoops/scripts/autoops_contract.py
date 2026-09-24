#!/usr/bin/env python3
"""Small versioned contracts shared by AutoOps entry points.

The project intentionally keeps this dependency-free.  The MaaS model may
produce a plan, but the project validates the fields which control scope,
capability selection and lifecycle state before an adapter is invoked.
"""
from __future__ import annotations

from typing import Any
import hashlib
import json
import time

from autoops_failure_policy import RETRY_CLASSES


REQUEST_SCHEMA_VERSION = 1
PLAN_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
INTENTS = {"inspect", "diagnose", "remediate", "verify", "watch", "resume", "cancel"}
TASK_STATES = {
    "RECEIVED", "NEEDS_INPUT", "PLANNED", "RUNNING", "WAITING_APPROVAL",
    "VERIFYING", "SUCCEEDED", "PARTIAL", "BLOCKED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
    "RECONCILING",
}
DIAGNOSIS_STATES = {"confirmed", "candidate", "inconclusive", "not_applicable"}
RECOVERY_STATES = {"recovered", "not_recovered", "unverified", "not_requested"}
PLAN_STATES = {
    "PLANNED", "RUNNING", "WAITING_APPROVAL", "VERIFYING", "SUCCEEDED",
    "PARTIAL", "BLOCKED", "FAILED",
}
INVOCATION_KINDS = {"native_expert", "adapter", "project_route"}
STEP_EFFECTS = {"read", "write"}


def autoops_request(*, request_id: str, task_id: str, original_request: str,
                    goal: str, intent: str, scope: dict[str, Any],
                    requested_minutes: int, constraints: dict[str, Any] | None = None,
                    completion_criteria: dict[str, Any] | None = None,
                    field_sources: dict[str, str] | None = None) -> dict[str, Any]:
    """Build and validate the canonical request exchanged by project roles."""
    payload = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "task_id": task_id,
        "original_request": original_request,
        "goal": goal,
        "intent": intent,
        "scope": scope,
        "requested_window": {"requested_minutes": requested_minutes},
        "constraints": constraints or {},
        "completion_criteria": completion_criteria or {},
        "field_sources": field_sources or {},
    }
    return validate_request(payload)


def autoops_plan(*, task_id: str, plan_revision: int, goal: str, scope: dict[str, Any],
                 steps: list[dict[str, Any]], status: str = "PLANNED",
                 template_id: str | None = None, mode: str | None = None,
                 evidence_refs: list[dict[str, Any]] | None = None,
                 budget: dict[str, int] | None = None,
                 workflow_ref: str | None = None, workflow_asset: str | None = None,
                 published_capabilities: set[str] | None = None) -> dict[str, Any]:
    """Build and validate the canonical plan exchanged by project roles."""
    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "task_id": task_id,
        "plan_revision": plan_revision,
        "goal": goal,
        "scope": scope,
        "status": status,
        "steps": steps,
        "budget": budget or {"max_steps": 12, "max_parallel_read_steps": 3, "max_replans": 1},
        "evidence_refs": evidence_refs or [],
    }
    if template_id is not None:
        payload["template_id"] = template_id
    if mode is not None:
        payload["mode"] = mode
    if workflow_ref is not None:
        payload["workflow_ref"] = workflow_ref
    if workflow_asset is not None:
        payload["workflow_asset"] = workflow_asset
    return validate_plan(payload, published_capabilities=published_capabilities)


def stable_operation_key(task_id: str, step_id: str, capability: str, target: str,
                         parameters: dict[str, Any]) -> tuple[str, str]:
    """Keep the existing idempotency contract available to all adapters."""
    canonical = json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    summary = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    material = "\x1f".join((task_id, step_id, capability, target, summary))
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), summary


def step_result(*, task_id: str, step_id: str, capability: str, execution_status: str,
                diagnosis_status: str | None = None, verification_status: str | None = None,
                changed: bool | None = None, evidence_refs: list[dict[str, Any]] | None = None,
                external_execution_id: str | None = None, error_code: str | None = None,
                retry_class: str | None = None, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the legacy adapter result shape while keeping it versioned."""
    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": task_id,
        "step_id": step_id,
        "capability": capability,
        # ``status`` is the canonical field. Keep ``execution_status`` for
        # existing adapters and consumers during the v1 transition.
        "status": execution_status,
        "execution_status": execution_status,
        "changed": changed,
        "evidence_refs": evidence_refs or [],
        "observed_at": int(time.time()),
    }
    if diagnosis_status is not None:
        payload["diagnosis_status"] = diagnosis_status
    if verification_status is not None:
        payload["verification_status"] = verification_status
    if external_execution_id is not None:
        payload["external_execution_id"] = external_execution_id
    if error_code is not None:
        payload["error_code"] = error_code
    if retry_class is not None:
        if retry_class not in RETRY_CLASSES:
            raise ValueError("retry_class is not published")
        payload["retry_class"] = retry_class
    if detail is not None:
        payload["detail"] = detail
    return payload


def _required_string(payload: dict[str, Any], key: str) -> None:
    if not isinstance(payload.get(key), str) or not payload[key].strip():
        raise ValueError(f"{key} must be a non-empty string")


def validate_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the project-owned request boundary and return the same object."""
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    if payload.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise ValueError("unsupported request schema_version")
    for key in ("request_id", "task_id", "original_request", "goal", "intent"):
        _required_string(payload, key)
    if payload["intent"] not in INTENTS:
        raise ValueError("intent is not published")
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    if not any(scope.get(key) for key in ("application_ref", "service_ref", "target_ref", "cluster_ref", "workload_ref")):
        raise ValueError("scope must contain a published reference")
    window = payload.get("requested_window")
    if not isinstance(window, dict) or not isinstance(window.get("requested_minutes"), int):
        raise ValueError("requested_window.requested_minutes must be an integer")
    if window["requested_minutes"] < 1:
        raise ValueError("requested_window.requested_minutes must be positive")
    constraints = payload.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("constraints must be an object")
    criteria = payload.get("completion_criteria", {})
    if not isinstance(criteria, dict):
        raise ValueError("completion_criteria must be an object")
    return payload


def validate_plan(payload: dict[str, Any], *, published_capabilities: set[str] | None = None) -> dict[str, Any]:
    """Validate dependencies and execution boundaries before a plan runs."""
    if not isinstance(payload, dict):
        raise ValueError("plan must be an object")
    if payload.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported plan schema_version")
    _required_string(payload, "task_id")
    _required_string(payload, "goal")
    if not isinstance(payload.get("plan_revision"), int) or payload["plan_revision"] < 1:
        raise ValueError("plan_revision must be a positive integer")
    if payload.get("status") not in PLAN_STATES:
        raise ValueError("plan status is invalid")
    if ("workflow_ref" in payload) != ("workflow_asset" in payload):
        raise ValueError("workflow_ref and workflow_asset must be supplied together")
    if "workflow_ref" in payload:
        _required_string(payload, "workflow_ref")
        _required_string(payload, "workflow_asset")
    if not isinstance(payload.get("scope"), dict) or not payload["scope"]:
        raise ValueError("plan scope must be a non-empty object")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan steps must be a non-empty array")
    budget = payload.get("budget")
    if not isinstance(budget, dict):
        raise ValueError("plan budget must be an object")
    for key in ("max_steps", "max_parallel_read_steps", "max_replans"):
        if not isinstance(budget.get(key), int) or budget[key] < 0:
            raise ValueError(f"plan budget.{key} must be a non-negative integer")
    if budget["max_steps"] < 1 or budget["max_parallel_read_steps"] < 1:
        raise ValueError("plan step budgets must be positive")
    if len(steps) > budget["max_steps"]:
        raise ValueError("plan exceeds max_steps budget")

    step_ids: set[str] = set()
    dependencies: dict[str, list[str]] = {}
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("plan step must be an object")
        for key in ("step_id", "role", "capability", "invocation_kind"):
            _required_string(step, key)
        step_id = step["step_id"]
        if step_id in step_ids:
            raise ValueError("plan contains duplicate step_id")
        step_ids.add(step_id)
        if step["invocation_kind"] not in INVOCATION_KINDS:
            raise ValueError("step invocation_kind is invalid")
        if published_capabilities is not None and step["capability"] not in published_capabilities:
            raise ValueError("step capability is not published")
        if step.get("effect") not in STEP_EFFECTS:
            raise ValueError("step effect is invalid")
        if not isinstance(step.get("inputs"), dict):
            raise ValueError("step inputs must be an object")
        if not isinstance(step.get("depends_on"), list) or not all(
                isinstance(item, str) and item for item in step["depends_on"]):
            raise ValueError("step depends_on must be an array of non-empty strings")
        if not isinstance(step.get("when"), str) or not step["when"].strip():
            raise ValueError("step when must be a non-empty string")
        if not isinstance(step.get("required"), bool):
            raise ValueError("step required must be boolean")
        if not isinstance(step.get("expected_result"), dict):
            raise ValueError("step expected_result must be an object")
        if not isinstance(step.get("timeout_seconds"), int) or step["timeout_seconds"] < 1:
            raise ValueError("step timeout_seconds must be a positive integer")
        dependencies[step_id] = step["depends_on"]

    for step_id, parents in dependencies.items():
        if step_id in parents:
            raise ValueError("plan step cannot depend on itself")
        if any(parent not in step_ids for parent in parents):
            raise ValueError("plan dependency references an unknown step")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise ValueError("plan dependencies contain a cycle")
        if step_id in visited:
            return
        visiting.add(step_id)
        for parent in dependencies[step_id]:
            visit(parent)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in dependencies:
        visit(step_id)
    independent_read_steps = sum(
        step.get("effect") == "read" and not step.get("depends_on") for step in steps
    )
    if independent_read_steps > budget["max_parallel_read_steps"]:
        raise ValueError("plan exceeds max_parallel_read_steps budget")
    return payload


def validate_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a route result produced by the deterministic router."""
    if not isinstance(payload, dict) or payload.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported route schema_version")
    if payload.get("plan_kind") not in {"single", "multi", "none"}:
        raise ValueError("plan_kind is invalid")
    epics = payload.get("selected_epics")
    roles = payload.get("selected_roles")
    capabilities = payload.get("selected_capabilities")
    if not isinstance(epics, list) or not isinstance(roles, list) or not isinstance(capabilities, list):
        raise ValueError("selected epics, roles and capabilities must be arrays")
    if not (len(epics) == len(roles) == len(capabilities)):
        raise ValueError("selected route arrays must have equal length")
    if payload["plan_kind"] == "single" and len(epics) != 1:
        raise ValueError("single route must contain one capability")
    if payload["plan_kind"] == "multi" and len(epics) < 2:
        raise ValueError("multi route must contain at least two capabilities")
    if payload["plan_kind"] == "none" and epics:
        raise ValueError("none route cannot select capabilities")
    if payload.get("primary_epic") != (epics[0] if epics else None):
        raise ValueError("primary_epic must match the first selected epic")
    return payload


def validate_step_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject a result which could otherwise be mistaken for a successful step."""
    if not isinstance(payload, dict):
        raise ValueError("step result must be an object")
    status = payload.get("status", payload.get("execution_status"))
    if status not in {"SUCCEEDED", "FAILED", "PARTIAL", "BLOCKED", "RUNNING", "WAITING_APPROVAL", "RECONCILING"}:
        raise ValueError("step result status is invalid")
    normalized = dict(payload)
    normalized.setdefault("status", status)
    if status == "SUCCEEDED" and payload.get("error_code"):
        raise ValueError("successful step cannot contain an error_code")
    if payload.get("retry_class") is not None and payload["retry_class"] not in RETRY_CLASSES:
        raise ValueError("retry_class is not published")
    if payload.get("recovery_status") == "recovered" and status != "SUCCEEDED":
        raise ValueError("recovered requires a successful step result")
    return normalized
