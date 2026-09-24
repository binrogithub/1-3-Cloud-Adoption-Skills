import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("k8s_restore", ROOT / "scripts" / "k8s-restore-replicas.py")
k8s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k8s)


class KubernetesRestoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Path(self.directory.name) / "workloads.json"
        self.config.write_text(json.dumps({
            "schema_version": 1,
            "clusters": {"dev": {"enabled": True, "workloads": {
                "staging/orders/order-api": {
                    "kind": "Deployment", "namespace": "staging", "name": "order-api",
                    "selector": "app.kubernetes.io/name=order-api", "baseline_replicas": 3,
                    "service": "order-api", "restore_job": "k8s-restore-order-api",
                }
            }}},
        }), encoding="utf-8")
        self.observation = {
            "status": "ok", "hpa_conflicts": [],
            "deployment": {"desired_replicas": 1},
        }

    def tearDown(self):
        self.directory.cleanup()

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = k8s.main(list(args))
        return code, json.loads(output.getvalue())

    def base_args(self):
        return ("--cluster", "dev", "--workload", "staging/orders/order-api",
                "--target", "test-host-01", "--task-id", "task-1", "--idempotency-key", "op-1")

    def test_requires_kubernetes_operator_identity(self):
        with patch.object(k8s, "CONFIG", self.config), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUTOOPS_AUTHENTICATED_ROLE", None)
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_code"], "ROLE_REQUIRED")

    def test_hpa_conflict_stops_before_rundeck(self):
        observation = {**self.observation, "hpa_conflicts": [{"name": "order-api-hpa"}]}
        with patch.object(k8s, "CONFIG", self.config), patch.dict(os.environ, {"AUTOOPS_AUTHENTICATED_ROLE": "kubernetes-operator"}), \
                patch.object(k8s, "inspect", return_value=(0, observation)), patch.object(k8s, "runbook") as runbook:
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "WAITING")
        self.assertEqual(payload["error_code"], "HPA_CONFLICT")
        runbook.assert_not_called()

    def test_at_baseline_returns_no_change(self):
        observation = {**self.observation, "deployment": {"desired_replicas": 3}}
        with patch.object(k8s, "CONFIG", self.config), patch.dict(os.environ, {"AUTOOPS_AUTHENTICATED_ROLE": "kubernetes-operator"}), \
                patch.object(k8s, "inspect", return_value=(0, observation)), patch.object(k8s, "runbook") as runbook:
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "NO_CHANGE")
        self.assertFalse(payload["changed"])
        runbook.assert_not_called()

    def test_below_baseline_calls_published_rundeck_job_once(self):
        with patch.object(k8s, "CONFIG", self.config), patch.dict(os.environ, {"AUTOOPS_AUTHENTICATED_ROLE": "kubernetes-operator"}), \
                patch.object(k8s, "inspect", side_effect=[(0, self.observation), (0, {
                    **self.observation, "deployment": {"desired_replicas": 3, "ready_replicas": 3},
                })]), \
                patch.object(k8s, "runbook", return_value=(0, {"status": "SUCCEEDED", "ansible_recap": {"result": "CHANGED", "changed": 1, "failed": 0}})) as runbook:
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertTrue(payload["changed"])
        self.assertEqual(payload["verification_status"], "PASSED")
        self.assertEqual(payload["resource_verification_status"], "PASSED")
        self.assertEqual(payload["business_verification_status"], "UNVERIFIED")
        self.assertEqual(payload["verified_replicas"], {"desired": 3, "ready": 3})
        runbook.assert_called_once_with("k8s-restore-order-api", "test-host-01", "task-1", "op-1")

    def test_successful_rundeck_job_fails_when_postcondition_is_not_met(self):
        with patch.object(k8s, "CONFIG", self.config), patch.dict(os.environ, {"AUTOOPS_AUTHENTICATED_ROLE": "kubernetes-operator"}), \
                patch.object(k8s, "inspect", side_effect=[(0, self.observation), (0, {
                    **self.observation, "deployment": {"desired_replicas": 2, "ready_replicas": 1},
                })]), \
                patch.object(k8s, "runbook", return_value=(0, {"status": "SUCCEEDED"})):
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "FAILED")
        self.assertEqual(payload["error_code"], "POSTCONDITION_NOT_MET")
        self.assertEqual(payload["verification_status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
