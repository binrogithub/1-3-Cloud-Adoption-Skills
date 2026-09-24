import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_business_verification import evaluate_probe_window, evaluate_window, verify_observation


class CssBusinessVerificationTests(unittest.TestCase):
    def test_capacity_ready_without_business_is_unverified(self):
        result = verify_observation({"engine": {"status": "green"}, "business": {"status": "UNVERIFIED"}})
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIn("BUSINESS_PROBE_NOT_CONFIGURED", result["reason_codes"])

    def test_unassigned_shards_degrade(self):
        result = verify_observation({
            "engine": {"status": "green", "unassigned_shards": 1},
            "business": {"status": "PASSED"},
        })
        self.assertEqual(result["status"], "DEGRADED")

    def test_window_does_not_pass_with_zero_samples(self):
        self.assertEqual(evaluate_window([], {"minimum_samples": 2})["status"], "UNVERIFIED")

    def test_probe_window_requires_sample_count_and_elapsed_stability(self):
        samples = [{"status": "PASSED", "latency_ms": 20, "observed_epoch": stamp}
                   for stamp in (100, 130, 160)]
        result = evaluate_probe_window(samples, {
            "minimum_samples": 3, "stable_business_minutes": 2,
            "max_error_rate": 0.01, "max_p95_latency_ms": 100,
        })
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertIn("BUSINESS_STABILITY_WINDOW_INSUFFICIENT", result["reason_codes"])
        samples.extend([{"status": "PASSED", "latency_ms": 25, "observed_epoch": 220},
                        {"status": "PASSED", "latency_ms": 23, "observed_epoch": 280}])
        result = evaluate_probe_window(samples, {
            "minimum_samples": 3, "stable_business_minutes": 2,
            "max_error_rate": 0.01, "max_p95_latency_ms": 100,
        })
        self.assertEqual(result["status"], "PASSED")

    def test_business_error_rate_and_latency_are_enforced(self):
        samples = [{"status": "PASSED", "latency_ms": 250, "observed_epoch": 100},
                   {"status": "FAILED", "latency_ms": 250, "observed_epoch": 700}]
        result = evaluate_probe_window(samples, {
            "minimum_samples": 2, "stable_business_minutes": 10,
            "max_error_rate": 0.0, "max_p95_latency_ms": 100,
        })
        self.assertEqual(result["status"], "DEGRADED")
        self.assertIn("BUSINESS_ERROR_RATE_EXCEEDED", result["reason_codes"])
        self.assertIn("BUSINESS_P95_LATENCY_EXCEEDED", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
