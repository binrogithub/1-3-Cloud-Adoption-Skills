import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "scripts" / "css-watch.py"
REGISTER = ROOT / "scripts" / "css-register.py"


class CssWatchTests(unittest.TestCase):
    def setup_config(self, root: Path) -> None:
        env = os.environ.copy()
        env.update(HUAWEICLOUD_SDK_AK="AK-test", HUAWEICLOUD_SDK_SK="SK-test")
        result = subprocess.run([
            sys.executable, str(REGISTER), "--profile-id", "production-search",
            "--cluster-id", "12345678-1234-4123-8123-123456789abc",
            "--region", "cn-north-4", "--project-id", "project-test",
            "--config-dir", str(root),
        ], env=env, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def fixture(self, root: Path) -> Path:
        path = root / "fixture.json"
        path.write_text(json.dumps({
            "source": "fixture",
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": {
                "cluster_status": 0, "disk_usage_pct": 60, "jvm_heap_max": 50,
                "cpu_max": 88, "search_rate": 100, "search_latency": 20,
                "indexing_rate": 30, "indexing_latency": 10,
            },
            "topology": {"cluster_healthy": True, "data_node_count": 2},
            "evidence_refs": ["fixture://css-pressure"],
        }), encoding="utf-8")
        return path

    def invoke(self, root: Path, fixture: Path, action="run") -> dict:
        result = subprocess.run([
            sys.executable, str(WATCH), "--profile-id", "production-search",
            "--config-dir", str(root), "--state-dir", str(root / "state"),
            "--events-file", str(root / "events.jsonl"), "--fixture", str(fixture),
            "--action", action,
        ], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_emits_one_deduplicated_css_pressure_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_config(root)
            fixture = self.fixture(root)
            first = self.invoke(root, fixture)
            self.assertEqual(first["status"], "PROCESSED")
            self.assertEqual(first["decision"]["decision"], "scale_out")
            self.assertEqual(first["emitted"], 1)
            second = self.invoke(root, fixture)
            self.assertEqual(second["emitted"], 0)
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["source"], "css")
            self.assertEqual(events[0]["profile_id"], "production-search")
            self.assertEqual(events[0]["annotations"]["mode"], "observe")

    def test_pause_and_resume_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_config(root)
            fixture = self.fixture(root)
            self.invoke(root, fixture, "pause")
            paused = self.invoke(root, fixture)
            self.assertEqual(paused["status"], "paused")
            self.invoke(root, fixture, "resume")
            resumed = self.invoke(root, fixture)
            self.assertEqual(resumed["status"], "PROCESSED")

    def test_unavailable_sdk_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_config(root)
            result = subprocess.run([
                sys.executable, str(WATCH), "--profile-id", "production-search",
                "--config-dir", str(root), "--state-dir", str(root / "state"),
                "--events-file", str(root / "events.jsonl"),
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "UNAVAILABLE")
            self.assertEqual(payload["error_code"], "CSS_DATASOURCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
