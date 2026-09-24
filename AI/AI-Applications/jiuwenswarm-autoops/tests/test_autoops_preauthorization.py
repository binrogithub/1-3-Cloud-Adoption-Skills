import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoops_preauthorization import finalize_reservation, load_policy, reserve, validate_scope
import autoops_project_manager


def policy_record(*, status="ACTIVE", cooldown=0, max_actions=1, expires_at="2099-01-01T00:00:00Z"):
    return {
        "schema_version": 1,
        "policy_id": "policy-test-v1",
        "status": status,
        "principal": "trusted-autoops-recovery",
        "scope": {
            "capability": "host.ensure_service.v1",
            "job": "ansible-ensure-autoops-demo",
            "target": "test-host-01",
            "service": "autoops-demo",
        },
        "limits": {
            "max_actions_per_incident": max_actions,
            "cooldown_seconds": cooldown,
        },
        "expires_at": expires_at,
    }


class PreauthorizationTests(unittest.TestCase):
    def configured_policy(self, directory, **kwargs):
        path = Path(directory) / "preauthorization.json"
        path.write_text(json.dumps(policy_record(**kwargs)), encoding="utf-8")
        path.chmod(0o600)
        return path

    def with_environment(self, **values):
        old = {key: os.environ.get(key) for key in values}
        os.environ.update({key: str(value) for key, value in values.items()})
        return old

    def restore_environment(self, old):
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def reserve_in_child(self, directory, incident_id, operation_id):
        code = (
            "import json, sys; "
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
            "from autoops_preauthorization import load_policy, reserve; "
            "status, policy = load_policy('policy-test-v1'); "
            f"status, details = reserve(policy, incident_id={incident_id!r}, operation_id={operation_id!r}); "
            "print(json.dumps({'status': status, 'details': details}))"
        )
        env = os.environ | {
            "AUTOOPS_PREAUTHORIZATION_FILE": str(Path(directory) / "preauthorization.json"),
            "AUTOOPS_STATE_DB": str(Path(directory) / "state.db"),
        }
        result = subprocess.run([sys.executable, "-c", code], text=True,
                                capture_output=True, env=env, check=True)
        return json.loads(result.stdout)

    def test_active_policy_requires_private_file_and_exact_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.configured_policy(directory)
            old = self.with_environment(AUTOOPS_PREAUTHORIZATION_FILE=path)
            try:
                status, policy = load_policy("policy-test-v1")
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = validate_scope(
                    policy,
                    capability="host.ensure_service.v1",
                    job="ansible-ensure-autoops-demo",
                    target="test-host-01",
                    service="autoops-demo",
                )
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = validate_scope(
                    policy,
                    capability="host.ensure_service.v1",
                    job="ansible-ensure-autoops-demo",
                    target="other-host",
                    service="autoops-demo",
                )
                self.assertEqual(status, "PREAUTHORIZATION_DENIED")
                path.chmod(0o644)
                status, details = load_policy("policy-test-v1")
                self.assertEqual(status, "PREAUTHORIZATION_DENIED")
                self.assertIn("private regular file", details["error"])
            finally:
                self.restore_environment(old)

    def test_reservation_is_atomic_and_bounded_to_one_action(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.configured_policy(directory)
            db = Path(directory) / "state.db"
            old = self.with_environment(AUTOOPS_PREAUTHORIZATION_FILE=path, AUTOOPS_STATE_DB=db)
            try:
                status, policy = load_policy("policy-test-v1")
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = reserve(policy, incident_id="incident-1", operation_id="operation-1")
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = reserve(policy, incident_id="incident-1", operation_id="operation-1")
                self.assertEqual(status, "PREAUTHORIZATION_ALREADY_RESERVED")
                status, _ = reserve(policy, incident_id="incident-1", operation_id="operation-2")
                self.assertEqual(status, "PREAUTHORIZATION_DENIED")
            finally:
                self.restore_environment(old)

    def test_cooldown_applies_across_incidents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.configured_policy(directory, cooldown=1800)
            db = Path(directory) / "state.db"
            old = self.with_environment(AUTOOPS_PREAUTHORIZATION_FILE=path, AUTOOPS_STATE_DB=db)
            try:
                status, policy = load_policy("policy-test-v1")
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = reserve(policy, incident_id="incident-1", operation_id="operation-1")
                self.assertEqual(status, "PREAUTHORIZED")
                status, _ = reserve(policy, incident_id="incident-2", operation_id="operation-2")
                self.assertEqual(status, "PREAUTHORIZATION_COOLDOWN")
            finally:
                self.restore_environment(old)

    def test_target_lock_blocks_other_incident_until_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.configured_policy(directory)
            db = Path(directory) / "state.db"
            old = self.with_environment(AUTOOPS_PREAUTHORIZATION_FILE=path, AUTOOPS_STATE_DB=db)
            try:
                status, policy = load_policy("policy-test-v1")
                self.assertEqual(status, "PREAUTHORIZED")
                self.assertEqual(reserve(policy, incident_id="incident-1", operation_id="operation-1")[0], "PREAUTHORIZED")
                status, details = reserve(policy, incident_id="incident-2", operation_id="operation-2")
                self.assertEqual(status, "PREAUTHORIZATION_TARGET_BUSY")
                self.assertEqual(details["incident_id"], "incident-1")
                self.assertEqual(finalize_reservation(policy, incident_id="incident-1", operation_id="operation-1", execution_status="UNKNOWN")[0], "PREAUTHORIZATION_HELD")
                self.assertEqual(reserve(policy, incident_id="incident-2", operation_id="operation-2")[0], "PREAUTHORIZATION_TARGET_BUSY")
                self.assertEqual(finalize_reservation(policy, incident_id="incident-1", operation_id="operation-1", execution_status="SUCCEEDED")[0], "PREAUTHORIZATION_RELEASED")
                self.assertEqual(reserve(policy, incident_id="incident-2", operation_id="operation-2")[0], "PREAUTHORIZED")
            finally:
                self.restore_environment(old)

    def test_target_lock_survives_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            self.configured_policy(directory)
            first = self.reserve_in_child(directory, "incident-1", "operation-1")
            second = self.reserve_in_child(directory, "incident-2", "operation-2")
            self.assertEqual(first["status"], "PREAUTHORIZED")
            self.assertEqual(second["status"], "PREAUTHORIZATION_TARGET_BUSY")
            old = self.with_environment(
                AUTOOPS_PREAUTHORIZATION_FILE=Path(directory) / "preauthorization.json",
                AUTOOPS_STATE_DB=Path(directory) / "state.db",
            )
            try:
                _, policy = load_policy("policy-test-v1")
                self.assertEqual(finalize_reservation(
                    policy, incident_id="incident-1", operation_id="operation-1",
                    execution_status="SUCCEEDED")[0], "PREAUTHORIZATION_RELEASED")
            finally:
                self.restore_environment(old)
            released = self.reserve_in_child(directory, "incident-2", "operation-2")
            self.assertEqual(released["status"], "PREAUTHORIZED")

    def test_expired_disabled_and_multi_action_policies_are_rejected(self):
        for options in (
            {"status": "DISABLED"},
            {"expires_at": "2000-01-01T00:00:00Z"},
            {"max_actions": 2},
        ):
            with tempfile.TemporaryDirectory() as directory:
                path = self.configured_policy(directory, **options)
                old = self.with_environment(AUTOOPS_PREAUTHORIZATION_FILE=path)
                try:
                    status, _ = load_policy("policy-test-v1")
                    self.assertEqual(status, "PREAUTHORIZATION_DENIED")
                finally:
                    self.restore_environment(old)

    def test_project_manager_uses_preauthorization_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.configured_policy(directory)
            old = self.with_environment(
                AUTOOPS_PREAUTHORIZATION_FILE=path,
                AUTOOPS_STATE_DB=Path(directory) / "state.db",
            )
            try:
                output = StringIO()
                with patch.object(autoops_project_manager, "run_adapter", return_value=(0, {"status": "SUCCEEDED"})) as adapter:
                    with redirect_stdout(output):
                        code = autoops_project_manager.main([
                            "--request", "Ensure the service is running",
                            "--service", "autoops-demo",
                            "--target", "test-host-01",
                            "--task-id", "task-preauth",
                            "--idempotency-key", "operation-preauth",
                            "--execute",
                            "--preauthorization-id", "policy-test-v1",
                            "--incident-id", "incident-preauth",
                        ])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 0)
                self.assertEqual(payload["execution_boundary"], "E01/runbook-operator/published-preauthorization")
                self.assertEqual(payload["adapter_result"]["status"], "SUCCEEDED")
                adapter.assert_called_once()
                self.assertIn("runbook-execute.py", adapter.call_args.args[0][1])
            finally:
                self.restore_environment(old)

    def test_project_manager_keeps_missing_preauthorization_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            old = self.with_environment(
                AUTOOPS_PREAUTHORIZATION_FILE=Path(directory) / "missing.json",
                AUTOOPS_STATE_DB=Path(directory) / "state.db",
            )
            try:
                output = StringIO()
                with patch.object(autoops_project_manager, "run_adapter") as adapter:
                    with redirect_stdout(output):
                        code = autoops_project_manager.main([
                            "--request", "Ensure the service is running",
                            "--service", "autoops-demo",
                            "--target", "test-host-01",
                            "--execute",
                            "--preauthorization-id", "policy-test-v1",
                        ])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 0)
                self.assertEqual(payload["status"], "AUTHORIZATION_DENIED")
                self.assertEqual(payload["error_code"], "PREAUTHORIZATION_REQUIRED")
                adapter.assert_not_called()
            finally:
                self.restore_environment(old)

    def test_project_manager_routes_kubernetes_restore_through_e01(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "k8s-policy.json"
            policy = policy_record()
            policy["policy_id"] = "k8s-policy-v1"
            policy["scope"] = {
                "capability": "k8s.restore_replicas.v1",
                "job": "k8s-restore-order-api",
                "target": "test-host-01",
                "service": "order-api",
            }
            path.write_text(json.dumps(policy), encoding="utf-8")
            path.chmod(0o600)
            old = self.with_environment(
                AUTOOPS_PREAUTHORIZATION_FILE=path,
                AUTOOPS_STATE_DB=Path(directory) / "state.db",
            )
            try:
                output = StringIO()
                with patch.object(autoops_project_manager, "run_adapter", return_value=(0, {"status": "NO_CHANGE"})) as adapter:
                    with redirect_stdout(output):
                        code = autoops_project_manager.main([
                            "--request", "恢复 Kubernetes Deployment 副本数",
                            "--cluster", "autoops-development",
                            "--workload", "staging/orders/order-api",
                            "--target", "test-host-01", "--task-id", "k8s-task",
                            "--idempotency-key", "k8s-operation", "--execute",
                            "--preauthorization-id", "k8s-policy-v1", "--incident-id", "k8s-incident",
                        ])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 0)
                self.assertEqual(payload["execution_boundary"], "E03/kubernetes-operator/E01/published-preauthorization")
                command = adapter.call_args.args[0]
                self.assertIn("k8s-restore-replicas.py", command[1])
                self.assertNotIn("kubectl", " ".join(command))
                self.assertEqual(payload["job"], "k8s-restore-order-api")
            finally:
                self.restore_environment(old)

    def test_project_manager_adds_independent_k8s_business_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "k8s-policy.json"
            policy = policy_record()
            policy["policy_id"] = "k8s-policy-v2"
            policy["scope"] = {
                "capability": "k8s.restore_replicas.v1",
                "job": "k8s-restore-order-api",
                "target": "test-host-01",
                "service": "order-api",
            }
            path.write_text(json.dumps(policy), encoding="utf-8")
            path.chmod(0o600)
            old = self.with_environment(
                AUTOOPS_PREAUTHORIZATION_FILE=path,
                AUTOOPS_STATE_DB=Path(directory) / "state.db",
            )
            try:
                output = StringIO()
                with patch.object(autoops_project_manager, "run_adapter",
                                  return_value=(0, {"status": "NO_CHANGE",
                                                    "resource_verification_status": "PASSED"})), \
                        patch.object(autoops_project_manager, "run_k8s_business_verifier",
                                     return_value=(0, {"verification_status": "PASSED"})) as verifier:
                    with redirect_stdout(output):
                        code = autoops_project_manager.main([
                            "--request", "恢复 Kubernetes Deployment 副本数",
                            "--cluster", "autoops-development",
                            "--workload", "staging/orders/order-api",
                            "--target", "test-host-01", "--task-id", "k8s-task-v2",
                            "--idempotency-key", "k8s-operation-v2", "--execute",
                            "--preauthorization-id", "k8s-policy-v2", "--incident-id", "k8s-incident-v2",
                        ])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 0)
                self.assertEqual(payload["status"], "SUCCEEDED")
                self.assertEqual(payload["recovery_status"], "recovered")
                self.assertEqual(payload["execution_boundary"],
                                 "E03/kubernetes-operator/E01/published-preauthorization/E09/recovery-verifier")
                verifier.assert_called_once()
            finally:
                self.restore_environment(old)


if __name__ == "__main__":
    unittest.main()
