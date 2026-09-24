import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.observability_env import load_observability_environment


class ObservabilityEnvironmentTests(unittest.TestCase):
    def test_unreadable_optional_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.observability_env.Path.is_file", side_effect=PermissionError("denied")):
                env = load_observability_environment({"JIUWENSWARM_AUTOOPS_CONFIG_DIR": directory})
        self.assertEqual(env["JIUWENSWARM_AUTOOPS_CONFIG_DIR"], directory)

    def test_loads_allowlisted_values_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            (local / "prometheus.env").write_text(
                'PROMETHEUS_BASE_URL="http://127.0.0.1:9090"\n'
                'PROMETHEUS_TIMEOUT_SECONDS=5\n'
                'UNSAFE=$(touch /tmp/autoops-env-should-not-exist)\n', encoding="utf-8")
            env = load_observability_environment({"JIUWENSWARM_AUTOOPS_CONFIG_DIR": str(local)})
            self.assertEqual(env["PROMETHEUS_BASE_URL"], "http://127.0.0.1:9090")
            self.assertEqual(env["PROMETHEUS_TIMEOUT_SECONDS"], "5")
            self.assertNotIn("UNSAFE", env)

    def test_process_environment_overrides_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            (local / "prometheus.env").write_text(
                'PROMETHEUS_BASE_URL="http://stale.example"\n', encoding="utf-8")
            env = load_observability_environment({
                "JIUWENSWARM_AUTOOPS_CONFIG_DIR": str(local),
                "PROMETHEUS_BASE_URL": "http://test.example",
            })
            self.assertEqual(env["PROMETHEUS_BASE_URL"], "http://test.example")

    def test_default_deployment_config_is_loaded_after_install(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory)
            (deployment / "opensearch.env").write_text(
                'OPENSEARCH_BASE_URL="http://opensearch.example:9200"\n',
                encoding="utf-8")
            with patch("scripts.observability_env.DEFAULT_DEPLOYMENT_CONFIG_DIR", deployment):
                env = load_observability_environment({})
            self.assertEqual(env["OPENSEARCH_BASE_URL"], "http://opensearch.example:9200")

    def test_default_deployment_config_wins_over_repository_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory)
            (deployment / "prometheus.env").write_text(
                'PROMETHEUS_BASE_URL="http://installed.example:9090"\n',
                encoding="utf-8")
            with patch("scripts.observability_env.ROOT", deployment / "checkout"), \
                    patch("scripts.observability_env.DEFAULT_DEPLOYMENT_CONFIG_DIR", deployment):
                fallback = deployment / "checkout/config/local"
                fallback.mkdir(parents=True)
                (fallback / "prometheus.env").write_text(
                    'PROMETHEUS_BASE_URL="http://development.example:9090"\n',
                    encoding="utf-8")
                env = load_observability_environment({})
            self.assertEqual(env["PROMETHEUS_BASE_URL"], "http://installed.example:9090")


if __name__ == "__main__":
    unittest.main()
