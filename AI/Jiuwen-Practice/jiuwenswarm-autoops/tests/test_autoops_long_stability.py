import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "autoops_long_stability", ROOT / "scripts" / "autoops-long-stability.py")
stability = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(stability)


class AutoOpsLongStabilityTests(unittest.TestCase):
    def test_soak_plan_has_ten_distinct_incidents_and_cleanup_policy(self):
        value = json.loads((ROOT / "config/acceptance/release-soak-v1.json").read_text(encoding="utf-8"))
        incidents = value["events"]
        self.assertEqual(len(incidents), 10)
        self.assertEqual(len({item["incident_id"] for item in incidents}), 10)
        self.assertTrue(value["cleanup"]["required"])
        self.assertIn("unresolved external execution IDs", value["cleanup"]["preserve"])

    def test_deployed_mode_rejects_accelerated_cycles_and_short_duration(self):
        args = type("Args", (), {
            "mode": "deployed", "cycles": 1, "duration_seconds": 60,
            "interval_seconds": 0, "policy": ROOT / "config/monitoring/autoops-demo-watch.json",
            "state_dir": Path("/tmp/does-not-matter"), "events_file": Path("/tmp/missing"),
            "state_db": Path("/tmp/state"), "evidence": None,
            "watch_service": "jiuwenswarm-autoops-watch.service",
        })()
        with self.assertRaises(ValueError):
            stability.audit(args)

    def test_accelerated_fixture_mode_remains_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            events.write_text("", encoding="utf-8")
            args = type("Args", (), {
                "mode": "fixture", "cycles": 1, "duration_seconds": 60,
                "interval_seconds": 0, "policy": ROOT / "config/monitoring/autoops-demo-watch.json",
                "state_dir": root / "watch", "events_file": events,
                "state_db": root / "state.db", "evidence": None,
                "watch_service": "jiuwenswarm-autoops-watch.service",
            })()
            result = stability.audit(args)
            self.assertEqual(result["mode"], "accelerated")
            self.assertFalse(result["second_consumer_started"])


if __name__ == "__main__":
    unittest.main()
