import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "css-register.py"


class CssRegisterTests(unittest.TestCase):
    def run_register(self, directory: Path, *extra: str, env=None):
        values = os.environ.copy()
        values.update({
            "HUAWEICLOUD_SDK_AK": "AK-test-only",
            "HUAWEICLOUD_SDK_SK": "SK-test-only",
        })
        if env:
            values.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--profile-id", "prod-search",
             "--cluster-id", "12345678-1234-4123-8123-123456789abc",
             "--region", "cn-north-4", "--project-id", "project-test",
             "--config-dir", str(directory), *extra],
            env=values, text=True, capture_output=True, check=False,
        )

    def test_registers_profile_and_private_credentials_without_echoing_sk(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_register(Path(directory))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("SK-test-only", result.stdout)
            profile = json.loads((Path(directory) / "clusters/prod-search.json").read_text())
            credential = json.loads((Path(directory) / "credentials/default.json").read_text())
            self.assertEqual(profile["cluster_id"], "12345678-1234-4123-8123-123456789abc")
            self.assertEqual(profile["credential_ref"], "css/credentials/default")
            self.assertNotIn("secret_access_key", profile)
            self.assertEqual(credential["secret_access_key"], "SK-test-only")
            self.assertEqual(
                (Path(directory) / "credentials/default.json").stat().st_mode & 0o777, 0o600
            )
            self.assertEqual(
                (Path(directory) / "credentials").stat().st_mode & 0o777, 0o700
            )

    def test_invalid_cluster_id_does_not_write_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_register(Path(directory), "--cluster-id", "not-a-cluster")
            self.assertEqual(result.returncode, 2)
            self.assertFalse((Path(directory) / "credentials/default.json").exists())

    def test_non_interactive_setup_requires_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_register(
                Path(directory),
                env={"HUAWEICLOUD_SDK_SK": ""},
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse((Path(directory) / "credentials/default.json").exists())

    def test_revision_must_increase(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(self.run_register(path).returncode, 0)
            result = self.run_register(path)
            self.assertEqual(result.returncode, 2)

    def test_koo_cli_registration_does_not_require_or_write_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_register(
                Path(directory), "--api-adapter", "koo-cli", "--koo-cli-profile", "default",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            profile = json.loads((Path(directory) / "clusters/prod-search.json").read_text())
            credential = json.loads((Path(directory) / "credentials/default.json").read_text())
            self.assertEqual(profile["api_adapter"], "koo-cli")
            self.assertEqual(profile["koo_cli_profile"], "default")
            self.assertNotIn("secret_access_key", credential)
            self.assertFalse(json.loads(result.stdout)["secret_written"])

    def test_koo_cli_home_is_a_non_secret_profile_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_register(
                Path(directory), "--api-adapter", "koo-cli", "--koo-cli-home", "/root",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            profile = json.loads((Path(directory) / "clusters/prod-search.json").read_text())
            credential = json.loads((Path(directory) / "credentials/default.json").read_text())
            self.assertEqual(profile["koo_cli_home"], "/root")
            self.assertNotIn("access_key_id", credential)
            self.assertNotIn("secret_access_key", credential)


if __name__ == "__main__":
    unittest.main()
