import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_business_evaluate", ROOT / "scripts" / "release-business-evaluate.py")
evaluator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(evaluator)


def manifest(ids):
    return {"kind": "AutoOpsReleaseAcceptanceCaseManifest",
            "cases": [{"case_id": item} for item in ids]}


def row(case_id, sha, business="PASS", **dimensions):
    return {"case_id": case_id, "artifact_sha256": sha, "result": "PASS_TUI_ROUTE",
            "business_status": business, "checker": {"ready": True}, **dimensions}


class ReleaseBusinessEvaluateTests(unittest.TestCase):
    def test_clean_business_row_passes_each_independent_dimension(self):
        sha = "a" * 64
        ids = ["AO50-01"]
        result = evaluator.evaluate_rows([row(
            ids[0], sha, native_dispatch_status="PASS", diagnosis_status="PASS",
            action_status="NOT_REQUIRED", verification_status="PASS")], manifest(ids), sha)
        self.assertEqual(result["status"], "GO")
        self.assertEqual(result["dimensions"]["action"]["status"], "PASS")

    def test_textual_route_without_business_evidence_is_no_go(self):
        sha = "b" * 64
        result = evaluator.evaluate_rows([row("AO50-01", sha, "NOT_EVALUATED_FIXTURE_REQUIRED",
                                              native_dispatch_status="PASS", diagnosis_status="PASS",
                                              action_status="NOT_REQUIRED", verification_status="PASS")],
                                         manifest(["AO50-01"]), sha)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("business_evidence_missing", result["reasons"])

    def test_stale_artifact_and_historical_failure_cannot_be_hidden_by_current_row(self):
        sha = "c" * 64
        rows = [row("AO50-01", sha, "FAIL", native_dispatch_status="PASS",
                    diagnosis_status="PASS", action_status="FAIL", verification_status="INCONCLUSIVE"),
                row("AO50-01", sha, "PASS", native_dispatch_status="PASS",
                    diagnosis_status="PASS", action_status="NOT_REQUIRED", verification_status="PASS"),
                row("AO50-02", "d" * 64, "PASS")]
        result = evaluator.evaluate_rows(rows, manifest(["AO50-01", "AO50-02"]), sha)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("historical_failure_present", result["reasons"])
        self.assertIn("artifact_mismatch", result["reasons"])


if __name__ == "__main__":
    unittest.main()
