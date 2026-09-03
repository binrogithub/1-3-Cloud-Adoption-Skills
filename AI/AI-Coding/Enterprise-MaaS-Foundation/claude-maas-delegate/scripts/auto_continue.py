#!/usr/bin/env python3
"""auto_continue — supervisor for `stream protocol error` auto-resume (WP-B).

PRD: docs/PRD_RUNTIME_RESILIENCE_V1.md

Wraps a headless `claude-maas -p` invocation. When the session ends on the
structured API-error marker, waits MAAS_AUTO_CONTINUE_DELAY (default 100s)
and retries with `--resume <same-session-id> -p "continue"`, up to
MAAS_AUTO_CONTINUE_MAX (default 2) retries, then gives up with a non-zero
exit and an audit record.

Design invariants (PRD §B3–B7):

  * Detection NEVER greps stdout — the error string can appear in model
    prose. The authoritative signal is the session JSONL's LAST assistant
    record with isApiErrorMessage === true AND text starting with the marker.
  * Session locking NEVER uses --continue (its semantics is "most recent
    session", which cross-talks under concurrency). First attempt carries
    --session-id <uuid>; retries carry --resume <same uuid>.
  * Only stream-protocol errors are retried. 401/400/OVER_CAPACITY/
    client-abort are terminal; 429 is explicitly NOT covered until the
    adapter stops masking upstream 429 as 502 (PRD_UPSTREAM_PROFILE_V1 D5).
  * Interactive TUI is out of scope — headless -p only.

This module is stdlib-only and doubles as the shared supervisor for
scripts/delegate, scripts/workflow, and client/claude-maas-run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Config (env-overridable)
# ---------------------------------------------------------------------------

DEFAULT_MAX_RETRIES = 2
DEFAULT_DELAY_S = 100.0
MARKER_PREFIX = "API Error: stream protocol error"

# Error texts that must NOT trigger a retry. Any text that is not the
# stream-protocol marker is terminal by default (fail-closed).
TERMINAL_EXAMPLES = (
    "API Error: 401",
    "API Error: 400",
    "API Error: 503",
    "API Error: Request was aborted",
)

AuditSink = Callable[[dict], None]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def auto_continue_enabled() -> bool:
    return os.environ.get("MAAS_AUTO_CONTINUE", "1") != "0"


def max_retries() -> int:
    return max(0, _env_int("MAAS_AUTO_CONTINUE_MAX", DEFAULT_MAX_RETRIES))


def retry_delay() -> float:
    return max(0.0, _env_float("MAAS_AUTO_CONTINUE_DELAY", DEFAULT_DELAY_S))


# ---------------------------------------------------------------------------
# Detection (B3): structured JSONL signal, never stdout grep
# ---------------------------------------------------------------------------


def _text_of(message: dict) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text")
            if isinstance(t, str):
                parts.append(t)
    return "".join(parts)


def _iter_jsonl(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def detect_stream_protocol_error(session_jsonl: Path) -> bool:
    """True iff the LAST assistant record is an API-error message whose text
    starts with the stream-protocol marker. Both conditions required."""
    last_assistant: dict | None = None
    for record in _iter_jsonl(session_jsonl):
        if isinstance(record, dict) and record.get("type") == "assistant":
            last_assistant = record
    if not isinstance(last_assistant, dict):
        return False
    if last_assistant.get("isApiErrorMessage") is not True:
        return False
    message = last_assistant.get("message")
    if not isinstance(message, dict):
        return False
    return _text_of(message).startswith(MARKER_PREFIX)


def detect_terminal_error(session_jsonl: Path) -> str | None:
    """Return the marker text of the last assistant API-error that is NOT
    retryable (used for reporting/audit). None when the session did not end
    on a terminal API error."""
    last_assistant: dict | None = None
    for record in _iter_jsonl(session_jsonl):
        if isinstance(record, dict) and record.get("type") == "assistant":
            last_assistant = record
    if not isinstance(last_assistant, dict):
        return None
    if last_assistant.get("isApiErrorMessage") is not True:
        return None
    message = last_assistant.get("message")
    if not isinstance(message, dict):
        return None
    text = _text_of(message)
    if text.startswith(MARKER_PREFIX):
        return None  # retryable — not terminal
    return text[:120] if text else "(empty api-error text)"


# Record types that constitute a normal session end.  A session whose last
# record is one of these did NOT get silently killed — it reached a natural
# turn boundary (assistant spoke, a stream-json result frame arrived, or a
# user/tool-result record closed the round).
_NORMAL_TERMINAL_TYPES = frozenset({"assistant", "result", "user"})


def detect_silent_kill(session_jsonl: Path) -> dict | None:
    """None when the session ended normally (an assistant/result/user terminal
    record, or a stream-protocol-error record already handled by
    detect_stream_protocol_error). Otherwise a dict describing the last
    record type found, for an honest failure summary.

    A session that ends on a non-terminal record type (``attachment``,
    ``last-prompt``, etc.) or that produced no records at all bears the
    signature of a process killed by an external signal — there is no
    assistant error record and no ``isApiErrorMessage`` marker, so
    detect_stream_protocol_error would never fire.  This detector fills
    that blind spot so the caller can report an honest cause instead of
    falling back to unrelated stderr text.

    Returns at least ``last_record_type`` and ``record_count``.
    """
    # If the session ended on the retryable stream-protocol marker, that
    # is NOT a silent kill — leave it to the existing path.
    if detect_stream_protocol_error(session_jsonl):
        return None
    records = list(_iter_jsonl(session_jsonl))
    if not records:
        # No records at all — the process produced nothing before
        # disappearing.
        return {"last_record_type": None, "record_count": 0}
    last = records[-1]
    last_type = last.get("type") if isinstance(last, dict) else None
    if last_type in _NORMAL_TERMINAL_TYPES:
        return None
    return {"last_record_type": last_type, "record_count": len(records)}


# ---------------------------------------------------------------------------
# Audit (B9)
# ---------------------------------------------------------------------------


def default_audit_path() -> Path:
    home = os.environ.get("HOME", str(Path.home()))
    return Path(home) / ".claude-hybrid" / "auto-continue-audit.jsonl"


_COUNTS = {"attempted": 0, "succeeded": 0, "abandoned": 0}


def counters() -> dict:
    return dict(_COUNTS)


def _write_audit(record: dict, audit_path: Path | None) -> None:
    path = audit_path or default_audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, separators=(",", ":")) + "\n"
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass  # audit is best-effort; never break the run


# ---------------------------------------------------------------------------
# Supervisor (B4 + B5 + B6)
# ---------------------------------------------------------------------------


def find_session_jsonl(claude_config_dir: Path, session_id: str) -> Path | None:
    """Locate <session_id>.jsonl under the profile's projects/ tree."""
    projects = claude_config_dir / "projects"
    if not projects.is_dir():
        return None
    target = f"{session_id}.jsonl"
    for project_dir in projects.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / target
        if candidate.is_file():
            return candidate
    return None


