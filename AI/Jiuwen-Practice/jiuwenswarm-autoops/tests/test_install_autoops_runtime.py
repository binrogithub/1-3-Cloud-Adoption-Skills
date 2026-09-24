import grp
import importlib.util
import json
import os
import pwd
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
INSTALLER = ROOT / "scripts" / "install-autoops-runtime.py"
SPEC = importlib.util.spec_from_file_location("install_autoops_runtime", INSTALLER)
install_runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_runtime)


class AutoOpsRuntimeInstallerTests(unittest.TestCase):
    def run_installer(self, root: Path, *extra: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(INSTALLER), "--source-root", str(ROOT),
             "--install-root", str(root / "install"),
             "--config-root", str(root / "etc"),
             "--state-root", str(root / "state"),
             "--systemd-root", str(root / "systemd"), *extra],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_installs_defaults_units_and_private_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.run_installer(root)
            self.assertEqual(payload["status"], ["READY"])
            self.assertEqual(payload["service_account"], ["not-managed"])
            self.assertTrue((root / "install/config/roles/project-manager.yaml").is_file())
            self.assertTrue((root / "install/config/service-profiles/autoops-demo.json").is_file())
            self.assertTrue((root / "install/config/model.env.example").is_file())
            self.assertFalse((root / "etc/model.env.example").exists())
            self.assertFalse((root / "etc/model.env").exists())
            self.assertEqual((root / "install/config/monitoring/autoops-demo-watch.json").stat().st_mode & 0o777, 0o644)
            self.assertTrue((root / "install/config/rundeck/e03-k8s-restore-order-api-job.json").is_file())
            self.assertEqual(json.loads((root / "etc/runtime.json").read_text(encoding="utf-8"))["schema_version"], 2)

    def test_css_env_is_auto_bound_only_for_one_customer_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_root = root / "etc"
            clusters = config_root / "css" / "clusters"
            clusters.mkdir(parents=True)
            (clusters / "css-santiago.json").write_text(
                json.dumps({"profile_id": "css-santiago"}), encoding="utf-8"
            )
            payload = self.run_installer(root)
            self.assertEqual(payload["css_env"]["status"], "CONFIGURED")
            self.assertEqual(
                (config_root / "css.env").read_text(encoding="utf-8"),
                "AUTOOPS_CSS_PROFILE_ID=css-santiago\n",
            )

    def test_installed_runtime_is_self_contained_and_reinstallable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            self.assertTrue((root / "install/skills/autoops-project-manager/SKILL.md").is_file())
            self.assertTrue((root / "install/skills/autoops-css-auto/SKILL.md").is_file())
            self.assertTrue((root / "install/skills/autoops-netops/SKILL.md").is_file())
            self.assertTrue((root / "install/scripts/netops-noli.py").is_file())
            self.assertTrue((root / "install/config/noli.env.example").is_file())
            self.assertTrue((root / "install/runbooks/ansible/host-inspect.yml").is_file())
            self.assertTrue((root / "install/config/autoops-agent-bootstrap.md").is_file())
            self.assertTrue((root / "install/config/systemd/jiuwenswarm-autoops-watch.service").is_file())
            self.assertTrue((root / "install/config/css/policy.example.json").is_file())
            self.assertTrue((root / "install/swarmflow/css-autoscale-v1.py").is_file())
            second = root / "second"
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--source-root", str(root / "install"),
                 "--install-root", str(second / "install"), "--config-root", str(second / "etc"),
                 "--state-root", str(second / "state"), "--systemd-root", str(second / "systemd"),
                 "--no-create-service-account", "--no-auto-configure-local-observability"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_manifest_v2_records_hashes_ownership_and_instance_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            manifest_path = root / "install/autoops-install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["instance"]["runtime_file"], str(root / "etc/runtime.json"))
            self.assertEqual(manifest["roots"]["install"], str(root / "install"))
            record = next(item for item in manifest["file_records"]
                          if item["path"] == str(root / "install/scripts/autoops_watch.py"))
            self.assertEqual(len(record["sha256"]), 64)
            self.assertEqual(record["sha256"], install_runtime.sha256_file(root / "install/scripts/autoops_watch.py"))
            self.assertIn("uid", record["ownership"])
            self.assertIn("gid", record["ownership"])
            payload = dict(manifest)
            manifest_hash = payload.pop("manifest_sha256")
            expected = install_runtime.hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            self.assertEqual(manifest_hash, expected)

    def test_v1_install_manifest_is_migrated_to_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            manifest_path = root / "install/autoops-install-manifest.json"
            manifest_path.write_text(json.dumps({
                "schema_version": 1, "manifest_sha256": "legacy-hash",
                "files": ["legacy-file"],
            }), encoding="utf-8")
            self.run_installer(root, "--no-auto-configure-local-observability")
            migrated = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 2)
            self.assertEqual(migrated["migrated_from"]["schema_version"], 1)
            self.assertEqual(migrated["migrated_from"]["manifest_sha256"], "legacy-hash")

    def test_changed_legacy_profile_is_migrated_before_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            external = root / "etc/service-profiles/autoops-demo.json"
            external.rename(root / "old-profile.json")
            installed_profile = root / "install/config/service-profiles/autoops-demo.json"
            profile = json.loads(installed_profile.read_text(encoding="utf-8"))
            profile["display_name"] = "customer-customized-name"
            installed_profile.write_text(json.dumps(profile), encoding="utf-8")
            self.run_installer(root, "--no-auto-configure-local-observability")
            migrated = json.loads((root / "etc/service-profiles/autoops-demo.json").read_text(encoding="utf-8"))
            refreshed = json.loads(installed_profile.read_text(encoding="utf-8"))
            self.assertEqual(migrated["display_name"], "customer-customized-name")
            self.assertNotEqual(refreshed["display_name"], "customer-customized-name")
            runtime = json.loads((root / "etc/runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(runtime["state_root"]), root / "state")
            self.assertTrue((root / "install/scripts/autoops_watch.py").is_file())
            self.assertTrue((root / "install/scripts/autoops_alertmanager_webhook.py").is_file())
            self.assertEqual((root / "install/scripts").stat().st_mode & 0o777, 0o755)
            self.assertTrue((root / "install/swarmflow/service-recovery-v1.py").is_file())
            self.assertTrue((root / "install/swarmflow/ro00-readonly-validation.py").is_file())
            self.assertTrue((root / "install/swarmflow/ro05-parallel-observability-v1.py").is_file())
            self.assertTrue((root / "install/swarmflow/e03-kubernetes-validation-v1.py").is_file())
            self.assertTrue((root / "state/events.jsonl").is_file())
            self.assertEqual((root / "state").stat().st_mode & 0o777, 0o750)
            unit = (root / "systemd/jiuwenswarm-autoops-watch.service").read_text()
            self.assertIn(f"WorkingDirectory={root / 'install'}", unit)
            self.assertIn(f"/state/events.jsonl", unit)
            self.assertNotIn("/root/.local", unit)
            self.assertIn("# Managed by JiuwenSwarm AutoOps installer", unit)

    def test_repeat_install_is_idempotent_and_keeps_customer_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            customer = root / "etc/authorization/preauthorization.example.json"
            customer.write_text('{"customer":true}\n', encoding="utf-8")
            unit = root / "systemd/jiuwenswarm-autoops-watch.service"
            before = unit.read_text(encoding="utf-8")
            second = self.run_installer(root)
            self.assertEqual(customer.read_text(encoding="utf-8"), '{"customer":true}\n')
            self.assertEqual(unit.read_text(encoding="utf-8"), before)
            self.assertGreaterEqual(len(second["preserved"]), 1)

    def test_repeat_install_refreshes_project_owned_runtime_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_installer(root)
            deployed = root / "install/scripts/autoops_alert_dispatch.py"
            deployed.write_text("stale project runtime\n", encoding="utf-8")
            result = self.run_installer(root)
            self.assertEqual(
                deployed.read_text(encoding="utf-8"),
                (ROOT / "scripts/autoops_alert_dispatch.py").read_text(encoding="utf-8"),
            )
            self.assertIn(str(deployed), result["updated"])

    def test_non_managed_systemd_unit_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            systemd = root / "systemd"
            systemd.mkdir()
            unit = systemd / "jiuwenswarm-autoops-watch.service"
            unit.write_text("[Unit]\nDescription=customer override\n", encoding="utf-8")
            self.run_installer(root)
            self.assertIn("customer override", unit.read_text(encoding="utf-8"))

    def test_invalid_project_policy_is_rejected_before_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for name in ("config", "scripts", "skills"):
                (source / name).mkdir(parents=True)
            (source / "config" / "monitoring").mkdir()
            (source / "config" / "kubernetes").mkdir()
            (source / "config" / "roles").mkdir()
            (source / "config" / "service-profiles").mkdir()
            (source / "config" / "authorization").mkdir()
            for relative in ("capability-registry.json", "workflow-registry.json", "ro00-compatibility-matrix.json", "autoops-input-policy.json", "observability-policy.json",
                             "project-manager-actions.json", "service-verification.json"):
                (source / "config" / relative).write_text('{"schema_version":1}\n', encoding="utf-8")
            (source / "config" / "autoops-input-policy.json").write_text(
                '{"schema_version":1,"default_scope":"host_system","default_target":"local","default_window_minutes":1440}\n', encoding="utf-8")
            (source / "config" / "service-verification.json").write_text(
                '{"schema_version":1,"services":{"demo":{}}}\n', encoding="utf-8")
            (source / "config" / "kubernetes/workloads.json").write_text(
                '{"schema_version":1,"clusters":{"dev":{"enabled":false,"context":"dev",'
                '"kubeconfig_env":"AUTOOPS_KUBECONFIG","workloads":{"demo":{"namespace":"staging",'
                '"kind":"Deployment","name":"demo","selector":"app=demo","baseline_replicas":1,'
                '"service":"demo","restore_job":"restore-demo"}}}}}\n', encoding="utf-8")
            (source / "config" / "monitoring/autoops-demo-watch.json").write_text(
                '{"schema_version":1,"kind":"WrongKind","spec":{}}\n', encoding="utf-8")
            (source / "config" / "service-profiles/demo.json").write_text(
                '{"schema_version":1,"profile_id":"demo","services":[{}]}\n', encoding="utf-8")
            (source / "config" / "authorization/preauthorization.example.json").write_text(
                '{"schema_version":1,"status":"DISABLED"}\n', encoding="utf-8")
            for name in (
                "jiuwenswarm-autoops-alert-dispatch.service",
                "jiuwenswarm-autoops-alert-dispatch.timer",
                "jiuwenswarm-autoops-alertmanager.service",
                "jiuwenswarm-autoops-watch.service",
                "jiuwenswarm-autoops-watch.timer",
            ):
                (source / "config" / "systemd").mkdir(exist_ok=True)
                (source / "config" / "systemd" / name).write_text("[Unit]\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--source-root", str(source),
                 "--install-root", str(root / "install"), "--config-root", str(root / "etc"),
                 "--state-root", str(root / "state"), "--systemd-root", str(root / "systemd")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("MonitoringPolicy", result.stdout)
            self.assertFalse((root / "install").exists())

    def test_publish_failure_rolls_back_partial_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            # The first top-level defaults can be published, then this
            # customer-created symlink makes the roles tree fail. The whole
            # attempt must leave no partial installation behind.
            (install / "config").mkdir(parents=True)
            (install / "config/roles").symlink_to(root / "customer-roles")
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--source-root", str(ROOT),
                 "--install-root", str(install), "--config-root", str(root / "etc"),
                 "--state-root", str(root / "state"), "--systemd-root", str(root / "systemd")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse((install / "config/capability-registry.json").exists())
            self.assertTrue((install / "config/roles").is_symlink())
            self.assertFalse((root / "etc").exists())
            self.assertFalse((root / "state").exists())
            self.assertFalse((root / "systemd").exists())

    def test_existing_root_account_and_state_are_safe_to_manage(self):
        root_account = pwd.getpwnam("root")
        root_group = grp.getgrnam("root")
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            event_file = state / "watch" / "events.jsonl"
            event_file.parent.mkdir(parents=True)
            event_file.write_text("{}\n", encoding="utf-8")
            foreign_link = state / "k3s-data-link"
            foreign_link.symlink_to("/tmp")
            uid, gid = install_runtime.ensure_service_account("root", "root", state)
            self.assertEqual((uid, gid), (root_account.pw_uid, root_group.gr_gid))
            install_runtime.set_state_owner(state, uid, gid)
            self.assertEqual(os.stat(event_file).st_uid, uid)
            self.assertEqual(os.stat(event_file).st_gid, gid)
            self.assertTrue(foreign_link.is_symlink())

    def test_root_service_account_does_not_modify_journal_group_membership(self):
        root_account = pwd.getpwnam("root")
        with mock.patch.object(install_runtime, "ensure_journal_access") as journal:
            install_runtime.ensure_service_account("root", "root", Path("/tmp/autoops-state"))
        journal.assert_called_once_with("root", root_account.pw_gid)

    def test_managed_config_is_readable_by_the_service_group_only(self):
        root_group = grp.getgrnam("root")
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config"
            authorization = config / "authorization"
            authorization.mkdir(parents=True)
            prometheus = config / "prometheus.env"
            prometheus.write_text("PROMETHEUS_BASE_URL=http://example.test\n", encoding="utf-8")
            runtime = config / "runtime.json"
            runtime.write_text('{"schema_version":2}\n', encoding="utf-8")
            policy = authorization / "preauthorization.json"
            policy.write_text('{"schema_version":1}\n', encoding="utf-8")
            install_runtime.set_config_access(config, root_group.gr_gid)
            self.assertEqual(config.stat().st_mode & 0o777, 0o710)
            self.assertEqual(authorization.stat().st_mode & 0o777, 0o710)
            self.assertEqual(prometheus.stat().st_mode & 0o777, 0o640)
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o640)
            self.assertEqual(policy.stat().st_mode & 0o777, 0o640)
            self.assertEqual(prometheus.stat().st_gid, root_group.gr_gid)
            self.assertEqual(runtime.stat().st_gid, root_group.gr_gid)

    def test_local_observability_discovery_configures_only_healthy_missing_sources(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = (b"ready" if self.path == "/ready" else
                        b"Prometheus is Ready." if self.path == "/-/ready" else
                        b'{"version":{"number":"2.15.0"}}')
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "config"
                config.mkdir()
                base_url = f"http://127.0.0.1:{server.server_port}"
                with mock.patch.dict(os.environ, {
                    "AUTOOPS_LOCAL_LOKI_URL": base_url,
                    "AUTOOPS_LOCAL_PROMETHEUS_URL": base_url,
                    "AUTOOPS_LOCAL_OPENSEARCH_URL": base_url,
                }, clear=False):
                    statuses = install_runtime.configure_local_observability(
                        ROOT, config, install_runtime.InstallTransaction())
                self.assertEqual(statuses, ["loki:configured", "prometheus:configured", "opensearch:configured"])
                self.assertIn('LOKI_BASE_URL="' + base_url, (config / "loki.env").read_text(encoding="utf-8"))
                self.assertIn('PROMETHEUS_BASE_URL="' + base_url, (config / "prometheus.env").read_text(encoding="utf-8"))
                self.assertIn('OPENSEARCH_BASE_URL="' + base_url, (config / "opensearch.env").read_text(encoding="utf-8"))
                preserved = config / "loki.env"
                preserved.write_text("LOKI_BASE_URL=https://customer.example\n", encoding="utf-8")
                statuses = install_runtime.configure_local_observability(
                    ROOT, config, install_runtime.InstallTransaction())
                self.assertEqual(statuses[0], "loki:preserved")
                self.assertIn("customer.example", preserved.read_text(encoding="utf-8"))
        finally:
            server.shutdown()
            server.server_close()


class ComponentBootstrapTests(unittest.TestCase):
    def test_bootstrap_pins_and_verifies_alloy(self):
        script = (ROOT / "scripts" / "bootstrap-components.sh").read_text(encoding="utf-8")
        components = (ROOT / "components.env").read_text(encoding="utf-8")
        self.assertIn("ALLOY_VERSION=1.19.2", components)
        self.assertIn("ALLOY_SHA256=99a1183c178349260fc9cda324f68b83ab3c73dd7a24ab27be5515781796adc3", components)
        self.assertIn('alloy-boringcrypto-linux-amd64.zip', script)
        self.assertIn('verify_sha256 "${alloy_archive}" "${ALLOY_SHA256}"', script)
        self.assertIn('record_sha256 "${COMPONENT_DIR}/alloy/${ALLOY_VERSION}/alloy"', script)


if __name__ == "__main__":
    unittest.main()
