import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("release_fixtures", ROOT / "scripts/release-fixtures.py")
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)


class ReleaseFixtureTests(unittest.TestCase):
    def test_setup_is_idempotent_and_truth_is_run_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "outside.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            first = fixtures.setup(work_dir=root, run_id="case-001", config_path=fixtures.DEFAULT_CONFIG)
            self.assertEqual(first["status"], "CREATED")
            second = fixtures.setup(work_dir=root, run_id="case-001", config_path=fixtures.DEFAULT_CONFIG)
            self.assertEqual(second["status"], "EXISTS")
            truth = json.loads(Path(first["ground_truth"]).read_text(encoding="utf-8"))
            self.assertEqual(truth["identity"]["application"], "autoops-release-case-001")
            self.assertEqual(truth["identity"]["opensearch_index"], "autoops-release-events-case-001")
            checked = fixtures.check(work_dir=root, run_id="case-001")
            self.assertEqual(checked["status"], "PASS")
            self.assertEqual(checked["datasource_checks"], {})

    def test_inject_records_anomaly_change_and_unrelated_data_without_crossing_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside.txt").write_text("keep\n", encoding="utf-8")
            fixtures.setup(work_dir=root, run_id="case-002", config_path=fixtures.DEFAULT_CONFIG)
            fixtures.setup(work_dir=root, run_id="case-003", config_path=fixtures.DEFAULT_CONFIG)
            fixtures.inject(work_dir=root, run_id="case-002", kind="anomaly")
            fixtures.inject(work_dir=root, run_id="case-002", kind="change")
            fixtures.inject(work_dir=root, run_id="case-002", kind="unrelated")
            result = fixtures.check(work_dir=root, run_id="case-002")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["record_counts"]["logs"], 2)
            self.assertEqual(result["record_counts"]["events"], 3)
            other_truth = json.loads((root / "fixture-case-003/ground-truth.json").read_text(encoding="utf-8"))
            self.assertEqual(other_truth["records"]["logs"], [
                {"kind": "normal", "message": "release-api-case-003 request completed"}
            ])
            cleaned = fixtures.cleanup(work_dir=root, run_id="case-002")
            self.assertEqual(cleaned["status"], "CLEANED")
            self.assertFalse((root / "fixture-case-002").exists())
            self.assertTrue((root / "fixture-case-003").exists())
            self.assertTrue((root / "fixture-case-003/fixture-manifest.json").exists())
            self.assertEqual((root / "outside.txt").read_text(encoding="utf-8"), "keep\n")

    def test_invalid_run_id_and_symlink_cleanup_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                fixtures.setup(work_dir=root, run_id="../escape", config_path=fixtures.DEFAULT_CONFIG)
            target = root / "fixture-case-004"
            target.symlink_to(root)
            with self.assertRaises(ValueError):
                fixtures.cleanup(work_dir=root, run_id="case-004")


if __name__ == "__main__":
    unittest.main()
