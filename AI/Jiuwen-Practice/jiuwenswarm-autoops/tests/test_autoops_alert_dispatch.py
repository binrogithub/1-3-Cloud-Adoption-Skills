import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import autoops_alert_dispatch


class AlertDispatchTests(unittest.TestCase):
    def event(self, delivery_id, status="firing", service="autoops-demo"):
        return {
            "id": delivery_id,
            "source": "alertmanager",
            "status": status,
            "alertname": "ServiceDown",
            "service": service,
            "target": "test-host-01",
            "scope_id": "autoops-development",
            "starts_at": "2026-09-13T00:00:00Z",
            "labels": {"alertname": "ServiceDown", "service": service,
                        "instance": "test-host-01", "scope_id": "autoops-development"},
        }

    def write_events(self, path, events):
        path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    def test_firing_is_dispatched_once_and_resolved_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [
                self.event("delivery-1"),
                self.event("delivery-2"),
                self.event("delivery-3", status="resolved"),
            ])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                with patch.object(autoops_alert_dispatch, "run_project_manager", return_value=(0, {"status": "NO_ANOMALY"})) as pm, \
                        patch.object(autoops_alert_dispatch, "run_verifier", return_value=(0, {"verification_status": "PASSED"})) as verifier:
                    result = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox,
                    )
                self.assertEqual(result["processed"], 2)
                self.assertEqual(result["duplicates"], 0)
                self.assertEqual(result["notifications"], 2)
                self.assertEqual(pm.call_count, 1)
                notifications = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
                self.assertEqual([item["kind"] for item in notifications], ["investigation", "recovery"])
                self.assertEqual(notifications[0]["status"], "DISPATCHED")
                self.assertEqual(notifications[1]["status"], "RECOVERED")
                self.assertFalse(notifications[1]["verification_required"])
                verifier.assert_called_once()
                import sqlite3
                connection = sqlite3.connect(root / "tasks.db")
                task = connection.execute("SELECT status,payload_json FROM tasks LIMIT 1").fetchone()
                connection.close()
                self.assertEqual(task[0], "COMPLETED")
                task_payload = json.loads(task[1])
                self.assertEqual(task_payload["parent_watch_id"], "autoops-demo-watch")
                self.assertEqual(task_payload["task_id"], task_payload["incident_id"])
                with events.open("a", encoding="utf-8") as stream:
                    for event in [self.event("delivery-1"), self.event("delivery-2"), self.event("delivery-3", status="resolved")]:
                        stream.write(json.dumps(event) + "\n")
                second = autoops_alert_dispatch.run_once(
                    ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                    state, events, outbox,
                )
                self.assertEqual(second["processed"], 0)
                self.assertEqual(second["duplicates"], 3)
                self.assertEqual(len(outbox.read_text(encoding="utf-8").splitlines()), 2)

    def test_sqlite_watermark_and_action_ledger_survive_json_state_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("durable-delivery")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                with patch.object(autoops_alert_dispatch, "run_project_manager",
                                  return_value=(0, {"status": "NO_ANOMALY"})) as pm:
                    first = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox,
                    )
                    self.assertEqual(first["processed"], 1)
                    state_file = state / "dispatch-state.json"
                    state_file.unlink()
                    second = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox,
                    )
                self.assertEqual(second["processed"], 0)
                self.assertEqual(second["duplicates"], 0)
                pm.assert_called_once()
                import sqlite3
                connection = sqlite3.connect(root / "tasks.db")
                delivery = connection.execute(
                    "SELECT status FROM dispatch_deliveries WHERE delivery_id=?",
                    ("durable-delivery",),
                ).fetchone()
                action = connection.execute(
                    "SELECT status FROM dispatch_actions WHERE action='firing'",
                ).fetchone()
                watermark = connection.execute(
                    "SELECT file_offset FROM dispatch_watermarks",
                ).fetchone()
                connection.close()
                self.assertEqual(delivery[0], "DONE")
                self.assertEqual(action[0], "DONE")
                self.assertEqual(watermark[0], events.stat().st_size)

    def test_same_incident_different_deliveries_use_one_logical_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("same-incident-1"), self.event("same-incident-2")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                with patch.object(autoops_alert_dispatch, "run_project_manager",
                                  return_value=(0, {"status": "NO_ANOMALY"})) as pm:
                    result = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox,
                    )
                self.assertEqual(result["processed"], 1)
                self.assertEqual(result["duplicates"], 0)
                pm.assert_called_once()
                import sqlite3
                connection = sqlite3.connect(root / "tasks.db")
                count = connection.execute(
                    "SELECT COUNT(*) FROM dispatch_actions WHERE action='firing'",
                ).fetchone()[0]
                deliveries = connection.execute(
                    "SELECT COUNT(*) FROM dispatch_deliveries WHERE status='DONE'",
                ).fetchone()[0]
                connection.close()
                self.assertEqual(count, 1)
                self.assertEqual(deliveries, 2)

    def test_inflight_action_does_not_advance_consumer_watermark(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            event = self.event("inflight-delivery")
            self.write_events(events, [event])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                incident_id = autoops_alert_dispatch.incident_identity(
                    event, autoops_alert_dispatch.load_policy(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json"
                    )
                )[1]
                from autoops_task_store import TaskStore
                store = TaskStore(root / "tasks.db")
                store.claim_dispatch_action(incident_id, "firing", "other-delivery", lease_seconds=300)
                store.close()
                with patch.object(autoops_alert_dispatch, "run_project_manager") as pm:
                    result = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox,
                    )
                self.assertEqual(result["processed"], 0)
                pm.assert_not_called()
                persisted = json.loads((state / "dispatch-state.json").read_text(encoding="utf-8"))
                self.assertEqual(persisted["file_offset"], 0)
                store = TaskStore(root / "tasks.db")
                self.assertEqual(store.dispatch_watermark(str(events.resolve())), None)
                delivery = store.connection.execute(
                    "SELECT status FROM dispatch_deliveries WHERE delivery_id=?",
                    ("inflight-delivery",),
                ).fetchone()
                self.assertEqual(delivery[0], "PROCESSING")
                store.close()

    def test_resolved_signal_stays_waiting_when_e09_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("delivery-firing"), self.event("delivery-resolved", status="resolved")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}), \
                    patch.object(autoops_alert_dispatch, "run_project_manager", return_value=(0, {"status": "NO_ANOMALY"})), \
                    patch.object(autoops_alert_dispatch, "run_verifier", return_value=(1, {"verification_status": "FAILED", "error_code": "HEALTH_PROBE_FAILED"})):
                result = autoops_alert_dispatch.run_once(ROOT / "config" / "monitoring" / "autoops-demo-watch.json", state, events, outbox)
            self.assertEqual(result["processed"], 2)
            notifications = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(notifications[1]["status"], "ALERT_RESOLVED_PENDING_VERIFICATION")
            self.assertTrue(notifications[1]["verification_required"])

    def test_partial_investigation_is_dispatched_not_marked_as_transport_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("delivery-partial")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}), \
                    patch.object(autoops_alert_dispatch, "run_project_manager",
                                 return_value=(1, {"status": "trace_incomplete"})):
                result = autoops_alert_dispatch.run_once(
                    ROOT / "config" / "monitoring" / "autoops-demo-watch.json", state, events, outbox,
                )
            self.assertEqual(result["incidents"][0]["status"], "DISPATCHED")
            notification = json.loads(outbox.read_text(encoding="utf-8"))
            self.assertEqual(notification["status"], "DISPATCHED")

    def test_invalid_alert_scope_is_recorded_without_external_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("delivery-invalid", service="arbitrary service")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                result = autoops_alert_dispatch.run_once(
                    ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                    state, events, outbox,
                )
            self.assertEqual(result["processed"], 1)
            notification = json.loads(outbox.read_text(encoding="utf-8"))
            self.assertEqual(notification["status"], "FAILED")
            self.assertEqual(notification["result"]["status"], "INPUT_ERROR")

    def test_project_manager_inherits_the_dispatcher_interpreter(self):
        event = self.event("delivery-interpreter")
        completed = subprocess.CompletedProcess([], 0, stdout='{"status":"NO_ANOMALY"}', stderr="")
        with patch.object(autoops_alert_dispatch.subprocess, "run", return_value=completed) as run:
            code, result = autoops_alert_dispatch.run_project_manager(event)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "NO_ANOMALY")
        self.assertEqual(run.call_args.args[0][0], sys.executable)

    def test_css_event_routes_profile_to_css_project_manager(self):
        event = self.event("delivery-css")
        event.update({"source": "css", "profile_id": "production-search",
                      "cluster_id": "12345678-1234-4123-8123-123456789abc"})
        completed = subprocess.CompletedProcess([], 0, stdout='{"status":"READY"}', stderr="")
        with patch.object(autoops_alert_dispatch.subprocess, "run", return_value=completed) as run:
            code, result = autoops_alert_dispatch.run_project_manager(event)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "READY")
        command = run.call_args.args[0]
        self.assertIn("--css-profile", command)
        self.assertIn("production-search", command)
        self.assertIn("CSS", command[command.index("--request") + 1])

    def test_pause_or_stop_in_watcher_blocks_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            state.mkdir()
            (state / "state.json").write_text(json.dumps({"status": "paused"}), encoding="utf-8")
            self.write_events(events, [self.event("delivery-paused")])
            with patch.object(autoops_alert_dispatch, "run_project_manager") as pm:
                result = autoops_alert_dispatch.run_once(
                    ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                    state, events, outbox,
                )
            self.assertEqual(result["status"], "paused")
            self.assertEqual(result["processed"], 0)
            pm.assert_not_called()
            self.assertFalse(outbox.exists())

    def test_optional_preauthorization_uses_recovery_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            state = root / "state"
            outbox = root / "notifications.jsonl"
            self.write_events(events, [self.event("delivery-recovery")])
            with patch.dict(os.environ, {"AUTOOPS_STATE_DB": str(root / "tasks.db")}):
                with patch.object(autoops_alert_dispatch, "run_recovery_flow", return_value=(0, {"status": "COMPLETED"})) as recovery:
                    result = autoops_alert_dispatch.run_once(
                        ROOT / "config" / "monitoring" / "autoops-demo-watch.json",
                        state, events, outbox, "policy-v1",
                    )
            self.assertEqual(result["processed"], 1)
            recovery.assert_called_once()
            notification = json.loads(outbox.read_text(encoding="utf-8"))
            self.assertEqual(notification["status"], "RECOVERED")


if __name__ == "__main__":
    unittest.main()
