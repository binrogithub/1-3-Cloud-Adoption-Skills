import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'local-journal-query.sh'


class LocalJournalAdapterTests(unittest.TestCase):
    def run_query(self, journal_output, *args):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'journalctl'
            fake.write_text(f'#!/bin/sh\nprintf %s "$JOURNAL_OUTPUT"\n', encoding='utf-8')
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ | {'PATH': f'{directory}:/usr/bin:/bin', 'JOURNAL_OUTPUT': journal_output}
            return subprocess.run([str(SCRIPT), *args], text=True, capture_output=True, env=env, check=False)

    def test_reads_fixed_unit_and_redacts(self):
        result = self.run_query(
            '2026-09-11T21:12:01+08:00 host chatbot[1]: ERROR token=top-secret failed\n',
            '--service', 'chatbot-ui', '--since-minutes', '15', '--limit', '20')
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['source'], 'local-journal')
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['entry_count'], 1)
        self.assertEqual(payload['source_status'], 'ready')
        self.assertEqual(payload['evidence_ref'], payload['query_ref'])
        self.assertIn('covered_window', payload)
        self.assertIn('freshness', payload)
        self.assertNotIn('top-secret', result.stdout)
        self.assertIn('token=[REDACTED]', result.stdout)

    def test_rejects_shell_injection(self):
        result = self.run_query('', '--service', 'chatbot;touch /tmp/should-not-exist')
        self.assertEqual(result.returncode, 2)

    def test_reads_host_system_scope_without_service(self):
        result = self.run_query(
            '2026-09-13T11:12:01+08:00 host kernel: ERROR failed to mount\n',
            '--scope', 'host_system', '--since-minutes', '1440', '--limit', '20')
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['scope'], 'host_system')
        self.assertIsNone(payload['service'])
        self.assertEqual(payload['entry_count'], 1)

    def test_journal_permission_failure_is_unavailable_not_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'journalctl'
            fake.write_text('#!/bin/sh\nprintf %s "permission denied" >&2\nexit 1\n', encoding='utf-8')
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            result = subprocess.run(
                [str(SCRIPT), '--scope', 'host_system', '--since-minutes', '15', '--limit', '20'],
                text=True, capture_output=True,
                env=os.environ | {'PATH': f'{directory}:/usr/bin:/bin'}, check=False,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['status'], 'unavailable')
        self.assertEqual(payload['error_code'], 'JOURNAL_QUERY_FAILED')
        self.assertEqual(payload['entries'], [])
        self.assertNotEqual(payload['status'], 'empty')


if __name__ == '__main__':
    unittest.main()
