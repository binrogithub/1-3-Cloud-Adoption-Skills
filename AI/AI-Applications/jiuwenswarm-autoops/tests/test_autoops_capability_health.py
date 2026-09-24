import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "autoops_capability_health", ROOT / "scripts" / "autoops-capability-health.py")
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class CapabilityHealthTests(unittest.TestCase):
    def test_runtime_probe_is_explicit_and_affects_readiness(self):
        registry = {"schema_version": 1, "capabilities": {
            "metrics.query.v1": {"role": "metrics-observer", "effect": "read",
                                  "input_schema_version": 1, "result_schema_version": 1,
                                  "resource_types": ["service"], "invocation_kind": "adapter",
                                  "required": ["target"], "prerequisites": ["prometheus_configured"],
                                  "adapter": "prometheus-query.py"}}}
        with patch.object(health, "probe_datasource", return_value={
                "status": "UNAVAILABLE", "source": "prometheus"}):
            result = health.inspect(registry, ["metrics.query.v1"], application=None,
                                    service=None, target=None, include_test=False,
                                    profile_dir=None, runtime=True)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["results"][0]["runtime"]["status"], "UNAVAILABLE")

    def test_host_capability_is_ready_without_application_binding(self):
        registry = {"schema_version": 1, "capabilities": {
            "host.inspect.v1": {"role": "runbook-operator", "effect": "read",
                                 "input_schema_version": 1, "result_schema_version": 1,
                                 "resource_types": ["host"], "invocation_kind": "project_route",
                                 "required": ["target"], "prerequisites": [], "job": "host-basic-check"}}}
        result = health.inspect(registry, ["host.inspect.v1"], application=None,
                                service=None, target=None, include_test=False, profile_dir=None)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["results"][0]["binding"]["status"], "READY")

    def test_application_binding_is_resolved_from_published_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_dir = Path(directory)
            (profile_dir / "orders.json").write_text(json.dumps({
                "schema_version": 1, "profile_id": "orders-v1", "application_id": "orders",
                "application": "orders", "target_id": "host-a", "scope_id": "prod",
                "services": [{"service_id": "orders-api", "sources": []}],
            }), encoding="utf-8")
            registry = {"schema_version": 1, "capabilities": {
                "logs.query.v2": {"role": "log-investigator", "effect": "read",
                                  "input_schema_version": 1, "result_schema_version": 1,
                                  "resource_types": ["service"], "invocation_kind": "adapter",
                                  "required": ["target"], "prerequisites": [], "adapter": "log-investigate.sh"}}}
            result = health.inspect(registry, ["logs.query.v2"], application="orders",
                                    service="orders-api", target="host-a", include_test=False,
                                    profile_dir=profile_dir)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(result["results"][0]["binding"]["profile_id"], "orders-v1")

    def test_unknown_capability_is_not_configured(self):
        registry = {"schema_version": 1, "capabilities": {}}
        result = health.inspect(registry, ["unknown.v1"], application=None,
                                service=None, target=None, include_test=False, profile_dir=None)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["results"][0]["status"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
