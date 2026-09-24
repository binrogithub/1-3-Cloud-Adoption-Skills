"""Durable CSS action state transitions shared by E01 and reconciliation."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


TERMINAL_STATES = {"SUCCEEDED", "BLOCKED", "FAILED", "CANCELLED"}
TRANSITIONS = {
    "PROPOSED": {"PRECHECKED", "BLOCKED", "UNKNOWN"},
    "PRECHECKED": {"AUTHORIZED", "BLOCKED"},
    "AUTHORIZED": {"INTENT_RECORDED", "BLOCKED"},
    "INTENT_RECORDED": {"SUBMITTED", "RECONCILING", "UNKNOWN", "BLOCKED", "FAILED"},
    "SUBMITTED": {"RECONCILING", "CAPACITY_READY", "VERIFYING_BUSINESS", "SUCCEEDED",
                   "UNVERIFIED", "DEGRADED", "UNKNOWN", "FAILED", "BLOCKED"},
    "RECONCILING": {"RECONCILING", "CAPACITY_READY", "VERIFYING_BUSINESS", "SUCCEEDED",
                     "UNVERIFIED", "DEGRADED", "UNKNOWN", "FAILED", "BLOCKED"},
    "CAPACITY_READY": {"CAPACITY_READY", "VERIFYING_BUSINESS", "SUCCEEDED", "UNVERIFIED",
                        "DEGRADED", "UNKNOWN", "FAILED", "BLOCKED"},
    "VERIFYING_BUSINESS": {"VERIFYING_BUSINESS", "SUCCEEDED", "UNVERIFIED", "DEGRADED",
                            "UNKNOWN", "FAILED", "BLOCKED"},
    "VERIFIED": {"SUCCEEDED", "RECONCILING", "CAPACITY_READY", "UNVERIFIED", "FAILED"},
    "UNVERIFIED": {"VERIFYING_BUSINESS", "SUCCEEDED", "DEGRADED", "UNKNOWN", "FAILED", "BLOCKED"},
    "DEGRADED": {"RECONCILING", "VERIFYING_BUSINESS", "SUCCEEDED", "UNKNOWN", "FAILED", "BLOCKED"},
    "UNKNOWN": {"RECONCILING", "CAPACITY_READY", "VERIFYING_BUSINESS", "FAILED", "BLOCKED"},
    "BLOCKED": set(),
    "FAILED": set(),
    "SUCCEEDED": set(),
}


def transition_status(current: str, target: str) -> str:
    """Validate and return a durable state transition.

    Repeating the same state is idempotent so a crashed process can safely
    replay its last ledger update. Terminal states cannot be reopened.
    """
    current = str(current).upper()
    target = str(target).upper()
    if current == target:
        return target
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid CSS action transition: {current} -> {target}")
    return target


def resource_key(profile: dict) -> str:
    """Return a stable identity independent of a local profile alias."""
    fields = (
        profile.get("provider", "huaweicloud"), profile.get("domain_id", ""),
        profile.get("project_id", ""), profile.get("region", ""),
        profile.get("cluster_id", ""),
    )
    return "|".join(str(value).strip().casefold() for value in fields)


def open_action_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Open and migrate the local action ledger.

    The caller owns the transaction. The partial unique index is the local
    single-writer fence; a distributed deployment must provide a shared store
    before enabling more than one writer.
    """
    db_path = Path(path or os.environ.get("AUTOOPS_CSS_ACTION_DB", ".runtime/css-actions.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("""CREATE TABLE IF NOT EXISTS css_actions (
        operation_id TEXT PRIMARY KEY, task_id TEXT, profile_id TEXT, direction TEXT,
        delta INTEGER, status TEXT, cloud_request_id TEXT,
        resource_key TEXT, target_nodes INTEGER, policy_revision INTEGER,
        evidence_ref TEXT, intent_recorded_at TEXT, submitted_at TEXT,
        reconciled_at TEXT, updated_at TEXT, error_code TEXT
    )""")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(css_actions)")}
    additions = {
        "resource_key": "TEXT", "target_nodes": "INTEGER", "policy_revision": "INTEGER",
        "evidence_ref": "TEXT", "intent_recorded_at": "TEXT", "submitted_at": "TEXT",
        "reconciled_at": "TEXT", "updated_at": "TEXT", "error_code": "TEXT",
    }
    for name, kind in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE css_actions ADD COLUMN {name} {kind}")
    connection.execute("CREATE INDEX IF NOT EXISTS css_actions_resource_status ON css_actions(resource_key, status)")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS css_actions_active_resource
        ON css_actions(resource_key)
        WHERE resource_key IS NOT NULL AND status IN
        ('INTENT_RECORDED','SUBMITTED','RECONCILING','UNKNOWN','CAPACITY_READY','VERIFYING_BUSINESS','DEGRADED')""")
    return connection
