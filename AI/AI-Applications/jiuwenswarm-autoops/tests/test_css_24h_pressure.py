import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "css-24h-pressure.py"


class Css24hPressureTests(unittest.TestCase):
    def _fixture(self, directory: Path, region: str = "la-south-2") -> Path:
        config = directory / "config"
        (config / "clusters").mkdir(parents=True)
        profile = {
            "resource_type": "css_cluster", "profile_id": "css-santiago",
            "cluster_id": "12345678-1234-4123-8123-123456789abc",
            "region": region, "project_id": "project", "credential_ref": "css/credentials/test",
        }
        (config / "clusters" / "css-santiago.json").write_text(json.dumps(profile), encoding="utf-8")
        plan = {
            "schema_version": 1, "expected_region": "la-south-2",
            "load": {"url": "", "method": "GET", "timeout_seconds": 10, "concurrency": 2,
                     "tls_verify": True},
            "phases": [{"name": "smoke", "duration_seconds": 60, "requests_per_second": 0}],
        }
        plan_path = directory / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return plan_path

    def test_default_is_plan_only_and_validates_chile_region(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan = self._fixture(directory)
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-santiago",
                "--config-dir", str(directory / "config"), "--plan", str(plan),
                "--duration-seconds", "60",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "PLAN_ONLY")
            self.assertFalse(payload["traffic_writes"])
            self.assertFalse(payload["css_writes"])

    def test_wrong_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan = self._fixture(directory, region="cn-north-4")
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-santiago",
                "--config-dir", str(directory / "config"), "--plan", str(plan),
                "--duration-seconds", "60",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not match expected region", result.stdout)

    def test_css_execute_requires_separate_confirmation(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan = self._fixture(directory)
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-santiago",
                "--config-dir", str(directory / "config"), "--plan", str(plan),
                "--duration-seconds", "60", "--css-actions", "execute",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("confirm-css-writes", result.stdout)

    def test_node_wave_is_kept_in_plan_output(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan = self._fixture(directory)
            value = json.loads(plan.read_text(encoding="utf-8"))
            value["node_wave"] = {
                "targets": [2, 10, 2], "hold_seconds": 900, "max_actions": 9
            }
            value["max_css_actions"] = 9
            plan.write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-santiago",
                "--config-dir", str(directory / "config"), "--plan", str(plan),
                "--duration-seconds", "60",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["plan"]["node_wave"]["targets"], [2, 10, 2])
            self.assertEqual(payload["plan"]["node_wave"]["max_cycles"], 1)
            self.assertEqual(payload["plan"]["max_css_actions"], 9)

    def test_repeating_node_wave_normalizes_cycle_and_total_action_budgets(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("css_24h_pressure_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan_path = self._fixture(directory)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["node_wave"] = {"targets": [2, 10, 2], "hold_seconds": 60,
                                 "max_actions": 9, "max_cycles": 3, "repeat": True}
            plan["max_css_actions"] = 27
            payload = module.validate_plan(plan, 86400, {
                "profile_id": "css-santiago", "resource_type": "css_cluster",
                "cluster_id": "12345678-1234-4123-8123-123456789abc", "region": "la-south-2",
                "project_id": "project", "credential_ref": "css/credentials/test",
            })
            self.assertEqual(payload["node_wave"]["max_cycles"], 3)
            self.assertTrue(payload["node_wave"]["repeat"])
            self.assertEqual(payload["max_css_actions"], 27)

    def test_wave_advances_only_after_target_hold_and_cycles_until_limit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("css_24h_wave_state_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        wave = {"targets": [2, 10, 2], "max_actions": 9,
                "max_cycles": 3, "repeat": True}
        blocked = module.advance_wave(
            wave, wave_index=0, cycle_index=0, cycle_actions=0, total_actions=0,
            hold_elapsed=True, target_reached=False, total_action_budget=27,
        )
        self.assertFalse(blocked["advanced"])
        next_target = module.advance_wave(
            wave, wave_index=0, cycle_index=0, cycle_actions=0, total_actions=0,
            hold_elapsed=True, target_reached=True, total_action_budget=27,
        )
        self.assertEqual(next_target["wave_index"], 1)
        next_cycle = module.advance_wave(
            wave, wave_index=2, cycle_index=0, cycle_actions=9, total_actions=9,
            hold_elapsed=True, target_reached=True, total_action_budget=27,
        )
        self.assertEqual(next_cycle["cycle_index"], 1)
        self.assertEqual(next_cycle["wave_index"], 0)
        exhausted = module.advance_wave(
            wave, wave_index=2, cycle_index=2, cycle_actions=9, total_actions=27,
            hold_elapsed=True, target_reached=True, total_action_budget=27,
        )
        self.assertFalse(exhausted["advanced"])

    def test_successful_intermediate_action_does_not_finish_wave_target(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("css_24h_wave_target_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        wave = {"targets": [2, 10, 2]}
        observation = {"records": [{
            "snapshot": {"topology": {"data_node_count": 3}},
            "decision": {"decision": "scale_out", "status": "PLANNED", "target_nodes": 3},
            "reconciliation": {"status": "SUCCEEDED", "target_nodes": 3},
        }]}
        self.assertFalse(module.observed_wave_target_reached(observation, wave, 1))
        observation["records"][0]["snapshot"]["topology"]["data_node_count"] = 10
        self.assertTrue(module.observed_wave_target_reached(observation, wave, 1))

    def test_blocked_wave_step_stops_load_but_normal_hold_does_not(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("css_24h_wave_block_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        blocked = {"records": [{"decision": {"decision": "scale_in", "status": "BLOCKED"}}]}
        hold = {"records": [{"decision": {"decision": "hold", "status": "HOLD"}}]}
        self.assertTrue(module.wave_action_blocked(blocked))
        self.assertFalse(module.wave_action_blocked(hold))

    def test_pressure_worker_keeps_sending_during_controller_wait(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("css_24h_concurrent_load_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(time.monotonic())
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        stop = threading.Event()
        state_lock = threading.Lock()
        state = {"phase_index": 0, "phase_elapsed_seconds": 0.0,
                 "phases": [], "stopped_reason": None}
        worker = threading.Thread(
            target=module.run_pressure_worker,
            kwargs={"url": f"http://127.0.0.1:{server.server_port}/",
                    "method": "GET", "headers": {}, "body": None,
                    "timeout": 1, "tls_verify": True,
                    "phases": [{"name": "test", "duration_seconds": 10,
                                "requests_per_second": 20, "concurrency": 2}],
                    "poll_interval": 1, "finish_epoch": time.time() + 10,
                    "guardrails": {"max_error_rate": 1.0,
                                   "max_p95_latency_ms": 10000, "bad_cycles": 3},
                    "state": state, "state_lock": state_lock, "stop_event": stop},
            daemon=True,
        )
        try:
            worker.start()
            time.sleep(0.3)  # models the controller blocked while reconciling a CSS action
            self.assertGreater(len(requests), 0)
            stop.set()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertTrue(state["phases"])
        finally:
            stop.set()
            server.shutdown()
            server.server_close()

    def test_execute_blocks_before_load_when_endpoint_is_unauthorized(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            plan = self._fixture(directory)
            value = json.loads(plan.read_text(encoding="utf-8"))
            value["load"]["url"] = "http://127.0.0.1:1/"
            plan.write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--profile-id", "css-santiago",
                "--config-dir", str(directory / "config"), "--plan", str(plan),
                "--duration-seconds", "60", "--execute", "--confirm-business-impact",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "BLOCKED_LOAD_PREFLIGHT")
            self.assertFalse(payload["traffic_writes"])


if __name__ == "__main__":
    unittest.main()
