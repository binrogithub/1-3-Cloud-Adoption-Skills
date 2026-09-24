import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "autoops-watch-policy.py"


class AutoOpsWatchPolicyTests(unittest.TestCase):
    def invoke(self, policy: Path, *args: str):
        result = subprocess.run([sys.executable, str(SCRIPT), "--policy", str(policy), *args],
                                text=True, capture_output=True, check=False)
        return result.returncode, json.loads(result.stdout)

    def test_create_update_and_status_publish_listener_and_next_run(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "orders-watch.json"
            code, payload = self.invoke(policy, "--action", "create", "--policy-id", "orders-watch",
                                        "--profile-ref", "orders-prod", "--service", "order-api",
                                        "--target", "ecs-01", "--interval", "30")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "CREATED")
            self.assertEqual(payload["policy"]["metadata"]["revision"], 1)
            self.assertEqual(payload["policy"]["spec"]["services"], ["order-api"])
            self.assertIn("next_run_at", payload)
            code, payload = self.invoke(policy, "--action", "update", "--policy-id", "orders-watch",
                                        "--profile-ref", "orders-prod", "--service", "order-api",
                                        "--target", "ecs-01", "--interval", "60")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "UPDATED")
            self.assertEqual(payload["policy"]["metadata"]["revision"], 2)
            code, payload = self.invoke(policy, "--action", "status")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "READY")
            self.assertEqual(payload["listener"]["source"], "alertmanager")

    def test_invalid_scope_is_rejected_and_existing_create_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "watch.json"
            code, payload = self.invoke(policy, "--action", "create", "--profile-ref", "orders-prod",
                                        "--service", "bad service", "--target", "ecs-01")
            self.assertEqual(code, 2)
            self.assertEqual(payload["status"], "INVALID")
            code, _ = self.invoke(policy, "--action", "create", "--profile-ref", "orders-prod",
                                  "--service", "order-api", "--target", "ecs-01")
            self.assertEqual(code, 0)
            code, payload = self.invoke(policy, "--action", "create", "--profile-ref", "orders-prod",
                                        "--service", "order-api", "--target", "ecs-01")
            self.assertEqual(code, 2)
            self.assertEqual(payload["status"], "ALREADY_EXISTS")


if __name__ == "__main__":
    unittest.main()
