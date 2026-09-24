import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_metrics import normalize_snapshot
from css_policy import evaluate


POLICY = {
    "schema_version": 1, "policy_id": "css-default", "revision": 1,
    "mode": "auto", "min_data_nodes": 2, "max_data_nodes": 10,
    "scale_out_step": 1, "scale_in_step": 1,
    "scale_out_cooldown_minutes": 30, "scale_in_cooldown_minutes": 120,
    "scale_in_delay_after_scale_out_minutes": 120,
    "scale_out_cpu_percent": 75, "scale_in_cpu_percent": 30,
    "scale_out_disk_percent": 75, "scale_in_disk_percent": 65,
    "allow_scale_out": True, "allow_scale_in": True,
}


def snapshot(**metrics):
    return normalize_snapshot({
        "observed_at": "2099-01-01T00:00:00Z",
        "metrics": {"cluster_status": 0, "disk_usage_pct": 40, "jvm_heap_max": 40,
                    "cpu_max": 20, "search_rate": 1, "search_latency": 1,
                    "indexing_rate": 1, "indexing_latency": 1, **metrics},
        "topology": {"data_node_count": 3, "cluster_healthy": True},
    })


class CssPolicyTests(unittest.TestCase):
    def test_scale_out_is_bounded_by_one_node(self):
        decision = evaluate(snapshot(cpu_max=90), POLICY)
        self.assertEqual(decision["decision"], "scale_out")
        self.assertEqual(decision["delta"], 1)
        self.assertEqual(decision["target_nodes"], 4)

    def test_policy_minimum_violation_generates_bounded_scale_out(self):
        policy = dict(POLICY)
        policy["allow_scale_out"] = False
        value = snapshot()
        value["topology"]["data_node_count"] = 1
        decision = evaluate(value, policy)
        self.assertEqual(decision["decision"], "scale_out")
        self.assertEqual(decision["target_nodes"], 2)
        self.assertIn("POLICY_MINIMUM_VIOLATED", decision["reason_codes"])

    def test_missing_metric_blocks_scale_in(self):
        value = snapshot()
        value["quality"] = "insufficient"
        decision = evaluate(value, POLICY)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertIn("EVIDENCE_INSUFFICIENT", decision["reason_codes"])

    def test_unhealthy_cluster_blocks_any_scale(self):
        decision = evaluate(snapshot(cluster_status=2, cpu_max=90), POLICY)
        self.assertEqual(decision["decision"], "investigate")
        self.assertIn("CLUSTER_NOT_HEALTHY", decision["reason_codes"])

    def test_scale_in_is_protected_after_scale_out(self):
        policy = dict(POLICY)
        policy["allow_scale_out"] = False
        decision = evaluate(snapshot(cpu_max=10, disk_usage_pct=20), policy,
                            now_epoch=1000, last_scale_out_epoch=950)
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertIn("SCALE_OUT_PROTECTION", decision["reason_codes"])

    def test_high_traffic_blocks_scale_in(self):
        decision = evaluate(snapshot(cpu_max=10, disk_usage_pct=20, search_rate=5000), POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("TRAFFIC_TOO_HIGH_FOR_SCALE_IN", decision["reason_codes"])

    def test_high_latency_blocks_scale_in(self):
        decision = evaluate(snapshot(cpu_max=10, disk_usage_pct=20, search_latency=500), POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("LATENCY_TOO_HIGH_FOR_SCALE_IN", decision["reason_codes"])

    def test_high_heap_blocks_scale_in(self):
        decision = evaluate(snapshot(cpu_max=10, disk_usage_pct=20, jvm_heap_max=90), POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("JVM_HEAP_TOO_HIGH_FOR_SCALE_IN", decision["reason_codes"])

    def test_missing_snapshot_blocks_scale_in(self):
        value = snapshot(cpu_max=10, disk_usage_pct=20)
        value["snapshot_available"] = False
        decision = evaluate(value, POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("SNAPSHOT_REQUIRED", decision["reason_codes"])

    def test_configured_policy_requires_sustained_pressure_window(self):
        policy = dict(POLICY, enforce_sustained_windows=True,
                      scale_out_required_samples=3, scale_out_window_minutes=5)
        decision = evaluate(snapshot(cpu_max=90), policy)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("SUSTAINED_PRESSURE_WINDOW_INSUFFICIENT", decision["reason_codes"])
        history = [{"quality": "ok", "observed_at": str(index),
                    "metrics": {"cpu_max": 90, "disk_usage_pct": 40}}
                   for index in range(3)]
        decision = evaluate(snapshot(cpu_max=90), policy, history=history)
        self.assertEqual(decision["decision"], "scale_out")

    def test_css_cli_fixture_does_not_expose_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run([
                sys.executable, str(ROOT / "scripts/css-register.py"),
                "--profile-id", "test-css",
                "--cluster-id", "12345678-1234-4123-8123-123456789abc",
                "--region", "cn-north-4", "--project-id", "project-test",
                "--mode", "auto",
                "--config-dir", str(root),
            ], env={**os.environ, "HUAWEICLOUD_SDK_AK": "AK-test",
                    "HUAWEICLOUD_SDK_SK": "SK-test"},
               check=True, capture_output=True, text=True)
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps({
                "observed_at": "2099-01-01T00:00:00Z",
                "metrics": {"cluster_status": 0, "disk_usage_pct": 80, "cpu_max": 90,
                            "jvm_heap_max": 60, "search_rate": 10, "search_latency": 20,
                            "indexing_rate": 10, "indexing_latency": 20},
                "topology": {"data_node_count": 2, "cluster_healthy": True},
            }), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/css-auto.py"), "plan",
                "--profile-id", "test-css", "--config-dir", str(root),
                "--fixture", str(fixture),
            ], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SK-test", result.stdout)
        self.assertIn('"decision": "hold"', result.stdout)
        self.assertIn("SUSTAINED_PRESSURE_WINDOW_INSUFFICIENT", result.stdout)


if __name__ == "__main__":
    unittest.main()
