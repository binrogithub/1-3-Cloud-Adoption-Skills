import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_capability import classify_api_error, validate_plan
from css_action_ledger import transition_status
from css_metrics import normalize_snapshot
from css_policy import evaluate
from css_reconcile import reconcile_action


POLICY = {
    "schema_version": 2, "policy_id": "css-default", "revision": 6,
    "mode": "auto", "min_data_nodes": 2, "max_data_nodes": 10,
    "scale_out_step": 1, "scale_in_step": 1,
    "scale_out_cpu_percent": 75, "scale_in_cpu_percent": 30,
    "scale_out_disk_percent": 75, "scale_in_disk_percent": 65,
    "scale_in_max_search_rate": 1000, "scale_in_max_indexing_rate": 1000,
    "scale_in_max_search_latency": 200, "scale_in_max_indexing_latency": 200,
    "scale_in_max_jvm_heap": 85, "allow_scale_out": True,
    "allow_scale_in": True,
    "provider_constraints": {
        "require_no_active_action": True,
        "shrink_rule": "reduced_nodes_less_than_half",
    },
}


def snapshot(nodes=3, **metrics):
    values = {
        "cluster_status": 0, "disk_usage_pct": 20, "jvm_heap_max": 40,
        "cpu_max": 10, "search_rate": 1, "search_latency": 1,
        "indexing_rate": 1, "indexing_latency": 1,
    }
    values.update(metrics)
    return normalize_snapshot({
        "observed_at": "2099-01-01T00:00:00Z", "metrics": values,
        "topology": {"data_node_count": nodes, "cluster_healthy": True},
    })


class CssOptimizedTests(unittest.TestCase):
    def test_provider_blocks_two_to_one(self):
        policy = dict(POLICY)
        policy["min_data_nodes"] = 1
        topology = {"data_node_count": 2, "cluster_healthy": True}
        reasons = validate_plan(topology, policy, "scale_in", 1, target_nodes=1)
        self.assertIn("PROVIDER_SCALE_IN_CONSTRAINT", reasons)
        decision = evaluate(snapshot(nodes=2), policy)
        self.assertIn("PROVIDER_SCALE_IN_CONSTRAINT", decision["reason_codes"])

    def test_provider_allows_three_to_two(self):
        reasons = validate_plan({"data_node_count": 3, "cluster_healthy": True},
                                POLICY, "scale_in", 1, target_nodes=2)
        self.assertEqual(reasons, [])
        self.assertEqual(evaluate(snapshot(nodes=3), POLICY)["decision"], "scale_in")

    def test_active_cloud_action_blocks_new_plan(self):
        value = snapshot(nodes=3)
        value["topology"]["actions"] = ["GROWING"]
        decision = evaluate(value, POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("ACTIVE_CLOUD_ACTION", decision["reason_codes"])

    def test_non_ready_ess_node_blocks_new_plan(self):
        value = snapshot(nodes=2)
        value["topology"]["instances"] = [
            {"type": "ess", "status": "200"},
            {"type": "ess", "status": "100"},
        ]
        decision = evaluate(value, POLICY)
        self.assertEqual(decision["decision"], "hold")
        self.assertIn("ESS_NODE_NOT_AVAILABLE", decision["reason_codes"])

    def test_error_classification_does_not_retry(self):
        self.assertEqual(classify_api_error("status_code:409 CSS.0011")["status"], "RECONCILING")
        self.assertFalse(classify_api_error("CSS.0001 incorrect parameters")["retry"])

    def test_action_ledger_rejects_reopening_terminal_state(self):
        self.assertEqual(transition_status("INTENT_RECORDED", "SUBMITTED"), "SUBMITTED")
        self.assertEqual(transition_status("SUBMITTED", "SUCCEEDED"), "SUCCEEDED")
        with self.assertRaises(ValueError):
            transition_status("SUCCEEDED", "SUBMITTED")

    def test_operation_status_does_not_require_profile_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actions.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE css_actions (operation_id TEXT PRIMARY KEY, task_id TEXT, profile_id TEXT, direction TEXT, delta INTEGER, status TEXT, cloud_request_id TEXT)")
            connection.execute("INSERT INTO css_actions VALUES (?, ?, ?, ?, ?, ?, ?)",
                               ("op-1", "task-1", "css-test", "scale_out", 1, "SUBMITTED", None))
            connection.commit()
            connection.close()
            environment = os.environ | {"AUTOOPS_CSS_ACTION_DB": str(path)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "css-auto.py"), "status",
                 "--operation-id", "op-1"], text=True, capture_output=True,
                env=environment, check=True,
            )
            payload = __import__("json").loads(result.stdout)
            self.assertEqual(payload["status"], "FOUND")
            self.assertEqual(payload["cloud_request_id"], "not_returned")

    def test_reconcile_waits_for_creating_node(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"},
                           {"type": "ess", "status": "100"}]},
        )
        self.assertEqual(result["status"], "RECONCILING")
        self.assertIn("ESS_NODE_NOT_AVAILABLE", result["reason_codes"])

    def test_reconcile_waits_when_topology_count_has_no_matching_instances(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"}]},
            {"status": "PASSED"},
        )
        self.assertEqual(result["status"], "RECONCILING")
        self.assertEqual(result["reason_codes"], ["ESS_NODE_STATUS_INCOMPLETE"])

    def test_reconcile_waits_for_active_action(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"},
                           {"type": "ess", "status": "200"}],
             "actions": ["GROWING"]},
        )
        self.assertEqual(result["status"], "RECONCILING")

    def test_reconcile_needs_independent_verification(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"},
                           {"type": "ess", "status": "200"}]},
        )
        self.assertEqual(result["status"], "CAPACITY_READY")
        self.assertIn("BUSINESS_VERIFICATION_PENDING", result["reason_codes"])

    def test_reconcile_succeeds_after_verification(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"},
                           {"type": "ess", "status": "200"}]},
            {"status": "PASSED"},
        )
        self.assertEqual(result["status"], "SUCCEEDED")

    def test_reconcile_reports_capacity_ready_until_business_is_verified(self):
        result = reconcile_action(
            {"target_nodes": 2},
            {"cluster_healthy": True, "data_node_count": 2,
             "instances": [{"type": "ess", "status": "200"},
                           {"type": "ess", "status": "200"}]},
            {"status": "UNVERIFIED"},
        )
        self.assertEqual(result["status"], "CAPACITY_READY")
        self.assertEqual(result["capacity_change_status"], "CAPACITY_READY")
        self.assertEqual(result["business_verification_status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
