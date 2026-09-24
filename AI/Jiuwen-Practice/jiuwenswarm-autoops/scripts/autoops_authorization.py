#!/usr/bin/env python3
"""Validate one-time, operator-created AutoOps execution approvals."""
from __future__ import annotations

import json
import fcntl
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / ".runtime" / "authorizations"


class AuthorizationConsumed(Exception):
    """Raised when a one-time approval was already reserved by another caller."""


def authorization_dir() -> Path:
    return Path(os.environ.get("AUTOOPS_AUTHORIZATION_DIR", str(DEFAULT_DIR)))


def load_approval(authorization_id: str, *, task_id: str, job: str, target: str):
    """Return (status, details), without treating a caller supplied ID as proof."""
    if not authorization_id:
        return "AUTHORIZATION_REQUIRED", {"error": "A trusted operator approval is required before execution."}
    if len(authorization_id) > 128 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in authorization_id):
        return "AUTHORIZATION_DENIED", {"error": "The authorization reference is malformed."}
    record_path = authorization_dir() / f"{authorization_id}.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "AUTHORIZATION_REQUIRED", {"error": "No trusted operator approval record exists for this request."}
    if record.get("status") != "APPROVED":
        return "AUTHORIZATION_DENIED", {"error": "The operator approval is not active."}
    if any(record.get(field) != value for field, value in (("task_id", task_id), ("job", job), ("target", target))):
        return "AUTHORIZATION_DENIED", {"error": "The approval scope does not match this task."}
    try:
        if float(record["expires_at"]) <= time.time():
            return "AUTHORIZATION_DENIED", {"error": "The operator approval has expired."}
    except (KeyError, TypeError, ValueError):
        return "AUTHORIZATION_DENIED", {"error": "The approval expiry is invalid."}
    return "APPROVED", record


def consume_approval(authorization_id: str, record) -> None:
    """Consume an approval before an external write is submitted."""
    path = authorization_dir() / f"{authorization_id}.json"
    with path.open("r+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            current = json.load(stream)
            if current.get("status") != "APPROVED":
                raise AuthorizationConsumed
            try:
                if float(current["expires_at"]) <= time.time():
                    raise AuthorizationConsumed
            except (KeyError, TypeError, ValueError) as exc:
                raise AuthorizationConsumed from exc
            consumed = dict(current)
            consumed["status"] = "CONSUMED"
            consumed["consumed_at"] = int(time.time())
            stream.seek(0)
            stream.truncate()
            json.dump(consumed, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
