import sys
import unittest
import asyncio
import importlib.util
import types
import io
import os
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoops_contract import validate_route, validate_step_result
from autoops_routing import route_request

WORKFLOW_SPEC = importlib.util.spec_from_file_location(
    "service_recovery_workflow", ROOT / "swarmflow" / "service-recovery-v1.py"
)
workflow = importlib.util.module_from_spec(WORKFLOW_SPEC)
WORKFLOW_SPEC.loader.exec_module(workflow)
PM_SPEC = importlib.util.spec_from_file_location(
    "autoops_project_manager", ROOT / "scripts" / "autoops_project_manager.py"
)
project_manager = importlib.util.module_from_spec(PM_SPEC)
PM_SPEC.loader.exec_module(project_manager)


class AutoOpsRoutingTests(unittest.TestCase):
    def route(self, request, **kwargs):
        return validate_route(route_request(request, **kwargs))

    def test_application_name_is_not_kubernetes_resource(self):
        result = self.route("查看 podcast 服务日志", service="podcast")
        self.assertEqual(result["intent"], "investigate")
        self.assertEqual(result["selected_epics"], ["E05"])

    def test_explicit_log_and_metric_requirements_are_preserved(self):
        result = self.route("排查服务日志和延迟指标", service="order-api")
        self.assertEqual(result["plan_kind"], "multi")
        self.assertEqual(result["selected_epics"], ["E05", "E04"])
        self.assertEqual(result["selected_capabilities"], ["logs.query.v2", "metrics.query.v1"])
        self.assertEqual(result["native_workflow"]["ref"], "ro05-parallel-observability-v1")
        self.assertEqual(result["native_workflow"]["asset"], "swarmflow/ro05-parallel-observability-v1.py")

    def test_root_cause_selects_all_evidence_domains(self):
        result = self.route("调查 order-api 根因", service="order-api")
        self.assertEqual(result["selected_epics"], ["E05", "E04", "E06"])
        self.assertEqual(result["native_workflow"]["capabilities"], [
            "logs.query.v2", "metrics.query.v1", "events.search.v1",
        ])

    def test_explicit_job_is_primary_when_request_mentions_cpu(self):
        result = self.route("执行 host-basic-check 检查 CPU", job="host-basic-check",
                            service="order-api")
        self.assertEqual(result["primary_epic"], "E01")
        self.assertEqual(result["selected_epics"][0], "E01")

    def test_verification_does_not_become_remediation(self):
        result = self.route("验证刚才修复后的业务是否恢复", service="order-api")
        self.assertEqual(result["intent"], "verify")
        self.assertEqual(result["selected_epics"], ["E09"])

    def test_kubernetes_recovery_with_verification_keeps_e03_primary(self):
        result = self.route("恢复 Kubernetes order-api Deployment 副本并验证业务健康",
                            service="order-api")
        self.assertEqual(result["intent"], "remediate")
        self.assertEqual(result["selected_epics"], ["E03", "E01", "E09"])
        self.assertEqual(result["selected_capabilities"][0], "k8s.restore_replicas.v1")

    def test_negative_kubernetes_constraint_is_retained(self):
        result = self.route("不要查询 Pod，只看本机 Linux 日志")
        self.assertEqual(result["selected_epics"], ["E05"])
        self.assertEqual(result["excluded_candidates"][0]["candidate"], "E03")

    def test_business_symptom_selects_diagnostic_capabilities(self):
        result = self.route("订单页面打不开，请找原因", service="order-api")
        self.assertEqual(result["intent"], "diagnose")
        self.assertEqual(result["selected_epics"], ["E05", "E04"])

    def test_unknown_request_has_no_capability(self):
        result = self.route("Change arbitrary kernel settings")
        self.assertEqual(result["plan_kind"], "none")
        self.assertEqual(result["selected_epics"], [])
        self.assertIn("published_capability", result["missing_inputs"])

    def test_route_result_rejects_mismatched_primary(self):
        result = route_request("查看服务日志", service="orders")
        result["primary_epic"] = "E04"
        with self.assertRaises(ValueError):
            validate_route(result)

    def test_recovered_requires_success(self):
        with self.assertRaises(ValueError):
            validate_step_result({"status": "FAILED", "recovery_status": "recovered"})

    def test_root_cause_uses_composite_adapter_with_requested_window(self):
        commands = []

        def fake_adapter(command, _environment):
            commands.append(command)
            return 0, {"status": "no_anomaly", "entry_count": 0}

        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("AUTOOPS_STATE_DB")
            os.environ["AUTOOPS_STATE_DB"] = str(Path(directory) / "state.db")
            output = io.StringIO()
            try:
                with patch.object(project_manager, "run_adapter", side_effect=fake_adapter), redirect_stdout(output):
                    code = project_manager.main([
                        "--request", "调查 order-api 根因", "--service", "order-api",
                        "--since-minutes", "30",
                    ])
            finally:
                if old_db is None:
                    os.environ.pop("AUTOOPS_STATE_DB", None)
                else:
                    os.environ["AUTOOPS_STATE_DB"] = old_db
        payload = __import__("json").loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["routing"]["selected_epics"], ["E05", "E04", "E06"])
        self.assertEqual(payload["capabilities"], ["logs.query.v2", "metrics.query.v1", "events.search.v1"])
        self.assertEqual(commands[0][commands[0].index("--since-minutes") + 1], "30")

    def test_workflow_stops_on_failed_required_expert(self):
        calls = []
        options_seen = []
        fake = types.ModuleType("swarmflow")

        async def agent(prompt, **options):
            calls.append(options["label"])
            options_seen.append(options)
            return {"task_id": "t", "execution_status": "FAILED"}

        fake.agent = agent
        fake.human = lambda *args, **kwargs: None
        fake.phase = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(workflow.run({"task": "inspect logs", "task_id": "t"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_phase"], "inspect")
        self.assertEqual(calls, ["runbook-operator"])
        self.assertNotIn("agent_type", options_seen[0])

    def test_workflow_rejects_expert_result_for_another_task(self):
        fake = types.ModuleType("swarmflow")

        async def agent(prompt, **options):
            return {"task_id": "different-task", "execution_status": "SUCCEEDED"}

        fake.agent = agent
        fake.human = lambda *args, **kwargs: None
        fake.phase = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(workflow.run({"task": "inspect logs", "task_id": "t"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_phase"], "inspect")

    def test_workflow_accepts_phase_specific_diagnosis_status_without_execution_status(self):
        self.assertTrue(workflow._step_ok(
            {"task_id": "t", "diagnosis_status": "confirmed"},
            "diagnosis_status", "t"))

    def test_workflow_requires_verifier_pass_before_completed(self):
        calls = []
        options_seen = []
        fake = types.ModuleType("swarmflow")

        async def agent(prompt, **options):
            label = options["label"]
            calls.append(label)
            options_seen.append(options)
            values = {
                "runbook-operator": {"task_id": "t", "execution_status": "SUCCEEDED"},
                "log-investigator": {"task_id": "t", "execution_status": "SUCCEEDED", "diagnosis_status": "confirmed"},
                "ansible-operator": {"task_id": "t", "execution_status": "SUCCEEDED"},
                "recovery-verifier": {"task_id": "t", "execution_status": "SUCCEEDED", "verification_status": "FAILED"},
            }
            return values[label]

        async def human(*args, **kwargs):
            return "yes"

        fake.agent = agent
        fake.human = human
        fake.phase = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(workflow.run({"task": "recover service", "task_id": "t"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_phase"], "verify")
        self.assertEqual(calls[-1], "recovery-verifier")
        self.assertTrue(all("agent_type" not in options for options in options_seen))


if __name__ == "__main__":
    unittest.main()
