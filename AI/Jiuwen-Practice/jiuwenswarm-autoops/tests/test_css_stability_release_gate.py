import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_stability_release_gate import check


class CssStabilityReleaseGateTests(unittest.TestCase):
    def write_evidence(self, root: Path, ready: bool) -> None:
        cases = []
        for number in range(1, 51):
            item = {"id": f"CSS50-{number:02d}", "case_id": f"CSS-S{number:02d}", "status": "PASS"}
            if number in {49, 50}:
                item.update({"execution_level": "REAL_BUSINESS" if ready else "CONTROL_PLANE_REAL",
                             "business_verification": "PASS" if ready else "UNVERIFIED"})
            cases.append(item)
        (root / "css-50-e2e.json").write_text(json.dumps({"results": cases}), encoding="utf-8")
        (root / "soak.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (root / "efficiency.json").write_text(json.dumps({"status": "PASS", "reduction_ratio": 0.66}), encoding="utf-8")
        (root / "tui.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (root / "install.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (root / "real-validation.json").write_text(json.dumps({
            "status": "PASS" if ready else "NOT_READY", "wall_clock_hours": 24 if ready else 0,
            "business_verification": "PASS" if ready else "UNVERIFIED", "cleanup": ready,
        }), encoding="utf-8")

    def test_gate_refuses_control_only_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, ready=False)
            result = check(root)
            self.assertEqual(result["status"], "NOT_READY")
            self.assertIn("real_24h_evidence_missing", result["reasons"])

    def test_gate_can_pass_complete_real_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, ready=True)
            self.assertEqual(check(root)["status"], "READY")

    def test_gate_prefers_real_write_report_over_skipped_read_only_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_evidence(root, ready=False)
            real_cases = []
            for number in range(1, 51):
                item = {"id": f"CSS50-{number:02d}", "case_id": f"CSS-S{number:02d}", "status": "PASS"}
                if number in {49, 50}:
                    item.update({"execution_level": "CONTROL_PLANE_REAL", "business_verification": "UNVERIFIED"})
                real_cases.append(item)
            (root / "css-50-real-writes.json").write_text(json.dumps({"results": real_cases}), encoding="utf-8")
            result = check(root)
            self.assertEqual(result["e2e_source"], "css-50-real-writes.json")
            self.assertNotIn("css_50_unresolved_case", result["reasons"])
            self.assertIn("real_business_level_missing:CSS-S49", result["reasons"])


if __name__ == "__main__":
    unittest.main()
