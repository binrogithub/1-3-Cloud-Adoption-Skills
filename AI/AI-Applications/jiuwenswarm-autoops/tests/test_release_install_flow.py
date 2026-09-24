import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install-autoops.sh"


class ReleaseInstallFlowTests(unittest.TestCase):
    def test_help_describes_explicit_component_download(self):
        result = subprocess.run([str(INSTALL), "--help"], text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--install-components", result.stdout)
        self.assertIn("--deployment-mode", result.stdout)
        self.assertIn("downloaded or started unless", result.stdout)

    def test_runtime_only_flow_uses_isolated_roots_and_can_skip_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run([
                str(INSTALL), "--source-root", str(ROOT),
                "--install-root", str(root / "install"), "--config-root", str(root / "etc"),
                "--state-root", str(root / "state"), "--systemd-root", str(root / "systemd"),
                "--skip-skills", "--no-create-service-account",
                "--no-auto-configure-local-observability",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "install/scripts/Jiuwen_autoops_tui").is_file())
            self.assertTrue((root / "etc/runtime.json").is_file())


if __name__ == "__main__":
    unittest.main()
