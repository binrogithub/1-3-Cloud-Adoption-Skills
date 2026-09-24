import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from css_history import append_sample, load_samples


class CssHistoryTests(unittest.TestCase):
    def test_history_is_bounded_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            for value in range(5):
                append_sample(path, {"value": value}, limit=3)
            self.assertEqual([item["value"] for item in load_samples(path)], [2, 3, 4])
            self.assertIsInstance(json.loads(path.read_text()), list)


if __name__ == "__main__":
    unittest.main()
