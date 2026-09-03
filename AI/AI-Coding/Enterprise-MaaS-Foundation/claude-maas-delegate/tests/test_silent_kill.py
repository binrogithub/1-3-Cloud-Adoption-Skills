#!/usr/bin/env python3
"""Unit tests for silent-kill detection (PRD AUTO_CONTINUE_SILENT_KILL_V1 §5).

Covers:
  * detect_silent_kill returns non-None for a session ending on
    attachment/last-prompt with no assistant error record.
  * detect_silent_kill returns None for a normal session ending on an
    assistant text record.
  * detect_silent_kill returns None when detect_stream_protocol_error is
    True (the two detectors are mutually exclusive — §4 reverse gate).
  * run_with_auto_continue returns outcome == "silent_kill" for a killed
    session and does NOT enter the stream-protocol-error retry path.
  * Existing stream-protocol-error detection still works (regression).
"""
from __future__ import annotations

import json
import importlib.util
import importlib.machinery
import sys
import tempfile
from pathlib import Path

import pytest

# Load auto_continue.py as a module (it lives in scripts/, no package).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "auto_continue.py"
_loader = importlib.machinery.SourceFileLoader("auto_continue_mod", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("auto_continue_mod", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return path


def _assistant_text(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _assistant_api_error(text: str) -> dict:
    return {
        "type": "assistant",
        "isApiErrorMessage": True,
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _user_tool_result(text: str) -> dict:
    return {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": text}]},
    }


# ---------------------------------------------------------------------------
# detect_silent_kill — unit tests
# ---------------------------------------------------------------------------


class TestDetectSilentKill:
    def test_normal_assistant_end_returns_none(self, tmp_path):
        """A session ending on an assistant text record is normal."""
        session = _write_jsonl(tmp_path / "normal.jsonl", [
            _assistant_text("Let me run the tests."),
            _user_tool_result("36 passed"),
            _assistant_text("All tests pass. Done."),
        ])
        assert mod.detect_silent_kill(session) is None

    def test_normal_result_end_returns_none(self, tmp_path):
        """A stream-json session ending on a result frame is normal."""
        session = _write_jsonl(tmp_path / "result.jsonl", [
            _assistant_text("Working..."),
            {"type": "result", "subtype": "success", "is_error": False},
        ])
        assert mod.detect_silent_kill(session) is None

    def test_normal_user_end_returns_none(self, tmp_path):
        """A session ending on a user/tool-result record is a normal round."""
        session = _write_jsonl(tmp_path / "user.jsonl", [
            _assistant_text("Running tests."),
            _user_tool_result("36 passed"),
        ])
        assert mod.detect_silent_kill(session) is None

    def test_attachment_last_prompt_end_returns_non_none(self, tmp_path):
        """The PRD §1 signature: ends on attachment + last-prompt, no error."""
        session = _write_jsonl(tmp_path / "killed.jsonl", [
            _assistant_text("Let me check git status."),
            _user_tool_result(" M bin/plan.py"),
            {"type": "attachment"},
            {"type": "last-prompt"},
        ])
        result = mod.detect_silent_kill(session)
        assert result is not None
        assert result["last_record_type"] == "last-prompt"
        assert result["record_count"] == 4

    def test_attachment_only_end_returns_non_none(self, tmp_path):
        """Ending on a bare attachment record."""
        session = _write_jsonl(tmp_path / "att.jsonl", [
            _assistant_text("Working..."),
            {"type": "attachment"},
        ])
        result = mod.detect_silent_kill(session)
        assert result is not None
        assert result["last_record_type"] == "attachment"

    def test_empty_file_returns_non_none(self, tmp_path):
        """A session file with no records at all."""
        session = tmp_path / "empty.jsonl"
        session.write_text("")
        result = mod.detect_silent_kill(session)
        assert result is not None
        assert result["last_record_type"] is None
        assert result["record_count"] == 0

    def test_stream_protocol_error_takes_precedence(self, tmp_path):
        """If detect_stream_protocol_error is True, detect_silent_kill must
        return None — the two detectors are mutually exclusive (§4)."""
        session = _write_jsonl(tmp_path / "spe.jsonl", [
            _assistant_text("Working..."),
            _assistant_api_error("API Error: stream protocol error"),
        ])
        # Sanity: the stream-protocol detector fires.
        assert mod.detect_stream_protocol_error(session) is True
        # And therefore silent-kill does NOT fire.
        assert mod.detect_silent_kill(session) is None


# ---------------------------------------------------------------------------
# run_with_auto_continue — integration of silent_kill outcome
# ---------------------------------------------------------------------------


class TestRunWithAutoContinueSilentKill:
    def _make_session(self, tmp_path, session_id, records):
        project_dir = tmp_path / "projects" / "proj"
        project_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(project_dir / f"{session_id}.jsonl", records)

    def test_silent_kill_outcome(self, tmp_path, monkeypatch):
        """A killed session produces outcome == 'silent_kill', not 'failed'."""
        session_id = "11111111-1111-4111-8111-111111111111"
        self._make_session(tmp_path, session_id, [
            _assistant_text("Running git status."),
            _user_tool_result(" M bin/plan.py"),
            {"type": "attachment"},
            {"type": "last-prompt"},
        ])

        # Stub subprocess.run to simulate a killed process (rc=137).
        class _FakeProc:
            returncode = 137

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: _FakeProc())
        monkeypatch.setattr(mod, "auto_continue_enabled", lambda: True)

        def build(sid, is_resume, prompt):
            return ["true"]  # argv is irrelevant; subprocess is stubbed

        result = mod.run_with_auto_continue(
            build,
            claude_config_dir=tmp_path,
            session_id=session_id,
            audit_path=tmp_path / "audit.jsonl",
        )
        assert result["outcome"] == "silent_kill"
        assert result["ok"] is False
        assert result["silent_kill_info"]["last_record_type"] == "last-prompt"
        assert result["silent_kill_info"]["record_count"] == 4

    def test_stream_protocol_error_still_retries(self, tmp_path, monkeypatch):
        """Regression: stream-protocol-error detection is not weakened."""
        session_id = "22222222-2222-4222-8222-222222222222"
        self._make_session(tmp_path, session_id, [
            _assistant_api_error("API Error: stream protocol error"),
        ])

        calls = []

        class _FakeProc:
            returncode = 1

        def fake_run(argv, *a, **kw):
            calls.append(argv)
            return _FakeProc()

        monkeypatch.setattr(mod.subprocess, "run", fake_run)
        monkeypatch.setattr(mod, "auto_continue_enabled", lambda: True)
        monkeypatch.setattr(mod, "max_retries", lambda: 1)
        monkeypatch.setattr(mod, "retry_delay", lambda: 0.0)

        def build(sid, is_resume, prompt):
            return ["true"]

        result = mod.run_with_auto_continue(
            build,
            claude_config_dir=tmp_path,
            session_id=session_id,
            audit_path=tmp_path / "audit.jsonl",
            sleep=lambda s: None,
        )
        # Should have retried (2 calls: initial + 1 retry).
        assert len(calls) == 2
        assert result["outcome"] == "abandoned"

    def test_normal_completion_not_silent_kill(self, tmp_path, monkeypatch):
        """A session ending on assistant text is 'completed', not 'silent_kill'."""
        session_id = "33333333-3333-4333-8333-333333333333"
        self._make_session(tmp_path, session_id, [
            _assistant_text("All done."),
        ])

        class _FakeProc:
            returncode = 0

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: _FakeProc())
        monkeypatch.setattr(mod, "auto_continue_enabled", lambda: True)

        def build(sid, is_resume, prompt):
            return ["true"]

        result = mod.run_with_auto_continue(
            build,
            claude_config_dir=tmp_path,
            session_id=session_id,
            audit_path=tmp_path / "audit.jsonl",
        )
        assert result["outcome"] == "completed"
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Audit record — silent_kill outcome value
# ---------------------------------------------------------------------------


class TestAuditSilentKill:
    def test_audit_records_silent_kill(self, tmp_path, monkeypatch):
        """The audit log receives an outcome == 'silent_kill' record."""
        session_id = "44444444-4444-4444-8444-444444444444"
        project_dir = tmp_path / "projects" / "proj"
        project_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(project_dir / f"{session_id}.jsonl", [
            _assistant_text("Working..."),
            {"type": "last-prompt"},
        ])

        audit_path = tmp_path / "audit.jsonl"

        class _FakeProc:
            returncode = 137

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: _FakeProc())
        monkeypatch.setattr(mod, "auto_continue_enabled", lambda: True)

        def build(sid, is_resume, prompt):
            return ["true"]

        mod.run_with_auto_continue(
            build,
            claude_config_dir=tmp_path,
            session_id=session_id,
            audit_path=audit_path,
        )
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["outcome"] == "silent_kill"
        assert record["trigger"] == "silent_kill"
        assert record["type"] == "auto_continue"
        assert record["session_id"] == session_id


# ---------------------------------------------------------------------------
# delegate — summary construction for silent_kill (PRD §3.2)
# ---------------------------------------------------------------------------


def _load_delegate():
    """Load scripts/delegate as an importable module."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "delegate"
    loader = importlib.machinery.SourceFileLoader("delegate_mod", str(path))
    spec = importlib.util.spec_from_loader("delegate_mod", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


class TestDelegateSilentKillSummary:
    def test_silent_kill_summary_is_structured(self, tmp_path, monkeypatch):
        """When the supervisor reports silent_kill, the delegate summary must
        NOT be raw stderr — it must be the structured honest message."""
        delegate = _load_delegate()

        # Point audit at a temp file.
        monkeypatch.setattr(delegate, "AUDIT_DIR", tmp_path)
        monkeypatch.setattr(delegate, "AUDIT_FILE", tmp_path / "audit.jsonl")

        # Inject a fake client that returns a silent-kill result.
        def fake_client(goal, **kw):
            return {
                "ok": False,
                "stdout": "",
                "stderr": '[claude-code:unrecognized_model] {"model":"glm-5.2"}',
                "status_code": None,
                "retry_after": None,
                "tokens_in": None,
                "tokens_out": None,
                "files_changed": [],
                "timed_out": False,
                "session_id": None,
                "supervisor_outcome": "silent_kill",
                "silent_kill_info": {
                    "last_record_type": "last-prompt",
                    "record_count": 183,
                },
            }

        delegate.set_client_factory(lambda **kw: fake_client)

        brief = {
            "task_type": "bug_fix",
            "goal": "fix the bug",
            "scope": ["src/main.py"],
        }
        result = delegate.run(brief, cwd=str(tmp_path))

        assert result["status"] == "needs_escalation"
        summary = result["summary"]
        # The misleading stderr line must NOT be the summary.
        assert "unrecognized_model" not in summary
        # The structured message must mention the last record type.
        assert '"last-prompt"' in summary
        assert "no API error recorded" in summary
        assert "silent" not in summary.lower() or "killed" in summary.lower()
        # stderr is preserved separately, not folded into summary.
        assert result.get("stderr", "").startswith("[claude-code:unrecognized_model]")

    def test_non_silent_kill_failure_uses_stderr(self, tmp_path, monkeypatch):
        """A normal (non-silent-kill) failure still uses stderr as summary."""
        delegate = _load_delegate()

        monkeypatch.setattr(delegate, "AUDIT_DIR", tmp_path)
        monkeypatch.setattr(delegate, "AUDIT_FILE", tmp_path / "audit.jsonl")

        def fake_client(goal, **kw):
            return {
                "ok": False,
                "stdout": "",
                "stderr": "Error: 401 unauthorized",
                "status_code": 401,
                "retry_after": None,
                "tokens_in": None,
                "tokens_out": None,
                "files_changed": [],
                "timed_out": False,
                "session_id": None,
                "supervisor_outcome": "failed",
                "silent_kill_info": None,
            }

        delegate.set_client_factory(lambda **kw: fake_client)

        brief = {
            "task_type": "bug_fix",
            "goal": "fix the bug",
            "scope": ["src/main.py"],
        }
        result = delegate.run(brief, cwd=str(tmp_path))

        assert result["status"] == "needs_escalation"
        assert result["summary"] == "Error: 401 unauthorized"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
