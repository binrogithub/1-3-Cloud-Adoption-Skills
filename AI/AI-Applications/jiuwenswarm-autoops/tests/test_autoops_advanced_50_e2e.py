import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "autoops_advanced_50_e2e", ROOT / "scripts" / "autoops-advanced-50-e2e.py")
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class AutoOpsAdvanced50RunnerTests(unittest.TestCase):
    def test_release_manifest_matches_all_source_cases(self):
        cases = runner.parse_cases(runner.DEFAULT_CASES)
        manifest = runner.load_release_manifest(runner.DEFAULT_MANIFEST, cases)
        self.assertEqual(manifest["case_count"], 50)
        self.assertEqual(manifest["cases"][-1]["case_id"], "AO50-50")

    def test_release_manifest_rejects_changed_prompt(self):
        cases = runner.parse_cases(runner.DEFAULT_CASES)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            value = runner.load_release_manifest(runner.DEFAULT_MANIFEST, cases)
            value["cases"][0]["original_prompt"] = "simplified prompt"
            import json
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.load_release_manifest(path, cases)

    def test_release_business_requires_artifact_sha(self):
        self.assertFalse(runner.valid_artifact_sha(None))
        self.assertFalse(runner.valid_artifact_sha("a" * 63))
        self.assertTrue(runner.valid_artifact_sha("a" * 64))


if __name__ == "__main__":
    unittest.main()
