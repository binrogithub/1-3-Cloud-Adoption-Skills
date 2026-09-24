import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_collection_efficiency import run_benchmark


class CssCollectionEfficiencyTests(unittest.TestCase):
    def test_shared_snapshot_reduces_reads_and_fresh_bypasses_cache(self):
        result = run_benchmark(consumers=6)
        self.assertEqual(result["status"], "PASS")
        self.assertGreaterEqual(result["reduction_ratio"], 0.5)
        self.assertEqual(result["fresh_bypass_reads"], {"topology": 1, "metrics": 1})
        self.assertEqual(result["business_probe_calls"], "measured_separately")


if __name__ == "__main__":
    unittest.main()
