import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RuntimeTests(unittest.TestCase):
    def test_user_global_hooks_use_current_python_interpreter(self):
        with tempfile.TemporaryDirectory() as home:
            code = f"""
import json
import sys
from pathlib import Path
sys.path.insert(0, {str(SCRIPTS)!r})
import _common
_common.install_user_global_hooks()
hooks = json.loads(_common.USER_HOOKS_JSON.read_text(encoding='utf-8'))['hooks']
for event in ('beforeSubmitPrompt', 'sessionStart'):
    command = hooks[event][0]['command']
    if sys.executable not in command:
        raise SystemExit(f'{{event}} command {{command!r}} does not use {{sys.executable!r}}')
"""
            proc = subprocess.run(
                [sys.executable, "-c", code],
                env={"HOME": home},
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_delegate_file_writes_cannot_escape_root_with_prefix_path(self):
        delegate = load_module("delegate_under_test", SCRIPTS / "delegate.py")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            touched = delegate._apply_file_writes(
                root,
                [{"path": "../root_evil/pwned.txt", "content": "escaped"}],
            )
            self.assertEqual(touched, [])
            self.assertFalse((base / "root_evil" / "pwned.txt").exists())

    def test_validate_brief_rejects_schema_limit_violations(self):
        delegate = load_module("delegate_validation_under_test", SCRIPTS / "delegate.py")
        with self.assertRaises(SystemExit):
            delegate.validate_brief(
                {"goal": "x", "files": [], "acceptance": "y", "max_attempts": 6}
            )

    def test_verify_fails_when_delegate_smoke_is_not_successful(self):
        verify = load_module("verify_under_test", SCRIPTS / "verify.py")
        failed_proc = SimpleNamespace(
            stdout=json.dumps({"status": "failed", "acceptance_met": False}),
            stderr="",
            returncode=2,
        )
        with (
            mock.patch.object(
                verify,
                "load_env",
                return_value={
                    "DELEGATE_API_KEY": "test",
                    "DELEGATE_API_BASE": "http://example.invalid/v1",
                    "DELEGATE_MODEL": "glm-test",
                },
            ),
            mock.patch.object(
                verify,
                "chat_completion",
                return_value={"choices": [{"message": {"content": "pong"}}]},
            ),
            mock.patch.object(verify.subprocess, "run", return_value=failed_proc),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(verify.main(), 1)

    def test_workflow_aborts_after_remainder_threshold_before_running_all_items(self):
        workflow = load_module("workflow_under_test", SCRIPTS / "workflow.py")
        manifest = {
            "workflow_id": "wf",
            "concurrency": 1,
            "items": [
                {"id": str(i), "goal": "x", "files": [f"{i}.txt"], "acceptance": "y"}
                for i in range(10)
            ],
        }
        seen = []

        def fake_run_item(item):
            seen.append(item["id"])
            return {"id": item["id"], "status": "failed", "acceptance_met": False}

        with mock.patch.object(workflow, "run_item", side_effect=fake_run_item):
            out = workflow.execute_manifest(manifest)

        self.assertTrue(out["abort_reclassify_premium"])
        self.assertLess(len(seen), 10)


if __name__ == "__main__":
    unittest.main()
