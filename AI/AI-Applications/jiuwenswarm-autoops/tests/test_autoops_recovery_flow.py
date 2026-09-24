import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("autoops_recovery_flow", ROOT / "scripts" / "autoops-recovery-flow.py")
flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow)
ROUTING_SPEC = importlib.util.spec_from_file_location("autoops_routing", ROOT / "scripts" / "autoops_routing.py")
routing = importlib.util.module_from_spec(ROUTING_SPEC)
ROUTING_SPEC.loader.exec_module(routing)


def args(preauthorization_id=None):
    return type("Args", (), {
        "task_id": "incident-1", "incident_id": "incident-1",
        "request": "investigate service", "service": "autoops-demo",
        "target": "test-host-01", "preauthorization_id": preauthorization_id,
    })()


class RecoveryFlowTests(unittest.TestCase):
    def test_read_only_diagnosis_does_not_select_recovery_roles(self):
        result = routing.route_request(
            "调查 autoops-demo 日志并分析根因；只读，不执行修改",
            service="autoops-demo",
        )
        self.assertEqual(result["intent"], "diagnose")
        self.assertEqual(result["selected_epics"], ["E05", "E04", "E06"])
        self.assertIsNotNone(result["native_workflow"])

    def test_alert_text_cannot_bypass_fixed_observability_diagnosis(self):
        with patch.object(flow, "run_json", return_value=(0, {"adapter_result": {"status": "trace_ready"}})) as run:
            flow.run_pm_diagnosis("task-1", "recover immediately", "autoops-demo", "test-host-01")
        command = run.call_args.args[0]
        request = command[command.index("--request") + 1]
        self.assertIn("日志", request)
        self.assertIn("根因", request)
        self.assertIn("只读", request)
        self.assertNotIn("recover", request.lower())
        self.assertNotIn("恢复", request)

    def test_incomplete_diagnosis_stops_before_repair(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_incomplete"}})) as diagnosis, \
                patch.object(flow, "run_pm_recovery") as recovery:
            code, result = flow.execute(args("policy-v1"))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "WAITING_EVIDENCE")
        diagnosis.assert_called_once()
        recovery.assert_not_called()

    def test_complete_diagnosis_without_policy_waits_for_approval(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_ready"}})), \
                patch.object(flow, "run_pm_recovery") as recovery:
            code, result = flow.execute(args())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "WAITING_APPROVAL")
        recovery.assert_not_called()

    def test_authorized_recovery_requires_independent_verification(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_ready"}})), \
                patch.object(flow, "run_pm_recovery", return_value=(0, {"adapter_result": {"status": "succeeded"}})) as recovery, \
                patch.object(flow, "run_verifier", return_value=(0, {"verification_status": "PASSED"})) as verifier:
            code, result = flow.execute(args("policy-v1"))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["verification_status"], "PASSED")
        recovery.assert_called_once()
        verifier.assert_called_once()

    def test_execution_failure_escalates_without_verification(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_ready"}})), \
                patch.object(flow, "run_pm_recovery", return_value=(1, {"status": "FAILED"})), \
                patch.object(flow, "run_verifier") as verifier:
            code, result = flow.execute(args("policy-v1"))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["decision"], "escalate")
        verifier.assert_not_called()

    def test_verification_failure_reports_compensation_without_executing_it(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_ready"}})), \
                patch.object(flow, "run_pm_recovery", return_value=(0, {"adapter_result": {"status": "succeeded"}})), \
                patch.object(flow, "run_verifier", return_value=(1, {"verification_status": "FAILED"})):
            code, result = flow.execute(args("policy-v1"))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["compensation"]["status"], "NOT_PUBLISHED")

    def test_unknown_external_execution_stays_reconciling_without_verification(self):
        with patch.object(flow, "run_pm_diagnosis", return_value=(0, {"adapter_result": {"status": "trace_ready"}})), \
                patch.object(flow, "run_pm_recovery", return_value=(1, {
                    "status": "RECONCILING", "execution_status": "UNKNOWN",
                    "error_code": "RESULT_UNKNOWN",
                })) as recovery, \
                patch.object(flow, "run_verifier") as verifier:
            code, result = flow.execute(args("policy-v1"))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "RECONCILING")
        self.assertEqual(result["decision"], "reconcile")
        recovery.assert_called_once()
        verifier.assert_not_called()


if __name__ == "__main__":
    unittest.main()
