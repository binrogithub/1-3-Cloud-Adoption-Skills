#!/usr/bin/env python3
"""Validate and reserve a published, incident-scoped AutoOps preauthorization."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = Path.home() / ".config" / "jiuwenswarm-autoops" / "preauthorization.json"
DEFAULT_DB = ROOT / ".runtime" / "autoops-state.db"


def policy_path() -> Path:
    return Path(os.environ.get("AUTOOPS_PREAUTHORIZATION_FILE", str(DEFAULT_POLICY))).expanduser()


def load_policy(policy_id: str) -> tuple[str, dict[str, Any]]:
    if not policy_id or len(policy_id) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in policy_id):
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization reference is malformed."}
    path = policy_path()
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization policy must be a private regular file."}
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "PREAUTHORIZATION_REQUIRED", {"error": "No active preauthorization policy is configured."}
    if not isinstance(policy, dict) or policy.get("schema_version") != 1 or policy.get("policy_id") != policy_id:
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization policy ID does not match."}
    if policy.get("status") != "ACTIVE":
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization policy is not active."}
    try:
        expires_at = datetime.fromisoformat(str(policy["expires_at"]).replace("Z", "+00:00"))
        if expires_at.tzinfo is None or expires_at.timestamp() <= time.time():
            return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization policy has expired."}
    except (KeyError, TypeError, ValueError):
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization expiry is invalid."}
    scope = policy.get("scope")
    limits = policy.get("limits")
    if not isinstance(policy.get("principal"), str) or not policy["principal"]:
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization principal is invalid."}
    if not isinstance(scope, dict) or not isinstance(limits, dict) or any(not isinstance(scope.get(key), str) or not scope[key] for key in ("capability", "job", "target", "service")):
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization scope or limits are invalid."}
    if limits.get("max_actions_per_incident") != 1:
        return "PREAUTHORIZATION_DENIED", {"error": "max_actions_per_incident must be exactly 1 for this policy version."}
    if not isinstance(limits.get("cooldown_seconds", 0), int) or not 0 <= limits["cooldown_seconds"] <= 86400:
        return "PREAUTHORIZATION_DENIED", {"error": "cooldown_seconds must be from 0 through 86400."}
    return "PREAUTHORIZED", policy


def validate_scope(policy: dict[str, Any], *, capability: str, job: str, target: str, service: str) -> tuple[str, dict[str, Any]]:
    scope = policy["scope"]
    expected = {"capability": capability, "job": job, "target": target, "service": service}
    if any(scope.get(key) != value for key, value in expected.items()):
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization scope does not match this action."}
    return "PREAUTHORIZED", policy


def reserve(policy: dict[str, Any], *, incident_id: str, operation_id: str) -> tuple[str, dict[str, Any]]:
    """Atomically reserve one incident action and its target write lock."""
    if not incident_id or not operation_id:
        return "PREAUTHORIZATION_DENIED", {"error": "incident_id and operation_id are required."}
    db_path = Path(os.environ.get("AUTOOPS_STATE_DB", str(DEFAULT_DB)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.executescript(
            """CREATE TABLE IF NOT EXISTS preauthorization_reservations (
                 policy_id TEXT NOT NULL, incident_id TEXT NOT NULL,
                 operation_id TEXT NOT NULL UNIQUE, reserved_at INTEGER NOT NULL,
                 PRIMARY KEY(policy_id, incident_id)
               );
               CREATE TABLE IF NOT EXISTS preauthorization_target_locks (
                 policy_id TEXT NOT NULL, target TEXT NOT NULL, job TEXT NOT NULL,
                 service TEXT NOT NULL, incident_id TEXT NOT NULL,
                 operation_id TEXT NOT NULL UNIQUE, locked_at INTEGER NOT NULL,
                 PRIMARY KEY(policy_id, target, job, service)
               )"""
        )
        connection.execute("BEGIN IMMEDIATE")
        policy_id = str(policy["policy_id"])
        existing = connection.execute(
            "SELECT operation_id FROM preauthorization_reservations WHERE policy_id=? AND incident_id=?",
            (policy_id, incident_id),
        ).fetchone()
        if existing:
            connection.rollback()
            if existing[0] == operation_id:
                # Backfill the target lock for reservations created before
                # target locking was introduced. Ignore a lock already held
                # by another incident; this call is still idempotent for the
                # original operation.
                connection.execute(
                    "INSERT OR IGNORE INTO preauthorization_target_locks "
                    "(policy_id,target,job,service,incident_id,operation_id,locked_at) VALUES(?,?,?,?,?,?,?)",
                    (policy_id, policy["scope"]["target"], policy["scope"]["job"],
                     policy["scope"]["service"], incident_id, operation_id, int(time.time())),
                )
                connection.commit()
                return "PREAUTHORIZATION_ALREADY_RESERVED", {"error": "This operation already reserved the incident action."}
            return "PREAUTHORIZATION_DENIED", {"error": "The incident already has its maximum reserved action."}
        cooldown = int(policy["limits"].get("cooldown_seconds", 0))
        if cooldown:
            latest = connection.execute(
                "SELECT reserved_at FROM preauthorization_reservations WHERE policy_id=? ORDER BY reserved_at DESC LIMIT 1",
                (policy_id,),
            ).fetchone()
            if latest and int(time.time()) - int(latest[0]) < cooldown:
                connection.rollback()
                return "PREAUTHORIZATION_COOLDOWN", {"error": "The preauthorization cooldown is active."}
        scope = policy["scope"]
        lock = connection.execute(
            "SELECT incident_id,operation_id FROM preauthorization_target_locks "
            "WHERE policy_id=? AND target=? AND job=? AND service=?",
            (policy_id, scope["target"], scope["job"], scope["service"]),
        ).fetchone()
        if lock:
            connection.rollback()
            return "PREAUTHORIZATION_TARGET_BUSY", {
                "error": "The target has an unresolved preauthorized action.",
                "incident_id": lock[0], "operation_id": lock[1],
            }
        connection.execute(
            "INSERT INTO preauthorization_reservations(policy_id,incident_id,operation_id,reserved_at) VALUES(?,?,?,?)",
            (policy_id, incident_id, operation_id, int(time.time())),
        )
        connection.execute(
            "INSERT INTO preauthorization_target_locks "
            "(policy_id,target,job,service,incident_id,operation_id,locked_at) VALUES(?,?,?,?,?,?,?)",
            (policy_id, scope["target"], scope["job"], scope["service"],
             incident_id, operation_id, int(time.time())),
        )
        connection.commit()
        return "PREAUTHORIZED", {"policy_id": policy_id, "incident_id": incident_id, "operation_id": operation_id}
    except sqlite3.IntegrityError:
        connection.rollback()
        return "PREAUTHORIZATION_DENIED", {"error": "The preauthorization operation was reserved concurrently."}
    finally:
        connection.close()


def finalize_reservation(policy: dict[str, Any], *, incident_id: str, operation_id: str,
                         execution_status: str) -> tuple[str, dict[str, Any]]:
    """Release a target lock only after a known terminal execution result."""
    terminal = {"SUCCEEDED", "FAILED", "NO_CHANGE", "CANCELLED"}
    status = str(execution_status).upper()
    if status not in terminal:
        return "PREAUTHORIZATION_HELD", {
            "policy_id": policy["policy_id"], "incident_id": incident_id,
            "operation_id": operation_id, "execution_status": execution_status,
        }
    db_path = Path(os.environ.get("AUTOOPS_STATE_DB", str(DEFAULT_DB)))
    connection = sqlite3.connect(db_path, timeout=5)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("BEGIN IMMEDIATE")
        scope = policy["scope"]
        result = connection.execute(
            "DELETE FROM preauthorization_target_locks WHERE policy_id=? AND target=? "
            "AND job=? AND service=? AND incident_id=? AND operation_id=?",
            (policy["policy_id"], scope["target"], scope["job"], scope["service"],
             incident_id, operation_id),
        )
        connection.commit()
        return ("PREAUTHORIZATION_RELEASED" if result.rowcount else "PREAUTHORIZATION_NOT_LOCKED", {
            "policy_id": policy["policy_id"], "incident_id": incident_id,
            "operation_id": operation_id, "execution_status": execution_status,
        })
    except sqlite3.Error as exc:
        connection.rollback()
        return "PREAUTHORIZATION_LOCK_ERROR", {"error": str(exc)}
    finally:
        connection.close()
