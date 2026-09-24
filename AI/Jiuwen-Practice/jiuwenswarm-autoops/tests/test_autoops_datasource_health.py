import json
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoops_datasource_health import probe


class DataSourceHealthTests(unittest.TestCase):
    def setUp(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/wrong/":
                    body = b"{}"
                    content_type = "application/json"
                elif self.path == "/ready":
                    body = b"ready"
                    content_type = "text/plain"
                elif self.path == "/-/ready":
                    body = b"Prometheus is Ready."
                    content_type = "text/plain"
                else:
                    body = json.dumps({"name": "opensearch", "version": {"number": "2.15.0"}}).encode()
                    content_type = "application/json"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_requires_component_identity(self):
        for source, key in (("loki", "LOKI_BASE_URL"), ("prometheus", "PROMETHEUS_BASE_URL"),
                             ("opensearch", "OPENSEARCH_BASE_URL")):
            result = probe(source, {key: self.url})
            self.assertEqual(result["status"], "READY")
            self.assertTrue(result["identity_valid"])
            self.assertTrue(result["capability_ready"])

    def test_empty_or_missing_configuration_is_not_ready(self):
        self.assertEqual(probe("loki", {})["status"], "NOT_CONFIGURED")

    def test_http_server_with_wrong_identity_is_degraded(self):
        result = probe("opensearch", {"OPENSEARCH_BASE_URL": self.url + "/wrong"})
        self.assertEqual(result["status"], "DEGRADED")
        self.assertFalse(result["identity_valid"])
        self.assertEqual(result["error_code"], "COMPONENT_IDENTITY_INVALID")

    def test_probe_does_not_mutate_configuration(self):
        environment = {"LOKI_BASE_URL": self.url}
        result = probe("loki", environment)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(environment, {"LOKI_BASE_URL": self.url})


if __name__ == "__main__":
    unittest.main()
