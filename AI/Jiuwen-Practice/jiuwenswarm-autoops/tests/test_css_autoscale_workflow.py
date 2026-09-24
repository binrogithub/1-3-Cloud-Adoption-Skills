import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "css_autoscale_workflow", ROOT / "swarmflow" / "css-autoscale-v1.py"
)
WORKFLOW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WORKFLOW
SPEC.loader.exec_module(WORKFLOW)


class Completed:
    def __init__(self, stdout, returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class CssAutoscaleWorkflowTests(unittest.TestCase):
    def test_status_mapping_accepts_agent_and_dispatcher_case(self):
        self.assertEqual(WORKFLOW._workflow_status("completed"), "COMPLETED")
        self.assertEqual(WORKFLOW._workflow_status("PLAN_READY"), "COMPLETED")
        self.assertEqual(WORKFLOW._workflow_status("INPUT_ERROR"), "INPUT_ERROR")
        self.assertEqual(WORKFLOW._workflow_status("unexpected"), "FAILED")

    def test_project_manager_result_keeps_role_plan_and_write_boundaries(self):
        result = {
            "status": "PLAN_READY",
            "routing": {"selected_roles": ["css_auto", "metrics-observer"],
                         "selected_capabilities": ["css.inspect.v1", "metrics.query.v1"]},
            "plan": {"steps": [{"step_id": "css-route-1", "role": "css_auto",
                                  "capability": "css.inspect.v1"}]},
        }
        with patch.object(WORKFLOW.subprocess, "run",
                          return_value=Completed(json.dumps(result))) as run:
            code, actual = WORKFLOW._run_project_manager(["python3", "pm"])
        self.assertEqual(code, 0)
        self.assertEqual(actual["status"], "PLAN_READY")
        self.assertEqual(run.call_args.kwargs["env"], WORKFLOW.os.environ)
        trace = WORKFLOW._role_trace(actual)
        self.assertEqual(trace[0]["role"], "project-manager")
        self.assertIn("css_auto", [item["role"] for item in trace])
        selected = next(item for item in trace if item["role"] == "css_auto")
        self.assertEqual(selected["status"], "SELECTED")

    def test_role_trace_marks_only_the_observed_css_inspection_as_executed(self):
        result = {
            "execution_mode": "inspect", "capability": "css.inspect.v1",
            "adapter_result": {"status": "READY"},
            "routing": {"selected_roles": ["css_auto", "metrics-observer"],
                        "selected_capabilities": ["css.inspect.v1", "metrics.query.v1"]},
        }
        trace = WORKFLOW._role_trace(result)
        roles = {item["role"]: item for item in trace}
        self.assertEqual(roles["css_auto"]["status"], "EXECUTED")
        self.assertEqual(roles["css_auto"]["result_status"], "READY")
        self.assertEqual(roles["metrics-observer"]["status"], "SELECTED")

    def test_invalid_project_manager_output_is_not_success(self):
        with patch.object(WORKFLOW.subprocess, "run",
                          return_value=Completed("not-json", returncode=0)):
            code, result = WORKFLOW._run_project_manager(["python3", "pm"])
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error_code"], "PROJECT_MANAGER_INVALID_OUTPUT")


if __name__ == "__main__":
    unittest.main()
