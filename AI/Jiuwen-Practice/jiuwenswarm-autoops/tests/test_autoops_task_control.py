import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "autoops-task-control.py"
RECONCILE = ROOT / "scripts" / "autoops-task-reconcile.py"
SESSION_BIND = ROOT / "scripts" / "autoops-session-bind.py"


class AutoOpsTaskControlTests(unittest.TestCase):
    def invoke(self, database: Path, *args: str):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state-db", str(database), *args],
            text=True, capture_output=True, check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def create_task(self, database: Path, status: str = "RUNNING"):
        sys.path.insert(0, str(ROOT / "scripts"))
        from autoops_task_store import TaskStore
        store = TaskStore(database)
        store.upsert("task-1", "intent-1", {"operation_id": "op-1"}, status=status)
        store.close()

    def test_resume_reuses_task_and_records_audit_event(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database)
            code, payload = self.invoke(database, "--action", "resume", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "RESUME_READY")
            self.assertEqual(payload["task"]["task_id"], "task-1")
            self.assertEqual(payload["task"]["payload"]["operation_id"], "op-1")
            self.assertEqual(payload["next_action"], "continue_existing_plan")
            _, status = self.invoke(database, "--action", "status", "--task-id", "task-1")
            self.assertEqual(status["events"][-1]["event_type"], "task.resume_requested")

    def test_progress_reports_owner_phase_and_waiting_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database, "WAITING_APPROVAL")
            from autoops_task_store import TaskStore
            store = TaskStore(database)
            store.event("task-1", "route.selected", {
                "selected_roles": ["ansible-operator", "runbook-operator"],
                "selected_capabilities": ["host.ensure_service.v1", "runbook.execute"],
            })
            store.close()
            code, payload = self.invoke(database, "--action", "progress", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "PROGRESS")
            self.assertEqual(payload["progress"]["phase"], "等待授权")
            self.assertEqual(payload["progress"]["owner"], "ansible-operator")
            self.assertIn("授权", payload["progress"]["waiting_for"])

    def test_budget_action_is_read_only_and_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database, "RUNNING")
            code, payload = self.invoke(database, "--action", "budget", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "BUDGET")
            self.assertEqual(payload["budget"]["status"], "NOT_PLANNED")

    def test_cancel_stops_new_steps_and_is_not_a_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database)
            code, payload = self.invoke(database, "--action", "cancel", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "CANCEL_REQUESTED")
            self.assertEqual(payload["next_action"], "reconcile_existing_action_only")
            code, payload = self.invoke(database, "--action", "resume", "--task-id", "task-1")
            self.assertEqual(code, 1)
            self.assertEqual(payload["error_code"], "CANCEL_PENDING")

    def test_missing_task_and_terminal_resume_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            code, payload = self.invoke(database, "--action", "resume", "--task-id", "missing")
            self.assertEqual(code, 1)
            self.assertEqual(payload["status"], "NOT_FOUND")
            self.create_task(database, "RECONCILING")
            code, payload = self.invoke(database, "--action", "resume", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "RECONCILE_REQUIRED")
            self.assertEqual(payload["next_action"], "query_existing_execution")

    def test_reconciling_task_can_be_cancelled_without_replaying_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database, "RECONCILING")
            code, payload = self.invoke(database, "--action", "cancel", "--task-id", "task-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "CANCEL_REQUESTED")
            self.assertEqual(payload["next_action"], "reconcile_existing_action_only")
            code, payload = self.invoke(database, "--action", "resume", "--task-id", "task-1")
            self.assertEqual(code, 1)
            self.assertEqual(payload["error_code"], "CANCEL_PENDING")

    def test_reconcile_command_requires_persisted_external_context(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            self.create_task(database, "RECONCILING")
            result = subprocess.run(
                [sys.executable, str(RECONCILE), "--state-db", str(database), "--task-id", "task-1"],
                text=True, capture_output=True, check=False,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["error_code"], "RECONCILE_CONTEXT_MISSING")

    def test_resume_resolves_unique_actor_session_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            from autoops_task_store import TaskStore
            store = TaskStore(database)
            store.upsert("task-session", "intent", {
                "request": "inspect logs", "actor_id": "robin", "session_id": "tui-1",
                "operation_id": "op-1",
            }, status="RUNNING")
            store.close()
            code, payload = self.invoke(database, "--action", "resume",
                                         "--actor-id", "robin", "--session-id", "tui-1")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "RESUME_READY")
            self.assertEqual(payload["task"]["task_id"], "task-session")

    def test_resume_rejects_ambiguous_actor_session_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.db"
            from autoops_task_store import TaskStore
            store = TaskStore(database)
            for task_id in ("task-a", "task-b"):
                store.upsert(task_id, "intent", {
                    "request": task_id, "actor_id": "robin", "session_id": "tui-1",
                }, status="RUNNING")
            store.close()
            code, payload = self.invoke(database, "--action", "resume",
                                         "--actor-id", "robin", "--session-id", "tui-1")
            self.assertEqual(code, 1)
            self.assertEqual(payload["error_code"], "TASK_IDENTITY_AMBIGUOUS")
            self.assertEqual({item["task_id"] for item in payload["candidates"]}, {"task-a", "task-b"})

    def test_session_bind_reads_task_from_history_and_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "state.db"
            history = root / "history.jsonl"
            task_id = "pm-0123456789abcdef0123456789abcdef"
            self.create_task(database, "RUNNING")
            # Use the expected generated task ID for this isolated fixture.
            from autoops_task_store import TaskStore
            store = TaskStore(database)
            store.connection.execute("UPDATE tasks SET task_id=? WHERE task_id=?", (task_id, "task-1"))
            store.connection.commit()
            store.close()
            history.write_text(json.dumps({"content": f"created {task_id}"}) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SESSION_BIND), "--history", str(history),
                 "--state-db", str(database), "--session-id", "tui-session",
                 "--actor-id", "tui"], text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "BOUND")
            store = TaskStore(database)
            self.assertEqual(store.get(task_id)["payload"]["session_id"], "tui-session")
            store.close()


if __name__ == "__main__":
    unittest.main()
