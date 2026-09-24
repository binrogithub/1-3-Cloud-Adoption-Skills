import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CssProjectManagerTests(unittest.TestCase):
    def test_project_manager_routes_registered_css_without_host_profile_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered = subprocess.run([
                sys.executable, str(ROOT / "scripts/css-register.py"),
                "--profile-id", "css-prod",
                "--cluster-id", "12345678-1234-4123-8123-123456789abc",
                "--region", "cn-north-4", "--project-id", "project-test",
                "--config-dir", str(root),
            ], env={**os.environ, "HUAWEICLOUD_SDK_AK": "AK-test",
                    "HUAWEICLOUD_SDK_SK": "SK-test"},
            check=False, capture_output=True, text=True)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/autoops-project-manager.py"),
                "--request", "查看华为云 CSS 集群查询流量",
                "--css-profile", "css-prod", "--css-config-dir", str(root),
                "--machine-output",
            ], check=False, capture_output=True, text=True)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selected_role"], "css_auto")
            self.assertEqual(payload["selected_epic"], "CSS")
            self.assertEqual(payload["status"], "UNAVAILABLE")
            self.assertNotIn("SK-test", result.stdout)

    def test_css_remediation_builds_runbook_and_verifier_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered = subprocess.run([
                sys.executable, str(ROOT / "scripts/css-register.py"),
                "--profile-id", "css-prod",
                "--cluster-id", "12345678-1234-4123-8123-123456789abc",
                "--region", "cn-north-4", "--project-id", "project-test",
                "--config-dir", str(root),
            ], env={**os.environ, "HUAWEICLOUD_SDK_AK": "AK-test",
                    "HUAWEICLOUD_SDK_SK": "SK-test"},
            check=False, capture_output=True, text=True)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/autoops-project-manager.py"),
                "--request", "扩容华为云 CSS 数据节点",
                "--css-profile", "css-prod", "--css-config-dir", str(root),
                "--machine-output",
            ], check=False, capture_output=True, text=True)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "PLAN_READY")
            self.assertEqual(payload["routing"]["selected_roles"],
                             ["css_auto", "runbook-operator", "recovery-verifier"])
            self.assertEqual([step["capability"] for step in payload["plan"]["steps"]],
                             ["css.plan.v1", "css.scale.v1", "css.verify.v1"])
            self.assertNotIn("SK-test", result.stdout)


if __name__ == "__main__":
    unittest.main()
