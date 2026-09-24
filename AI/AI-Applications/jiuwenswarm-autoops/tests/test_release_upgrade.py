import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "scripts" / "autoops-runtime-backup.py"
import sys

sys.path.insert(0, str(ROOT / "scripts"))

SPEC = importlib.util.spec_from_file_location("autoops_runtime_backup", BACKUP)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)
from autoops_task_store import TaskStore


class ReleaseUpgradeTests(unittest.TestCase):
    def make_instance(self, root: Path) -> tuple[Path, Path, Path, Path]:
        install = root / "install"
        config = root / "etc"
        state = root / "state"
        systemd = root / "systemd"
        for path in (install, config, state, systemd):
            path.mkdir(parents=True)
        (install / "autoops-install-manifest.json").write_text(
            '{"schema_version":2,"instance":{"instance_id":"test"}}\n', encoding="utf-8")
        (config / "service-profile.json").write_text(
            '{"profile_id":"demo","credentials":"customer-secret"}\n', encoding="utf-8")
        (systemd / "jiuwenswarm-autoops-watch.service").write_text(
            "[Service]\nExecStart=/opt/Jiuwenswarm_AutoOps/scripts/autoops_watch.py\n", encoding="utf-8")
        return install, config, state, systemd

    def test_sqlite_backup_preserves_execution_id_and_does_not_copy_wal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            destination = root / "snapshot.db"
            store = TaskStore(source)
            store.upsert("task-1", "incident-1", {
                "external_execution_id": "rundeck-42", "operation_id": "op-42",
            })
            store.event("task-1", "action.submitted", {"external_execution_id": "rundeck-42"})
            store.backup_to(destination)
            store.connection.close()
            connection = sqlite3.connect(destination)
            row = connection.execute("SELECT payload_json FROM tasks WHERE task_id='task-1'").fetchone()
            event = connection.execute("SELECT payload_json FROM task_events WHERE task_id='task-1'").fetchone()
            connection.close()
            self.assertIn("rundeck-42", row[0])
            self.assertIn("rundeck-42", event[0])
            self.assertFalse(Path(str(destination) + "-wal").exists())

    def test_backup_restore_recovers_config_unit_and_ledger_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install, config, state, systemd = self.make_instance(root)
            store = TaskStore(state / "autoops-state.db")
            store.upsert("task-1", "incident-1", {"external_execution_id": "rundeck-42"})
            store.connection.close()
            backup_dir = root / "backup"
            result = backup.create_backup(output=backup_dir, install_root=install,
                                          config_root=config, state_root=state,
                                          systemd_root=systemd)
            self.assertEqual(result["status"], "READY")
            self.assertGreaterEqual(result["file_count"], 2)
            self.assertTrue((backup_dir / "state/autoops-state.db").is_file())
            self.assertFalse((backup_dir / "state/autoops-state.db-wal").exists())

            (config / "service-profile.json").write_text("changed\n", encoding="utf-8")
            changed = TaskStore(state / "autoops-state.db")
            changed.upsert("task-2", "incident-2", {"external_execution_id": "rundeck-43"})
            changed.connection.close()
            with self.assertRaises(ValueError):
                backup.restore_backup(backup=backup_dir, assume_stopped=False, dry_run=False)
            restored = backup.restore_backup(backup=backup_dir, assume_stopped=True, dry_run=False)
            self.assertEqual(restored["status"], "RESTORED")
            self.assertEqual((config / "service-profile.json").read_text(encoding="utf-8"),
                             '{"profile_id":"demo","credentials":"customer-secret"}\n')
            self.assertEqual((systemd / "jiuwenswarm-autoops-watch.service").read_text(encoding="utf-8").splitlines()[0], "[Service]")
            recovered = TaskStore(state / "autoops-state.db")
            self.assertIsNotNone(recovered.get("task-1"))
            self.assertIsNone(recovered.get("task-2"))
            self.assertIn("rundeck-42", json.dumps(recovered.get("task-1"), ensure_ascii=False))
            recovered.connection.close()

    def test_tampered_backup_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install, config, state, systemd = self.make_instance(root)
            backup_dir = root / "backup"
            backup.create_backup(output=backup_dir, install_root=install, config_root=config,
                                 state_root=state, systemd_root=systemd)
            manifest = backup_dir / "backup-manifest.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["roots"]["state"] = "/tampered"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                backup.load_backup(backup_dir)


if __name__ == "__main__":
    unittest.main()
