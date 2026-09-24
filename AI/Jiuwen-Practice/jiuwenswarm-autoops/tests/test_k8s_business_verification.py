import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("verify_k8s_business", ROOT / "scripts" / "verify-k8s-business.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class FakeResponse:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False


class K8sBusinessVerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Path(self.directory.name) / "workloads.json"
        self.config.write_text(json.dumps({
            "schema_version": 1,
            "clusters": {"dev": {"enabled": True, "workloads": {
                "staging/orders/order-api": {
                    "business_verification": {
                        "health_url": "http://published.test/health",
                        "probe_attempts": 7,
                        "probe_interval_seconds": 0,
                        "max_http_error_rate": 0.0,
                    }
                }
            }}}
        }), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = verifier.main(list(args))
        return code, json.loads(output.getvalue())

    def base_args(self, timestamp="1"):
        return ("--cluster", "dev", "--workload", "staging/orders/order-api",
                "--task-id", "task-1", "--action-completed-at", timestamp)

    def test_missing_probe_is_inconclusive(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        del config["clusters"]["dev"]["workloads"]["staging/orders/order-api"]["business_verification"]
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with patch.object(verifier, "CONFIG", self.config):
            code, payload = self.invoke(*self.base_args())
        self.assertEqual(code, 1)
        self.assertEqual(payload["verification_status"], "INCONCLUSIVE")
        self.assertEqual(payload["error_code"], "NO_BUSINESS_PROBE")

    def test_uses_the_same_deployment_config_override_as_e03_restore(self):
        with patch.dict("os.environ", {"AUTOOPS_KUBERNETES_WORKLOADS_FILE": str(self.config)}):
            spec = importlib.util.spec_from_file_location(
                "verify_k8s_business_with_override", ROOT / "scripts" / "verify-k8s-business.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        self.assertEqual(module.CONFIG, self.config)

    def test_published_probe_passes_with_post_action_evidence(self):
        with patch.object(verifier, "CONFIG", self.config), patch.object(verifier, "urlopen", return_value=FakeResponse()):
            code, payload = self.invoke(*self.base_args("0"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["verification_status"], "PASSED")
        self.assertEqual(len(payload["evidence_refs"]), 1)
        self.assertEqual(payload["evidence_refs"][0]["url"], "http://published.test/health")

    def test_failed_http_probe_does_not_pass(self):
        response = FakeResponse()
        response.status = 503
        with patch.object(verifier, "CONFIG", self.config), patch.object(verifier, "urlopen", return_value=response):
            code, payload = self.invoke(*self.base_args("0"))
        self.assertEqual(code, 1)
        self.assertEqual(payload["verification_status"], "FAILED")
        self.assertEqual(payload["error_code"], "HEALTH_PROBE_ERROR_RATE")


if __name__ == "__main__":
    unittest.main()
