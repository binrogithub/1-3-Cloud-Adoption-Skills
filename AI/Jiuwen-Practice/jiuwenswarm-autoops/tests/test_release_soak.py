import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

BACKUP_SPEC = importlib.util.spec_from_file_location(
    "autoops_runtime_backup_for_soak", ROOT / "scripts" / "autoops-runtime-backup.py"
)
backup = importlib.util.module_from_spec(BACKUP_SPEC)
BACKUP_SPEC.loader.exec_module(backup)
from autoops_task_store import TaskStore


class ReleaseSoakTests(unittest.TestCase):
    def make_instance(self, root: Path):
        install, config, state, systemd = (root / name for name in ("install", "config", "state", "systemd"))
        for path in (install, config, state, systemd):
            path.mkdir()
        (install / "autoops-install-manifest.json").write_text(
            '{"schema_version":2,"instance":{"instance_id":"soak"}}\n', encoding="utf-8"
        )
        (config / "service-profile.json").write_text('{"profile_id":"soak"}\n', encoding="utf-8")
        (systemd / "jiuwenswarm-autoops-watch.service").write_text(
            "[Service]\nExecStart=/opt/Jiuwenswarm_AutoOps/scripts/autoops_watch.py\n", encoding="utf-8"
        )
        return install, config, state, systemd

    def test_soak_plan_has_distinct_incidents_and_recovery(self):
        plan = json.loads((ROOT / "config/acceptance/release-soak-v1.json").read_text(encoding="utf-8"))
        incidents = plan["events"]
        self.assertEqual(len(incidents), 10)
        self.assertEqual(len({item["incident_id"] for item in incidents}), 10)
        self.assertTrue(any(item["truth"] == "controlled-recovery" for item in incidents))
        self.assertGreaterEqual(plan["minimum_duration_seconds"], 86400)
        self.assertIn("cleanup", plan)

    def test_restore_keeps_unconfirmed_delivery_and_external_execution_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install, config, state, systemd = self.make_instance(root)
            database = state / "autoops-state.db"
            store = TaskStore(database)
            store.upsert("task-pending", "incident-pending", {
                "operation_id": "op-pending", "external_execution_id": "rundeck-9001",
            }, status="RECONCILING")
            store.event("task-pending", "external.execution_unknown", {
                "operation_id": "op-pending", "external_execution_id": "rundeck-9001",
                "reconcile_policy": "query_existing_execution_only",
            })
            claimed_delivery = store.claim_dispatch_delivery(
                "delivery-pending", "incident-pending", "incident-key-pending", {"status": "firing"}
            )
            claimed_action = store.claim_dispatch_action("incident-pending", "firing", "delivery-pending")
            self.assertTrue(claimed_delivery["claimed"])
            self.assertTrue(claimed_action["claimed"])
            store.claim_dispatch_delivery("delivery-done", "incident-done", "incident-key-done", {"status": "resolved"})
            store.finish_dispatch_delivery("delivery-done", {"status": "DONE"})
            store.claim_dispatch_action("incident-done", "resolved", "delivery-done")
            store.finish_dispatch_action("incident-done", "resolved", {"status": "DONE"})
            store.set_dispatch_watermark("events.jsonl", 1234)
            store.close()

            backup_dir = root / "backup"
            backup.create_backup(output=backup_dir, install_root=install, config_root=config,
                                 state_root=state, systemd_root=systemd)
            restored = backup.restore_backup(backup=backup_dir, assume_stopped=True, dry_run=False)
            self.assertFalse(restored["external_actions_replayed"])

            recovered = TaskStore(database)
            task = recovered.get("task-pending")
            self.assertEqual(task["status"], "RECONCILING")
            self.assertIn("rundeck-9001", json.dumps(task, ensure_ascii=False))
            pending_delivery = recovered.connection.execute(
                "SELECT status FROM dispatch_deliveries WHERE delivery_id='delivery-pending'"
            ).fetchone()
            pending_action = recovered.connection.execute(
                "SELECT status FROM dispatch_actions WHERE incident_id='incident-pending' AND action='firing'"
            ).fetchone()
            done_action = recovered.connection.execute(
                "SELECT status FROM dispatch_actions WHERE incident_id='incident-done' AND action='resolved'"
            ).fetchone()
            watermark = recovered.dispatch_watermark("events.jsonl")
            recovered.close()
            self.assertEqual(pending_delivery[0], "PROCESSING")
            self.assertEqual(pending_action[0], "PROCESSING")
            self.assertEqual(done_action[0], "DONE")
            self.assertEqual(watermark, 1234)

    def test_restore_requires_stopped_writers_and_dry_run_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install, config, state, systemd = self.make_instance(root)
            backup_dir = root / "backup"
            backup.create_backup(output=backup_dir, install_root=install, config_root=config,
                                 state_root=state, systemd_root=systemd)
            result = backup.restore_backup(backup=backup_dir, assume_stopped=False, dry_run=True)
            self.assertEqual(result["status"], "DRY_RUN")
            with self.assertRaises(ValueError):
                backup.restore_backup(backup=backup_dir, assume_stopped=False, dry_run=False)


if __name__ == "__main__":
    unittest.main()
