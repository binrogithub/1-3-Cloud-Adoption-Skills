import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


class CssMigrationTests(unittest.TestCase):
    def test_migration_preserves_existing_action_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "actions.sqlite3"
            backup = Path(directory) / "actions.sqlite3.bak"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE css_actions (operation_id TEXT PRIMARY KEY, task_id TEXT, profile_id TEXT, direction TEXT, delta INTEGER, status TEXT, cloud_request_id TEXT)")
            connection.execute("INSERT INTO css_actions VALUES ('op-1','task-1','css','scale_out',1,'SUBMITTED',NULL)")
            connection.commit()
            connection.close()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/css_migrate.py"),
                                     "--db", str(db), "--backup", str(backup)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(backup.exists())
            payload = json.loads(result.stdout)
            self.assertEqual(payload["active_rows"], 1)
            connection = sqlite3.connect(db)
            self.assertEqual(connection.execute("SELECT status FROM css_actions WHERE operation_id='op-1'").fetchone()[0], "SUBMITTED")
            connection.close()


if __name__ == "__main__":
    unittest.main()
