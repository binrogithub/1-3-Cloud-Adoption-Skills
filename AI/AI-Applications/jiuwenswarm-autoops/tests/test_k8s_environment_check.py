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
SPEC = importlib.util.spec_from_file_location("k8s_environment_check", ROOT / "scripts" / "k8s-environment-check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class KubernetesEnvironmentCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Path(self.directory.name) / "workloads.json"
        self.config.write_text(json.dumps({
            "schema_version": 1,
            "clusters": {"dev": {"enabled": False, "context": "dev-context",
                                    "kubeconfig_env": "AUTOOPS_KUBECONFIG", "workloads": {}}},
        }), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = check.main(list(args))
        return code, json.loads(output.getvalue())

    def test_disabled_cluster_does_not_contact_api(self):
        with patch.object(check, "CONFIG", self.config), patch.object(check, "kubectl_path", return_value="/opt/kubectl"), \
                patch.object(check, "run", return_value=(0, json.dumps({"clientVersion": {"gitVersion": "v1.37.0"}}), "")) as run:
            code, payload = self.invoke("--cluster", "dev")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "CLUSTER_NOT_ENABLED")
        self.assertFalse(payload["write_attempted"])
        self.assertEqual(run.call_count, 1)  # client version only
        self.assertEqual(payload["checks"][-1]["status"], "BLOCKED")

    def test_enabled_cluster_requires_kubeconfig_before_api(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["clusters"]["dev"]["enabled"] = True
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with patch.object(check, "CONFIG", self.config), patch.object(check, "kubectl_path", return_value="/opt/kubectl"), \
                patch.object(check, "run", return_value=(0, json.dumps({"clientVersion": {"gitVersion": "v1.37.0"}}), "")) as run, \
                patch.dict(os.environ, {}, clear=True):
            code, payload = self.invoke("--cluster", "dev")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "KUBECONFIG_NOT_AVAILABLE")
        self.assertFalse(payload["write_attempted"])
        self.assertEqual(run.call_count, 2)  # client version and context discovery

    def test_ready_check_uses_read_only_api_probe(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["clusters"]["dev"]["enabled"] = True
        config["clusters"]["dev"]["kubeconfig_env"] = "AUTOOPS_KUBECONFIG"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        kubeconfig = Path(self.directory.name) / "config"
        kubeconfig.write_text("placeholder", encoding="utf-8")
        responses = [
            (0, json.dumps({"clientVersion": {"gitVersion": "v1.37.0"}}), ""),
            (0, "dev-context\n", ""),
            (0, json.dumps({"gitVersion": "v1.31.0"}), ""),
        ]
        with patch.object(check, "CONFIG", self.config), patch.object(check, "kubectl_path", return_value="/opt/kubectl"), \
                patch.object(check, "run", side_effect=responses) as run, \
                patch.dict(os.environ, {"AUTOOPS_KUBECONFIG": str(kubeconfig)}, clear=True):
            code, payload = self.invoke("--cluster", "dev")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "READY")
        self.assertTrue(payload["api"]["reachable"])
        self.assertFalse(payload["write_attempted"])
        self.assertEqual(run.call_args_list[-1].args[1][-1:], ["--raw=/version"])

    def test_recovery_preflight_reports_missing_registered_job(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        cluster = config["clusters"]["dev"]
        cluster["enabled"] = True
        cluster["workloads"] = {"demo": {"restore_job": "k8s-restore-demo"}}
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with patch.object(check, "CONFIG", self.config), patch.object(check, "kubectl_path", return_value="/opt/kubectl"), \
                patch.object(check, "run", side_effect=[
                    (0, json.dumps({"clientVersion": {"gitVersion": "v1.37.0"}}), ""),
                    (0, "dev-context\n", ""),
                    (0, json.dumps({"gitVersion": "v1.34.0"}), ""),
                ]), patch.object(check, "recovery_job_check", return_value={
                    "status": "BLOCKED", "error_code": "RUNDECK_JOB_NOT_REGISTERED",
                    "required_jobs": ["k8s-restore-demo"], "missing_jobs": ["k8s-restore-demo"],
                }):
            kubeconfig = Path(self.directory.name) / "config"
            kubeconfig.write_text("placeholder", encoding="utf-8")
            with patch.dict(os.environ, {"AUTOOPS_KUBECONFIG": str(kubeconfig)}, clear=True):
                code, payload = self.invoke("--cluster", "dev", "--require-recovery")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "RUNDECK_JOB_NOT_REGISTERED")
        self.assertEqual(payload["recovery"]["status"], "BLOCKED")
        self.assertFalse(payload["write_attempted"])


if __name__ == "__main__":
    unittest.main()
