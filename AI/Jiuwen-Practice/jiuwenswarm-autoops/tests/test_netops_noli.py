"""End-to-end read-only NetOps routing against a local NOLI API fixture."""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "netops-noli.py"
DISPATCHER = ROOT / "scripts" / "autoops-project-manager.py"
sys.path.insert(0, str(ROOT / "scripts"))
from autoops_routing import route_request
from observability_env import load_observability_environment

spec = importlib.util.spec_from_file_location("netops_noli", ADAPTER)
netops = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(netops)


class NoliFixture(BaseHTTPRequestHandler):
    calls: list[tuple[str, str, str]] = []
    coverage = 100
    index_available = True
    include_incidents = True
    nodata = False
    sensors_total_override = None
    generated_at_age_seconds = 0
    malformed_groups = False
    delay_seconds = 0

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        self.calls.append(("GET", self.path, self.headers.get("Authorization", "")))
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.headers.get("Authorization") != "Bearer fixture-token":
            self.send_response(401)
            self.end_headers()
            return
        path = urlsplit(self.path)
        if path.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/api/noc/board?window=60m")
            self.end_headers()
            return
        if path.path == "/oversized":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"x" * (netops.MAX_BYTES + 1))
            return
        if path.path == "/api/noc/board":
            payload = {
                "window": parse_qs(path.query).get("window", [None])[0],
                "generated_at": (datetime.now(timezone.utc) - timedelta(
                    seconds=self.generated_at_age_seconds)).isoformat(),
                "index_available": self.index_available,
                "sensors_total": (self.sensors_total_override if self.sensors_total_override is not None else
                                  (0 if self.malformed_groups else 1)),
                "coverage_pct": self.coverage,
                "gap_count": 0 if self.coverage == 100 else 1,
                "groups": (None if self.malformed_groups else
                           [{"status": "nodata" if self.nodata else "ok",
                             "sensors": ([] if self.sensors_total_override == 0 else
                                         [{"id": "a10-1", "status": "nodata" if self.nodata else "ok"}])}]),
                "incidents": [
                    {"id": "pool|KAN-SMS#2026-09-24T00:00:00Z", "key": "pool|KAN-SMS",
                     "label": "KAN-SMS", "severity": "critical", "open": True,
                     "opened_at": "2026-09-24T00:00:00Z", "closed_at": None,
                     "alerts": 4, "sensors": [{"id": "a10-1", "name": "A10 pool"}]},
                    {"id": "pool|OTHER#2026-09-24T00:00:00Z", "key": "pool|OTHER",
                     "label": "OTHER", "severity": "warning", "open": False,
                     "opened_at": "2026-09-24T00:00:00Z", "closed_at": "2026-09-24T01:00:00Z",
                     "alerts": 1, "sensors": []},
                ] if self.include_incidents else [],
            }
        elif path.path == "/api/noc/incident":
            payload = {"agent": {"state": "investigating"},
                       "timeline": [{"message": "pool errors observed"}],
                       "findings": [{"summary": "A10 pool warning"}],
                       "recommendation": {"kind": "inspect"}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        self.calls.append(("POST", self.path, self.headers.get("Authorization", "")))
        self.send_response(405)
        self.end_headers()


class NetOpsNoliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), NoliFixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        NoliFixture.calls = []
        NoliFixture.coverage = 100
        NoliFixture.index_available = True
        NoliFixture.include_incidents = True
        NoliFixture.nodata = False
        NoliFixture.sensors_total_override = None
        NoliFixture.generated_at_age_seconds = 0
        NoliFixture.malformed_groups = False
        NoliFixture.delay_seconds = 0

    def env(self, token="fixture-token"):
        return {**os.environ, "NOLI_BASE_URL": self.url,
                "NOLI_BEARER_TOKEN": token, "NOLI_TIMEOUT_SECONDS": "3"}

    def run_json(self, command, env):
        result = subprocess.run([sys.executable, *map(str, command)], cwd=ROOT,
                                env=env, text=True, capture_output=True, check=False)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_explicit_network_route_and_css_capacity_boundary(self):
        route = route_request("查看 NOLI A10 KAN-SMS 网络日志和告警", service="KAN-SMS")
        self.assertEqual(route["selected_epics"], ["NETOPS"])
        self.assertEqual(route["primary_role"], "netops")
        self.assertEqual(route["selected_capabilities"], ["netops.incidents.read.v1"])
        self.assertEqual(route_request("排查本机 Linux 日志")["primary_epic"], "E05")
        self.assertEqual(route_request("CSS 数据节点扩容")["primary_epic"], "CSS")

    def test_project_manager_reads_only_board_and_exact_incident(self):
        incident_id = "pool|KAN-SMS#2026-09-24T00:00:00Z"
        with tempfile.TemporaryDirectory() as temp:
            env = self.env()
            env["AUTOOPS_STATE_DB"] = str(Path(temp) / "state.db")
            code, result = self.run_json([
                DISPATCHER, "--request", "查看 NOLI A10 KAN-SMS 网络事件", "--since-minutes", "480",
                "--netops-pool", "KAN-SMS", "--netops-incident-id", incident_id,
                "--machine-output"], env)
        self.assertEqual(code, 0)
        self.assertEqual(result["selected_role"], "netops")
        self.assertEqual(result["status"], "anomalies_found")
        self.assertEqual(result["adapter_result"]["total_matches"], 1)
        self.assertEqual(result["adapter_result"]["incidents"][0]["id"], incident_id)
        self.assertIn("dossier", result["adapter_result"])
        self.assertEqual(len(NoliFixture.calls), 2)
        self.assertTrue(all(method == "GET" and token == "Bearer fixture-token"
                            for method, _, token in NoliFixture.calls))
        self.assertIn("window=480m", NoliFixture.calls[0][1])
        self.assertNotIn("fixture-token", json.dumps(result))

    def test_network_write_is_blocked_without_noli_call(self):
        with tempfile.TemporaryDirectory() as temp:
            env = self.env()
            env["AUTOOPS_STATE_DB"] = str(Path(temp) / "state.db")
            code, result = self.run_json([
                DISPATCHER, "--request", "重启 NOLI A10 KAN-SMS 池节点", "--execute",
                "--machine-output"], env)
        self.assertEqual(code, 2)
        self.assertEqual(result["selected_role"], "netops")
        self.assertEqual(result["error_code"], "NETOPS_ACTION_NOT_PUBLISHED")
        self.assertFalse(result["changed"])
        self.assertEqual(NoliFixture.calls, [])

    def test_missing_configuration_and_auth_are_distinct(self):
        with self.assertRaises(netops.AdapterError) as missing:
            netops.inspect(minutes=60, limit=5, pool=None, incident_id=None, environment={})
        self.assertEqual(missing.exception.status, "NOT_CONFIGURED")
        code, payload = self.run_json([ADAPTER, "--window-minutes", "60"], self.env(token="wrong"))
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "AUTH_FAILED")
        self.assertNotIn("wrong", json.dumps(payload))

    def test_customer_noli_env_and_capability_health(self):
        with tempfile.TemporaryDirectory() as temp:
            config_dir = Path(temp)
            (config_dir / "noli.env").write_text(
                'NOLI_BASE_URL="https://noli.example.internal"\n'
                'NOLI_BEARER_TOKEN="fixture-token"\n', encoding="utf-8")
            env = {"JIUWENSWARM_AUTOOPS_CONFIG_DIR": temp}
            loaded = load_observability_environment(env)
            self.assertEqual(loaded["NOLI_BASE_URL"], "https://noli.example.internal")
            self.assertEqual(loaded["NOLI_BEARER_TOKEN"], "fixture-token")
            checked = subprocess.run(
                [sys.executable, str(ROOT / "scripts/autoops-capability-health.py"),
                 "--capability", "netops.incidents.read.v1", "--runtime"],
                cwd=ROOT, env={**os.environ, **env, "NOLI_BASE_URL": "", "NOLI_BEARER_TOKEN": ""},
                text=True, capture_output=True, check=False)
            payload = json.loads(checked.stdout)
            self.assertEqual(checked.returncode, 1)
            self.assertEqual(payload["results"][0]["status"], "NOT_CONFIGURED")
            self.assertNotIn("fixture-token", checked.stdout)

    def test_partial_coverage_and_empty_incident_never_claim_health(self):
        NoliFixture.coverage = 50
        result = netops.inspect(minutes=60, limit=5, pool="KAN-SMS", incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["complete"])
        NoliFixture.coverage = 100
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id="missing",
                                environment=self.env())
        self.assertEqual(result["status"], "empty")

    def test_clean_result_requires_complete_fresh_coverage_and_no_nodata(self):
        NoliFixture.include_incidents = False
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "no_anomaly")
        NoliFixture.nodata = True
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(result["nodata"])

    def test_unknown_pool_is_empty_not_healthy(self):
        NoliFixture.include_incidents = False
        result = netops.inspect(minutes=60, limit=5, pool="UNKNOWN", incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "empty")
        self.assertTrue(result["complete"])

    def test_insecure_remote_http_and_redirect_are_rejected(self):
        with self.assertRaises(netops.AdapterError) as insecure:
            netops.base_url({"NOLI_BASE_URL": "http://example.com"})
        self.assertEqual(insecure.exception.code, "NOLI_HTTPS_REQUIRED")
        self.assertIsNone(netops.NoRedirect().redirect_request(None, None, 302, "", {},
                                                                 "https://other.example/"))
        with self.assertRaises(netops.AdapterError) as redirect:
            netops.fetch_json(self.url + "/redirect", "fixture-token", 3)
        self.assertEqual(redirect.exception.code, "NOLI_HTTP_ERROR")
        self.assertEqual(len(NoliFixture.calls), 1)

    def test_oversized_payload_is_rejected(self):
        with self.assertRaises(netops.AdapterError) as oversized:
            netops.fetch_json(self.url + "/oversized", "fixture-token", 3)
        self.assertEqual(oversized.exception.code, "NOLI_RESPONSE_TOO_LARGE")

    def test_connection_failure_and_timeout_are_unavailable(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            unused_port = sock.getsockname()[1]
        with self.assertRaises(netops.AdapterError) as disconnected:
            netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                           environment={"NOLI_BASE_URL": f"http://127.0.0.1:{unused_port}",
                                        "NOLI_BEARER_TOKEN": "fixture-token",
                                        "NOLI_TIMEOUT_SECONDS": "1"})
        self.assertEqual(disconnected.exception.status, "UNAVAILABLE")
        self.assertEqual(disconnected.exception.code, "NOLI_REQUEST_FAILED")

        NoliFixture.delay_seconds = 2
        with self.assertRaises(netops.AdapterError) as timeout:
            netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                           environment={**self.env(), "NOLI_TIMEOUT_SECONDS": "1"})
        self.assertEqual(timeout.exception.status, "UNAVAILABLE")
        self.assertEqual(timeout.exception.code, "NOLI_REQUEST_FAILED")

    def test_empty_sensor_set_stale_board_and_malformed_board_are_inconclusive(self):
        NoliFixture.include_incidents = False
        NoliFixture.sensors_total_override = 0
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["complete"])
        self.assertTrue(result["invalid_board"])

        NoliFixture.sensors_total_override = None
        NoliFixture.generated_at_age_seconds = 301
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["complete"])

        NoliFixture.generated_at_age_seconds = 0
        NoliFixture.malformed_groups = True
        result = netops.inspect(minutes=60, limit=5, pool=None, incident_id=None,
                                environment=self.env())
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["complete"])
        self.assertTrue(result["invalid_board"])


if __name__ == "__main__":
    unittest.main()
