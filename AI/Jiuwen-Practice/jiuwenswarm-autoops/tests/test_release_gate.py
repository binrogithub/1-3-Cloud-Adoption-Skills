import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SPEC = importlib.util.spec_from_file_location("release_check", ROOT / "scripts" / "release-check.py")
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)
check = release_check.check


class ReleaseGateTests(unittest.TestCase):
    def evidence(self, task_id: str, artifact: str, **extra):
        item = {
            "schema_version": 1, "epic_id": task_id[:6], "task_id": task_id,
            "run_id": "test-run", "attempt": 1, "commit": "abcdef1234567",
            "artifact_sha256": artifact, "config_sha256": "d" * 64,
            "case_manifest_sha256": "e" * 64,
            "environment_manifest_ref": "environment.json",
            "started_at": "2026-09-15T00:00:00Z", "finished_at": "2026-09-15T00:00:01Z",
            "status": "PASS", "evidence_refs": [{"path": "result.json", "sha256": "f" * 64, "kind": "result"}],
            "reason": "synthetic release evidence",
        }
        item.update(extra)
        return item

    def test_missing_evidence_is_no_go(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": "a" * 64,
                                            "evidence": []}), encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            result = check("rc", manifest, evidence)
            self.assertEqual(result["status"], "NO_GO")
            self.assertIn("required_evidence_missing", result["reasons"])

    def test_historical_evidence_with_different_artifact_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": "b" * 64,
                                            "evidence": [{"task_id": "REL-01-01", "status": "PASS",
                                                          "artifact_sha256": "a" * 64}]}), encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            result = check("rc", manifest, evidence)
            self.assertEqual(result["status"], "NO_GO")
            self.assertIn("evidence_artifact_mismatch", result["reasons"])

    def test_complete_custom_gate_can_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gates = root / "gates.json"
            gates.write_text(json.dumps({"schema_version": 1, "rc_required_tasks": ["REL-01-01"],
                                         "ga_required_tasks": ["REL-01-01"]}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": "c" * 64,
                                            "evidence": [self.evidence("REL-01-01", "c" * 64)]}), encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            self.assertEqual(check("rc", manifest, evidence, gates)["status"], "GO")

    def test_missing_evidence_envelope_fields_is_no_go(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gates = root / "gates.json"
            gates.write_text(json.dumps({"schema_version": 1, "rc_required_tasks": ["REL-01-01"],
                                         "ga_required_tasks": ["REL-01-01"]}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": "a" * 64,
                                            "evidence": [{"task_id": "REL-01-01", "status": "PASS",
                                                          "artifact_sha256": "a" * 64}]}), encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            result = check("rc", manifest, evidence, gates)
            self.assertEqual(result["status"], "NO_GO")
            self.assertIn("REL-01-01", result["invalid_fields"])

    def test_ga_requires_event_bearing_deployed_restore_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gates = root / "gates.json"
            gates.write_text(json.dumps({"schema_version": 1, "rc_required_tasks": ["REL-07-01"],
                                         "ga_required_tasks": ["REL-07-01"], "task_requirements": {
                                             "REL-07-01": {"mode": "deployed", "min_duration_seconds": 86400}
                                         }}), encoding="utf-8")
            artifact = "b" * 64
            item = self.evidence("REL-07-01", artifact, epic_id="REL-07", mode="deployed",
                                 duration_seconds=86400)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": artifact,
                                            "evidence": [item]}), encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            self.assertEqual(check("ga", manifest, evidence, gates)["status"], "GO")
            item["duration_seconds"] = 60
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": artifact,
                                            "evidence": [item]}), encoding="utf-8")
            result = check("ga", manifest, evidence, gates)
            self.assertEqual(result["status"], "NO_GO")
            self.assertIn("duration_seconds", result["invalid_fields"]["REL-07-01"])

    def test_credential_canary_fails_without_echoing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gates = root / "gates.json"
            gates.write_text(json.dumps({"schema_version": 1, "rc_required_tasks": ["T-1"],
                                         "ga_required_tasks": ["T-1"]}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "artifact_sha256": "c" * 64,
                                            "evidence": [{"task_id": "T-1", "status": "PASS",
                                                          "artifact_sha256": "c" * 64}]}), encoding="utf-8")
            scan_root = root / "artifact"
            scan_root.mkdir()
            canary = "AUTOOPS_CREDENTIAL_CANARY_20260915_abcdef"
            (scan_root / "config.env").write_text(f"RUNDECK_API_TOKEN={canary}\n", encoding="utf-8")
            evidence = root / "evidence"
            evidence.mkdir()
            result = check("rc", manifest, evidence, gates, scan_root)
            self.assertEqual(result["status"], "NO_GO")
            self.assertIn("credential_leak_detected", result["reasons"])
            self.assertEqual(result["credential_hits"], ["config.env"])
            self.assertNotIn(canary, json.dumps(result))

    def test_placeholder_example_is_allowed_by_credential_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.env").write_text(
                "HUAWEI_MAAS_API_KEY=replace-with-a-secret-manager-reference\n", encoding="utf-8")
            self.assertEqual(release_check.scan_credentials(root), [])


if __name__ == "__main__":
    unittest.main()