def run_with_auto_continue(
    argv_builder: Callable[[str, bool, str], list[str]],
    *,
    claude_config_dir: Path,
    session_id: str | None = None,
    audit_path: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> dict:
    """Run a headless claude-maas invocation with auto-continue supervision.

    argv_builder(session_id, is_resume, prompt) must return the full argv for
    the underlying CLI call: for the first attempt is_resume=False (the
    builder includes --session-id <sid> and the task prompt); for retries
    is_resume=True and prompt is "continue" (the builder includes
    --resume <sid> -p "continue"). The supervisor owns the retry prompt —
    callers never hardcode it.

    Returns a dict:
      {ok, attempts, retried, session_id, outcome, last_returncode}
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    else:
        try:
            parsed_session_id = uuid.UUID(session_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("session_id must be a UUID") from exc
        if parsed_session_id.int == 0:
            raise ValueError("session_id must not be the nil UUID")
        session_id = str(parsed_session_id)
    attempts = 0
    last_rc: int | None = None
    retried = 0

    if not auto_continue_enabled():
        proc_argv = argv_builder(session_id, False, "")
        try:
            proc = subprocess.run(proc_argv)
            last_rc = proc.returncode
        except OSError as exc:
            return {"ok": False, "attempts": 1, "retried": 0,
                    "session_id": session_id, "outcome": "spawn_error",
                    "last_returncode": None, "error": str(exc)}
        return {"ok": last_rc == 0, "attempts": 1, "retried": 0,
                "session_id": session_id,
                "outcome": "completed" if last_rc == 0 else "failed",
                "last_returncode": last_rc}

    while True:
        attempts += 1
        prompt = "" if attempts == 1 else "continue"
        proc_argv = argv_builder(session_id, attempts > 1, prompt)
        try:
            proc = subprocess.run(proc_argv)
            last_rc = proc.returncode
        except OSError as exc:
            return {"ok": False, "attempts": attempts, "retried": retried,
                    "session_id": session_id, "outcome": "spawn_error",
                    "last_returncode": None, "error": str(exc)}

        session_jsonl = find_session_jsonl(claude_config_dir, session_id)
        ended_on_marker = (
            session_jsonl is not None
            and detect_stream_protocol_error(session_jsonl)
        )

        if not ended_on_marker:
            # Silent-kill detection (PRD AUTO_CONTINUE_SILENT_KILL_V1 §3.1):
            # the session ended on a non-terminal record type with no API
            # error marker — the process was likely killed externally. This
            # is a separate outcome, NOT merged into "failed" or the
            # stream-protocol-error retry path.
            sk_info = (
                detect_silent_kill(session_jsonl)
                if session_jsonl is not None else None
            )
            if sk_info is not None:
                _write_audit({
                    "type": "auto_continue", "session_id": session_id,
                    "attempt": attempts, "trigger": "silent_kill",
                    "delay_s": retry_delay(), "outcome": "silent_kill",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }, audit_path)
                return {"ok": False, "attempts": attempts, "retried": retried,
                        "session_id": session_id, "outcome": "silent_kill",
                        "last_returncode": last_rc,
                        "silent_kill_info": sk_info}

            outcome = "completed" if last_rc == 0 else "failed"
            if retried > 0:
                # B9: the retry produced a final outcome — record it.
                _COUNTS["succeeded" if last_rc == 0 else "abandoned"] += 1
                _write_audit({
                    "type": "auto_continue", "session_id": session_id,
                    "attempt": attempts, "trigger": "stream_protocol_error",
                    "delay_s": retry_delay(),
                    "outcome": "succeeded" if last_rc == 0 else "failed",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }, audit_path)
            return {"ok": last_rc == 0, "attempts": attempts, "retried": retried,
                    "session_id": session_id, "outcome": outcome,
                    "last_returncode": last_rc}

        # Marker detected. Retry budget?
        if retried >= max_retries():
            _COUNTS["attempted"] += 1
            _COUNTS["abandoned"] += 1
            _write_audit({
                "type": "auto_continue", "session_id": session_id,
                "attempt": attempts, "trigger": "stream_protocol_error",
                "delay_s": retry_delay(), "outcome": "abandoned",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }, audit_path)
            return {"ok": False, "attempts": attempts, "retried": retried,
                    "session_id": session_id, "outcome": "abandoned",
                    "last_returncode": last_rc}

        _COUNTS["attempted"] += 1
        _write_audit({
            "type": "auto_continue", "session_id": session_id,
            "attempt": attempts, "trigger": "stream_protocol_error",
            "delay_s": retry_delay(), "outcome": "retrying",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, audit_path)
        sleep(retry_delay())
        retried += 1
        # Loop: next iteration builds --resume <session_id> -p continue.
