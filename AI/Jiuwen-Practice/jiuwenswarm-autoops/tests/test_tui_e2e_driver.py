import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'tui-autoops-e2e.sh'


class TuiDriverTests(unittest.TestCase):
    def test_driver_uses_history_instead_of_terminal_text(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / 'bin'
            fake_bin.mkdir()
            fake_expect = fake_bin / 'expect'
            fake_tui = fake_bin / 'jiuwenswarm-tui'
            fake_expect.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            fake_tui.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            for path in (fake_expect, fake_tui):
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            result = subprocess.run(
                [str(SCRIPT), '--help'],
                text=True,
                capture_output=True,
                env=os.environ | {'PATH': f'{fake_bin}:/usr/bin:/bin'},
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn('session history', result.stdout)

    def test_driver_bootstraps_team_and_swarmflow_before_prompt(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('--persist-session --session', source)
        self.assertNotIn('send -- "/new --persist-session\\r"', source)
        self.assertLess(source.index('/mode team'), source.index('$env(AUTOOPS_PROMPT)'))
        self.assertLess(source.index('/swarmflow on'), source.index('$env(AUTOOPS_PROMPT)'))
        launcher = (ROOT / 'scripts' / 'Jiuwen_autoops_tui').read_text(encoding='utf-8')
        self.assertIn('jiuwenswarm-tui --persist-session --session', launcher)
        self.assertIn('install-autoops-runtime.py', launcher)
        self.assertNotIn('send -- "/new --persist-session\\r"', launcher)
        self.assertLess(launcher.index('/mode team'), launcher.index('$env(AUTOOPS_PROMPT)'))
        self.assertLess(launcher.index('/swarmflow on'), launcher.index('$env(AUTOOPS_PROMPT)'))

    def test_history_checker_requires_final_after_last_tool_result(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect logs'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'autoops-project-manager.py'}},
                {'event_type': 'chat.tool_result', 'result': 'success=True'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ready'])

    def test_history_checker_accepts_one_watcher_control_call(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager watch autoops-demo'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-control.py --action status'}},
                {'event_type': 'chat.tool_result', 'result': '{"status":"OK"}'},
                {'event_type': 'chat.final', 'content': 'Watcher is active; business recovery was not evaluated.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_history_checker_ignores_execute_in_bash_description(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager preview Kubernetes restore'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': json.dumps({
                    'command': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py --request "restore" --cluster autoops-development --workload staging/orders/order-api',
                    'description': 'dry-run, no --execute',
                })}},
                {'event_type': 'chat.tool_result', 'result': 'success=True'},
                {'event_type': 'chat.final', 'content': 'PENDING_CONFIRMATION; no write was submitted.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertTrue(payload['ready'])
            self.assertEqual(payload['unsafe_actions'], 0)

    def test_history_checker_accepts_context_registration_route(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager onboard orders logs'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-context-register.py --profile-id orders'}},
                {'event_type': 'chat.tool_result', 'result': '{"status":"REGISTERED"}'},
                {'event_type': 'chat.final', 'content': 'Registered the profile; downstream log evidence is unavailable.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_history_checker_accepts_project_runtime_evidence_read(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            evidence = ROOT / '.runtime' / 'test-evidence.json'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect logs'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py --request inspect'}},
                {'event_type': 'chat.tool_result', 'result': 'success=False data={"status":"PARTIAL"}'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'read_file', 'arguments': json.dumps({'file_path': str(evidence)})}},
                {'event_type': 'chat.tool_result', 'result': 'success=True data={"content":"redacted evidence"}'},
                {'event_type': 'chat.final', 'content': 'The read-only evidence is PARTIAL and has been reported.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_history_checker_rejects_read_outside_project_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect logs'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py --request inspect'}},
                {'event_type': 'chat.tool_result', 'result': 'success=True'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'read_file', 'arguments': json.dumps({'file_path': '/etc/shadow'})}},
                {'event_type': 'chat.tool_result', 'result': 'success=True'},
                {'event_type': 'chat.final', 'content': 'done'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn('read_file', json.loads(result.stdout)['forbidden_tools'])

    def test_history_checker_accepts_native_bash_output_read(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager investigate logs'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/observability-investigate.py --service chatbot-ui'}},
                {'event_type': 'chat.tool_result', 'result': 'success=False data={"status":"PARTIAL"}'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'read_file', 'arguments': json.dumps({'file_path': '/tmp/openjiuwen_bash_outputs/bash_example.txt'})}},
                {'event_type': 'chat.tool_result', 'result': 'success=True data={"content":"redacted evidence"}'},
                {'event_type': 'chat.final', 'content': 'The evidence is PARTIAL and has been reported.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_history_checker_accepts_published_css_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            asset = ROOT / 'swarmflow' / 'css-autoscale-v1.py'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager verify CSS css-santiago'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'swarmflow', 'arguments': json.dumps({
                    'script_path': str(asset), 'args': {'css_profile': 'css-santiago'},
                })}},
                {'event_type': 'chat.tool_result', 'result': '[Swarmflow launched] run_id=wf-css, task_id=task-css'},
                {'event_type': 'chat.tool_result', 'tool_name': 'async_task_output',
                 'result': '[task task-css] status=completed'},
                {'event_type': 'chat.final', 'content': 'The published CSS workflow completed.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)['ready'])
            self.assertEqual(json.loads(result.stdout)['operational_calls'], 1)

    def test_history_checker_accepts_plain_input_when_bootstrap_reaches_project_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '查询本机 Linux 系统日志，最近24小时，只读'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/autoops-project-manager.py --request "查询本机 Linux 系统日志" --machine-output'}},
                {'event_type': 'chat.tool_result', 'result': 'success=True data={"task_id":"pm-1","selected_role":"log-investigator"}'},
                {'event_type': 'chat.final', 'content': 'ProjectManager 已完成本机日志只读查询。'},
            ]
            history.write_text('\n'.join(json.dumps(event, ensure_ascii=False) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertTrue(payload['ready'])
            self.assertFalse(payload['user_prefixed'])

    def test_history_checker_accepts_published_native_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager investigate order-api'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'swarmflow', 'arguments': json.dumps({
                    'script_path': str(ROOT / 'swarmflow' / 'ro05-parallel-observability-v1.py'),
                    'args': {'service': 'order-api'},
                })}},
                {'event_type': 'chat.tool_result', 'result': '[Swarmflow launched] run_id=wf-test'},
                {'event_type': 'chat.final', 'content': 'The published read-only workflow completed.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)['operational_calls'], 1)

    def test_history_checker_allows_only_published_workflow_asset_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            asset = ROOT / 'swarmflow' / 'ro05-parallel-observability-v1.py'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect payment'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': json.dumps({
                    'command': f'ls -la {asset}',
                })}},
                {'event_type': 'chat.tool_result', 'result': 'success=True'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'swarmflow', 'arguments': json.dumps({
                    'script_path': str(asset), 'args': {'service': 'payment'},
                })}},
                {'event_type': 'chat.tool_result', 'result': '[Swarmflow launched] run_id=wf-test'},
                {'event_type': 'chat.final', 'content': 'The published workflow completed.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)['forbidden_tools'], [])

    def test_history_checker_accepts_read_only_recovery_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager verify previous recovery'},
                {'event_type': 'chat.tool_call', 'tool_call': {'name': 'bash', 'arguments': 'python3 /root/Jiuwenswarm_AutoOps/scripts/verify-service-recovery.py --task-id task-1 --step-id verify-service --target local --service autoops-demo'}},
                {'event_type': 'chat.tool_result', 'result': 'success=True data={"verification_status":"INCONCLUSIVE"}'},
                {'event_type': 'chat.final', 'content': 'Verification is INCONCLUSIVE and no recovery action was submitted.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_history_checker_accepts_safe_continuity_boundary_without_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager continue the previous task'},
                {'event_type': 'chat.final', 'content': 'Continuity Gap — Cannot Continue without the current task ID.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])
            self.assertTrue(json.loads(result.stdout)['continuity_boundary'])

    def test_history_checker_accepts_missing_watch_profile_boundary_without_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager watch the order app'},
                {'event_type': 'chat.final', 'content': '缺少 profile-ref；请提供已发布的值守 profile。'},
            ]
            history.write_text('\n'.join(json.dumps(event, ensure_ascii=False) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertTrue(payload['ready'])
            self.assertTrue(payload['input_boundary'])
            self.assertEqual(payload['operational_calls'], 0)

    def test_history_checker_accepts_english_input_boundary_without_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager watch gateway logs'},
                {'event_type': 'chat.final', 'content': 'A profile reference is required before creating the watch policy.'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-history-completion-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(json.loads(result.stdout)['ready'])

    def test_lifecycle_checker_requires_two_turns_with_one_task_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect logs'},
                {'event_type': 'chat.tool_result', 'result': {'task_id': 'task-1'}},
                {'event_type': 'chat.final', 'content': 'first complete'},
                {'role': 'user', 'content': '#autoops-project-manager continue'},
                {'event_type': 'chat.final', 'content': 'same task continued'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-session-lifecycle-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertTrue(payload['ready'])
            self.assertEqual(payload['task_ids'], ['task-1'])

    def test_lifecycle_checker_rejects_second_turn_without_new_final(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / 'history.jsonl'
            events = [
                {'role': 'user', 'content': '#autoops-project-manager inspect logs'},
                {'event_type': 'chat.tool_result', 'result': '{"task_id": "task-1"}'},
                {'event_type': 'chat.final', 'content': 'first complete'},
                {'role': 'user', 'content': '#autoops-project-manager continue'},
            ]
            history.write_text('\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8')
            checker = ROOT / 'scripts' / 'tui-session-lifecycle-check.py'
            result = subprocess.run([sys.executable, str(checker), str(history)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ready'])


if __name__ == '__main__':
    unittest.main()
