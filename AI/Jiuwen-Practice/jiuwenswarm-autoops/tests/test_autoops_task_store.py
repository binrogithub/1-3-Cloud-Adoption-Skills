import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from autoops_task_store import TaskStore, lifecycle_status

STATUS = Path(__file__).resolve().parents[1] / "scripts" / "autoops-task-status.py"


class AutoOpsTaskStoreTests(unittest.TestCase):
    def test_plan_and_step_result_are_persisted_as_structured_events(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {"request": "检查"})
            plan = {
                "schema_version": 1, "task_id": "task-1", "plan_revision": 1,
                "goal": "检查主机", "scope": {"target_ref": "local"}, "status": "PLANNED",
                "budget": {"max_steps": 12, "max_parallel_read_steps": 3, "max_replans": 1},
                "steps": [{"step_id": "inspect", "role": "runbook-operator",
                            "capability": "host.inspect.v1", "invocation_kind": "project_route",
                            "effect": "read", "inputs": {"target": "local"}, "depends_on": [],
                            "when": "always", "required": True,
                            "expected_result": {"status": "SUCCEEDED"}, "timeout_seconds": 300}],
            }
            record = store.record_plan("task-1", plan)
            self.assertEqual(record["payload"]["plan_revision"], 1)
            store.record_step_result("task-1", {
                "schema_version": 1, "task_id": "task-1", "step_id": "inspect",
                "capability": "host.inspect.v1", "execution_status": "SUCCEEDED",
                "evidence_refs": [{"ref": "evidence-1"}], "changed": False,
            })
            events = store.events("task-1")
            self.assertEqual([event["event_type"] for event in events], ["plan.created", "step.result"])
            self.assertEqual(events[-1]["payload"]["status"], "SUCCEEDED")
            self.assertEqual(events[-1]["payload"]["retry_class"], "none")
            store.close()

    def test_plan_replanning_is_bounded_and_same_revision_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {})

            def make_plan(revision, max_replans=1):
                return {
                    "schema_version": 1, "task_id": "task-1", "plan_revision": revision,
                    "goal": "检查主机", "scope": {"target_ref": "local"}, "status": "PLANNED",
                    "budget": {"max_steps": 2, "max_parallel_read_steps": 1,
                               "max_replans": max_replans},
                    "steps": [{"step_id": "inspect", "role": "runbook-operator",
                                "capability": "host.inspect.v1", "invocation_kind": "project_route",
                                "effect": "read", "inputs": {"target": "local"}, "depends_on": [],
                                "when": "always", "required": True,
                                "expected_result": {"status": "SUCCEEDED"}, "timeout_seconds": 300}],
                }

            first = make_plan(1)
            store.record_plan("task-1", first)
            store.record_plan("task-1", first)
            second = make_plan(2)
            store.record_plan("task-1", second)
            with self.assertRaisesRegex(ValueError, "max_replans"):
                store.record_plan("task-1", make_plan(3))
            with self.assertRaisesRegex(ValueError, "expanded"):
                store.record_plan("task-1", make_plan(3, max_replans=2))
            self.assertEqual(store.get("task-1")["payload"]["plan_revision"], 2)
            self.assertEqual([event["event_type"] for event in store.events("task-1")],
                             ["plan.created", "plan.created"])
            store.close()

    def test_upsert_and_event_are_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            first = TaskStore(path)
            first.upsert("task-1", "intent-1", {"service": "orders"})
            first.event("task-1", "route.selected", {"role": "log-investigator"})
            first.close()

            second = TaskStore(path)
            record = second.get("task-1")
            self.assertEqual(record["status"], "RECEIVED")
            self.assertEqual(record["payload"]["service"], "orders")
            event_count = second.connection.execute(
                "SELECT count(*) FROM task_events WHERE task_id=?", ("task-1",)
            ).fetchone()[0]
            self.assertEqual(event_count, 1)
            second.close()

    def test_upsert_does_not_create_duplicate_task(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {"value": 1})
            store.upsert("task-1", "intent-1", {"value": 2})
            self.assertEqual(store.connection.execute("SELECT count(*) FROM tasks").fetchone()[0], 1)
            self.assertEqual(store.get("task-1")["payload"]["value"], 2)
            store.close()

    def test_terminal_task_cannot_be_reopened_by_late_result(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {})
            store.set_status("task-1", "SUCCEEDED")
            store.set_status("task-1", "RUNNING")
            self.assertEqual(store.get("task-1")["status"], "SUCCEEDED")
            store.close()

    def test_unknown_external_result_enters_reconciliation(self):
        self.assertEqual(lifecycle_status({
            "status": "UNKNOWN", "error_code": "RESULT_UNKNOWN",
        }, 1), "RECONCILING")

    def test_reconciliation_does_not_reopen_while_external_action_is_running(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {}, status="RECONCILING")
            self.assertEqual(store.set_status("task-1", "RUNNING")["status"], "RECONCILING")
            self.assertEqual(lifecycle_status({
                "status": "RUNNING", "reconciliation": True,
            }), "RECONCILING")
            self.assertEqual(store.set_status("task-1", "SUCCEEDED")["status"], "SUCCEEDED")
            store.close()

    def test_cancel_request_survives_reconciliation_until_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {}, status="RECONCILING")
            store.request_cancel("task-1", "operator stopped the task")
            pending = store.record_result("task-1", {
                "status": "RUNNING", "reconciliation": True,
                "adapter_result": {"status": "RUNNING", "reconciliation": True},
            })
            self.assertEqual(pending["status"], "CANCEL_REQUESTED")
            settled = store.record_result("task-1", {
                "status": "SUCCEEDED", "execution_status": "SUCCEEDED",
                "adapter_result": {"status": "SUCCEEDED", "external_execution_id": "42"},
            })
            self.assertEqual(settled["status"], "SUCCEEDED")
            store.close()
        self.assertEqual(lifecycle_status({
            "adapter_result": {"status": "UNKNOWN", "error_code": "RESULT_UNKNOWN"},
        }, 1), "RECONCILING")

    def test_restarted_store_preserves_reconciliation_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            first = TaskStore(path)
            first.upsert("task-1", "operation-1", {
                "request": "恢复服务", "actor_id": "tui", "session_id": "s-1",
                "operation_id": "operation-1",
            })
            first.event("task-1", "route.selected", {
                "selected_roles": ["ansible-operator", "runbook-operator"],
            })
            first.set_status("task-1", "RECONCILING")
            first.event("task-1", "external.execution_unknown", {
                "operation_id": "operation-1", "external_execution_id": "42",
                "reconcile_policy": "query_existing_execution_only",
            })
            first.close()

            second = TaskStore(path)
            # Re-entry after a backend restart must not reset the durable
            # lifecycle while rebuilding the request context.
            second.upsert("task-1", "operation-1", {"request": "恢复服务"}, status="RECEIVED")
            self.assertEqual(second.get("task-1")["status"], "RECONCILING")
            progress = second.progress("task-1")
            self.assertEqual(progress["status"], "RECONCILING")
            self.assertEqual(progress["waiting_for"], "查询原 external execution，不重复提交")
            self.assertEqual(progress["budget"]["status"], "NOT_PLANNED")
            self.assertEqual(second.events("task-1")[-1]["event_type"], "external.execution_unknown")
            second.close()

    def test_budget_status_reports_step_usage_and_stops_after_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {})
            plan = {
                "schema_version": 1, "task_id": "task-1", "plan_revision": 1,
                "goal": "检查", "scope": {"target_ref": "local"}, "status": "PLANNED",
                "budget": {"max_steps": 1, "max_parallel_read_steps": 1, "max_replans": 1},
                "steps": [{"step_id": "inspect", "role": "runbook-operator",
                            "capability": "host.inspect.v1", "invocation_kind": "project_route",
                            "effect": "read", "inputs": {}, "depends_on": [], "when": "always",
                            "required": True, "expected_result": {}, "timeout_seconds": 30}],
            }
            store.record_plan("task-1", plan)
            self.assertEqual(store.budget_status("task-1")["status"], "AVAILABLE")
            store.record_step_result("task-1", {
                "task_id": "task-1", "step_id": "inspect", "capability": "host.inspect.v1",
                "status": "SUCCEEDED", "execution_status": "SUCCEEDED", "changed": False,
            })
            budget = store.budget_status("task-1")
            self.assertEqual(budget["status"], "EXHAUSTED")
            self.assertEqual(budget["exhausted_by"], ["max_steps"])
            with self.assertRaisesRegex(ValueError, "outside the published plan"):
                store.record_step_result("task-1", {
                    "task_id": "task-1", "step_id": "other", "capability": "host.inspect.v1",
                    "status": "SUCCEEDED", "execution_status": "SUCCEEDED", "changed": False,
                })
            store.close()

    def test_progress_uses_current_plan_step_as_owner_and_latest_result(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {})
            plan = {
                "schema_version": 1, "task_id": "task-1", "plan_revision": 1,
                "goal": "诊断并验证", "scope": {"target_ref": "local"}, "status": "RUNNING",
                "budget": {"max_steps": 2, "max_parallel_read_steps": 1, "max_replans": 1},
                "steps": [
                    {"step_id": "logs", "role": "log-investigator", "capability": "logs.query.v2",
                     "invocation_kind": "project_route", "effect": "read", "inputs": {},
                     "depends_on": [], "when": "always", "required": True,
                     "expected_result": {}, "timeout_seconds": 30},
                    {"step_id": "verify", "role": "recovery-verifier", "capability": "recovery.verify.v1",
                     "invocation_kind": "project_route", "effect": "read", "inputs": {},
                     "depends_on": ["logs"], "when": "always", "required": True,
                     "expected_result": {}, "timeout_seconds": 30},
                ],
            }
            store.record_plan("task-1", plan)
            store.event("task-1", "route.selected", {
                "selected_roles": ["log-investigator", "recovery-verifier"],
                "selected_capabilities": ["logs.query.v2", "recovery.verify.v1"],
            })
            store.record_step_result("task-1", {
                "task_id": "task-1", "step_id": "logs", "capability": "logs.query.v2",
                "status": "SUCCEEDED", "execution_status": "SUCCEEDED", "changed": False,
            })
            store.set_status("task-1", "RUNNING")
            progress = store.progress("task-1")
            self.assertEqual(progress["owner"], "recovery-verifier")
            self.assertEqual(progress["current_step"]["step_id"], "verify")
            self.assertEqual(progress["completed_steps"], ["logs"])
            self.assertIn("recovery.verify.v1", progress["waiting_for"])
            self.assertEqual(progress["business_name"], "未命名运维任务")
            self.assertEqual([step["status"] for step in progress["steps"]], ["SUCCEEDED", "PENDING"])
            self.assertEqual(progress["steps"][0]["evidence_refs"], [])
            self.assertIn(progress["activity_state"], {"active", "waiting"})
            self.assertIsInstance(progress["snapshot_at"], int)
            store.close()

    def test_concurrent_status_updates_keep_sqlite_ledger_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            store = TaskStore(path)
            store.upsert("task-1", "intent-1", {})
            store.close()
            barrier = threading.Barrier(2)
            errors = []

            def update(status):
                try:
                    current = TaskStore(path)
                    barrier.wait(timeout=5)
                    current.set_status("task-1", status)
                    current.close()
                except Exception as exc:  # pragma: no cover - diagnostic assertion below
                    errors.append(exc)

            first = threading.Thread(target=update, args=("RUNNING",))
            second = threading.Thread(target=update, args=("PARTIAL",))
            first.start()
            second.start()
            first.join(timeout=10)
            second.join(timeout=10)
            self.assertFalse(errors)
            final = TaskStore(path)
            self.assertIn(final.get("task-1")["status"], {"RUNNING", "PARTIAL"})
            final.close()

    def test_cancel_request_is_idempotent_and_does_not_reopen_terminal_task(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {}, status="RUNNING")
            self.assertEqual(store.request_cancel("task-1")["status"], "CANCEL_REQUESTED")
            self.assertEqual(store.request_cancel("task-1")["status"], "CANCEL_REQUESTED")
            store.set_status("task-1", "SUCCEEDED")
            self.assertEqual(store.get("task-1")["status"], "SUCCEEDED")
            store.close()

    def test_identity_binding_survives_store_reopen_and_rejects_rebinding(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            store = TaskStore(database)
            store.upsert("task-1", "intent-1", {"operation_id": "op-1"}, status="RUNNING")
            bound = store.bind_identity("task-1", actor_id="tui", session_id="session-1")
            self.assertEqual(bound["payload"]["session_id"], "session-1")
            store.close()
            reopened = TaskStore(database)
            matches = reopened.find_by_identity(actor_id="tui", session_id="session-1")
            self.assertEqual([item["task_id"] for item in matches], ["task-1"])
            with self.assertRaisesRegex(ValueError, "different identity"):
                reopened.bind_identity("task-1", actor_id="tui", session_id="session-2")
            self.assertEqual(reopened.events("task-1")[-1]["event_type"], "task.identity_bound")
            reopened.close()

    def test_status_transition_and_ordered_events_are_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {})
            store.event("task-1", "started", {"phase": 1})
            store.set_status("task-1", "INVESTIGATING")
            store.event("task-1", "finished", {"phase": 2})
            self.assertEqual(store.get("task-1")["status"], "INVESTIGATING")
            self.assertEqual([event["event_type"] for event in store.events("task-1")], ["started", "finished"])
            store.close()

    def test_status_cli_returns_persisted_task_and_events(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            store = TaskStore(database)
            store.upsert("task-1", "intent-1", {"service": "orders"})
            store.set_status("task-1", "COMPLETED")
            store.event("task-1", "completed", {"source": "alert-dispatch"})
            store.close()
            result = subprocess.run(
                [sys.executable, str(STATUS), "--task-id", "task-1"],
                text=True, capture_output=True,
                env=os.environ | {"AUTOOPS_STATE_DB": str(database)}, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "FOUND")
            self.assertEqual(payload["task"]["status"], "COMPLETED")
            self.assertEqual(payload["events"][0]["event_type"], "completed")

    def test_record_result_persists_compact_terminal_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "state.db")
            store.upsert("task-1", "intent-1", {"service": "orders"})
            store.record_result("task-1", {
                "status": "PLAN_READY", "execution_mode": "plan",
                "selected_epics": ["E05", "E04"],
                "adapter_result": {"status": "ok", "evidence_ref": "evidence-1",
                                   "entries": ["must not be stored"]},
            })
            self.assertEqual(store.get("task-1")["status"], "PLANNED")
            result = store.events("task-1")[-1]["payload"]["result"]
            self.assertEqual(result["selected_epics"], ["E05", "E04"])
            self.assertEqual(result["adapter_evidence_ref"], "evidence-1")
            self.assertNotIn("entries", result)
            store.close()

    def test_lifecycle_result_does_not_call_failed_adapter_success(self):
        self.assertEqual(lifecycle_status({"adapter_result": {"status": "COMPLETED"}}, 1), "FAILED")
        self.assertEqual(lifecycle_status({"status": "PENDING_CONFIRMATION"}), "WAITING_APPROVAL")
        self.assertEqual(lifecycle_status({"status": "UNAVAILABLE"}), "BLOCKED")
        self.assertEqual(lifecycle_status({"status": "PARTIAL"}, 1), "PARTIAL")
        self.assertEqual(lifecycle_status({"adapter_result": {"status": "empty"}}), "PARTIAL")
        self.assertEqual(lifecycle_status({"status": "trace_incomplete"}), "PARTIAL")


if __name__ == "__main__":
    unittest.main()
