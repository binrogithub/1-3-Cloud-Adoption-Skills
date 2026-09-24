import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("k8s_inspect", ROOT / "scripts" / "k8s-inspect.py")
k8s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k8s)


class KubernetesInspectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Path(self.directory.name) / "workloads.json"
        self.config.write_text(json.dumps({
            "schema_version": 1,
            "clusters": {
                "dev": {
                    "enabled": True,
                    "context": "dev-context",
                    "kubeconfig_env": "AUTOOPS_KUBECONFIG",
                    "workloads": {
                        "staging/orders/order-api": {
                            "namespace": "staging", "kind": "Deployment", "name": "order-api",
                            "selector": "app.kubernetes.io/name=order-api", "baseline_replicas": 3,
                            "service": "order-api",
                        }
                    },
                }
            },
        }), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = k8s.main(list(args))
        return code, json.loads(output.getvalue())

    def test_inspect_uses_only_published_read_calls_and_reports_hpa(self):
        responses = {
            "deployment": {"metadata": {"name": "order-api", "namespace": "staging", "generation": 4},
                            "spec": {"replicas": 1}, "status": {"observedGeneration": 4, "readyReplicas": 1,
                            "updatedReplicas": 1, "availableReplicas": 1}},
            "pods": {"items": [{"metadata": {"name": "order-api-1"}, "status": {"phase": "Running",
                       "conditions": [{"type": "Ready", "status": "True"}],
                       "containerStatuses": [{"restartCount": 2}]}}]},
            "events": {"items": [{"type": "Warning", "reason": "FailedScheduling", "message": "insufficient cpu",
                        "lastTimestamp": "2026-09-13T00:00:00Z"}]},
            "hpa": {"items": [{"metadata": {"name": "order-api-hpa"}, "spec": {"minReplicas": 1, "maxReplicas": 5,
                     "scaleTargetRef": {"kind": "Deployment", "name": "order-api"}}}]},
        }
        calls = []

        def fake_run(binary, command, cluster):
            calls.append(command)
            label = "deployment" if command[1] == "deployment" else command[1]
            return 0, responses[label], ""

        with patch.object(k8s, "CONFIG", self.config), patch.object(k8s, "kubectl_path", return_value="/opt/kubectl"), \
                patch.object(k8s, "run_kubectl", side_effect=fake_run):
            code, payload = self.invoke("--cluster", "dev", "--workload", "staging/orders/order-api")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["deployment"]["desired_replicas"], 1)
        self.assertEqual(payload["pods"][0]["restart_count"], 2)
        self.assertEqual(payload["hpa_conflicts"][0]["name"], "order-api-hpa")
        self.assertEqual(calls[0][:2], ["get", "deployment"])
        self.assertTrue(all(command[0] == "get" for command in calls))
        self.assertNotIn("--all-namespaces", json.dumps(calls))

    def test_unpublished_namespace_is_rejected_before_kubectl(self):
        with patch.object(k8s, "CONFIG", self.config), patch.object(k8s, "kubectl_path") as binary, \
                patch.object(k8s, "run_kubectl") as run:
            code, payload = self.invoke("--cluster", "dev", "--workload", "staging/orders/order-api", "--namespace", "prod")
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_code"], "NAMESPACE_NOT_PUBLISHED")
        binary.assert_not_called()
        run.assert_not_called()

    def test_disabled_cluster_is_explicitly_unavailable(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["clusters"]["dev"]["enabled"] = False
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with patch.object(k8s, "CONFIG", self.config), patch.object(k8s, "kubectl_path") as binary:
            code, payload = self.invoke("--cluster", "dev", "--workload", "staging/orders/order-api")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "CLUSTER_NOT_ENABLED")
        binary.assert_not_called()


if __name__ == "__main__":
    unittest.main()
