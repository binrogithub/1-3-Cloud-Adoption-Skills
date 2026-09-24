#!/usr/bin/env python3
"""Reconcile a persisted CSS action from JSON evidence.

The CLI is intentionally side-effect free. A service or E09 can supply the
latest action, topology and verification records; this command returns the
deterministic next state without making another CSS write.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from css_reconcile import reconcile_action
from css_action_ledger import open_action_db, transition_status


def read_object(path: str) -> dict:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"evidence must be a regular file: {source}")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence must be an object: {source}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile a CSS action without writing CSS.")
    parser.add_argument("--action", required=True)
    parser.add_argument("--topology", required=True)
    parser.add_argument("--verification")
    parser.add_argument("--operation-id")
    parser.add_argument("--action-db")
    args = parser.parse_args(argv)
    try:
        result = reconcile_action(
            read_object(args.action), read_object(args.topology),
            read_object(args.verification) if args.verification else None,
        )
        if args.operation_id:
            connection = open_action_db(args.action_db)
            try:
                row = connection.execute(
                    "SELECT status FROM css_actions WHERE operation_id=?", (args.operation_id,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"CSS action is missing from ledger: {args.operation_id}")
                target = result["status"]
                current = str(row["status"])
                transition_status(current, target)
                connection.execute(
                    "UPDATE css_actions SET status=?, reconciled_at=?, updated_at=? "
                    "WHERE operation_id=?",
                    (target, datetime.now(timezone.utc).isoformat(),
                     datetime.now(timezone.utc).isoformat(), args.operation_id),
                )
            finally:
                connection.close()
            result["ledger_updated"] = True
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
