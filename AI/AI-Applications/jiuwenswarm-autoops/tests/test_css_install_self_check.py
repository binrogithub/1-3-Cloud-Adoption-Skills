import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-autoops-runtime.py"
CHECKER = ROOT / "scripts" / "css_install_self_check.py"


class CssInstallSelfCheckTests(unittest.TestCase):
    def test_clean_runtime_layout_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run([
                sys.executable, str(INSTALLER), "--source-root", str(ROOT),
                "--install-root", str(root / "install"), "--config-root", str(root / "etc"),
                "--state-root", str(root / "state"), "--systemd-root", str(root / "systemd"),
                "--no-create-service-account", "--no-auto-configure-local-observability",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            checked = subprocess.run([
                sys.executable, str(CHECKER), "--source-root", str(ROOT),
                "--install-root", str(root / "install"), "--config-root", str(root / "etc"),
                "--systemd-root", str(root / "systemd"),
            ], text=True, capture_output=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
