import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT / "scripts" / "autoops_watch.py"


class AutoOpsWatcherTests(unittest.TestCase):
    def test_watermark_and_delivery_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            event_time = (datetime.now(timezone.utc).replace(microsecond=0)
                          - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
            event = {"id": "delivery-1", "source": "alertmanager", "alertname": "ServiceDown",
                     "status": "firing", "starts_at": event_time,
                     "target": "test-host-01", "service": "autoops-demo"}
            events.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n", encoding="utf-8")
            env = os.environ | {"AUTOOPS_STATE_DB": str(root / "tasks.db")}
            def run(*args):
                result = subprocess.run([sys.executable, str(WATCHER), "--state-dir", str(root / "state"),
                                         "--events-file", str(events), "--policy",
                                         str(ROOT / "config/monitoring/autoops-demo-watch.json"), *args],
                                        text=True, capture_output=True, env=env, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            first = run("--action", "run")
            self.assertEqual(first["processed"], 1)
            self.assertEqual(first["duplicates"], 1)
            self.assertEqual(first["source_watermarks"]["alertmanager"]["watermark"], event_time)
            expected_next = (datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                             - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
            self.assertEqual(first["source_watermarks"]["alertmanager"]["next_query_start"], expected_next)
            self.assertEqual(first["source_watermarks"]["alertmanager"]["max_backfill_minutes"], 1440)
            import sqlite3
            connection = sqlite3.connect(root / "tasks.db")
            task_payload = json.loads(connection.execute("SELECT payload_json FROM tasks LIMIT 1").fetchone()[0])
            connection.close()
            self.assertEqual(task_payload["watch_policy_id"], "autoops-demo-watch")
            self.assertEqual(task_payload["parent_watch_id"], "autoops-demo-watch")
            second = run("--action", "run")
            self.assertEqual(second["processed"], 0)
            self.assertEqual(second["duplicates"], 0)
            status = run("--action", "status")
            self.assertEqual(status["watermark"], event_time)
            self.assertIsInstance(status["next_run_at"], str)
            self.assertEqual(len(status["incidents"]), 1)
            self.assertEqual(status["source_watermarks"]["alertmanager"]["overlap_minutes"], 2)
            self.assertEqual(first["incidents"][0]["task_id"], first["incidents"][0]["incident_id"])

            events.write_text(
                events.read_text(encoding="utf-8")
                + json.dumps({"id": "delivery-2", "source": "loki", "timestamp": event_time}) + "\n"
                + json.dumps({"id": "delivery-3", "source": "loki", "timestamp": event_time}) + "\n",
                encoding="utf-8")
            third = run("--action", "run")
            self.assertEqual(third["processed"], 2)
            self.assertEqual(third["source_watermarks"]["loki"]["watermark"], event_time)
            self.assertEqual(third["source_watermarks"]["loki"]["next_query_start"], expected_next)

    def test_pause_resume_and_stop_bound_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            events.write_text(json.dumps({"id": "delivery-2", "service": "autoops-demo"}) + "\n", encoding="utf-8")
            env = os.environ | {"AUTOOPS_STATE_DB": str(root / "tasks.db")}
            base = [sys.executable, str(WATCHER), "--state-dir", str(root / "state"),
                    "--events-file", str(events), "--policy", str(ROOT / "config/monitoring/autoops-demo-watch.json")]
            for action in ("pause", "stop"):
                result = subprocess.run(base + ["--action", action], text=True, capture_output=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(base + ["--action", "run"], text=True, capture_output=True, env=env)
            self.assertEqual(json.loads(result.stdout)["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
