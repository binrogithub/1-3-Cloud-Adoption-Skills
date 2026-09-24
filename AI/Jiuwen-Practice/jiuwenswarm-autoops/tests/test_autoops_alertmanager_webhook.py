import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBHOOK = ROOT / "scripts" / "autoops_alertmanager_webhook.py"


class AlertmanagerWebhookTests(unittest.TestCase):
    def test_normalizes_alert_and_persists_before_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.json"
            events = root / "events.jsonl"
            body.write_text(json.dumps({"alerts": [{
                "status": "firing",
                "labels": {"alertname": "ServiceDown", "service": "autoops-demo",
                            "instance": "test-host-01", "scope_id": "test-scope"},
                "annotations": {"summary": "service is down"},
                "startsAt": "2026-09-13T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z"
            }]}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(WEBHOOK), "--body-file", str(body),
                                     "--events-file", str(events)], text=True, capture_output=True,
                                    env=os.environ | {"ALERTMANAGER_WEBHOOK_TOKEN": "secret"}, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["accepted"], 1)
            event = json.loads(events.read_text(encoding="utf-8"))
            self.assertEqual(event["service"], "autoops-demo")
            self.assertEqual(event["target"], "test-host-01")
            self.assertEqual(event["scope_id"], "test-scope")
            self.assertTrue(event["id"].startswith("am-"))

    def test_rejects_malformed_payload_without_creating_event_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.json"
            events = root / "events.jsonl"
            body.write_text(json.dumps({"alerts": {}}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(WEBHOOK), "--body-file", str(body),
                                     "--events-file", str(events)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(events.exists())

    def test_rejects_missing_occurrence_timestamp_and_unknown_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            for alert in (
                {"status": "firing", "labels": {"service": "order-api"}},
                {"status": "pending", "startsAt": "2026-09-13T00:00:00Z",
                 "labels": {"service": "order-api"}},
            ):
                body = root / "body.json"
                body.write_text(json.dumps({"alerts": [alert]}), encoding="utf-8")
                result = subprocess.run([sys.executable, str(WEBHOOK), "--body-file", str(body),
                                         "--events-file", str(events)], text=True,
                                        capture_output=True, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(events.exists())


if __name__ == "__main__":
    unittest.main()
