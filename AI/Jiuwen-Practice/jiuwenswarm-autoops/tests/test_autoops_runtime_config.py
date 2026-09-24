import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import autoops_runtime_config
from autoops_runtime_config import resolve_runtime, runtime_environment, write_runtime


class RuntimeConfigTests(unittest.TestCase):
    def test_persisted_runtime_wins_over_cwd_and_exports_all_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_file = root / "etc/runtime.json"
            runtime = {
                "schema_version": 1,
                "instance_id": "instance-a",
                "install_root": str(root / "install"),
                "config_root": str(root / "etc"),
                "state_root": str(root / "state"),
                "state_db": str(root / "state/autoops-state.db"),
                "watch_state_dir": str(root / "state/watch"),
                "events_file": str(root / "state/events.jsonl"),
                "outbox_file": str(root / "state/notifications.jsonl"),
                "deployment_mode": "installed",
            }
            write_runtime(runtime_file, runtime)
            with patch.dict(os.environ, {"JIUWENSWARM_AUTOOPS_RUNTIME_FILE": str(runtime_file)}, clear=False):
                resolved = resolve_runtime()
            self.assertEqual(resolved["instance_id"], "instance-a")
            self.assertEqual(resolved["state_db"], str(root / "state/autoops-state.db"))
            self.assertEqual(runtime_environment(resolved)["AUTOOPS_EVENTS_FILE"], str(root / "state/events.jsonl"))

    def test_explicit_test_paths_are_isolated_from_persisted_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_file = root / "runtime.json"
            write_runtime(runtime_file, {
                "schema_version": 1, "instance_id": "installed", "state_root": "/var/lib/installed",
                "config_root": "/etc/installed", "install_root": "/opt/installed",
            })
            with patch.dict(os.environ, {"JIUWENSWARM_AUTOOPS_RUNTIME_FILE": str(runtime_file)}, clear=False):
                resolved = resolve_runtime(state_db=root / "test.db", watch_state_dir=root / "watch")
            self.assertEqual(resolved["instance_id"], "installed")
            self.assertEqual(Path(resolved["state_db"]), root / "test.db")
            self.assertEqual(Path(resolved["watch_state_dir"]), root / "watch")

    def test_invalid_persisted_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
            with patch.dict(os.environ, {"JIUWENSWARM_AUTOOPS_RUNTIME_FILE": str(path)}, clear=False):
                with self.assertRaises(ValueError):
                    resolve_runtime()

    def test_invalid_default_runtime_does_not_fall_back_to_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_root = root / "etc"
            config_root.mkdir()
            (config_root / "runtime.json").write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
            with patch.object(autoops_runtime_config, "DEFAULT_CONFIG_ROOT", config_root):
                with patch.dict(os.environ, {"AUTOOPS_DEV_MODE": "0"}, clear=False):
                    with self.assertRaises(ValueError):
                        resolve_runtime()


if __name__ == "__main__":
    unittest.main()
