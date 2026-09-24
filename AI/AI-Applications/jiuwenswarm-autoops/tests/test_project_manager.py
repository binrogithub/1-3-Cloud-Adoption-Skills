import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "scripts" / "autoops-project-manager.py"
INSTALLER = ROOT / "scripts" / "install-jiuwenswarm-autoops-skills.py"
sys.path.insert(0, str(ROOT / "scripts"))
from autoops_authorization import AuthorizationConsumed, consume_approval, load_approval
import autoops_project_manager as project_manager


def invoke(*args):
    result = subprocess.run([sys.executable, str(DISPATCHER), *args], text=True, capture_output=True, check=False)
    return result.returncode, json.loads(result.stdout)


class ProjectManagerTests(unittest.TestCase):

    def test_adapter_receives_project_manager_interpreter(self):
        completed = subprocess.CompletedProcess([], 0, stdout='{"status":"ok"}', stderr="")
        with patch("autoops_project_manager.subprocess.run", return_value=completed) as run:
            code, result = project_manager.run_adapter(["adapter"], {"EXAMPLE": "value"})
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(run.call_args.kwargs["env"]["AUTOOPS_PYTHON_EXECUTABLE"], sys.executable)
    def test_log_request_selects_e05_without_writing(self):
        code, payload = invoke("--request", "Investigate Linux error logs", "--service", "chatbot-ui")
        self.assertEqual(payload["selected_epic"], "E05")
        self.assertEqual(payload["selected_role"], "log-investigator")
        self.assertEqual(payload["execution_mode"], "inspect")
        # This test verifies routing. The adapter may return 1 when the
        # external MaaS service is unavailable; that must not invalidate E05
        # selection itself.
        self.assertIn(code, (0, 1))

    def test_runbook_requires_explicit_confirmation(self):
        code, payload = invoke("--request", "Run the host check", "--job", "host-basic-check", "--target", "test-host-01")
        self.assertEqual(code, 0)
        self.assertEqual(payload["selected_epic"], "E01")
        self.assertEqual(payload["status"], "PENDING_CONFIRMATION")
        self.assertEqual(payload["execution_mode"], "dry-run")

    def test_unknown_external_result_is_reconciling(self):
        fields = project_manager.execution_result_fields(
            {"status": "UNKNOWN", "error_code": "RESULT_UNKNOWN"}, 1
        )
        self.assertEqual(fields["status"], "RECONCILING")
        self.assertEqual(fields["execution_status"], "UNKNOWN")
        self.assertEqual(
            project_manager.execution_result_fields(
                {"status": "RUNNING", "reconciliation": True}, 0
            )["status"], "RECONCILING"
        )

    def test_service_action_routes_through_e02_then_e01(self):
        code, payload = invoke("--request", "Ensure the service is running", "--service", "autoops-demo", "--target", "test-host-01")
        self.assertEqual(code, 0)
        self.assertEqual(payload["selected_epic"], "E02")
        self.assertEqual(payload["selected_role"], "ansible-operator")
        self.assertEqual(payload["job"], "ansible-ensure-autoops-demo")
        self.assertEqual(payload["status"], "PENDING_CONFIRMATION")

    def test_service_action_job_comes_from_published_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_dir = Path(directory)
            (profile_dir / "orders.json").write_text(json.dumps({
                "schema_version": 1, "profile_id": "orders-test",
                "visibility": "customer", "lifecycle": "active",
                "application_id": "orders", "application": "orders",
                "target_id": "orders-host", "scope_id": "orders-test",
                "services": [{
                    "service_id": "orders-api", "systemd_unit": "orders-api.service",
                    "sources": [], "capabilities": {"ensure": {
                        "capability": "host.ensure_service.v1",
                        "job": "ansible-ensure-orders-api",
                    }},
                }],
            }), encoding="utf-8")
            old = os.environ.get("AUTOOPS_SERVICE_PROFILE_DIR")
            os.environ["AUTOOPS_SERVICE_PROFILE_DIR"] = directory
            try:
                self.assertEqual(project_manager.load_service_job("orders-api", "ensure", "orders-host"),
                                 "ansible-ensure-orders-api")
            finally:
                if old is None:
                    os.environ.pop("AUTOOPS_SERVICE_PROFILE_DIR", None)
                else:
                    os.environ["AUTOOPS_SERVICE_PROFILE_DIR"] = old

    def test_resolved_profile_without_action_does_not_use_legacy_demo_job(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_dir = Path(directory)
            (profile_dir / "orders.json").write_text(json.dumps({
                "schema_version": 1, "profile_id": "orders-test",
                "visibility": "customer", "lifecycle": "active",
                "application_id": "orders", "application": "orders",
                "target_id": "orders-host", "scope_id": "orders-test",
                "services": [{"service_id": "orders-api", "sources": []}],
            }), encoding="utf-8")
            old = os.environ.get("AUTOOPS_SERVICE_PROFILE_DIR")
            os.environ["AUTOOPS_SERVICE_PROFILE_DIR"] = directory
            try:
                self.assertIsNone(project_manager.load_service_job("orders-api", "ensure"))
            finally:
                if old is None:
                    os.environ.pop("AUTOOPS_SERVICE_PROFILE_DIR", None)
                else:
                    os.environ["AUTOOPS_SERVICE_PROFILE_DIR"] = old

    def test_service_action_rejects_target_outside_published_profile(self):
        code, payload = invoke("--request", "Ensure the service is running",
                               "--service", "autoops-demo", "--target", "other-host")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "INPUT_ERROR")
        self.assertNotIn("job", payload)

    def test_execute_requires_operator_created_approval(self):
        code, payload = invoke(
            "--request", "Ensure the service is running", "--service", "autoops-demo",
            "--target", "test-host-01", "--execute",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PENDING_CONFIRMATION")
        self.assertEqual(payload["error_code"], "AUTHORIZATION_REQUIRED")
        self.assertFalse(payload["changed"])

    def test_published_host_inspection_is_read_only(self):
        code, payload = invoke("--request", "只读检查 autoops-demo 服务状态",
                               "--job", "host-basic-check", "--action", "inspect",
                               "--service", "autoops-demo", "--target", "test-host-01")
        self.assertIn(code, (0, 1, 2))
        self.assertEqual(payload["capability"], "host.inspect.v1")
        self.assertEqual(payload["execution_mode"], "inspect")
        self.assertNotEqual(payload["status"], "PENDING_CONFIRMATION")

    def test_machine_output_is_forwarded_to_log_adapter(self):
        with patch("autoops_project_manager.run_adapter", return_value=(0, {"status": "ok", "entry_count": 0})) as run:
            output = io.StringIO()
            with redirect_stdout(output):
                code = project_manager.main(["--request", "查询本机 Linux 日志", "--target", "local",
                                             "--since-minutes", "5", "--machine-output"])
            payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["selected_role"], "log-investigator")
        command = run.call_args.args[0]
        self.assertIn("--machine-output", command)

    def test_tui_machine_output_environment_prevents_nested_log_chat(self):
        with patch.dict(os.environ, {"AUTOOPS_MACHINE_OUTPUT": "1"}):
            with patch("autoops_project_manager.run_adapter", return_value=(0, {"status": "empty", "entry_count": 0})) as run:
                output = io.StringIO()
                with redirect_stdout(output):
                    code = project_manager.main(["--request", "查询本机 Linux 日志", "--target", "local"])
                payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["adapter_result"]["status"], "empty")
        self.assertIn("--machine-output", run.call_args.args[0])

    def test_approval_is_one_time_under_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            approval_dir = Path(directory)
            approval = approval_dir / "approval-test.json"
            approval.write_text(json.dumps({
                "status": "APPROVED", "task_id": "task-1", "job": "host-basic-check",
                "target": "test-host-01", "expires_at": 4102444800,
            }), encoding="utf-8")
            old = os.environ.get("AUTOOPS_AUTHORIZATION_DIR")
            os.environ["AUTOOPS_AUTHORIZATION_DIR"] = directory
            try:
                status, record = load_approval("approval-test", task_id="task-1", job="host-basic-check", target="test-host-01")
                self.assertEqual(status, "APPROVED")
                consume_approval("approval-test", record)
                status, _ = load_approval("approval-test", task_id="task-1", job="host-basic-check", target="test-host-01")
                self.assertEqual(status, "AUTHORIZATION_DENIED")
                with self.assertRaises(AuthorizationConsumed):
                    consume_approval("approval-test", record)
            finally:
                if old is None:
                    os.environ.pop("AUTOOPS_AUTHORIZATION_DIR", None)
                else:
                    os.environ["AUTOOPS_AUTHORIZATION_DIR"] = old

    def test_expired_approval_cannot_be_consumed_under_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            approval_dir = Path(directory)
            approval = approval_dir / "approval-expired.json"
            approval.write_text(json.dumps({
                "status": "APPROVED", "task_id": "task-1", "job": "host-basic-check",
                "target": "test-host-01", "expires_at": 1,
            }), encoding="utf-8")
            old = os.environ.get("AUTOOPS_AUTHORIZATION_DIR")
            os.environ["AUTOOPS_AUTHORIZATION_DIR"] = directory
            try:
                status, record = load_approval("approval-expired", task_id="task-1", job="host-basic-check", target="test-host-01")
                self.assertEqual(status, "AUTHORIZATION_DENIED")
                with self.assertRaises(AuthorizationConsumed):
                    consume_approval("approval-expired", record)
            finally:
                if old is None:
                    os.environ.pop("AUTOOPS_AUTHORIZATION_DIR", None)
                else:
                    os.environ["AUTOOPS_AUTHORIZATION_DIR"] = old

    def test_unknown_request_never_selects_a_role(self):
        code, payload = invoke("--request", "Change arbitrary kernel settings")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "UNSUPPORTED")
        self.assertIsNone(payload["selected_role"])

    def test_observation_request_never_silently_reads_a_remote_target_locally(self):
        code, payload = invoke("--request", "Investigate Linux error logs", "--service", "autoops-demo",
                               "--target", "production-host-01")
        self.assertEqual(code, 1)
        self.assertEqual(payload["selected_epic"], "E05")
        self.assertEqual(payload["status"], "UNAVAILABLE")
        self.assertEqual(payload["error_code"], "TARGET_UNSUPPORTED")

    def test_application_profile_supplies_service_context_for_logs(self):
        code, payload = invoke("--request", "查看 demo 日志", "--application", "demo", "--limit", "5",
                               "--include-test-profiles")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["selected_epic"], "E05")
        self.assertEqual(payload["context"]["status"], "RESOLVED")
        self.assertEqual(payload["context"]["context"]["service"], "autoops-demo")

    def test_host_linux_log_request_does_not_require_service(self):
        code, payload = invoke("--request", "运维 Linux 系统日志")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["selected_epic"], "E05")
        self.assertEqual(payload["selected_role"], "log-investigator")
        self.assertEqual(payload["intent"]["scope"]["kind"], "host_system")
        self.assertIsNone(payload["intent"]["scope"]["service_ref"])
        self.assertEqual(payload["intent"]["time"]["requested_minutes"], 1440)
        self.assertEqual(payload["user_view"]["scope"], "本机 Linux 系统日志")
        self.assertEqual(payload["user_view"]["mode"], "只读诊断")

    def test_kubernetes_request_routes_to_e03_without_guessing_scope(self):
        code, payload = invoke("--request", "检查 Kubernetes Deployment 副本和 Pod 状态",
                               "--cluster", "autoops-development",
                               "--workload", "staging/orders/order-api")
        self.assertEqual(code, 1)  # the published development cluster is disabled by default
        self.assertEqual(payload["selected_epic"], "E03")
        self.assertEqual(payload["selected_role"], "kubernetes-operator")
        self.assertEqual(payload["capability"], "k8s.inspect.v1")
        self.assertEqual(payload["adapter_result"]["error_code"], "CLUSTER_NOT_ENABLED")
        self.assertNotIn("context", payload)

    def test_kubernetes_request_requires_published_scope(self):
        code, payload = invoke("--request", "检查 Kubernetes Pod 状态")
        self.assertEqual(code, 2)
        self.assertEqual(payload["selected_epic"], "E03")
        self.assertEqual(payload["status"], "INPUT_ERROR")

    def test_kubernetes_restore_requires_confirmation_before_write(self):
        code, payload = invoke("--request", "恢复 Kubernetes Deployment 副本数",
                               "--cluster", "autoops-development",
                               "--workload", "staging/orders/order-api",
                               "--target", "test-host-01")
        self.assertEqual(code, 0)
        self.assertEqual(payload["selected_epic"], "E03")
        self.assertEqual(payload["capability"], "k8s.restore_replicas.v1")
        self.assertEqual(payload["status"], "PENDING_CONFIRMATION")
        self.assertEqual(payload["execution_mode"], "dry-run")

    def test_host_target_followup_is_not_a_service(self):
        code, payload = invoke("--request", "查询本机系统日志", "--service", "local")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["intent"]["scope"]["kind"], "host_system")
        self.assertIsNone(payload["intent"]["scope"]["service_ref"])

    def test_metrics_request_selects_e04_capability(self):
        code, payload = invoke("--request", "检查 order-api 指标和延迟", "--service", "order-api")
        self.assertIn(code, (0, 1))  # the development host may have Prometheus configured
        self.assertEqual(payload["selected_epic"], "E04")
        self.assertEqual(payload["selected_role"], "metrics-observer")
        self.assertEqual(payload["capability"], "metrics.query.v1")

    def test_metric_audit_is_not_misclassified_as_events(self):
        code, payload = invoke("--request", "latency anomaly audit for order-api", "--service", "order-api", "--profile", "service_latency")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["selected_epic"], "E04")
        self.assertEqual(payload["selected_role"], "metrics-observer")

    def test_explicit_error_profile_overrides_log_word(self):
        code, payload = invoke("--request", "error budget pre-check for order-api", "--service", "order-api", "--profile", "service_errors")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["selected_epic"], "E04")
        self.assertEqual(payload["selected_role"], "metrics-observer")

    def test_natural_language_24_hour_window_is_preserved(self):
        code, payload = invoke("--request", "检查 order-api 最近24小时指标", "--service", "order-api")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["selected_epic"], "E04")
        self.assertEqual(payload["adapter_result"]["window"]["requested_minutes"], 1440)

    def test_composite_observability_passes_one_exact_window_to_child(self):
        commands = []
        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("AUTOOPS_STATE_DB")
            os.environ["AUTOOPS_STATE_DB"] = str(Path(directory) / "state.db")
            try:
                with patch.object(project_manager, "run_adapter",
                                  side_effect=lambda command, _env: (commands.append(command) or
                                                                       (0, {"status": "no_anomaly"}))):
                    code = project_manager.main([
                        "--request", "调查 order-api 根因", "--service", "order-api",
                        "--since-minutes", "15",
                    ])
            finally:
                if old_db is None:
                    os.environ.pop("AUTOOPS_STATE_DB", None)
                else:
                    os.environ["AUTOOPS_STATE_DB"] = old_db
        self.assertEqual(code, 0)
        self.assertEqual(len(commands), 1)
        command = commands[0]
        self.assertIn("--task-id", command)
        self.assertRegex(command[command.index("--task-id") + 1], r"^pm-[a-f0-9]{32}$")
        self.assertEqual(command[command.index("--since-minutes") + 1], "15")
        start_index = command.index("--start")
        end_index = command.index("--end")
        self.assertEqual(end_index, start_index + 2)
        self.assertLess(start_index, end_index)

    def test_composite_observability_exposes_published_route_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("AUTOOPS_STATE_DB")
            os.environ["AUTOOPS_STATE_DB"] = str(Path(directory) / "state.db")
            try:
                with patch.object(project_manager, "run_adapter",
                                  return_value=(0, {"status": "no_anomaly", "entry_count": 0})):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = project_manager.main([
                            "--request", "调查 order-api 根因", "--service", "order-api",
                            "--since-minutes", "15",
                        ])
            finally:
                if old_db is None:
                    os.environ.pop("AUTOOPS_STATE_DB", None)
                else:
                    os.environ["AUTOOPS_STATE_DB"] = old_db
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["capability"], "observability.investigate.v1")
        self.assertEqual(payload["capabilities"], [
            "logs.query.v2", "metrics.query.v1", "events.search.v1",
        ])

    def test_business_symptom_continues_from_clean_logs_to_metrics(self):
        commands = []
        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("AUTOOPS_STATE_DB")
            os.environ["AUTOOPS_STATE_DB"] = str(Path(directory) / "state.db")
            try:
                with patch.object(project_manager, "run_adapter",
                                  side_effect=lambda command, _env: (commands.append(command) or
                                                                       (0, {"status": "trace_ready"}))):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = project_manager.main([
                            "--request", "订单页面打不开，请找原因", "--service", "order-api",
                            "--since-minutes", "15",
                        ])
            finally:
                if old_db is None:
                    os.environ.pop("AUTOOPS_STATE_DB", None)
                else:
                    os.environ["AUTOOPS_STATE_DB"] = old_db
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["capability"], "observability.investigate.v1")
        self.assertEqual(payload["capabilities"], ["logs.query.v2", "metrics.query.v1"])
        self.assertIn("--continue-on-clean", commands[0])

    def test_history_request_selects_e06_capability(self):
        code, payload = invoke("--request", "查询 order-api 最近的发布历史事件", "--service", "order-api")
        self.assertEqual(code, 1)  # datasource is not configured in the unit test environment
        self.assertEqual(payload["selected_epic"], "E06")
        self.assertEqual(payload["selected_role"], "event-investigator")
        self.assertEqual(payload["capability"], "events.search.v1")

    def test_installer_exposes_all_tui_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.yaml"
            config.write_text("modes:\n  team:\n    jiuwen_team:\n      workspace:\n        enabled: true\npermissions:\n  enabled: true\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(INSTALLER), "--skills-dir", str(Path(directory) / "skills"), "--config-file", str(config), "--deployment-mode", "full-access-test"], text=True, capture_output=True, check=True)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY")
            for name in payload["installed"]:
                self.assertTrue((Path(directory) / "skills" / name / "SKILL.md").is_file())
            text = config.read_text(encoding="utf-8")
            self.assertIn("enable_swarmflow: true", text)
            self.assertIn("enable_permissions: false", text)
            self.assertIn("enabled: false", text)
            self.assertIn("'*': allow", text)
            self.assertTrue((Path(directory) / "config.yaml.autoops.bak").is_file())

    def test_installer_preserves_customer_permissions_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.yaml"
            config.write_text("permissions:\n  enabled: true\n", encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(INSTALLER), "--skills-dir", str(Path(directory) / "skills"),
                "--config-file", str(config),
            ], text=True, capture_output=True, check=True)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["runtime"]["deployment_mode"], "preserve-existing")
            self.assertEqual(payload["runtime"]["permission_policy"], "preserved")
            self.assertIn("permissions:\n  enabled: true", config.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
