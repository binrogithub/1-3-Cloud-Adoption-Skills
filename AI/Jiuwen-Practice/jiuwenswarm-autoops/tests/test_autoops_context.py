import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from autoops_context import resolve

REGISTER = Path(__file__).resolve().parents[1] / "scripts" / "autoops-context-register.py"


class AutoOpsContextTests(unittest.TestCase):
    def profile_dir(self, *profiles):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name)
        for index, profile in enumerate(profiles):
            (path / f"profile-{index}.json").write_text(json.dumps(profile), encoding="utf-8")
        self.addCleanup(directory.cleanup)
        return path

    def profile(self, profile_id="orders-test", application="orders", target="test-host-01"):
        return {
            "profile_id": profile_id,
            "application_id": application,
            "application": application,
            "display_name": application.title(),
            "target_id": target,
            "scope_id": "test-scope",
            "environment": "test",
            "services": [{
                "service_id": "orders-api",
                "aliases": ["orders"],
                "sources": [{"kind": "file", "path": "/var/log/orders/*.log"},
                            {"kind": "journal", "unit": "orders-api.service"}],
            }],
        }

    def test_resolves_application_and_preserves_provenance(self):
        result = resolve(application="orders", profile_dir=self.profile_dir(self.profile()))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["context"]["service"], "orders-api")
        self.assertEqual(result["context"]["target"]["name"], "test-host-01")
        self.assertEqual(result["context"]["provenance"]["application"], "service_profile")

    def test_resolves_application_capability_and_probe_bindings(self):
        profile = self.profile()
        profile["services"][0]["capabilities"] = {
            "ensure": {"capability": "host.ensure_service.v1", "job": "ensure-orders"}
        }
        profile["services"][0]["verification"] = {"health_url": "http://127.0.0.1/health"}
        result = resolve(application="orders", profile_dir=self.profile_dir(profile))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["context"]["capabilities"]["ensure"]["job"], "ensure-orders")
        self.assertEqual(result["context"]["verification"]["health_url"], "http://127.0.0.1/health")
        self.assertEqual(len(result["context"]["log_sources"]), 2)

    def test_resolves_application_by_display_name(self):
        profile = self.profile()
        profile["display_name"] = "订单服务"
        result = resolve(application="订单服务", profile_dir=self.profile_dir(profile))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["context"]["display_name"], "订单服务")

    def test_multiple_profiles_are_ambiguous_without_guessing(self):
        result = resolve(application="orders", profile_dir=self.profile_dir(
            self.profile("orders-test-a", target="test-host-a"),
            self.profile("orders-test-b", target="test-host-b"),
        ))
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertEqual(len(result["candidates"]), 2)

    def test_test_profile_is_hidden_by_default_and_available_explicitly(self):
        profile = self.profile("demo-test", application="demo")
        profile["visibility"] = "test"
        hidden = resolve(application="demo", profile_dir=self.profile_dir(profile))
        self.assertEqual(hidden["status"], "NOT_FOUND")
        visible = resolve(application="demo", profile_dir=self.profile_dir(profile), include_test=True)
        self.assertEqual(visible["status"], "RESOLVED")

    def test_exact_duplicate_profiles_are_collapsed(self):
        first = self.profile("orders-v1")
        second = json.loads(json.dumps(first))
        second["profile_id"] = "orders-v2"
        result = resolve(application="orders", profile_dir=self.profile_dir(first, second))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["deduplicated_profiles"], [["orders-v1", "orders-v2"]])

    def test_host_system_context_is_explicit_and_has_no_service(self):
        from autoops_context import host_system_context
        context = host_system_context()
        self.assertEqual(context["scope_kind"], "host_system")
        self.assertIsNone(context["service"])
        self.assertEqual(context["target"]["name"], "local")

    def test_unpublished_log_path_is_rejected(self):
        result = resolve(application="orders", log_path="/etc/passwd", profile_dir=self.profile_dir(self.profile()))
        self.assertEqual(result["status"], "INPUT_ERROR")
        self.assertEqual(result["error_code"], "PATH_NOT_PUBLISHED")

    def test_unpublished_target_is_rejected(self):
        result = resolve(application="orders", target="production-01", profile_dir=self.profile_dir(self.profile()))
        self.assertEqual(result["status"], "INPUT_ERROR")
        self.assertEqual(result["error_code"], "TARGET_NOT_PUBLISHED")

    def test_register_publishes_private_profile_and_resolver_reuses_it(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, str(REGISTER),
                "--profile-id", "payments-test-v1",
                "--application-id", "payments",
                "--application", "Payments API",
                "--display-name", "支付服务",
                "--application-alias", "payments-api",
                "--service", "payments-api",
                "--service-alias", "payments.service",
                "--target", "test-host-01",
                "--scope-id", "payments-test",
                "--environment", "test",
                "--journal-unit", "payments-api.service",
                "--log-path", "/var/log/payments/*.log",
                "--profile-dir", directory,
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            profile_path = Path(payload["path"])
            self.assertEqual(payload["status"], "REGISTERED")
            self.assertEqual(stat.S_IMODE(profile_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(Path(directory).stat().st_mode), 0o700)
            resolved = resolve(application="payments", profile_dir=Path(directory))
            self.assertEqual(resolved["status"], "RESOLVED")
            self.assertEqual(resolved["context"]["profile_revision"], 1)
            self.assertEqual(resolved["context"]["provenance"]["application"], "service_profile")
            self.assertEqual(resolved["context"]["log_sources"][1]["path"], "/var/log/payments/*.log")
            self.assertEqual(resolved["context"]["display_name"], "支付服务")

    def test_register_requires_monotonic_revision_and_rejects_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = [
                sys.executable, str(REGISTER),
                "--profile-id", "orders-test-v1", "--application-id", "orders",
                "--application", "orders", "--service", "orders-api",
                "--target", "test-host-01", "--scope-id", "orders-test",
                "--journal-unit", "orders-api.service", "--profile-dir", directory,
            ]
            first = subprocess.run(base, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            lower = subprocess.run(base + ["--revision", "1"], text=True, capture_output=True, check=False)
            self.assertEqual(lower.returncode, 2)
            relative = subprocess.run(base + ["--profile-id", "orders-test-v2", "--log-path", "relative.log"], text=True, capture_output=True, check=False)
            self.assertEqual(relative.returncode, 2)


if __name__ == "__main__":
    unittest.main()
