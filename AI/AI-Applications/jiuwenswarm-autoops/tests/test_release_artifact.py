import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "scripts" / "build-autoops-release.py")
build_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_release)


class ReleaseArtifactTests(unittest.TestCase):
    def test_dirty_checkout_is_rejected_without_explicit_candidate_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(["git", "init", "-q", str(root)], check=False)
            self.assertEqual(result.returncode, 0)
            (root / "README.md").write_text("readme\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_release.build(root, root / "release.tar.gz")

    def test_candidate_build_excludes_runtime_and_local_secret_area(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("scripts/x.py", "skills/x/SKILL.md", "runbooks/x.yml",
                             "swarmflow/x.py", "config/x.json", "components.env", "README.md"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("value\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=False)
            subprocess.run(["git", "-C", str(root), "add", "."], check=False)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "initial"], check=False)
            (root / "config/local").mkdir(parents=True)
            (root / "config/local/secret.env").write_text("API_KEY=canary\n", encoding="utf-8")
            (root / ".runtime").mkdir()
            (root / ".runtime/state.db").write_text("state\n", encoding="utf-8")
            output = root / "release.tar.gz"
            result = build_release.build(root, output, allow_dirty=True)
            self.assertEqual(result["status"], "candidate-unverified")
            self.assertEqual(len(result["artifact_sha256"]), 64)
            with build_release.tarfile.open(output, "r:gz") as archive:
                names = archive.getnames()
            self.assertFalse(any("secret.env" in name or ".runtime" in name for name in names))
            self.assertEqual(json.loads((root / "release.tar.gz.manifest.json").read_text())["artifact_sha256"], result["artifact_sha256"])


if __name__ == "__main__":
    unittest.main()
