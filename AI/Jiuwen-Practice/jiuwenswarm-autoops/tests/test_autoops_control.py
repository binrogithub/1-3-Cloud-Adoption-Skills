import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "scripts" / "autoops-control.py"
LAUNCHER = ROOT / "scripts" / "Jiuwen_autoops_tui"


class AutoOpsControlTests(unittest.TestCase):
    def run_control(self, root: Path, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(CONTROL), "--state-dir", str(root / "watch"),
             "--state-db", str(root / "tasks.db"), *args],
            text=True, capture_output=True, env=os.environ.copy(), check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_status_pause_resume_stop_is_one_control_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_control(root, "--action", "status")["watcher"]["status"], "active")
            self.assertEqual(self.run_control(root, "--action", "pause")["watcher"]["status"], "paused")
            self.assertEqual(self.run_control(root, "--action", "status")["watcher"]["status"], "paused")
            self.assertEqual(self.run_control(root, "--action", "resume")["watcher"]["status"], "active")
            self.assertEqual(self.run_control(root, "--action", "stop")["watcher"]["status"], "stopped")

    def test_status_can_include_missing_task_without_failing_control_plane(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = self.run_control(Path(directory), "--task-id", "missing-task")
            self.assertEqual(payload["status"], "OK")
            self.assertIsNone(payload["task"])

    def test_health_reports_pending_events_without_invoking_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "watch"
            events = root / "events.jsonl"
            events.write_text('{"id":"pending-1"}\n{"id":"pending-2"}\n', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CONTROL), "--action", "health",
                 "--state-dir", str(state), "--events-file", str(events)],
                text=True, capture_output=True, env=os.environ.copy(), check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["health"]["status"], "ok")
            self.assertEqual(payload["health"]["queue_depth"], 2)
            self.assertIsNone(payload["health"]["source_lag_seconds"])

    def test_tui_launcher_exposes_control_without_starting_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "watch"
            result = subprocess.run(
                [str(LAUNCHER), "--control", "pause", "--state-dir", str(state_dir)],
                text=True, capture_output=True, env=os.environ.copy(), check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["watcher"]["status"], "paused")

    def test_progress_and_budget_are_available_from_unified_control_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sys.path.insert(0, str(ROOT / "scripts"))
            from autoops_task_store import TaskStore
            store = TaskStore(root / "tasks.db")
            store.upsert("task-1", "intent-1", {"operation_id": "op-1"})
            store.close()
            for action, field, expected in (("progress", "progress", "task-1"),
                                            ("budget", "budget", "NOT_PLANNED")):
                result = subprocess.run(
                    [sys.executable, str(CONTROL), "--action", action, "--task-id", "task-1",
                     "--state-dir", str(root / "watch"), "--state-db", str(root / "tasks.db")],
                    text=True, capture_output=True, env=os.environ.copy(), check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "OK")
                self.assertEqual(payload[field]["task_id"] if action == "progress"
                                 else payload[field]["status"], expected)
            launcher = subprocess.run(
                [str(LAUNCHER), "--control", "progress", "--task-id", "task-1",
                 "--state-dir", str(root / "watch"), "--state-db", str(root / "tasks.db")],
                text=True, capture_output=True, env=os.environ.copy(), check=False,
            )
            self.assertEqual(launcher.returncode, 0, launcher.stderr)
            self.assertEqual(json.loads(launcher.stdout)["progress"]["task_id"], "task-1")

    def test_follow_emits_timestamped_progress_and_stops_at_requested_update_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sys.path.insert(0, str(ROOT / "scripts"))
            from autoops_task_store import TaskStore
            store = TaskStore(root / "tasks.db")
            store.upsert("task-1", "intent-1", {"operation_id": "op-1"})
            store.close()
            result = subprocess.run(
                [str(LAUNCHER), "--control", "follow", "--task-id", "task-1",
                 "--state-dir", str(root / "watch"), "--state-db", str(root / "tasks.db"),
                 "--max-updates", "1"], text=True, capture_output=True,
                env=os.environ.copy(), check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "FOLLOW")
            self.assertTrue(payload["observed_at"].endswith("Z"))
            self.assertEqual(payload["progress"]["task_id"], "task-1")

    def test_tui_launcher_bootstraps_team_swarmflow_before_autoops_request(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("jiuwenswarm-tui --persist-session --session", source)
        self.assertNotIn('/new --persist-session', source)
        self.assertLess(source.index("/mode team"), source.index("$env(AUTOOPS_PROMPT)"))
        self.assertLess(source.index("/swarmflow on"), source.index("$env(AUTOOPS_PROMPT)"))


if __name__ == "__main__":
    unittest.main()
