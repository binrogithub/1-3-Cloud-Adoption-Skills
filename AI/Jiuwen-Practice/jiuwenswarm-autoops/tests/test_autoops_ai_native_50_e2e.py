import tempfile
import unittest
from pathlib import Path
import sys
import json


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("autoops_ai_native_50_e2e", ROOT / "scripts" / "autoops-ai-native-50-e2e.py")
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class AutoOpsAiNative50Tests(unittest.TestCase):
    def test_case_document_has_fifty_prompts(self):
        cases = module.parse_cases(ROOT / "docs/jiuwen-autoops-ai-native-50-hard-test-cases.md")
        self.assertEqual(len(cases), 50)
        self.assertEqual(cases[0]["case_id"], "AN-T01")
        self.assertEqual(cases[-1]["case_id"], "AN-T50")
        self.assertTrue(cases[0]["prompt"])

    def test_missing_history_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.classify(Path(directory) / "history.jsonl", 124, "")
            self.assertEqual(result, ("INCONCLUSIVE", "history_missing"))

    def test_continuity_gap_is_a_boundary_result(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text("\n".join(json.dumps(event) for event in [
                {"role": "user", "content": "#autoops-project-manager continue"},
                {"event_type": "chat.final", "content": "Continuity Gap — Cannot Continue without task context."},
            ]) + "\n", encoding="utf-8")
            result = module.classify(history, 0, "")
            self.assertEqual(result, ("PASS-BOUNDARY", "route_completed_with_boundary_signal"))


if __name__ == "__main__":
    unittest.main()
