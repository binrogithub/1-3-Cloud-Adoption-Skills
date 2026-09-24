import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PROM = ROOT / "scripts" / "prometheus-query.py"
OPEN = ROOT / "scripts" / "opensearch-events-query.py"
FLOW = ROOT / "scripts" / "observability-investigate.py"


class Handler(BaseHTTPRequestHandler):
    prometheus_queries = []
    opensearch_requests = []
    loki_failure = False

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/loki/api/v1/query_range":
            if self.__class__.loki_failure:
                self.send_response(503)
                self.end_headers()
                return
            body = {"status": "success", "data": {"resultType": "streams", "result": []}}
            encoded = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        self.__class__.prometheus_queries.append((parsed.path, parse_qs(parsed.query)))
        body = {"status": "success", "data": {"resultType": "matrix", "result": [
            {"metric": {"__name__": "up", "service": "order-api"}, "values": [["1", "1"]]}
        ]}}
        encoded = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self.__class__.opensearch_requests.append((parsed.path, body))
        response = {"hits": {"hits": [
            {"_index": "autoops-events-2026.09.12", "_id": "evt-1",
             "_source": {"@timestamp": "2026-09-12T00:00:00Z", "service.name": "order-api",
                         "event.action": "deploy", "change.id": "chg-1"}}
        ]}}
        encoded = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args):
        pass


class ObservabilityAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def run_script(self, script, env, *args):
        return subprocess.run([sys.executable, str(script), *args], text=True,
                              capture_output=True, env=os.environ | env, check=False)

    def test_prometheus_profile_is_fixed_and_normalized(self):
        result = self.run_script(PROM, {"PROMETHEUS_BASE_URL": self.base_url},
                                 "--service", "order-api", "--profile", "service_up")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "prometheus")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["profile"], "service_up")
        self.assertIn('up{job="order-api"}', payload["query"])
        path, query = Handler.prometheus_queries[-1]
        self.assertEqual(path, "/api/v1/query_range")
        self.assertEqual(query["step"], ["60"])
        self.assertEqual(payload["series_count"], 1)
        self.assertIn(payload["data_freshness"]["status"], {"fresh", "stale", "unknown"})
        self.assertIn("query_completed_at", payload)

    def test_prometheus_accepts_shared_explicit_window(self):
        result = self.run_script(PROM, {"PROMETHEUS_BASE_URL": self.base_url},
                                 "--service", "order-api", "--profile", "service_up",
                                 "--since-minutes", "15", "--start", "2026-09-12T00:00:00Z",
                                 "--end", "2026-09-12T00:15:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["window"]["start"], "2026-09-12T00:00:00Z")
        path, query = Handler.prometheus_queries[-1]
        self.assertEqual(query["start"], ["1789171200"])
        self.assertEqual(query["end"], ["1789172100"])

    def test_prometheus_rejects_unknown_profile_before_request(self):
        before = len(Handler.prometheus_queries)
        result = self.run_script(PROM, {"PROMETHEUS_BASE_URL": self.base_url},
                                 "--service", "order-api", "--profile", "raw_promql")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(Handler.prometheus_queries), before)

    def test_opensearch_uses_allowlisted_indices_and_fields(self):
        result = self.run_script(OPEN, {"OPENSEARCH_BASE_URL": self.base_url},
                                 "--service", "order-api", "--keyword", "deploy",
                                 "--since-minutes", "1440", "--limit", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "opensearch")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["items"][0]["index"], "autoops-events-2026.09.12")
        path, body = Handler.opensearch_requests[-1]
        self.assertEqual(path, "/autoops-events-*,audit-events-*/_search")
        self.assertEqual(body["size"], 20)
        self.assertEqual(body["_source"]["includes"][0], "@timestamp")
        self.assertNotIn("match_all", json.dumps(body))
        self.assertNotIn("deploy", body["query"]["bool"]["filter"][2]["multi_match"]["fields"])
        self.assertEqual(payload["window"]["requested_minutes"], 1440)
        self.assertEqual(payload["returned_count"], 1)
        self.assertTrue(payload["pagination_complete"])
        self.assertIn("query_completed_at", payload)

    def test_opensearch_rejects_untrusted_service_before_request(self):
        before = len(Handler.opensearch_requests)
        result = self.run_script(OPEN, {"OPENSEARCH_BASE_URL": self.base_url},
                                 "--service", "order-api/_search")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(Handler.opensearch_requests), before)

    def test_opensearch_full_page_is_marked_incomplete(self):
        result = self.run_script(OPEN, {"OPENSEARCH_BASE_URL": self.base_url},
                                 "--service", "order-api", "--limit", "1",
                                 "--start", "2026-09-12T00:00:00Z",
                                 "--end", "2026-09-12T00:15:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["window"]["start"], "2026-09-12T00:00:00Z")
        self.assertEqual(payload["window"]["end"], "2026-09-12T00:15:00Z")
        self.assertEqual(payload["returned_count"], 1)
        self.assertFalse(payload["pagination_complete"])

    def run_flow_with_journal(self, line, extra_env=None, extra_args=()):
        import stat
        import tempfile

        directory = tempfile.TemporaryDirectory()
        fake = Path(directory.name) / "journalctl"
        fake.write_text(f"#!/bin/sh\nprintf '%s' '{line}'\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        # Keep the test's fake journal and HTTP endpoints independent from a
        # host-installed AutoOps datasource configuration.
        env = os.environ | {
            "PATH": f"{directory.name}:/usr/bin:/bin",
            "JIUWENSWARM_AUTOOPS_CONFIG_DIR": directory.name,
        } | (extra_env or {})
        completed = subprocess.run([sys.executable, str(FLOW), "--service", "order-api",
                                    "--since-minutes", "1440", "--limit", "20", *extra_args],
                                   text=True, capture_output=True, env=env, check=False)
        directory.cleanup()
        return completed

    def test_empty_loki_falls_back_to_local_anomaly(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T00:00:00Z host order-api[1]: ERROR timeout\\n",
            {"LOKI_BASE_URL": self.base_url, "LOKI_TIMEOUT_SECONDS": "5"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "trace_incomplete")
        self.assertEqual(payload["current_logs"]["source"], "local-journal")
        self.assertEqual(payload["current_logs"]["diagnostics"]["loki_probe"]["status"], "empty")
        self.assertTrue(payload["open_search_called"])
        self.assertEqual(payload["investigation_window"]["requested_minutes"], 1440)

    def test_clean_24_hour_window_stops_without_opensearch(self):
        completed = self.run_flow_with_journal("2026-09-12T00:00:00Z host order-api[1]: INFO healthy\\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "no_anomaly")
        self.assertEqual(payload["decision"], "stop")
        self.assertFalse(payload["open_search_called"])
        self.assertEqual(payload["investigation_window"]["requested_minutes"], 1440)

    def test_loki_failure_is_preserved_when_local_fallback_is_clean(self):
        Handler.loki_failure = True
        try:
            completed = self.run_flow_with_journal(
                "2026-09-12T00:00:00Z host order-api[1]: INFO healthy\\n",
                {"LOKI_BASE_URL": self.base_url},
            )
        finally:
            Handler.loki_failure = False
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "inconclusive")
        self.assertEqual(payload["error_code"], "LOG_EVIDENCE_INCOMPLETE")
        self.assertEqual(payload["current_logs"]["source_health"], "degraded")
        self.assertEqual(payload["current_logs"]["diagnostics"]["loki_probe"]["status"], "unavailable")
        self.assertFalse(payload["open_search_called"])

    def test_clean_logs_continue_to_metrics_for_business_symptom(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T00:00:00Z host order-api[1]: INFO healthy\\n",
            {"PROMETHEUS_BASE_URL": self.base_url},
            extra_args=("--continue-on-clean", "--since-minutes", "15"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "trace_ready")
        self.assertEqual(payload["diagnosis_status"], "INCONCLUSIVE")
        self.assertIn("metrics", payload)
        self.assertEqual(payload["metrics"]["window"]["start"], payload["investigation_window"]["start"])
        self.assertFalse(payload["open_search_called"])
        self.assertEqual(payload["historical_events"]["status"], "not_requested")

    def test_truncated_clean_window_is_inconclusive(self):
        lines = "".join(
            f"2026-09-12T00:{index:02d}:00Z host order-api[1]: INFO healthy\n"
            for index in range(20)
        )
        completed = self.run_flow_with_journal(lines, extra_args=("--limit", "2"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "inconclusive")
        self.assertEqual(payload["error_code"], "LOG_EVIDENCE_INCOMPLETE")
        self.assertFalse(payload["open_search_called"])
        self.assertTrue(payload["current_logs"]["truncated"])
        self.assertEqual(payload["current_logs"]["coverage_status"], "partial")

    def test_explicit_window_is_preserved_without_recomputing_now(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T00:00:00Z host order-api[1]: INFO healthy\\n",
            extra_args=("--start", "2026-09-12T00:00:00Z", "--end", "2026-09-12T00:15:00Z"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["investigation_window"], {
            "start": "2026-09-12T00:00:00Z", "end": "2026-09-12T00:15:00Z",
            "requested_minutes": 1440})

    def test_anomaly_triggers_previous_window_and_opensearch(self):
        completed = self.run_flow_with_journal("2026-09-12T00:00:00Z host order-api[1]: ERROR timeout\\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "trace_incomplete")
        self.assertEqual(payload["decision"], "trace")
        self.assertTrue(payload["open_search_called"])
        self.assertIn("metrics", payload)
        self.assertIn(payload["metrics"]["status"], ("ok", "empty", "unavailable"))
        self.assertEqual(payload["historical_events"]["status"], "unavailable")
        self.assertEqual(payload["investigation_window"]["requested_minutes"], 1440)

    def test_systemd_short_iso_offset_is_accepted_as_anomaly_anchor(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T08:00:00+0800 host order-api[1]: ERROR timeout\\n"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "trace")
        self.assertNotEqual(payload.get("error_code"), "ANOMALY_TIMESTAMP_MISSING")

    def test_empty_window_is_inconclusive_and_stops(self):
        completed = self.run_flow_with_journal("")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "inconclusive")
        self.assertEqual(payload["decision"], "needs_more_evidence")
        self.assertFalse(payload["open_search_called"])

    def test_empty_flow_persists_task_for_reconnect(self):
        import stat
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "journalctl"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            state_db = root / "state.db"
            result = subprocess.run(
                [sys.executable, str(FLOW), "--service", "order-api",
                 "--since-minutes", "1440"], text=True, capture_output=True,
                env=os.environ | {"PATH": f"{root}:/usr/bin:/bin",
                                  "AUTOOPS_STATE_DB": str(state_db)}, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertRegex(payload["task_id"], r"^pm-[a-f0-9]{32}$")
            sys.path.insert(0, str(ROOT / "scripts"))
            from autoops_task_store import TaskStore
            store = TaskStore(state_db)
            task = store.get(payload["task_id"])
            self.assertEqual(task["status"], "PARTIAL")
            self.assertEqual(task["payload"]["service"], "order-api")
            self.assertEqual(store.events(payload["task_id"])[-1]["event_type"], "task.result")
            store.close()

    def test_loki_backtrace_uses_first_entry_as_anchor(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T00:00:00Z host order-api[1]: ERROR first\\n"
            "2026-09-12T00:05:00Z host order-api[1]: ERROR second\\n",
            {"LOKI_BASE_URL": self.base_url, "LOKI_TIMEOUT_SECONDS": "5"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "trace_incomplete")
        self.assertEqual(payload["current_logs"]["source"], "local-journal")
        self.assertEqual(payload["current_logs"]["entries"][0]["timestamp"], "2026-09-12T00:00:00Z")

    def test_trace_exposes_candidate_root_cause_with_evidence_warning(self):
        completed = self.run_flow_with_journal(
            "2026-09-12T00:00:00Z host order-api[1]: ERROR timeout\\n",
            {"PROMETHEUS_BASE_URL": self.base_url, "OPENSEARCH_BASE_URL": self.base_url},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "trace_ready")
        assessment = payload["root_cause_assessment"]
        self.assertEqual(assessment["status"], "candidate")
        self.assertTrue(assessment["requires_independent_validation"])
        ids = {item["candidate_id"] for item in assessment["candidates"]}
        self.assertIn("recurring_log_signature", ids)
        self.assertIn("recent_change_correlation", ids)
        change = next(item for item in assessment["candidates"] if item["candidate_id"] == "recent_change_correlation")
        self.assertIn("Correlation only", change["warning"])


if __name__ == "__main__":
    unittest.main()
