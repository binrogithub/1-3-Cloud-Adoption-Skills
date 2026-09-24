import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoops_contract import (  # noqa: E402
    autoops_request,
    autoops_plan,
    step_result,
    validate_request,
    validate_plan,
    validate_step_result,
)


class AutoOpsContractTests(unittest.TestCase):
    def test_request_builder_preserves_scope_and_field_provenance(self):
        request = autoops_request(
            request_id="req-1",
            task_id="task-1",
            original_request="排查订单日志",
            goal="确认最近24小时是否存在异常",
            intent="diagnose",
            scope={"service_ref": "orders", "target_ref": "local"},
            requested_minutes=1440,
            field_sources={"scope.service_ref": "operator"},
        )
        self.assertEqual(request["scope"]["service_ref"], "orders")
        self.assertEqual(request["field_sources"]["scope.service_ref"], "operator")

    def test_request_rejects_unscoped_or_non_positive_window(self):
        with self.assertRaises(ValueError):
            autoops_request(
                request_id="req-1", task_id="task-1", original_request="检查",
                goal="检查", intent="inspect", scope={}, requested_minutes=60,
            )
        with self.assertRaises(ValueError):
            validate_request({
                "schema_version": 1, "request_id": "req-1", "task_id": "task-1",
                "original_request": "检查", "goal": "检查", "intent": "inspect",
                "scope": {"target_ref": "local"},
                "requested_window": {"requested_minutes": 0},
                "constraints": {}, "completion_criteria": {},
            })

    def test_legacy_execution_status_is_accepted_and_normalized(self):
        result = step_result(
            task_id="task-1", step_id="step-1", capability="logs.query.v2",
            execution_status="SUCCEEDED", changed=False,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(validate_step_result(result)["status"], "SUCCEEDED")

    def test_recovered_result_requires_successful_execution(self):
        with self.assertRaises(ValueError):
            validate_step_result({
                "schema_version": 1,
                "execution_status": "FAILED",
                "recovery_status": "recovered",
            })

    def test_retry_class_is_published_and_bounded(self):
        result = step_result(
            task_id="task-1", step_id="step-1", capability="logs.query.v2",
            execution_status="FAILED", retry_class="transient_read",
        )
        self.assertEqual(validate_step_result(result)["retry_class"], "transient_read")
        with self.assertRaisesRegex(ValueError, "retry_class"):
            step_result(task_id="task-1", step_id="step-1", capability="logs.query.v2",
                        execution_status="FAILED", retry_class="retry_anything")

    def test_plan_builder_requires_explicit_invocation_and_dependency_contract(self):
        plan = autoops_plan(
            task_id="task-1", plan_revision=1, goal="检查服务",
            scope={"target_ref": "local"}, steps=[
                {"step_id": "inspect", "role": "runbook-operator",
                 "capability": "host.inspect.v1", "invocation_kind": "project_route",
                 "effect": "read", "inputs": {"target": "local"}, "depends_on": [],
                 "when": "always", "required": True,
                 "expected_result": {"status": "SUCCEEDED"}, "timeout_seconds": 300},
            ],
        )
        self.assertEqual(plan["schema_version"], 1)

    def test_plan_rejects_unknown_dependency_and_cycle(self):
        base = {
            "schema_version": 1, "task_id": "task-1", "plan_revision": 1,
            "goal": "检查服务", "scope": {"target_ref": "local"},
            "status": "PLANNED",
            "budget": {"max_steps": 12, "max_parallel_read_steps": 3, "max_replans": 1},
        }
        step = {"step_id": "inspect", "role": "runbook-operator",
                "capability": "host.inspect.v1", "invocation_kind": "project_route",
                "effect": "read", "inputs": {}, "depends_on": ["missing"],
                "when": "always", "required": True,
                "expected_result": {}, "timeout_seconds": 300}
        with self.assertRaises(ValueError):
            validate_plan({**base, "steps": [step]})
        first = {**step, "step_id": "first", "depends_on": ["second"]}
        second = {**step, "step_id": "second", "depends_on": ["first"]}
        with self.assertRaises(ValueError):
            validate_plan({**base, "steps": [first, second]})

    def test_plan_rejects_capability_missing_from_published_catalog(self):
        step = {"step_id": "inspect", "role": "runbook-operator",
                "capability": "unknown.v1", "invocation_kind": "project_route",
                "effect": "read", "inputs": {}, "depends_on": [],
                "when": "always", "required": True,
                "expected_result": {}, "timeout_seconds": 300}
        with self.assertRaises(ValueError):
            validate_plan({"schema_version": 1, "task_id": "task-1", "plan_revision": 1,
                           "goal": "检查服务", "scope": {"target_ref": "local"},
                           "status": "PLANNED", "budget": {"max_steps": 12,
                           "max_parallel_read_steps": 3, "max_replans": 1}, "steps": [step]},
                          published_capabilities={"host.inspect.v1"})

    def test_plan_rejects_parallel_read_budget_overflow(self):
        def step(step_id):
            return {"step_id": step_id, "role": "log-investigator",
                    "capability": "logs.query.v2", "invocation_kind": "adapter",
                    "effect": "read", "inputs": {}, "depends_on": [],
                    "when": "always", "required": True,
                    "expected_result": {}, "timeout_seconds": 300}
        with self.assertRaisesRegex(ValueError, "max_parallel_read_steps"):
            validate_plan({"schema_version": 1, "task_id": "task-1", "plan_revision": 1,
                           "goal": "并行调查", "scope": {"target_ref": "local"},
                           "status": "PLANNED", "budget": {"max_steps": 12,
                           "max_parallel_read_steps": 1, "max_replans": 1},
                           "steps": [step("one"), step("two")]})


if __name__ == "__main__":
    unittest.main()
