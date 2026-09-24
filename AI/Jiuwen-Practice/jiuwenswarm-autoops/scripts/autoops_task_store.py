#!/usr/bin/env python3
"""Small durable business task ledger for the single-node AutoOps MVP."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from autoops_contract import validate_plan, validate_step_result
from autoops_failure_policy import classify_failure
from autoops_runtime_config import resolve_runtime

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / ".runtime" / "autoops-state.db"
# RECONCILING is deliberately excluded: an unknown external result may still
# settle after the original execution is queried, and cancellation must be
# recorded while that reconciliation is in progress.
TERMINAL_STATES = {"SUCCEEDED", "PARTIAL", "BLOCKED", "FAILED", "CANCELLED"}


def database_path() -> Path:
    return Path(resolve_runtime(state_db=Path(os.environ["AUTOOPS_STATE_DB"]) if os.environ.get("AUTOOPS_STATE_DB") else None)["state_db"])


def lifecycle_status(payload: dict[str, Any], return_code: int = 0) -> str:
    """Map an adapter/dispatcher result to the durable task lifecycle."""
    status = str(payload.get("status", "")).upper()
    adapter = payload.get("adapter_result")
    adapter_status = str(adapter.get("status", "")).upper() if isinstance(adapter, dict) else ""
    adapter_error = str(adapter.get("error_code", "")).upper() if isinstance(adapter, dict) else ""
    reconciliation = bool(payload.get("reconciliation"))
    if isinstance(adapter, dict):
        reconciliation = reconciliation or bool(adapter.get("reconciliation"))
    # A submitted external action with an unknown outcome is not a normal
    # failure: retrying it could create a duplicate write. Keep the task
    # mutable until the original execution is queried and settled.
    if (status == "UNKNOWN" and str(payload.get("error_code", "")).upper() == "RESULT_UNKNOWN") \
            or (adapter_status == "UNKNOWN" and adapter_error == "RESULT_UNKNOWN"):
        return "RECONCILING"
    if reconciliation and (status in {"", "RUNNING", "WAITING"} or adapter_status in {"RUNNING", "WAITING"}):
        return "RECONCILING"
    if status in {"PENDING_CONFIRMATION", "WAITING_APPROVAL"}:
        return "WAITING_APPROVAL"
    if status in {"PLAN_READY", "PLANNED"}:
        return "PLANNED"
    if status in {"INPUT_ERROR", "NEEDS_INPUT"}:
        return "NEEDS_INPUT"
    if status in {"UNAVAILABLE", "UNSUPPORTED", "AUTHORIZATION_DENIED"}:
        return "BLOCKED"
    if status in {"EMPTY", "INCONCLUSIVE", "TRACE_INCOMPLETE"} \
            or adapter_status in {"EMPTY", "INCONCLUSIVE", "TRACE_INCOMPLETE"}:
        # The read completed, but the evidence cannot support a clean or
        # confirmed diagnosis. Keep the task terminal and visible as partial.
        return "PARTIAL"
    if status in {"CANCELLED"}:
        return "CANCELLED"
    if status == "CANCEL_REQUESTED":
        return "CANCEL_REQUESTED"
    if status == "PARTIAL":
        return "PARTIAL"
    if status in {"FAILED", "ERROR"} or return_code != 0:
        return "FAILED"
    verification = str(payload.get("verification_status", "")).upper()
    if verification in {"FAILED", "INCONCLUSIVE"}:
        return "PARTIAL"
    if status in {"COMPLETED", "SUCCEEDED"} or adapter_status in {"COMPLETED", "SUCCEEDED", "OK"}:
        return "SUCCEEDED"
    return "RUNNING"


class TaskStore:
    def __init__(self, path: Path | None = None):
        self.path = path or database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY,
              intent_key TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS tasks_intent_key ON tasks(intent_key);
            CREATE TABLE IF NOT EXISTS task_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              observed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dispatch_deliveries (
              delivery_id TEXT PRIMARY KEY,
              incident_id TEXT NOT NULL,
              incident_key TEXT NOT NULL,
              event_json TEXT NOT NULL,
              status TEXT NOT NULL,
              lease_until INTEGER NOT NULL,
              result_json TEXT,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS dispatch_deliveries_incident
              ON dispatch_deliveries(incident_id);
            CREATE TABLE IF NOT EXISTS dispatch_actions (
              incident_id TEXT NOT NULL,
              action TEXT NOT NULL,
              delivery_id TEXT NOT NULL,
              status TEXT NOT NULL,
              lease_until INTEGER NOT NULL,
              result_json TEXT,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              PRIMARY KEY (incident_id, action)
            );
            CREATE TABLE IF NOT EXISTS dispatch_watermarks (
              source TEXT PRIMARY KEY,
              file_offset INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            """
        )
        self.connection.commit()

    def claim_dispatch_delivery(self, delivery_id: str, incident_id: str,
                                incident_key: str, event: dict[str, Any],
                                lease_seconds: int = 300) -> dict[str, Any]:
        """Claim an Alertmanager delivery exactly once, durably.

        A lease allows a later poll to recover a process that died mid-dispatch.
        The external action has its own claim, so recovery never treats a lease
        expiry as permission to submit a second write.
        """
        now = int(time.time())
        lease_until = now + max(1, int(lease_seconds))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT status,lease_until FROM dispatch_deliveries WHERE delivery_id=?",
                (delivery_id,),
            ).fetchone()
            if row is not None:
                status = str(row[0])
                if status == "DONE":
                    self.connection.commit()
                    return {"claimed": False, "reason": "already_done", "status": status}
                if status == "PROCESSING" and int(row[1]) > now:
                    self.connection.commit()
                    return {"claimed": False, "reason": "in_flight", "status": status}
                self.connection.execute(
                    "UPDATE dispatch_deliveries SET incident_id=?, incident_key=?, event_json=?, "
                    "status='PROCESSING', lease_until=?, updated_at=? WHERE delivery_id=?",
                    (incident_id, incident_key, json.dumps(event, ensure_ascii=False, sort_keys=True),
                     lease_until, now, delivery_id),
                )
            else:
                self.connection.execute(
                    "INSERT INTO dispatch_deliveries(delivery_id,incident_id,incident_key,event_json,status,"
                    "lease_until,result_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (delivery_id, incident_id, incident_key,
                     json.dumps(event, ensure_ascii=False, sort_keys=True), "PROCESSING",
                     lease_until, None, now, now),
                )
            self.connection.commit()
            return {"claimed": True, "reason": "claimed", "status": "PROCESSING",
                    "lease_until": lease_until}
        except Exception:
            self.connection.rollback()
            raise

    def finish_dispatch_delivery(self, delivery_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark a delivery consumed only after its durable action handling ends."""
        self.connection.execute(
            "UPDATE dispatch_deliveries SET status='DONE', lease_until=0, result_json=?, updated_at=? "
            "WHERE delivery_id=?",
            (json.dumps(result or {}, ensure_ascii=False, sort_keys=True), int(time.time()), delivery_id),
        )
        self.connection.commit()

    def claim_dispatch_action(self, incident_id: str, action: str, delivery_id: str,
                              lease_seconds: int = 300) -> dict[str, Any]:
        """Claim one logical incident action, independent of delivery retries."""
        now = int(time.time())
        lease_until = now + max(1, int(lease_seconds))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT status,lease_until FROM dispatch_actions WHERE incident_id=? AND action=?",
                (incident_id, action),
            ).fetchone()
            if row is not None:
                status = str(row[0])
                if status == "DONE":
                    self.connection.commit()
                    return {"claimed": False, "reason": "already_done", "status": status}
                if status == "PROCESSING" and int(row[1]) > now:
                    self.connection.commit()
                    return {"claimed": False, "reason": "in_flight", "status": status}
                self.connection.execute(
                    "UPDATE dispatch_actions SET delivery_id=?, status='PROCESSING', lease_until=?, updated_at=? "
                    "WHERE incident_id=? AND action=?",
                    (delivery_id, lease_until, now, incident_id, action),
                )
            else:
                self.connection.execute(
                    "INSERT INTO dispatch_actions(incident_id,action,delivery_id,status,lease_until,result_json,"
                    "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (incident_id, action, delivery_id, "PROCESSING", lease_until, None, now, now),
                )
            self.connection.commit()
            return {"claimed": True, "reason": "claimed", "status": "PROCESSING",
                    "lease_until": lease_until}
        except Exception:
            self.connection.rollback()
            raise

    def finish_dispatch_action(self, incident_id: str, action: str,
                               result: dict[str, Any] | None = None) -> None:
        """Persist the result of one logical incident action."""
        self.connection.execute(
            "UPDATE dispatch_actions SET status='DONE', lease_until=0, result_json=?, updated_at=? "
            "WHERE incident_id=? AND action=?",
            (json.dumps(result or {}, ensure_ascii=False, sort_keys=True), int(time.time()), incident_id, action),
        )
        self.connection.commit()

    def set_dispatch_watermark(self, source: str, file_offset: int) -> None:
        """Persist the consumer position after a batch is safely handled."""
        self.connection.execute(
            "INSERT INTO dispatch_watermarks(source,file_offset,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(source) DO UPDATE SET file_offset=excluded.file_offset, updated_at=excluded.updated_at",
            (source, max(0, int(file_offset)), int(time.time())),
        )
        self.connection.commit()

    def dispatch_watermark(self, source: str) -> int | None:
        row = self.connection.execute(
            "SELECT file_offset FROM dispatch_watermarks WHERE source=?", (source,)
        ).fetchone()
        return None if row is None else int(row[0])

    def backup_to(self, destination: Path) -> None:
        """Create a consistent SQLite snapshot, including committed WAL data."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination, timeout=10)
        try:
            self.connection.backup(target)
            target.commit()
        finally:
            target.close()

    def upsert(self, task_id: str, intent_key: str, payload: dict[str, Any], status: str = "RECEIVED") -> dict[str, Any]:
        now = int(time.time())
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.connection.execute(
            """INSERT INTO tasks(task_id,intent_key,status,payload_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(task_id) DO UPDATE SET intent_key=excluded.intent_key,
                 payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
            (task_id, intent_key, status, encoded, now, now),
        )
        self.connection.commit()
        return self.get(task_id) or {}

    def event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO task_events(task_id,event_type,payload_json,observed_at) VALUES(?,?,?,?)",
            (task_id, event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), int(time.time())),
        )
        self.connection.commit()

    def record_plan(self, task_id: str, plan: dict[str, Any]) -> dict[str, Any] | None:
        """Persist a validated plan and its revision before any step starts."""
        validate_plan(plan)
        task = self.get(task_id)
        if task is None:
            return None
        payload = dict(task["payload"])
        current_plan = payload.get("plan")
        if isinstance(current_plan, dict):
            current_revision = int(current_plan.get("plan_revision", 0))
            requested_revision = int(plan["plan_revision"])
            if requested_revision == current_revision:
                if current_plan != plan:
                    raise ValueError("plan revision already exists with different content")
                return task
            if requested_revision != current_revision + 1:
                raise ValueError("plan revisions must increase by one")
            previous_budget = current_plan.get("budget", {})
            previous_max_replans = int(previous_budget.get("max_replans", 0))
            requested_max_replans = int(plan.get("budget", {}).get("max_replans", 0))
            if requested_max_replans > previous_max_replans:
                raise ValueError("plan replan budget cannot be expanded")
            if requested_revision - 1 > previous_max_replans:
                raise ValueError("plan exceeds max_replans budget")
        payload["plan"] = plan
        payload["plan_revision"] = plan["plan_revision"]
        self.upsert(task_id, task["intent_key"], payload, status=task["status"])
        self.set_status(task_id, plan["status"])
        self.event(task_id, "plan.created", {
            "plan_revision": plan["plan_revision"],
            "step_ids": [step["step_id"] for step in plan["steps"]],
            "status": plan["status"],
        })
        return self.get(task_id)

    def record_step_result(self, task_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Persist a canonical step result without storing raw tool output."""
        normalized = validate_step_result(result)
        task = self.get(task_id)
        if task is None:
            return None
        plan = task.get("payload", {}).get("plan", {})
        plan_steps = {step.get("step_id") for step in plan.get("steps", [])
                      if isinstance(step, dict)} if isinstance(plan, dict) else set()
        if plan_steps and normalized.get("step_id") not in plan_steps:
            raise ValueError("step result references a step outside the published plan")
        completed_steps = {
            event.get("payload", {}).get("step_id")
            for event in self.events(task_id)
            if event.get("event_type") == "step.result"
            and isinstance(event.get("payload"), dict)
        }
        if normalized.get("step_id") not in completed_steps:
            max_steps = int(plan.get("budget", {}).get("max_steps", len(plan_steps) or 0)) \
                if isinstance(plan, dict) else 0
            if max_steps and len(completed_steps) >= max_steps:
                raise ValueError("task max_steps budget is exhausted")
        summary = {key: normalized[key] for key in (
            "schema_version", "task_id", "step_id", "capability", "status",
            "execution_status", "diagnosis_status", "verification_status",
            "recovery_status", "changed", "evidence_refs", "external_execution_id",
            "error_code", "retry_class", "observed_at",
        ) if key in normalized}
        summary.setdefault("retry_class", classify_failure(
            status=normalized.get("status"), error_code=normalized.get("error_code")))
        self.event(task_id, "step.result", summary)
        return self.get(task_id)

    def record_result(self, task_id: str, payload: dict[str, Any], return_code: int = 0,
                      event_type: str = "task.result") -> dict[str, Any] | None:
        """Persist a compact result summary and its lifecycle transition."""
        status = lifecycle_status(payload, return_code)
        summary = {
            key: payload[key] for key in (
                "status", "execution_mode", "selected_epic", "selected_role",
                "selected_epics", "selected_roles", "selected_capabilities",
                "operation_id",
                "error_code", "capability", "execution_boundary", "execution_status",
                "verification_status", "recovery_status",
            ) if key in payload
        }
        adapter = payload.get("adapter_result")
        if isinstance(adapter, dict):
            summary["adapter_status"] = adapter.get("status")
            for key in ("error_code", "evidence_ref", "external_execution_id"):
                if key in adapter:
                    summary[f"adapter_{key}"] = adapter[key]
        summary["retry_class"] = payload.get("retry_class") or (
            adapter.get("retry_class") if isinstance(adapter, dict) else None
        ) or classify_failure(
            status=(adapter.get("status") if isinstance(adapter, dict) else payload.get("status")),
            error_code=(adapter.get("error_code") if isinstance(adapter, dict) else payload.get("error_code")),
        )
        self.set_status(task_id, status)
        self.event(task_id, event_type, {"lifecycle_status": status, "result": summary})
        return self.get(task_id)

    def set_status(self, task_id: str, status: str) -> dict[str, Any] | None:
        """Persist a lifecycle transition without changing the task payload."""
        current = self.connection.execute(
            "SELECT status FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if current is None:
            return None
        # A late adapter response must never reopen a hard terminal task.  A
        # RECONCILING task is intentionally mutable until its original
        # external execution has been accounted for.
        if current["status"] in TERMINAL_STATES and status != current["status"]:
            return self.get(task_id)
        if current["status"] == "RECONCILING" and status not in TERMINAL_STATES | {"RECONCILING", "CANCEL_REQUESTED"}:
            # A still-running reconciliation query must not make the task
            # look like a fresh execution after a restart.
            return self.get(task_id)
        if current["status"] == "CANCEL_REQUESTED" and status not in TERMINAL_STATES | {"CANCEL_REQUESTED"}:
            # Cancellation is an operator intent, not a transient adapter
            # result. Preserve it while the already-submitted action settles.
            return self.get(task_id)
        self.connection.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
            (status, int(time.time()), task_id),
        )
        self.connection.commit()
        return self.get(task_id)

    def request_cancel(self, task_id: str, reason: str = "operator requested cancellation") -> dict[str, Any] | None:
        """Request cancellation without touching an already submitted action."""
        task = self.get(task_id)
        if task is None:
            return None
        if task["status"] in TERMINAL_STATES:
            self.event(task_id, "task.cancel_ignored", {
                "reason": "task is already terminal", "current_status": task["status"],
            })
            return self.get(task_id)
        if task["status"] != "CANCEL_REQUESTED":
            self.set_status(task_id, "CANCEL_REQUESTED")
        self.event(task_id, "task.cancel_requested", {
            "reason": reason, "submitted_action_policy": "reconcile_existing_only",
        })
        return self.get(task_id)

    def bind_identity(self, task_id: str, *, actor_id: str | None = None,
                      session_id: str | None = None) -> dict[str, Any] | None:
        """Bind a trusted launcher identity to an existing durable task."""
        if not actor_id and not session_id:
            raise ValueError("actor_id or session_id is required")
        task = self.get(task_id)
        if task is None:
            return None
        payload = dict(task["payload"])
        for key, value in (("actor_id", actor_id), ("session_id", session_id)):
            if not value:
                continue
            current = payload.get(key)
            if current and current != value:
                raise ValueError(f"{key} is already bound to a different identity")
            payload[key] = value
        self.upsert(task_id, task["intent_key"], payload, status=task["status"])
        self.event(task_id, "task.identity_bound", {
            "actor_id": payload.get("actor_id"),
            "session_id": payload.get("session_id"),
            "source": "autoops-launcher",
        })
        return self.get(task_id)

    def progress(self, task_id: str) -> dict[str, Any] | None:
        """Build a small user-facing progress view from durable task events."""
        task = self.get(task_id)
        if task is None:
            return None
        route: dict[str, Any] = {}
        last_result: dict[str, Any] = {}
        step_results: dict[str, dict[str, Any]] = {}
        events = self.events(task_id)
        for event in events:
            payload = event.get("payload", {})
            if event.get("event_type") == "route.selected" and isinstance(payload, dict):
                # events() is newest-first; keep the newest route selection.
                if not route:
                    route = payload
            if event.get("event_type") in {"task.result", "external.execution_reconciled"} \
                    and isinstance(payload, dict):
                result = payload.get("result")
                if isinstance(result, dict) and not last_result:
                    last_result = result
            if event.get("event_type") == "step.result" and isinstance(payload, dict):
                step_id = payload.get("step_id")
                if isinstance(step_id, str) and step_id not in step_results:
                    step_results[step_id] = payload
        status = task["status"]
        phases = {
            "RECEIVED": "已接收", "PLANNED": "已生成计划", "RUNNING": "执行中",
            "WAITING_APPROVAL": "等待授权", "NEEDS_INPUT": "等待补充信息",
            "VERIFYING": "验证中", "RECONCILING": "外部执行对账中",
            "CANCEL_REQUESTED": "等待取消对账", "SUCCEEDED": "已完成",
            "PARTIAL": "部分完成", "BLOCKED": "已阻塞", "FAILED": "执行失败",
            "CANCELLED": "已取消",
        }
        next_actions = {
            "RECEIVED": "ProjectManager 生成并校验计划",
            "PLANNED": "ProjectManager 调度已发布角色",
            "RUNNING": "等待当前负责人返回结果",
            "WAITING_APPROVAL": "等待操作员提供已发布授权",
            "NEEDS_INPUT": "补充缺少的目标或范围信息",
            "RECONCILING": "查询原 external execution，不重复提交",
            "CANCEL_REQUESTED": "只对账已提交动作，不创建新步骤",
            "VERIFYING": "等待 E09 独立验证",
            "PARTIAL": "查看证据缺口或独立验证结果",
            "FAILED": "查看错误原因后重新创建任务或人工处理",
            "BLOCKED": "补齐配置、权限或外部依赖",
            "SUCCEEDED": "无需后续动作",
            "CANCELLED": "任务已取消，不自动恢复",
        }
        selected_roles = route.get("selected_roles", [])
        if not isinstance(selected_roles, list):
            selected_roles = []
        plan = task["payload"].get("plan", {})
        plan_steps = plan.get("steps", []) if isinstance(plan, dict) else []
        if not isinstance(plan_steps, list):
            plan_steps = []
        current_step = None
        for step in plan_steps:
            if not isinstance(step, dict) or not isinstance(step.get("step_id"), str):
                continue
            if step["step_id"] not in step_results:
                current_step = step
                break
        if current_step is None and step_results:
            latest_step_id = next(iter(step_results))
            current_step = next((step for step in plan_steps
                                 if isinstance(step, dict) and step.get("step_id") == latest_step_id), None)
        owner = current_step.get("role") if isinstance(current_step, dict) else (
            last_result.get("selected_role") or (selected_roles[0] if selected_roles else None))
        if status in TERMINAL_STATES:
            owner = "ProjectManager（汇总）"
        completed_steps = [step.get("step_id") for step in plan_steps
                           if isinstance(step, dict) and step.get("step_id") in step_results]
        waiting_for = next_actions.get(status)
        if status == "RUNNING" and isinstance(current_step, dict):
            waiting_for = f"等待 {current_step.get('role', '当前负责人')} 返回 {current_step.get('capability', '步骤')} 结果"
        elif status == "WAITING_APPROVAL" and isinstance(current_step, dict):
            waiting_for = f"等待授权后由 {current_step.get('role', '执行角色')} 执行"
        step_views = []
        for step in plan_steps:
            if not isinstance(step, dict) or not isinstance(step.get("step_id"), str):
                continue
            step_id = step["step_id"]
            step_result = step_results.get(step_id, {})
            view = {
                key: step[key] for key in ("step_id", "role", "capability", "effect", "depends_on")
                if key in step
            }
            view["status"] = step_result.get("status", "PENDING")
            view["execution_status"] = step_result.get("execution_status", "PENDING")
            view["evidence_refs"] = step_result.get("evidence_refs", [])
            step_views.append(view)
        last_event = events[-1] if events else None
        snapshot_at = int(time.time())
        last_activity = None
        if isinstance(last_event, dict):
            observed_at = last_event.get("observed_at")
            if isinstance(observed_at, int):
                last_activity = {
                    "event_type": last_event.get("event_type"),
                    "observed_at": observed_at,
                    "age_seconds": max(0, snapshot_at - observed_at),
                }
        if status in TERMINAL_STATES:
            activity_state = "complete"
        elif last_activity is None or last_activity["age_seconds"] > 30:
            activity_state = "waiting"
        else:
            activity_state = "active"
        payload = task.get("payload", {})
        business_name = (payload.get("application") or payload.get("service")
                         or payload.get("target") or "未命名运维任务")
        return {
            "task_id": task_id,
            "status": status,
            "phase": phases.get(status, status),
            "business_name": business_name,
            "owner": owner or "ProjectManager",
            "roles": selected_roles,
            "selected_capabilities": route.get("selected_capabilities", []),
            "current_step": ({key: current_step[key] for key in
                               ("step_id", "role", "capability", "effect", "depends_on")
                               if key in current_step} if isinstance(current_step, dict) else None),
            "steps": step_views,
            "completed_steps": completed_steps,
            "waiting_for": waiting_for,
            "activity_state": activity_state,
            "last_activity": last_activity,
            "snapshot_at": snapshot_at,
            "operation_id": task["payload"].get("operation_id"),
            "updated_at": task["updated_at"],
            "budget": self.budget_status(task_id),
        }

    def budget_status(self, task_id: str) -> dict[str, Any] | None:
        """Report the durable plan budget without starting or stopping work."""
        task = self.get(task_id)
        if task is None:
            return None
        plan = task["payload"].get("plan")
        if not isinstance(plan, dict):
            return {"status": "NOT_PLANNED", "can_continue": False}
        budget = plan.get("budget", {})
        step_ids = {
            event.get("payload", {}).get("step_id")
            for event in self.events(task_id)
            if event.get("event_type") == "step.result"
            and isinstance(event.get("payload"), dict)
        }
        plan_events = [event for event in self.events(task_id)
                       if event.get("event_type") == "plan.created"]
        steps_used = len({item for item in step_ids if item})
        max_steps = int(budget.get("max_steps", 0))
        max_replans = int(budget.get("max_replans", 0))
        replans_used = max(0, len(plan_events) - 1)
        exhausted = []
        if max_steps and steps_used >= max_steps:
            exhausted.append("max_steps")
        if replans_used >= max_replans and task["status"] in {"FAILED", "PARTIAL"}:
            exhausted.append("max_replans")
        return {
            "status": "EXHAUSTED" if exhausted else "AVAILABLE",
            "can_continue": not exhausted and task["status"] not in TERMINAL_STATES,
            "steps_used": steps_used,
            "max_steps": max_steps,
            "replans_used": replans_used,
            "max_replans": max_replans,
            "exhausted_by": exhausted,
        }

    def events(self, task_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event_id,event_type,payload_json,observed_at FROM task_events "
            "WHERE task_id=? ORDER BY event_id DESC LIMIT ?", (task_id, limit)
        ).fetchall()
        return [{"event_id": row["event_id"], "event_type": row["event_type"],
                 "payload": json.loads(row["payload_json"]), "observed_at": row["observed_at"]}
                for row in reversed(rows)]

    def get(self, task_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        return {"task_id": row["task_id"], "intent_key": row["intent_key"], "status": row["status"],
                "payload": payload, "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def find_by_identity(self, *, actor_id: str | None = None,
                         session_id: str | None = None) -> list[dict[str, Any]]:
        """Find durable tasks owned by a trusted actor/session pair."""
        if not actor_id and not session_id:
            return []
        rows = self.connection.execute(
            "SELECT * FROM tasks ORDER BY updated_at DESC, task_id DESC"
        ).fetchall()
        matches = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                continue
            if actor_id and payload.get("actor_id") != actor_id:
                continue
            if session_id and payload.get("session_id") != session_id:
                continue
            matches.append({"task_id": row["task_id"], "intent_key": row["intent_key"],
                            "status": row["status"], "payload": payload,
                            "created_at": row["created_at"], "updated_at": row["updated_at"]})
        return matches

    def close(self) -> None:
        self.connection.close()
