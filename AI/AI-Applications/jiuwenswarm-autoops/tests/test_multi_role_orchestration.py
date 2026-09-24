import io
import json
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "scripts" / "project-manager-orchestrator.py"
sys.path.insert(0, str(ROOT / "scripts"))
from autoops_contract import validate_plan, validate_step_result
SPEC = importlib.util.spec_from_file_location("verify_service_recovery", ROOT / "scripts" / "verify-service-recovery.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)
WORKFLOW_SPEC = importlib.util.spec_from_file_location("service_recovery_workflow", ROOT / "swarmflow" / "service-recovery-v1.py")
workflow = importlib.util.module_from_spec(WORKFLOW_SPEC)
WORKFLOW_SPEC.loader.exec_module(workflow)
READONLY_SPEC = importlib.util.spec_from_file_location("ro00_readonly_validation", ROOT / "swarmflow" / "ro00-readonly-validation.py")
readonly_workflow = importlib.util.module_from_spec(READONLY_SPEC)
READONLY_SPEC.loader.exec_module(readonly_workflow)
PARALLEL_SPEC = importlib.util.spec_from_file_location("ro05_parallel_observability", ROOT / "swarmflow" / "ro05-parallel-observability-v1.py")
parallel_workflow = importlib.util.module_from_spec(PARALLEL_SPEC)
PARALLEL_SPEC.loader.exec_module(parallel_workflow)


def plan(*args):
    result = subprocess.run([sys.executable, str(ORCHESTRATOR), *args], text=True, capture_output=True, check=False)
    return result.returncode, json.loads(result.stdout)


class OrchestrationTests(unittest.TestCase):
    def test_workflow_normalizes_object_args(self):
        self.assertEqual(workflow.normalize_args({"task": "inspect logs"}), {"task": "inspect logs"})

    def test_workflow_normalizes_json_string_args(self):
        self.assertEqual(workflow.normalize_args('{"task":"inspect logs"}'), {"task": "inspect logs"})

    def test_workflow_rejects_invalid_args(self):
        with self.assertRaises(ValueError):
            workflow.normalize_args("not-json")
        with self.assertRaises(ValueError):
            workflow.normalize_args('["not-an-object"]')

    def test_readonly_workflow_has_real_human_gate_and_no_recovery_node(self):
        source = (ROOT / "swarmflow" / "ro00-readonly-validation.py").read_text(encoding="utf-8")
        self.assertIn("await human(", source)
        self.assertIn('phase("approval")', source)
        self.assertNotIn('phase("recover")', source)
        self.assertNotIn('phase("verify")', source)

    def test_readonly_workflow_returns_completed_after_gate_without_write_phase(self):
        calls = []
        fake = type("Swarmflow", (), {})()

        async def agent(prompt, **options):
            calls.append(options["label"])
            if options["label"] == "runbook-operator":
                return {"task_id": "RO-00", "execution_status": "completed",
                        "service": "autoops-demo.service", "active_state": "active",
                        "unit_load_state": "loaded"}
            return {"task_id": "RO-00", "diagnosis_status": "completed",
                    "log_scope": "host-system", "findings": "none"}

        async def human(*args, **kwargs):
            return "close"

        fake.agent = agent
        fake.human = human
        fake.phase = lambda *_args: None
        fake.log = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(readonly_workflow.run({"task": "inspect logs"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["phase_stopped"], "approval")
        self.assertEqual(calls, ["runbook-operator", "log-investigator"])

    def test_ro05_runs_independent_experts_in_parallel_and_replans_once(self):
        active = 0
        max_active = 0
        calls = []
        fake = type("Swarmflow", (), {})()

        async def agent(prompt, **options):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            label = options["label"]
            calls.append(label)
            await asyncio.sleep(0.01)
            active -= 1
            if label == "log-investigator":
                status = "ANOMALY_DETECTED"
                capability = "logs.query.v2"
            elif label == "metrics-observer":
                status = "SUCCEEDED"
                capability = "metrics.query.v1"
            else:
                status = "SUCCEEDED"
                capability = "events.search.v1"
            return {"task_id": "ro05-task", "capability": capability, "status": status,
                    "evidence_refs": [{"source": label}]}

        async def human(*args, **kwargs):
            return "close"

        fake.agent = agent
        fake.human = human
        fake.phase = lambda *_args: None
        fake.log = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(parallel_workflow.run({
                "task": "diagnose order-api", "task_id": "ro05-task",
                "service": "order-api", "since_minutes": 15, "limit": 20,
                "require_human": True,
            }))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["plan_revision"], 2)
        self.assertEqual(result["replans"], 1)
        self.assertEqual(max_active, 2)
        self.assertEqual(calls[:2], ["log-investigator", "metrics-observer"])
        self.assertEqual(calls[2], "event-investigator")

    def test_ro05_replans_when_partial_log_evidence_contains_anomaly(self):
        calls = []
        fake = type("Swarmflow", (), {})()

        async def agent(prompt, **options):
            label = options["label"]
            calls.append(label)
            task_id = prompt.split("Locked parent task_id: ", 1)[1].split(";", 1)[0]
            if label == "log-investigator":
                return {
                    "task_id": task_id,
                    "capability": "logs.query.v2",
                    "status": "PARTIAL",
                    "evidence_refs": ["journal-test"],
                    "adapter_result": {
                        "status": "ok",
                        "coverage_status": "partial",
                        "entries": [{"line": "service: Main process exited, status=1/FAILURE"}],
                    },
                }
            capability = "metrics.query.v1" if label == "metrics-observer" else "events.search.v1"
            return {"task_id": task_id, "capability": capability, "status": "PARTIAL",
                    "evidence_refs": [label]}

        fake.agent = agent
        fake.human = lambda *args, **kwargs: asyncio.sleep(0, result="close")
        fake.phase = lambda *_args: None
        fake.log = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(parallel_workflow.run({
                "task_id": "ro05-partial-anomaly", "service": "chatbot-ui",
            }))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["plan_revision"], 2)
        self.assertEqual(result["replans"], 1)
        self.assertEqual(calls, ["log-investigator", "metrics-observer", "event-investigator"])

    def test_ro05_generates_unique_task_identity_and_rejects_non_local_target(self):
        fake = type("Swarmflow", (), {})()

        async def agent(prompt, **options):
            capability = "logs.query.v2" if options["label"] == "log-investigator" else "metrics.query.v1"
            return {"task_id": prompt.split("Locked parent task_id: ", 1)[1].split(";", 1)[0],
                    "capability": capability, "status": "SUCCEEDED", "evidence_refs": []}

        fake.agent = agent
        fake.human = lambda *args, **kwargs: asyncio.sleep(0, result="cancel")
        fake.phase = lambda *_args: None
        fake.log = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            first = asyncio.run(parallel_workflow.run({"service": "order-api"}))
            second = asyncio.run(parallel_workflow.run({"service": "order-api"}))
            invalid = asyncio.run(parallel_workflow.run({"service": "order-api", "target": "remote-1"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(second["status"], "COMPLETED")
        self.assertNotEqual(first["task_id"], second["task_id"])
        self.assertEqual(invalid["error_code"], "INVALID_WORKFLOW_SCOPE")

    def test_ro05_read_only_run_completes_without_human_gate_by_default(self):
        fake = type("Swarmflow", (), {})()

        async def agent(prompt, **options):
            capability = "logs.query.v2" if options["label"] == "log-investigator" else "metrics.query.v1"
            task_id = prompt.split("Locked parent task_id: ", 1)[1].split(";", 1)[0]
            return {"task_id": task_id, "capability": capability,
                    "status": "SUCCEEDED", "evidence_refs": []}

        async def unexpected_human(*args, **kwargs):
            raise AssertionError("default read-only RO-05 run must not wait for human acknowledgement")

        fake.agent = agent
        fake.human = unexpected_human
        fake.phase = lambda *_args: None
        fake.log = lambda *_args: None
        old = sys.modules.get("swarmflow")
        sys.modules["swarmflow"] = fake
        try:
            result = asyncio.run(parallel_workflow.run({"task_id": "ro05-auto", "service": "order-api"}))
        finally:
            if old is None:
                sys.modules.pop("swarmflow", None)
            else:
                sys.modules["swarmflow"] = old
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["human_gate"], "skipped_read_only")

    def test_inspect_plan_selects_two_read_roles(self):
        code, payload = plan("--request", "inspect autoops-demo", "--target", "test-host-01", "--service", "autoops-demo")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PLANNED")
        self.assertEqual(payload["workflow_ref"], "service-recovery-v1")
        self.assertEqual(payload["workflow_asset"], "swarmflow/service-recovery-v1.py")
        self.assertEqual([step["role"] for step in payload["steps"]], ["runbook-operator", "log-investigator"])
        self.assertTrue(all(step["effect"] == "read" for step in payload["steps"]))
        self.assertEqual(validate_plan(payload)["schema_version"], 1)

    def test_confirm_plan_waits_before_write(self):
        code, payload = plan("--request", "recover autoops-demo", "--target", "test-host-01", "--service", "autoops-demo", "--mode", "confirm")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "WAITING_APPROVAL")
        validate_plan(payload)
        action = next(step for step in payload["steps"] if step["step_id"] == "ensure-service")
        self.assertEqual(action["approval"], "required")
        self.assertEqual(action["role"], "ansible-operator")

    def test_local_alias_resolves_to_the_single_published_fixture(self):
        code, payload = plan("--request", "recover autoops-demo", "--target", "local",
                             "--service", "autoops-demo", "--mode", "confirm")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "WAITING_APPROVAL")
        self.assertEqual(payload["scope"]["target"], "test-host-01")

    def test_repeated_default_plan_keeps_task_identity(self):
        args = ("--request", "recover autoops-demo", "--target", "test-host-01", "--service", "autoops-demo", "--mode", "confirm")
        first_code, first = plan(*args)
        second_code, second = plan(*args)
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(first["plan_revision"], second["plan_revision"])

    def test_auto_requires_authorization_reference(self):
        code, payload = plan("--request", "recover", "--target", "test-host-01", "--service", "autoops-demo", "--mode", "auto")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "INPUT_ERROR")

    def test_unpublished_service_is_rejected(self):
        code, payload = plan("--request", "recover", "--target", "test-host-01", "--service", "nginx")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "INPUT_ERROR")

    def test_unpublished_target_is_rejected(self):
        code, payload = plan("--request", "recover", "--target", "ecs-maas-test", "--service", "autoops-demo")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "INPUT_ERROR")


