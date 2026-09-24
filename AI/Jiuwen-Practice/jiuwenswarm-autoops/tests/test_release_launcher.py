import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "Jiuwen_autoops_tui"
INSTALL = ROOT / "scripts" / "install-autoops.sh"


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ReleaseLauncherTests(unittest.TestCase):
    def test_help_and_invalid_session_do_not_require_backend(self):
        help_result = subprocess.run([str(LAUNCHER), "--help"], text=True,
                                     capture_output=True, check=False)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("Project Manager", help_result.stdout)
        invalid = subprocess.run([str(LAUNCHER), "--session", "bad/name", "--once", "inspect"],
                                 text=True, capture_output=True, check=False)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("invalid session name", invalid.stderr)

    def test_launcher_works_from_space_cwd_with_existing_backend_and_native_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin with spaces"
            fake_bin.mkdir()
            executable(fake_bin / "ss", "#!/bin/sh\nprintf '%s\\n' 'LISTEN 128 0 127.0.0.1:18092 127.0.0.1:*' 'LISTEN 128 0 127.0.0.1:19001 127.0.0.1:*'\n")
            executable(fake_bin / "expect", "#!/bin/sh\ncat >/dev/null\nexit 0\n")
            executable(fake_bin / "jiuwenswarm-tui", "#!/bin/sh\nexit 0\n")
            env = os.environ | {"PATH": f"{fake_bin}:/usr/bin:/bin", "HOME": str(root / "user home"),
                                "JIUWENSWARM_HOME": str(root / "swarm home")}
            cwd = root / "cwd"
            cwd.mkdir()
            result = subprocess.run([str(LAUNCHER), "--no-install", "--once", "--session", "space-cwd", "inspect logs"],
                                    cwd=cwd,
                                    text=True, capture_output=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_native_dependency_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            executable(fake_bin / "ss", "#!/bin/sh\nexit 0\n")
            env = os.environ | {"PATH": f"{fake_bin}:/usr/bin:/bin"}
            result = subprocess.run([str(LAUNCHER), "--no-install", "--once", "inspect logs"],
                                    cwd=root, text=True, capture_output=True, env=env, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing required TUI command: jiuwenswarm-tui", result.stderr)

    def test_install_entry_publishes_both_aliases_without_overwriting_existing_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run([str(INSTALL), "--source-root", str(ROOT),
                                     "--install-root", str(root / "install"), "--config-root", str(root / "etc"),
                                     "--state-root", str(root / "state"), "--systemd-root", str(root / "systemd"),
                                     "--bin-dir", str(root / "bin"), "--skip-skills",
                                     "--no-create-service-account", "--no-auto-configure-local-observability"],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("Jiuwen_autoops_tui", "jiuwen_autoops_tui"):
                link = root / "bin" / name
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), (root / "install/scripts/Jiuwen_autoops_tui").resolve())

    def test_ready_runtime_start_does_not_call_installer_or_rewrite_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            for relative, content in (
                ("scripts/autoops_runtime_config.py", "# runtime helper\n"),
                ("scripts/install-autoops-runtime.py", f"{root / 'installer-called'}\n"),
                ("skills/autoops-project-manager/SKILL.md", "# PM\n"),
                ("config/autoops-agent-bootstrap.md", "# bootstrap\n"),
                ("autoops-install-manifest.json", '{"schema_version":2}\n'),
            ):
                path = runtime / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            skills = root / "skills"
            (skills / "autoops-project-manager").mkdir(parents=True)
            (skills / "autoops-project-manager/SKILL.md").write_text("# registered PM\n", encoding="utf-8")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            executable(fake_bin / "ss", "#!/bin/sh\nprintf '%s\\n' 'LISTEN 128 0 127.0.0.1:18092 127.0.0.1:*' 'LISTEN 128 0 127.0.0.1:19001 127.0.0.1:*'\n")
            executable(fake_bin / "expect", "#!/bin/sh\nexit 0\n")
            executable(fake_bin / "jiuwenswarm-tui", "#!/bin/sh\nexit 0\n")
            before = {path: path.stat().st_mtime_ns for path in runtime.rglob("*") if path.is_file()}
            env = os.environ | {"PATH": f"{fake_bin}:/usr/bin:/bin", "HOME": str(root / "home"),
                                "JIUWENSWARM_AGENT_SKILLS_DIR": str(skills),
                                "AUTOOPS_LAUNCHER_RUNTIME_ROOT": str(runtime)}
            work = root / "work"
            work.mkdir()
            result = subprocess.run([str(LAUNCHER), "--once", "--session", "light-start", "inspect logs"],
                                    cwd=work, text=True, capture_output=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "installer-called").exists())
            self.assertEqual(before, {path: path.stat().st_mtime_ns for path in runtime.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
