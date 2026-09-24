#!/usr/bin/env python3
"""Migrate the CSS action ledger without deleting unfinished work."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from css_action_ledger import open_action_db


def migrate(path: Path, backup: Path | None = None) -> dict[str, object]:
    if path.exists() and backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    connection = open_action_db(path)
    try:
        count = connection.execute("SELECT COUNT(*) FROM css_actions").fetchone()[0]
        active = connection.execute(
            "SELECT COUNT(*) FROM css_actions WHERE status IN "
            "('INTENT_RECORDED','SUBMITTED','RECONCILING','UNKNOWN','CAPACITY_READY','VERIFYING_BUSINESS','DEGRADED')"
        ).fetchone()[0]
    finally:
        connection.close()
    return {"status": "MIGRATED", "path": str(path), "rows": count,
            "active_rows": active, "migrated_at": datetime.now(timezone.utc).isoformat(),
            "backup": str(backup) if backup else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate the CSS AutoOps action ledger.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args(argv)
    import json
    print(json.dumps(migrate(args.db, args.backup), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
