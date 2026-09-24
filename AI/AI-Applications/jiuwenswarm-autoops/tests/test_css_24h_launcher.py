import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "css-24h-launch.py"
spec = importlib.util.spec_from_file_location("css_24h_launcher_under_test", SCRIPT)
launcher = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = launcher
assert spec.loader is not None
spec.loader.exec_module(launcher)


class Css24hLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({"schema_version": 1, "phases": []}), encoding="utf-8")
        self.state = self.root / "state"
        self.state.mkdir()
        self.args = ["--profile-id", "css-test", "--config-dir", str(self.root),
                     "--plan", str(self.plan), "--duration-seconds", "86400",
                     "--state-dir", str(self.state), "--execute"]

    def tearDown(self):
        self.temp.cleanup()

    def select(self):
        return launcher.select_run_args(self.args, profile_id="css-test",
                                        config_dir=self.root, plan_path=self.plan,
                                        state_dir=self.state, duration_seconds=86400)

    def test_starts_a_new_run_when_state_is_empty(self):
        self.assertEqual(self.select()[-1], "--new-run")

    def test_resumes_a_matching_running_checkpoint(self):
        from css_run_state import digest
        plan = json.loads(self.plan.read_text())
        checkpoint = {"profile_id": "css-test", "status": "RUNNING",
                      "plan_digest": digest({"plan": plan, "duration_seconds": 86400,
                                             "business_config_digest": None}),
                      "duration_seconds": 86400, "run_id": "run-123"}
        (self.state / "run-123.checkpoint.json").write_text(json.dumps(checkpoint))
        self.assertEqual(self.select()[-2:], ["--resume-run-id", "run-123"])

    def test_does_not_restart_after_a_terminal_run(self):
        (self.state / "run-123.checkpoint.json").write_text(json.dumps(
            {"profile_id": "css-test", "status": "STOPPED_GUARDRAIL"}))
        with self.assertRaisesRegex(ValueError, "terminal run"):
            self.select()

    def test_blocks_an_incompatible_running_run(self):
        (self.state / "run-123.checkpoint.json").write_text(json.dumps(
            {"profile_id": "css-test", "status": "RUNNING", "plan_digest": "other",
             "duration_seconds": 86400}))
        with self.assertRaisesRegex(ValueError, "incompatible plan"):
            self.select()
