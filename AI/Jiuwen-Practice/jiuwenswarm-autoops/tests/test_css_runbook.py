import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "scripts/css-register.py"
RUNBOOK = ROOT / "scripts/css-scale-runbook.py"


class CssRunbookTests(unittest.TestCase):
    def setup_profile(self, root: Path):
        result = subprocess.run([
            sys.executable, str(REGISTER), "--profile-id", "css-test",
            "--cluster-id", "12345678-1234-4123-8123-123456789abc",
            "--region", "cn-north-4", "--project-id", "project-test",
            "--mode", "auto", "--config-dir", str(root),
        ], env={**os.environ, "HUAWEICLOUD_SDK_AK": "AK-test",
                "HUAWEICLOUD_SDK_SK": "SK-test"},
        check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def invoke(self, root: Path, *extra: str, env=None):
        values = os.environ.copy()
        values["AUTOOPS_CSS_ACTION_DB"] = str(root / "actions.sqlite3")
        if env:
            values.update(env)
        return subprocess.run([
            sys.executable, str(RUNBOOK), "--task-id", "task-1",
            "--idempotency-key", "op-1", "--profile-id", "css-test",
            "--direction", "scale_out", "--delta", "1",
            "--config-dir", str(root), *extra,
        ], env=values, check=False, capture_output=True, text=True)

    def test_default_is_pending_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_profile(root)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "PENDING_CONFIRMATION")

    def test_mutation_requires_explicit_runtime_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_profile(root)
            result = self.invoke(root, "--execute",
                                 env={"AUTOOPS_AUTHENTICATED_ROLE": "runbook-operator"})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")

    def test_wrong_role_is_rejected_before_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_profile(root)
            result = self.invoke(
                root, "--execute",
                env={"AUTOOPS_AUTHENTICATED_ROLE": "project-manager",
                     "AUTOOPS_CSS_MUTATION_ENABLED": "1"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "PERMISSION_DENIED")

    def test_execute_requires_current_topology_and_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_profile(root)
            result = self.invoke(
                root, "--execute",
                env={"AUTOOPS_AUTHENTICATED_ROLE": "runbook-operator",
                     "AUTOOPS_CSS_MUTATION_ENABLED": "1"},
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertEqual(payload["error_code"], "PRECHECK_EVIDENCE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
