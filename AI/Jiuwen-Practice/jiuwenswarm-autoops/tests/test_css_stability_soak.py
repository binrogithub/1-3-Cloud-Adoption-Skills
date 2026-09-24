import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from css_stability_soak import run_soak


class CssStabilitySoakTests(unittest.TestCase):
    def test_local_soak_preserves_unknown_and_recovers_after_fresh_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_soak(Path(directory) / "soak.json", iterations=10, restart_every=3)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["checks"]["unknown_does_not_resolve"])
            self.assertTrue(result["checks"]["fresh_healthy_sample_resolves"])
            self.assertTrue(result["real_24h_required"])
            self.assertEqual(result["real_24h_status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
