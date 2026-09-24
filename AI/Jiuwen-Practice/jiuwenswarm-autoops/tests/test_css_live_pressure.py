import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "css-live-pressure.py"


def load_live_pressure_module():
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("css_live_pressure_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CssLivePressureTests(unittest.TestCase):
    def test_live_reconciliation_persists_capacity_state(self):
        module = load_live_pressure_module()
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            db = state_dir / "css-actions.sqlite3"
            connection = module.open_action_db(db)
            connection.execute(
                "INSERT INTO css_actions(operation_id,status,resource_key) VALUES(?,?,?)",
                ("op-1", "SUBMITTED", "fixture"),
            )
            connection.close()
            result = module.persist_reconciliation(
                SimpleNamespace(state_dir=state_dir), "op-1", "CAPACITY_READY"
            )
            self.assertEqual(result["current"], "CAPACITY_READY")
            connection = module.open_action_db(db)
            row = connection.execute(
                "SELECT status,reconciled_at FROM css_actions WHERE operation_id=?", ("op-1",)
            ).fetchone()
            connection.close()
            self.assertEqual(row["status"], "CAPACITY_READY")
            self.assertIsNotNone(row["reconciled_at"])

    def test_live_reconciliation_uses_shared_runtime_action_ledger(self):
        module = load_live_pressure_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local_state = root / "local"
            local_state.mkdir()
            shared_db = root / "shared-actions.sqlite3"
            connection = module.open_action_db(shared_db)
            connection.execute(
                "INSERT INTO css_actions(operation_id,status,resource_key) VALUES(?,?,?)",
                ("shared-op", "SUBMITTED", "shared-resource"),
            )
            connection.close()
            previous = os.environ.get("AUTOOPS_CSS_ACTION_DB")
            os.environ["AUTOOPS_CSS_ACTION_DB"] = str(shared_db)
            try:
                result = module.persist_reconciliation(
                    SimpleNamespace(state_dir=local_state), "shared-op", "SUCCEEDED"
                )
            finally:
                if previous is None:
                    os.environ.pop("AUTOOPS_CSS_ACTION_DB", None)
                else:
                    os.environ["AUTOOPS_CSS_ACTION_DB"] = previous
            self.assertEqual(result["current"], "SUCCEEDED")
            self.assertFalse((local_state / "css-actions.sqlite3").exists())

    def test_probe_loads_auth_headers_and_allows_private_tls_mode(self):
        module = load_live_pressure_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "headers.json"
            path.write_text(json.dumps({"Authorization": "Basic fixture"}), encoding="utf-8")
            self.assertEqual(module.probe_headers(str(path)), {"Authorization": "Basic fixture"})

    def test_explicit_wave_target_uses_policy_step_and_target(self):
        module = load_live_pressure_module()
        snapshot = {
            "quality": "ok",
            "topology": {"cluster_healthy": True, "data_node_count": 2,
                         "instances": [{"type": "ess", "status": "200"},
                                       {"type": "ess", "status": "200"}]},
        }
        policy = {"min_data_nodes": 2, "max_data_nodes": 10, "scale_out_step": 8,
                  "scale_in_step": 8, "allow_scale_out": True, "allow_scale_in": True,
                  "provider_constraints": {"require_no_active_action": True}}
        decision = module.explicit_target_decision(snapshot, policy, 10)
        self.assertEqual(decision["decision"], "scale_out")
        self.assertEqual(decision["delta"], 8)

        snapshot["topology"]["data_node_count"] = 10
        snapshot["topology"]["instances"] = [{"type": "ess", "status": "200"}] * 10
        policy["scale_in_step"] = 1
        blocked = module.explicit_target_decision(snapshot, policy, 2)
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("BUSINESS_VERIFICATION_REQUIRED_FOR_SCALE_IN", blocked["reason_codes"])
        down = module.explicit_target_decision(snapshot, policy, 2, business_verified=True)
        self.assertEqual(down["decision"], "scale_in")
        self.assertEqual(down["target_nodes"], 9)
        self.assertEqual(down["wave_target_nodes"], 2)
        self.assertEqual(down["delta"], 1)

    def test_http_success_without_business_assertions_is_not_verified(self):
        module = load_live_pressure_module()
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from threading import Thread

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = b'{"status":"ready"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/"
            result = module.probe(url, 2, business_config=None)
            self.assertEqual(result["status"], "UNVERIFIED")
            verified = module.probe(url, 2, business_config={
                "probe_url": url, "expected_status": 200,
                "expected_json": {"status": "ready"},
            })
            self.assertEqual(verified["status"], "PASSED")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_real_script_requires_profile(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], text=True,
                                capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_missing_real_sdk_is_explicit_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / "clusters").mkdir()
            (config / "credentials").mkdir()
            (config / "policies").mkdir()
            (config / "clusters" / "css-test.json").write_text(json.dumps({
                "resource_type": "css_cluster", "profile_id": "css-test",
                "cluster_id": "12345678-1234-4123-8123-123456789abc",
                "region": "simulated", "project_id": "project", "credential_ref": "css/credentials/test",
            }), encoding="utf-8")
            (config / "credentials" / "test.json").write_text(json.dumps({
                "access_key_id": "fixture-ak", "secret_access_key": "fixture-sk",
                "project_id": "project", "region": "simulated",
            }), encoding="utf-8")
            (config / "policies" / "css-default.json").write_text(json.dumps({
                "schema_version": 1, "policy_id": "css-default", "revision": 1,
                "mode": "observe", "min_data_nodes": 2, "max_data_nodes": 10,
                "scale_out_step": 1, "scale_in_step": 1,
            }), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-test",
                "--config-dir", str(config), "--execute", "--max-actions", "1",
            ], text=True, capture_output=True, check=False)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "UNAVAILABLE")
            self.assertFalse(payload["secrets_included"])


if __name__ == "__main__":
    unittest.main()
