import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "acceptance" / "release-ao50-v1.json"
CRITICAL = ROOT / "config" / "acceptance" / "release-critical-v1.json"
SOURCE = ROOT / "docs" / "jiuwen-autoops-e2e-50-advanced-scenarios-20260915.md"


def source_cases():
    text = SOURCE.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^### (AO50-\d{2})：(.+)$", text, re.MULTILINE))
    values = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        prompt = re.search(r"^\*\*用户输入：\*\*(.+)$", block, re.MULTILINE)
        values[match.group(1)] = {
            "title": match.group(2).strip(),
            "prompt": prompt.group(1).strip() if prompt else "",
        }
    return values


class ReleaseCaseManifestTests(unittest.TestCase):
    def load(self):
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(value["kind"], "AutoOpsReleaseAcceptanceCaseManifest")
        self.assertEqual(value["case_count"], 50)
        return value["cases"]

    def test_manifest_has_exactly_fifty_source_identity_mappings(self):
        cases = self.load()
        source = source_cases()
        self.assertEqual(len(cases), 50)
        self.assertEqual([case["case_id"] for case in cases],
                         [f"AO50-{number:02d}" for number in range(1, 51)])
        self.assertEqual(set(source), {case["case_id"] for case in cases})
        for case in cases:
            self.assertEqual(case["title"], source[case["case_id"]]["title"])
            self.assertIn(source[case["case_id"]]["prompt"], case["original_prompt"])

    def test_each_case_declares_scope_fixture_truth_expected_evidence_and_cleanup(self):
        for case in self.load():
            for field in ("scope", "fixture_ref", "ground_truth_ref", "expected", "cleanup"):
                self.assertTrue(case.get(field), f"{case['case_id']} missing {field}")
            expected = case["expected"]
            self.assertEqual(expected["route"], "ProjectManager")
            self.assertTrue(expected["action"])
            self.assertTrue(expected["evidence_required"])
            self.assertTrue(case["truth_summary"])
            self.assertTrue(case["collaboration"])
            if expected["action"] == "N/A":
                self.assertTrue(case.get("na_basis"), f"{case['case_id']} N/A needs basis")

    def test_manifest_does_not_replace_original_case_with_a_simple_prompt(self):
        source = source_cases()
        for case in self.load():
            prompt = case["original_prompt"]
            self.assertGreaterEqual(len(prompt), 8)
            self.assertIn(prompt, source[case["case_id"]]["prompt"])

    def test_critical_manifest_covers_eight_groups_with_three_repeats(self):
        value = json.loads(CRITICAL.read_text(encoding="utf-8"))
        self.assertEqual(value["kind"], "AutoOpsReleaseCriticalCases")
        self.assertEqual(value["repeat"], 3)
        self.assertEqual([group["group_id"] for group in value["groups"]],
                         [f"REL-{number:02d}" for number in range(1, 9)])
        available = {case["case_id"] for case in self.load()}
        for group in value["groups"]:
            self.assertTrue(group["case_ids"])
            self.assertTrue(set(group["case_ids"]) <= available)


if __name__ == "__main__":
    unittest.main()
