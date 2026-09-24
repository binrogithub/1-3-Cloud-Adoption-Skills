import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from css_capacity_forecast import forecast_capacity, summarize_lead_times


class CssCapacityForecastTests(unittest.TestCase):
    def test_small_sample_is_not_reported_as_p95(self):
        result = summarize_lead_times([{"submitted_at": 100, "capacity_ready_at": 200}])
        self.assertIsNone(result["p95_seconds"])
        self.assertEqual(result["quality"], "insufficient_samples")

    def test_forecast_is_a_planning_hint(self):
        result = forecast_capacity({"growth_per_hour": 10, "capacity_headroom_units": 1},
                                   {"initial_capacity_lead_minutes": 15},
                                   {"median_seconds": 900, "quality": "insufficient_samples"})
        self.assertEqual(result["status"], "PRESSURE_FORECAST")


if __name__ == "__main__":
    unittest.main()
