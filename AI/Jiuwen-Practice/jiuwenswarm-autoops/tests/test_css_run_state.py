import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_action_ledger import open_action_db, resource_key
from css_run_state import (STATE_SCHEMA_VERSION, atomic_write, digest,
                           load_checkpoint, unresolved_actions)


class CssRunStateTests(unittest.TestCase):
    def test_checkpoint_is_atomic_and_resume_binds_plan_profile_and_duration(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "run.checkpoint.json"
            plan_digest = digest({"plan": 1})
            atomic_write(path, {
                "schema_version": STATE_SCHEMA_VERSION, "status": "RUNNING",
                "run_id": "run-1", "profile_id": "cluster-a", "plan_digest": plan_digest,
                "duration_seconds": 86400,
            })
            loaded = load_checkpoint(path, plan_digest=plan_digest,
                                     profile_id="cluster-a", duration_seconds=86400)
            self.assertEqual(loaded["run_id"], "run-1")
            with self.assertRaisesRegex(ValueError, "plan differs"):
                load_checkpoint(path, plan_digest="different", profile_id="cluster-a",
                                 duration_seconds=86400)
            with self.assertRaisesRegex(ValueError, "profile differs"):
                load_checkpoint(path, plan_digest=plan_digest, profile_id="cluster-b",
                                 duration_seconds=86400)

    def test_terminal_checkpoints_cannot_be_restarted(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "done.checkpoint.json"
            plan_digest = digest({"plan": "done"})
            atomic_write(path, {"schema_version": STATE_SCHEMA_VERSION, "status": "COMPLETED",
                                "profile_id": "p", "plan_digest": plan_digest,
                                "duration_seconds": 60})
            with self.assertRaisesRegex(ValueError, "terminal"):
                load_checkpoint(path, plan_digest=plan_digest, profile_id="p", duration_seconds=60)

    def test_resource_action_query_returns_unresolved_operations(self):
        with tempfile.TemporaryDirectory() as raw:
            database = Path(raw) / "actions.sqlite3"
            connection = open_action_db(database)
            profile = {"provider": "huaweicloud", "domain_id": "d", "project_id": "p",
                       "region": "r", "cluster_id": "c"}
            key = resource_key(profile)
            connection.execute("INSERT INTO css_actions(operation_id,profile_id,status,resource_key) VALUES(?,?,?,?)",
                               ("op-active", "alias-a", "UNKNOWN", key))
            connection.execute("INSERT INTO css_actions(operation_id,profile_id,status,resource_key) VALUES(?,?,?,?)",
                               ("op-done", "alias-b", "SUCCEEDED", key))
            connection.close()
            actions = unresolved_actions(database, key)
            self.assertEqual([item["operation_id"] for item in actions], ["op-active"])

    def test_concurrent_resource_claims_admit_only_one_active_operation(self):
        with tempfile.TemporaryDirectory() as raw:
            database = Path(raw) / "actions.sqlite3"
            profile = {"provider": "huaweicloud", "domain_id": "d", "project_id": "p",
                       "region": "r", "cluster_id": "same-cluster"}
            key = resource_key(profile)
            barrier = threading.Barrier(2)

            def claim(operation_id):
                connection = open_action_db(database)
                try:
                    barrier.wait(timeout=5)
                    connection.execute("BEGIN IMMEDIATE")
                    active = connection.execute(
                        "SELECT operation_id FROM css_actions WHERE resource_key=? "
                        "AND status IN ('INTENT_RECORDED','SUBMITTED','RECONCILING','UNKNOWN',"
                        "'CAPACITY_READY','VERIFYING_BUSINESS','DEGRADED') LIMIT 1", (key,)
                    ).fetchone()
                    if active:
                        connection.rollback()
                        return "BLOCKED"
                    connection.execute(
                        "INSERT INTO css_actions(operation_id,profile_id,status,resource_key) "
                        "VALUES(?,?,?,?)", (operation_id, operation_id, "INTENT_RECORDED", key)
                    )
                    connection.commit()
                    return "CLAIMED"
                finally:
                    connection.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(claim, ("op-a", "op-b")))
            self.assertCountEqual(outcomes, ["CLAIMED", "BLOCKED"])
            self.assertEqual(len(unresolved_actions(database, key)), 1)


if __name__ == "__main__":
    unittest.main()
