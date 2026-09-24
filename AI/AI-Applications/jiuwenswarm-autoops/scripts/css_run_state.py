"""Durable state helpers for long-running CSS pressure runs."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = 2


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink state path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def checkpoint_path(state_dir: Path, run_id: str) -> Path:
    return state_dir / f"{run_id}.checkpoint.json"


def load_checkpoint(path: Path, *, plan_digest: str, profile_id: str,
                    duration_seconds: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"checkpoint is missing or not a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkpoint must be a JSON object")
    if value.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("checkpoint schema is incompatible; CSS writes are blocked")
    if value.get("plan_digest") != plan_digest:
        raise ValueError("plan differs from checkpoint; CSS writes are blocked")
    if value.get("profile_id") != profile_id:
        raise ValueError("profile differs from checkpoint; CSS writes are blocked")
    if int(value.get("duration_seconds", -1)) != duration_seconds:
        raise ValueError("duration differs from checkpoint; CSS writes are blocked")
    if value.get("status") not in {"RUNNING", "RECOVERY_BLOCKED"}:
        raise ValueError("checkpoint is already terminal and cannot be resumed")
    return value


def unresolved_actions(database: Path, resource: str) -> list[dict[str, Any]]:
    if not database.exists():
        return []
    import sqlite3

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT operation_id,profile_id,direction,delta,target_nodes,status,error_code "
            "FROM css_actions WHERE resource_key=? AND status IN "
            "('INTENT_RECORDED','SUBMITTED','RECONCILING','UNKNOWN','CAPACITY_READY',"
            "'VERIFYING_BUSINESS','DEGRADED') ORDER BY intent_recorded_at,operation_id",
            (resource,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def reconcile_action_status(database: Path, operation_id: str, new_status: str) -> str:
    from css_action_ledger import open_action_db, transition_status

    connection = open_action_db(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM css_actions WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"action disappeared from ledger: {operation_id}")
        current = str(row["status"])
        if current == "INTENT_RECORDED" and new_status in {"CAPACITY_READY", "SUCCEEDED", "DEGRADED"}:
            connection.execute(
                "UPDATE css_actions SET status='RECONCILING', updated_at=? WHERE operation_id=?",
                (datetime.now(timezone.utc).isoformat(), operation_id),
            )
            current = "RECONCILING"
        target = transition_status(current, new_status)
        connection.execute(
            "UPDATE css_actions SET status=?, reconciled_at=?, updated_at=? WHERE operation_id=?",
            (target, datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat(), operation_id),
        )
        connection.commit()
        return target
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
