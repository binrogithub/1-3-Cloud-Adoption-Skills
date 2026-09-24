import contextlib
import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "observability_correlate", ROOT / "scripts" / "observability-correlate.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ObservabilityCorrelationTests(unittest.TestCase):
    def test_all_child_investigations_receive_one_shared_window(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps({"status": "no_anomaly"}), "")

        output = io.StringIO()
        with patch.object(MODULE.subprocess, "run", side_effect=run), contextlib.redirect_stdout(output):
            code = MODULE.main(["--service", "orders", "--service", "payments", "--since-minutes", "30"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "no_anomaly")
        self.assertEqual(payload["shared_window"]["requested_minutes"], 30)
        windows = [
            (command[command.index("--start") + 1], command[command.index("--end") + 1])
            for command in calls
        ]
        self.assertEqual(len(set(windows)), 1)


if __name__ == "__main__":
    unittest.main()
