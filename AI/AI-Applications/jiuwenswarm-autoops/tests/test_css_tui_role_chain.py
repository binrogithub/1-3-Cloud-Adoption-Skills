import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "css_tui_role_chain_check.py"


class CssTuiRoleChainTests(unittest.TestCase):
    def test_project_manager_skill_forwards_registered_css_scope(self):
        skill = (ROOT / "skills" / "autoops-project-manager" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--css-profile <published-profile-id>", skill)
        self.assertIn("--css-config-dir", skill)
        self.assertIn("CSS_PROFILE_REQUIRED", skill)
        self.assertIn("Do not report a CSS profile as unregistered", skill)

    def test_checker_requires_complete_durable_role_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            events = [
                {"role": "user", "content": "#autoops-project-manager 扩容 CSS"},
                {"event_type": "chat.tool_call", "tool_call": {"name": "css_auto"}},
                {"event_type": "chat.tool_result", "result": json.dumps({
                    "selected_roles": ["project-manager", "css_auto", "runbook-operator", "recovery-verifier"]
                })},
                {"event_type": "chat.final", "content": "任务已完成并给出证据。"},
            ]
            history.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
                               encoding="utf-8")
            result = subprocess.run([sys.executable, str(CHECKER), str(history)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_checker_rejects_missing_final_message(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            history.write_text(json.dumps({
                "event_type": "chat.tool_result", "result": "css_auto runbook-operator recovery-verifier"
            }) + "\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(CHECKER), str(history)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("final_after_last_tool_result_missing", json.loads(result.stdout)["reasons"])

    def test_checker_rejects_native_workflow_wait_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            events = [
                {"event_type": "chat.tool_call", "tool_call": {"name": "swarmflow"}},
                {"event_type": "chat.tool_result", "tool_name": "swarmflow",
                 "result": "[Swarmflow launched] run_id=wf-1, task_id=task-1"},
                {"event_type": "chat.tool_result", "tool_name": "async_task_output",
                 "result": "Task 'wf-1' not found"},
                {"event_type": "chat.final", "content": "workflow status=FAILED"},
            ]
            history.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(CHECKER), str(history),
                                     "--required-role", "project-manager"],
                                    text=True, capture_output=True, check=False)
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertIn("native_workflow_wait_failed", report["reasons"])
            self.assertIn("native_workflow_failed", report["reasons"])

    def test_skill_mentions_do_not_count_as_executed_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            events = [
                {"role": "user", "content": "#autoops-project-manager inspect CSS"},
                {"event_type": "chat.tool_result", "tool_name": "skill_tool",
                 "result": "The workflow may use project-manager, css_auto, runbook-operator, recovery-verifier."},
                {"event_type": "chat.final", "content": "The skill was loaded."},
            ]
            history.write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(CHECKER), str(history)],
                                    text=True, capture_output=True, check=False)
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(report["observed_roles"], [])
            self.assertIn("role_evidence_missing", report["reasons"])


if __name__ == "__main__":
    unittest.main()
