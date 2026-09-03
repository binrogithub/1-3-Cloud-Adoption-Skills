#!/usr/bin/env python3
"""Persistent, privacy-preserving session ownership for Claude-MaaS delegates.

The registry stores only hashes of host conversation and workspace identifiers.
It deliberately has no provider credentials or delegated prompts.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 2
HANDLE_RE = re.compile(r"^dlg_[A-Za-z0-9_-]+$")


class SessionConflict(Exception):
    """A session cannot safely be used by the requested caller."""


class SessionBusy(Exception):
    """A caller could not acquire exclusive access to a delegated session."""


@dataclass(frozen=True)
class SessionLease:
    handle: str
    claude_session_id: str | None
    reused: bool


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _workspace_hash(workspace: str) -> str:
    return _hash(str(Path(workspace).expanduser().resolve(strict=False)))


def _new_handle() -> str:
    # token_urlsafe can include only [A-Za-z0-9_-], suitable for a CLI handle.
    return "dlg_" + secrets.token_urlsafe(18).rstrip("=")


@contextmanager
def session_lock(locks_dir: Path, handle: str, timeout_s: float) -> Iterator[None]:
    """Hold an OS-level exclusive lock for a single delegation handle.

    A lock is required before resuming a Claude Code session: concurrent
    prompts in one session would cross-talk.  This fails closed on timeout.
    """
    if not HANDLE_RE.fullmatch(handle):
        raise ValueError("invalid delegation handle")
    if timeout_s < 0:
        raise ValueError("timeout_s must not be negative")

    path = Path(locks_dir)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    lock_path = path / handle
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(lock_path, 0o600)
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SessionBusy(f"delegation session is busy: {handle}")
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class SessionRegistry:
    """SQLite-backed map from a host conversation to a Claude Code session."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            # Migrate from schema 1 if the table has a NOT NULL claude_session_id.
            existing = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            ).fetchone()
            if existing:
                cols = db.execute("PRAGMA table_info(sessions)").fetchall()
                for col in cols:
                    if col[1] == "claude_session_id" and col[3] == 1:  # notnull
                        db.executescript(
                            """
                            DROP INDEX IF EXISTS sessions_owner_conversation;
                            ALTER TABLE sessions RENAME TO sessions_v1_backup;
                            CREATE TABLE sessions (
                              handle TEXT PRIMARY KEY,
                              owner_agent TEXT NOT NULL,
                              owner_conversation_hash TEXT,
                              claude_session_id TEXT UNIQUE,
                              workspace_realpath_hash TEXT NOT NULL,
                              status TEXT NOT NULL,
                              created_at REAL NOT NULL,
                              last_used_at REAL NOT NULL,
                              last_outcome TEXT,
                              schema_version INTEGER NOT NULL
                            );
                            INSERT INTO sessions SELECT * FROM sessions_v1_backup;
                            DROP TABLE sessions_v1_backup;
                            """
                        )
                        break
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  handle TEXT PRIMARY KEY,
                  owner_agent TEXT NOT NULL,
                  owner_conversation_hash TEXT,
                  claude_session_id TEXT UNIQUE,
                  workspace_realpath_hash TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at REAL NOT NULL,
                  last_used_at REAL NOT NULL,
                  last_outcome TEXT,
                  schema_version INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS sessions_owner_conversation
                  ON sessions(owner_agent, owner_conversation_hash)
                  WHERE owner_conversation_hash IS NOT NULL;
                """
            )
        os.chmod(self.path, 0o600)

    @staticmethod
    def _assert_owner(owner_agent: str) -> None:
        if not isinstance(owner_agent, str) or not owner_agent.strip():
            raise ValueError("owner_agent must be a non-empty string")

    @staticmethod
    def _lease(row: sqlite3.Row, *, reused: bool) -> SessionLease:
        return SessionLease(
            handle=row["handle"],
            claude_session_id=row["claude_session_id"],
            reused=reused,
        )

    def acquire(
        self, owner_agent: str, conversation_key: str | None, workspace: str
    ) -> SessionLease:
        """Acquire a lease for a host conversation, creating it if necessary.

        A newly created lease is *pending*: it has no upstream Claude session ID
        until bind_session is called with the real ID returned by a successful
        Claude invocation.  Missing host conversation IDs intentionally create
        a fresh random handle; callers can persist and pass that handle on
        future invocations.
        """
        self._assert_owner(owner_agent)
        if conversation_key is not None and not isinstance(conversation_key, str):
            raise ValueError("conversation_key must be a string or None")
        conversation_hash = _hash(conversation_key) if conversation_key else None
        workspace_hash = _workspace_hash(workspace)
        now = time.time()

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if conversation_hash is not None:
                row = db.execute(
                    """
                    SELECT * FROM sessions
                    WHERE owner_agent = ? AND owner_conversation_hash = ?
                    """,
                    (owner_agent, conversation_hash),
                ).fetchone()
                if row is not None:
                    if row["workspace_realpath_hash"] != workspace_hash:
                        raise SessionConflict("conversation belongs to another workspace")
                    if row["status"] not in ("active", "pending"):
                        raise SessionConflict("conversation session is closed")
                    db.execute(
                        "UPDATE sessions SET last_used_at = ? WHERE handle = ?",
                        (now, row["handle"]),
                    )
                    # A bound session is reused; a pending one is not yet reusable.
                    reused = row["claude_session_id"] is not None
                    return self._lease(row, reused=reused)

            handle = _new_handle()
            db.execute(
                """
                INSERT INTO sessions (
                  handle, owner_agent, owner_conversation_hash, claude_session_id,
                  workspace_realpath_hash, status, created_at, last_used_at,
                  last_outcome, schema_version
                ) VALUES (?, ?, ?, NULL, ?, 'pending', ?, ?, NULL, ?)
                """,
                (
                    handle,
                    owner_agent,
                    conversation_hash,
                    workspace_hash,
                    now,
                    now,
                    SCHEMA_VERSION,
                ),
            )
        return SessionLease(handle, None, reused=False)

    def acquire_handle(self, handle: str, owner_agent: str, workspace: str) -> SessionLease:
        """Reuse an explicit handle after checking its agent and workspace owner."""
        self._assert_owner(owner_agent)
        workspace_hash = _workspace_hash(workspace)
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM sessions WHERE handle = ?", (handle,)).fetchone()
            if row is None:
                raise SessionConflict("unknown delegation handle")
            if row["owner_agent"] != owner_agent:
                raise SessionConflict("delegation handle belongs to another agent")
            if row["workspace_realpath_hash"] != workspace_hash:
                raise SessionConflict("delegation handle belongs to another workspace")
            if row["status"] not in ("active", "pending"):
                raise SessionConflict("delegation handle is closed")
            db.execute(
                "UPDATE sessions SET last_used_at = ? WHERE handle = ?", (now, handle)
            )
            reused = row["claude_session_id"] is not None
            return self._lease(row, reused=reused)

    def bind_session(self, handle: str, claude_session_id: str) -> None:
        """Atomically bind the real session ID returned by a successful Claude call.

        Transitions a pending session to active with the upstream-returned UUID.
        Raises SessionConflict if the handle is unknown or already bound.
        """
        try:
            claude_session_id = str(uuid.UUID(claude_session_id))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("claude_session_id must be a UUID") from exc
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM sessions WHERE handle = ?", (handle,)).fetchone()
            if row is None:
                raise SessionConflict("unknown delegation handle")
            if row["claude_session_id"] is not None:
                if row["claude_session_id"] == claude_session_id:
                    return  # idempotent rebind
                raise SessionConflict("handle is already bound to a different session")
            db.execute(
                """
                UPDATE sessions
                SET claude_session_id = ?, status = 'active'
                WHERE handle = ? AND claude_session_id IS NULL
                """,
                (claude_session_id, handle),
            )

    def discard_unbound(self, handle: str) -> bool:
        """Remove an unbound (pending) lease after a failed first call.

        Returns True if the handle was removed, False if it was already bound
        or not found.  A bound session is never discarded.
        """
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM sessions WHERE handle = ?", (handle,)).fetchone()
            if row is None:
                return False
            if row["claude_session_id"] is not None:
                return False  # bound — do not discard
            db.execute("DELETE FROM sessions WHERE handle = ?", (handle,))
            return True

    def close(self, handle: str) -> bool:
        """Close an active or pending handle. The session record remains for audit."""
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE sessions SET status = 'closed', last_used_at = ?
                WHERE handle = ? AND status IN ('active', 'pending')
                """,
                (time.time(), handle),
            )
            return cursor.rowcount == 1

    def status(self, handle: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE handle = ?", (handle,)).fetchone()
        return dict(row) if row is not None else None

    def record_outcome(self, handle: str, outcome: str) -> None:
        """Record a non-sensitive terminal result for status and later GC."""
        with self._connect() as db:
            cursor = db.execute(
                """
                UPDATE sessions SET last_outcome = ?, last_used_at = ?
                WHERE handle = ? AND status IN ('active', 'pending')
                """,
                (outcome, time.time(), handle),
            )
            if cursor.rowcount != 1:
                raise SessionConflict("delegation handle is not active")

    def gc(self, older_than_days: int) -> int:
        if older_than_days < 0:
            raise ValueError("older_than_days must not be negative")
        cutoff = time.time() - older_than_days * 24 * 60 * 60
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM sessions WHERE status = 'closed' AND last_used_at < ?",
                (cutoff,),
            )
            return cursor.rowcount
