import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "css-24h-pressure.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("css_24h_recovery", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
LIVE_SPEC = importlib.util.spec_from_file_location(
    "css_live_recovery", ROOT / "scripts" / "css-live-pressure.py"
)
LIVE_MODULE = importlib.util.module_from_spec(LIVE_SPEC)
sys.modules[LIVE_SPEC.name] = LIVE_MODULE
LIVE_SPEC.loader.exec_module(LIVE_MODULE)
from css_action_ledger import open_action_db, resource_key
from css_run_state import unresolved_actions


class Css24hRecoveryTests(unittest.TestCase):
    def test_restart_reconciles_capacity_read_only_and_keeps_business_gate(self):
        with tempfile.TemporaryDirectory() as raw:
            database = Path(raw) / "actions.sqlite3"
            profile = {"provider": "huaweicloud", "domain_id": "d", "project_id": "p",
                       "region": "r", "cluster_id": "cluster"}
            key = resource_key(profile)
            connection = open_action_db(database)
            connection.execute(
                "INSERT INTO css_actions(operation_id,profile_id,direction,delta,target_nodes,status,resource_key) "
                "VALUES(?,?,?,?,?,?,?)",
                ("op-1", "profile", "scale_out", 1, 3, "SUBMITTED", key),
            )
            connection.close()
            topology = {"data_node_count": 3, "cluster_healthy": True,
                        "instances": [{"type": "ess", "status": "200"}] * 3,
                        "actions": [], "action_progress": {}}
            with patch.object(MODULE, "load_credentials", return_value={}), \
                    patch.object(MODULE, "cluster_snapshot", return_value=topology):
                result = MODULE.reconcile_existing_actions(profile, None, database, key)
            self.assertEqual(result[0]["status"], "CAPACITY_READY")
            self.assertEqual(unresolved_actions(database, key)[0]["status"], "CAPACITY_READY")

    def test_restart_uses_business_verifier_without_enabling_cloud_writes(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            database = directory / "css-actions.sqlite3"
            profile = {"profile_id": "profile", "provider": "huaweicloud", "domain_id": "d",
                       "project_id": "p", "region": "r", "cluster_id": "cluster"}
            key = resource_key(profile)
            connection = open_action_db(database)
            connection.execute(
                "INSERT INTO css_actions(operation_id,profile_id,direction,delta,target_nodes,status,resource_key) "
                "VALUES(?,?,?,?,?,?,?)",
                ("op-resume", "profile", "scale_out", 1, 3, "CAPACITY_READY", key),
            )
            connection.close()
            business_config = directory / "business.json"
            business_config.write_text("{}\n", encoding="utf-8")
            response = {"status": "SUCCEEDED", "cloud_writes": False}
            with patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(
                    stdout=json.dumps(response), returncode=0)) as run:
                outcomes = MODULE.reconcile_existing_actions(
                    profile, directory, database, key, str(business_config)
                )
            command = run.call_args.args[0]
            self.assertIn("--reconcile-operation-id", command)
            self.assertIn("op-resume", command)
            self.assertIn("--business-config", command)
            self.assertNotIn("--execute", command)
            self.assertEqual(outcomes[0]["status"], "SUCCEEDED")
            self.assertFalse(outcomes[0]["cloud_writes"])

    def test_persisted_operation_resume_is_read_only_and_uses_existing_target(self):
        with tempfile.TemporaryDirectory() as raw:
            database = Path(raw) / "css-actions.sqlite3"
            connection = open_action_db(database)
            connection.execute(
                "INSERT INTO css_actions(operation_id,target_nodes,status) VALUES(?,?,?)",
                ("op-1", 4, "CAPACITY_READY"),
            )
            connection.close()
            args = SimpleNamespace(state_dir=Path(raw))
            with patch.object(LIVE_MODULE, "reconcile_until_settled", return_value={
                    "status": "SUCCEEDED", "timeline": []}) as live_reconcile:
                result = LIVE_MODULE.reconcile_persisted_operation(
                    args, {"profile_id": "p"}, {}, "op-1"
                )
            self.assertEqual(result["status"], "SUCCEEDED")
            self.assertFalse(result["cloud_writes"])
            self.assertEqual(live_reconcile.call_args.args[3], {"target_nodes": 4})


if __name__ == "__main__":
    unittest.main()
