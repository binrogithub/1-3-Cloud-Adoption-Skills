import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render-alloy-profile.py"


class RenderAlloyProfileTests(unittest.TestCase):
    def profile(self):
        return {
            "schema_version": 1, "profile_id": "orders-v1", "application_id": "orders",
            "application": "orders", "environment": "prod", "target_id": "host-a",
            "scope_id": "orders-prod", "lifecycle": "active", "visibility": "customer",
            "services": [{"service_id": "orders-api", "systemd_unit": "orders-api",
                           "sources": [{"kind": "journal", "unit": "orders-api"},
                                       {"kind": "file", "path": "/var/log/orders/*.log"},
                                       {"kind": "loki", "labels": {"service": "orders-api"}}]}],
        }

    def invoke(self, profile, url="https://loki.example.internal"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "profile.json"
            output = root / "autoops.alloy"
            source.write_text(json.dumps(profile), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--profile", str(source),
                 "--loki-url", url, "--output", str(output)],
                text=True, capture_output=True, check=False)
            rendered = output.read_text(encoding="utf-8") if output.exists() else ""
            return result, rendered

    def test_renders_journal_and_file_with_published_labels(self):
        result, rendered = self.invoke(self.profile())
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["credentials_persisted"])
        self.assertIn("loki.source.journal", rendered)
        self.assertIn("loki.source.file", rendered)
        self.assertIn("file_match", rendered)
        self.assertIn('service = "orders-api"', rendered)
        self.assertIn('url = "https://loki.example.internal/loki/api/v1/push"', rendered)

    def test_rejects_unsafe_path_and_url_credentials(self):
        profile = self.profile()
        profile["services"][0]["sources"][1]["path"] = "relative/orders.log"
        result, _ = self.invoke(profile)
        self.assertEqual(result.returncode, 2)
        self.assertIn("absolute safe path", result.stdout)
        result, _ = self.invoke(self.profile(), "https://user:secret@loki.example.internal")
        self.assertEqual(result.returncode, 2)
        self.assertIn("credentials", result.stdout)

    def test_requires_service_for_multi_service_profile(self):
        profile = self.profile()
        profile["services"].append({"service_id": "payments-api", "sources": [
            {"kind": "journal", "unit": "payments-api"}]})
        result, _ = self.invoke(profile)
        self.assertEqual(result.returncode, 2)
        self.assertIn("multiple services", result.stdout)


if __name__ == "__main__":
    unittest.main()
