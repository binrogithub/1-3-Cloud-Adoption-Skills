import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("configure_model", ROOT / "scripts/configure-model.py")
configure_model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure_model)


class ModelConfigurationTests(unittest.TestCase):
    def test_wizard_writes_private_config_with_recommended_model(self):
        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory)
            with mock.patch.object(configure_model, "input", side_effect=["", ""]), \
                    mock.patch.object(configure_model.getpass, "getpass", return_value="unit-test-$key"), \
                    mock.patch.object(configure_model.argparse.ArgumentParser, "parse_args",
                                      return_value=mock.Mock(env_file=config_root / ".env", force=False)):
                self.assertEqual(configure_model.main(), 0)
            target = config_root / ".env"
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            content = target.read_text(encoding="utf-8")
            self.assertIn('MODEL_NAME="deepseek-v4.1-flash"', content)
            self.assertIn('API_KEY="unit-test-$key"', content)

    def test_shared_env_loader_parses_secret_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.env"
            path.write_text(
                'API_BASE="https://maas.example/v1"\n'
                'API_KEY="literal-$(touch /tmp/should-not-exist)-$value"\n'
                'MODEL_NAME="deepseek-v4.1-flash"\nMODEL_PROVIDER="OpenAI"\n',
                encoding="utf-8",
            )
            path.chmod(0o600)
            result = subprocess.run(
                ["bash", "-c", 'source "$1"; printf "%s\\n" "$API_KEY"', "test",
                 str(ROOT / "scripts/load-model-env.sh")],
                env={**os.environ, "JIUWENSWARM_AUTOOPS_MODEL_ENV": str(path)},
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'literal-$(touch /tmp/should-not-exist)-$value')
            self.assertFalse(Path("/tmp/should-not-exist").exists())

    def test_wizard_updates_only_model_fields_and_keeps_other_jiuwenswarm_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ".env"
            target.write_text(
                'VIDEO_API_BASE="https://video.example/v1"\n'
                'API_BASE="https://old.example/v1"\nAPI_KEY="existing-key"\n'
                'MODEL_NAME="old-model"\nMODEL_PROVIDER="OpenAI"\n',
                encoding="utf-8",
            )
            target.chmod(0o600)
            with mock.patch.object(configure_model, "input", side_effect=["", ""]), \
                    mock.patch.object(configure_model.getpass, "getpass", return_value=""), \
                    mock.patch.object(configure_model.argparse.ArgumentParser, "parse_args",
                                      return_value=mock.Mock(env_file=target, force=True)):
                self.assertEqual(configure_model.main(), 0)
            content = target.read_text(encoding="utf-8")
            self.assertIn('VIDEO_API_BASE="https://video.example/v1"', content)
            self.assertIn('API_KEY="existing-key"', content)
            self.assertIn('MODEL_NAME="old-model"', content)
            self.assertEqual(content.count("API_KEY="), 1)

    def test_model_env_loader_rejects_group_readable_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.env"
            path.write_text("API_KEY=secret\n", encoding="utf-8")
            path.chmod(0o640)
            result = subprocess.run(
                ["bash", "-c", 'source "$1"', "test", str(ROOT / "scripts/load-model-env.sh")],
                env={**os.environ, "JIUWENSWARM_AUTOOPS_MODEL_ENV": str(path)},
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mode 0600 or 0400", result.stderr)


if __name__ == "__main__":
    unittest.main()