class HealthHandler(BaseHTTPRequestHandler):
    status = 200
    def do_GET(self):
        self.send_response(type(self).status)
        self.end_headers()
    def log_message(self, *_args):
        pass


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        import threading
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/health"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def test_active_service_and_probe_pass(self):
        with patch.object(verifier, "unit_state", return_value="active"), patch.object(verifier, "unit_restart_count", return_value=0):
            output = io.StringIO()
            with redirect_stdout(output):
                code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "test-host-01", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "7", "--interval-seconds", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["verification_status"], "PASSED")

    def test_inactive_service_fails_without_probe(self):
        with patch.object(verifier, "unit_state", return_value="inactive"):
            output = io.StringIO()
            with redirect_stdout(output):
                code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "test-host-01", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "1", "--interval-seconds", "0"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["verification_status"], "FAILED")

    def test_short_probe_window_is_inconclusive(self):
        with patch.object(verifier, "unit_state", return_value="active"), patch.object(verifier, "unit_restart_count", return_value=0):
            output = io.StringIO()
            with redirect_stdout(output):
                code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "test-host-01", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "3", "--interval-seconds", "0"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["verification_status"], "INCONCLUSIVE")
        self.assertEqual(payload["error_code"], "INSUFFICIENT_SAMPLES")
        validate_step_result(payload)

    def test_restart_during_window_fails_even_if_probe_is_healthy(self):
        with patch.object(verifier, "unit_state", return_value="active"), patch.object(verifier, "unit_restart_count", side_effect=[2, 3]):
            output = io.StringIO()
            with redirect_stdout(output):
                code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "test-host-01", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "7", "--interval-seconds", "0"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["verification_status"], "FAILED")
        self.assertEqual(payload["error_code"], "SERVICE_RESTARTED_DURING_WINDOW")

    def test_http_error_rate_fails_after_complete_sample_window(self):
        HealthHandler.status = 503
        try:
            with patch.object(verifier, "unit_state", return_value="active"), patch.object(verifier, "unit_restart_count", return_value=0):
                output = io.StringIO()
                with redirect_stdout(output):
                    code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "test-host-01", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "7", "--interval-seconds", "0"])
            payload = json.loads(output.getvalue())
        finally:
            HealthHandler.status = 200
        self.assertEqual(code, 1)
        self.assertEqual(payload["verification_status"], "FAILED")
        self.assertEqual(payload["error_code"], "HEALTH_PROBE_ERROR_RATE")
        validate_step_result(payload)
        probe_ref = next(item for item in payload["evidence_refs"] if item["source"] == "health_probe")
        self.assertEqual(len(probe_ref["observations"]), 7)
        self.assertEqual(probe_ref["error_rate"], 1.0)

    def test_unpublished_target_is_rejected(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = verifier.main(["--task-id", "t", "--step-id", "v", "--target", "other-host", "--service", "autoops-demo", "--probe-url", self.url, "--attempts", "7", "--interval-seconds", "0"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_code"], "TARGET_NOT_PUBLISHED")

    def test_verifier_uses_published_application_binding(self):
        config = verifier.published_service_config("autoops-demo", "local")
        self.assertEqual(config["systemd_unit"], "autoops-demo.service")
        self.assertEqual(config["target_aliases"]["local"], "test-host-01")
        self.assertEqual(config["probe_attempts"], 7)

    def test_verifier_rejects_future_action_completion_time(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = verifier.main([
                "--task-id", "t", "--step-id", "v", "--target", "test-host-01",
                "--service", "autoops-demo", "--action-completed-at", "4102444800",
            ])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_code"], "INVALID_ACTION_COMPLETION_TIME")
        validate_step_result(payload)


if __name__ == "__main__":
    unittest.main()
