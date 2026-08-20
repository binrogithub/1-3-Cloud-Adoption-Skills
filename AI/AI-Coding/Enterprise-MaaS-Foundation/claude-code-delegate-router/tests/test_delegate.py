"""Safety tests for the structured single-task delegate runner (scripts/delegate).

These tests verify the delegation contract from PRD section 8:

  * ``bounded_attempts`` clamps to 1..2 and ``bounded_turns`` clamps to 1..MAX_TURNS.
  * Image briefs are rejected *before* the client is launched.
  * Two consecutive failures return ``needs_escalation`` with exactly 2 attempts.
  * 429 Retry-After is honored but total attempts never exceed 2.
  * 401/403 fail immediately with no retry.
  * 5xx allows one retry then structured failure.
  * Timeout handling produces a structured failure.
  * Acceptance command runs with an explicit cwd and timeout.
  * Audit redaction: brief text and tool arguments are NEVER stored in audit.
  * ``--max-turns`` is propagated to the client.
  * The model is always ``glm-5.2``.
  * The ``fallback`` audit field is always ``false``.
  * Empty scope on a write-op task type is rejected as ``invalid_brief``.
  * A successful acceptance returns ``status == "success"`` with files_changed,
    verification evidence tail, tokens, duration, model.

The runner is imported as a Python module via importlib so we can unit-test its
pure functions and inject a fake client instead of spawning a real subprocess.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DELEGATE_PATH = ROOT / "scripts" / "delegate"
SCHEMA_PATH = ROOT / "assets" / "brief-schema.json"

MODEL = "glm-5.2"


# ---------------------------------------------------------------------------
# Module loading fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def delegate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Load scripts/delegate as a Python module.

    The script is a ``#!/usr/bin/env python3`` file that is also valid as a
    module. We load it via importlib so the tests can call ``run``,
    ``bounded_attempts``, ``bounded_turns`` etc. directly. A fresh import each
    test avoids state leakage between tests.
    """
    if not DELEGATE_PATH.exists():
        pytest.fail("scripts/delegate does not exist yet")
    # The script has no .py extension, so spec_from_file_location cannot infer
    # a loader. Use SourceFileLoader explicitly.
    loader = importlib.machinery.SourceFileLoader("delegate_under_test", str(DELEGATE_PATH))
    spec = importlib.util.spec_from_loader("delegate_under_test", loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # The module may reference __file__ to find the schema; make sure it can.
    sys.modules["delegate_under_test"] = mod
    spec.loader.exec_module(mod)
    # Point audit dir into tmp_path so tests never touch the real HOME.
    audit_dir = tmp_path / ".claude-hybrid"
    monkeypatch.setattr(mod, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(mod, "AUDIT_FILE", audit_dir / "route-audit.jsonl")
    yield mod
    sys.modules.pop("delegate_under_test", None)


@pytest.fixture()
def schema() -> dict:
    if not SCHEMA_PATH.exists():
        pytest.fail("assets/brief-schema.json does not exist yet")
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Fake client
# ---------------------------------------------------------------------------


class FakeClient:
    """A stand-in for the claude-maas subprocess.

    Records every call and can be configured to fail in various ways. Each
    ``call`` returns a dict mimicking what the real client wrapper produces:

        {
          "ok": bool,
          "stdout": str,
          "stderr": str,
          "status_code": int | None,   # HTTP-ish status for retry logic
          "retry_after": float | None, # seconds, from a 429 Retry-After header
          "tokens_in": int,
          "tokens_out": int,
          "files_changed": list[str],
          "timed_out": bool,
        }
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._mode = "ok"  # ok | fail_always | fail_once | status_429 | status_401 | status_403 | status_500 | timeout
        self._retry_after = 0.0
        self._fail_remaining = 0
        self._sleeps: list[float] = []

    # --- configuration -----------------------------------------------------

    def fail_always(self) -> None:
        self._mode = "fail_always"

    def fail_once(self) -> None:
        self._mode = "fail_once"
        self._fail_remaining = 1

    def fail_with_429(self, retry_after: float = 0.0) -> None:
        self._mode = "status_429"
        self._retry_after = retry_after

    def fail_with_401(self) -> None:
        self._mode = "status_401"

    def fail_with_403(self) -> None:
        self._mode = "status_403"

    def fail_with_500(self) -> None:
        self._mode = "status_500"

    def timeout_always(self) -> None:
        self._mode = "timeout"

    @property
    def sleeps(self) -> list[float]:
        return self._sleeps

    # --- the callable ------------------------------------------------------

    def __call__(self, goal: str, *, model: str, max_turns: int, timeout: float,
                 cwd: str | None = None, client_bin: str = "claude-maas") -> dict:
        call = {
            "goal": goal,
            "model": model,
            "max_turns": max_turns,
            "timeout": timeout,
            "cwd": cwd,
            "client_bin": client_bin,
        }
        self.calls.append(call)
        if self._mode == "ok":
            return {
                "ok": True,
                "stdout": "task complete",
                "stderr": "",
                "status_code": None,
                "retry_after": None,
                "tokens_in": 100,
                "tokens_out": 50,
                "files_changed": ["src/parser.py"],
                "timed_out": False,
            }
        if self._mode == "fail_always":
            return {
                "ok": False,
                "stdout": "",
                "stderr": "boom",
                "status_code": 500,
                "retry_after": None,
                "tokens_in": 10,
                "tokens_out": 0,
                "files_changed": [],
                "timed_out": False,
            }
        if self._mode == "fail_once":
            if self._fail_remaining > 0:
                self._fail_remaining -= 1
                return {
                    "ok": False, "stdout": "", "stderr": "transient",
                    "status_code": 503, "retry_after": None,
                    "tokens_in": 5, "tokens_out": 0,
                    "files_changed": [], "timed_out": False,
                }
            return {
                "ok": True, "stdout": "ok now", "stderr": "",
                "status_code": None, "retry_after": None,
                "tokens_in": 100, "tokens_out": 50,
                "files_changed": ["src/x.py"], "timed_out": False,
            }
        if self._mode == "status_429":
            return {
                "ok": False, "stdout": "", "stderr": "rate limited",
                "status_code": 429, "retry_after": self._retry_after,
                "tokens_in": 1, "tokens_out": 0,
                "files_changed": [], "timed_out": False,
            }
        if self._mode == "status_401":
            return {
                "ok": False, "stdout": "", "stderr": "unauthorized",
                "status_code": 401, "retry_after": None,
                "tokens_in": 0, "tokens_out": 0,
                "files_changed": [], "timed_out": False,
            }
        if self._mode == "status_403":
            return {
                "ok": False, "stdout": "", "stderr": "forbidden",
                "status_code": 403, "retry_after": None,
                "tokens_in": 0, "tokens_out": 0,
                "files_changed": [], "timed_out": False,
            }
        if self._mode == "status_500":
            return {
                "ok": False, "stdout": "", "stderr": "server error",
                "status_code": 500, "retry_after": None,
                "tokens_in": 0, "tokens_out": 0,
                "files_changed": [], "timed_out": False,
            }
        if self._mode == "timeout":
            return {
                "ok": False, "stdout": "", "stderr": "timeout",
                "status_code": None, "retry_after": None,
                "tokens_in": 0, "tokens_out": 0,
                "files_changed": [], "timed_out": True,
            }
        raise AssertionError(f"unknown mode {self._mode!r}")


@pytest.fixture()
def fake_client(delegate):
    """A FakeClient wired into the delegate module as the client callable."""
    fc = FakeClient()
    delegate.set_client_factory(lambda **kw: fc)
    return fc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def valid_brief(**overrides) -> dict:
    """Return a valid brief dict with optional overrides."""
    brief = {
        "task_type": "unit_test_generation",
        "goal": "add boundary tests for src/parser.py",
        "scope": ["src/parser.py", "tests/test_parser.py"],
        "constraints": ["do not modify public API"],
        "acceptance": "true",
        "context_notes": "minimal context",
        "max_attempts": 2,
        "max_turns": 12,
    }
    brief.update(overrides)
    return brief


# ---------------------------------------------------------------------------
# Bounded attempts / turns
# ---------------------------------------------------------------------------


def test_attempt_and_turn_limits_are_clamped(delegate):
    assert delegate.bounded_attempts(99) == 2
    assert delegate.bounded_attempts(0) == 1
    assert delegate.bounded_attempts(1) == 1
    assert delegate.bounded_attempts(2) == 2
    assert delegate.MAX_TURNS >= 1


def test_bounded_turns_clamps_to_max(delegate):
    assert delegate.bounded_turns(999) == delegate.MAX_TURNS
    assert delegate.bounded_turns(0) == 1
    assert delegate.bounded_turns(-5) == 1
    assert delegate.bounded_turns(1) == 1
    if delegate.MAX_TURNS > 1:
        assert delegate.bounded_turns(delegate.MAX_TURNS) == delegate.MAX_TURNS
        assert delegate.bounded_turns(delegate.MAX_TURNS - 1) == delegate.MAX_TURNS - 1


# ---------------------------------------------------------------------------
# Image rejection before launch
# ---------------------------------------------------------------------------


def test_image_brief_is_rejected_before_launch(delegate, fake_client):
    result = delegate.run({"task_type": "image", "goal": "inspect image"})
    assert result["status"] == "unsupported_capability"
    assert fake_client.calls == []


def test_image_brief_with_full_scope_still_rejected(delegate, fake_client):
    result = delegate.run({
        "task_type": "image",
        "goal": "describe screenshot",
        "scope": ["screenshot.png"],
        "acceptance": "true",
    })
    assert result["status"] == "unsupported_capability"
    assert fake_client.calls == []


# ---------------------------------------------------------------------------
# Scope-empty write-op rejection
# ---------------------------------------------------------------------------


def test_empty_scope_write_op_is_rejected(delegate, fake_client):
    """A write-op task type with an empty scope must be rejected as invalid_brief."""
    for tt in ("code_generation", "refactor", "bug_fix", "unit_test_generation"):
        result = delegate.run({
            "task_type": tt,
            "goal": "do something",
            "scope": [],
            "acceptance": "true",
        })
        assert result["status"] == "invalid_brief", f"task_type={tt}"
    assert fake_client.calls == []


def test_empty_scope_read_op_is_allowed(delegate, fake_client):
    """A read-only task type (e.g. docs, review) with empty scope may proceed."""
    result = delegate.run({
        "task_type": "docs",
        "goal": "summarize readme",
        "scope": [],
        "acceptance": "true",
    })
    assert result["status"] != "invalid_brief"


# ---------------------------------------------------------------------------
# Two failures -> needs_escalation
# ---------------------------------------------------------------------------


def test_failed_twice_returns_needs_escalation(delegate, fake_client):
    fake_client.fail_always()
    result = delegate.run(valid_brief(max_attempts=99))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 2


def test_failed_twice_even_with_max_attempts_one(delegate, fake_client):
    """max_attempts is clamped to at least 1, but 5xx still gets one retry
    so the total attempt count is 2 and the result is needs_escalation."""
    fake_client.fail_always()
    result = delegate.run(valid_brief(max_attempts=1))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 2


# ---------------------------------------------------------------------------
# 429 Retry-After honored but total attempts <= 2
# ---------------------------------------------------------------------------


def test_429_retry_after_honored_but_attempts_bounded(delegate, fake_client, monkeypatch):
    slept = []
    monkeypatch.setattr(delegate, "_sleep", lambda s: slept.append(s))
    fake_client.fail_with_429(retry_after=5.0)
    result = delegate.run(valid_brief(max_attempts=99))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 2
    # It should have slept once for the first 429 (bounded Retry-After).
    assert len(slept) == 1
    assert slept[0] <= 60.0  # bounded to a max of 60s


def test_429_retry_after_is_bounded_to_60s(delegate, fake_client, monkeypatch):
    slept = []
    monkeypatch.setattr(delegate, "_sleep", lambda s: slept.append(s))
    fake_client.fail_with_429(retry_after=9999.0)
    delegate.run(valid_brief(max_attempts=99))
    assert slept[0] == 60.0


# ---------------------------------------------------------------------------
# 401/403 immediate failure, no retry
# ---------------------------------------------------------------------------


def test_401_fails_immediately_no_retry(delegate, fake_client):
    fake_client.fail_with_401()
    result = delegate.run(valid_brief(max_attempts=2))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 1


def test_403_fails_immediately_no_retry(delegate, fake_client):
    fake_client.fail_with_403()
    result = delegate.run(valid_brief(max_attempts=2))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 1


# ---------------------------------------------------------------------------
# 5xx one retry then structured failure
# ---------------------------------------------------------------------------


def test_500_one_retry_then_failure(delegate, fake_client):
    fake_client.fail_with_500()
    result = delegate.run(valid_brief(max_attempts=2))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 2


def test_500_then_success_on_retry(delegate, fake_client):
    fake_client.fail_once()
    result = delegate.run(valid_brief(max_attempts=2))
    assert result["status"] == "success"
    assert len(fake_client.calls) == 2


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


def test_timeout_produces_structured_failure(delegate, fake_client):
    fake_client.timeout_always()
    result = delegate.run(valid_brief(max_attempts=2))
    assert result["status"] in ("needs_escalation", "capacity_error")
    assert len(fake_client.calls) >= 1


# ---------------------------------------------------------------------------
# --max-turns propagation
# ---------------------------------------------------------------------------


def test_max_turns_propagated_to_client(delegate, fake_client):
    delegate.run(valid_brief(max_turns=7))
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["max_turns"] == 7


def test_max_turns_clamped_when_huge(delegate, fake_client):
    delegate.run(valid_brief(max_turns=999999))
    assert fake_client.calls[0]["max_turns"] == delegate.MAX_TURNS


# ---------------------------------------------------------------------------
# Model assertion: always glm-5.2
# ---------------------------------------------------------------------------


def test_model_is_always_glm_5_2(delegate, fake_client):
    delegate.run(valid_brief())
    assert fake_client.calls[0]["model"] == MODEL


def test_model_in_result_is_glm_5_2(delegate, fake_client):
    result = delegate.run(valid_brief())
    assert result["model"] == MODEL


# ---------------------------------------------------------------------------
# Acceptance command authority
# ---------------------------------------------------------------------------


def test_acceptance_runs_with_explicit_cwd_and_timeout(delegate, fake_client, tmp_path):
    """The acceptance command must be run with an explicit cwd and timeout."""
    marker = tmp_path / "ran.txt"
    brief = valid_brief(acceptance=f"touch {marker}")
    result = delegate.run(brief, cwd=str(tmp_path))
    assert result["status"] == "success"
    assert marker.exists()
    assert "verification" in result
    v = result["verification"]
    assert v["cmd"] == brief["acceptance"]
    assert v["passed"] is True


def test_acceptance_failure_makes_result_not_success(delegate, fake_client):
    brief = valid_brief(acceptance="false")
    result = delegate.run(brief)
    assert result["status"] != "success"
    assert result["verification"]["passed"] is False


def test_acceptance_evidence_tail_captured(delegate, fake_client):
    brief = valid_brief(acceptance="echo hello && echo world")
    result = delegate.run(brief)
    assert result["status"] == "success"
    tail = result["verification"]["evidence_tail"]
    assert isinstance(tail, str)
    # The tail should contain some evidence of the output.
    assert "world" in tail or "hello" in tail


# ---------------------------------------------------------------------------
# Successful result shape
# ---------------------------------------------------------------------------


def test_success_result_shape(delegate, fake_client):
    result = delegate.run(valid_brief())
    assert result["status"] == "success"
    assert "summary" in result
    assert "files_changed" in result
    assert isinstance(result["files_changed"], list)
    assert "verification" in result
    assert "attempts" in result
    assert result["attempts"] == 1
    assert "duration_s" in result
    assert isinstance(result["duration_s"], (int, float))
    assert "tokens" in result
    assert "in" in result["tokens"] and "out" in result["tokens"]
    assert result["model"] == MODEL


# ---------------------------------------------------------------------------
# Audit redaction
# ---------------------------------------------------------------------------


@pytest.fixture()
def audit_lines(delegate, fake_client, tmp_path):
    """Run a brief and return the parsed audit JSONL lines."""
    delegate.run(valid_brief(goal="SECRET-GOAL-TEXT-XYZ"))
    af = delegate.AUDIT_FILE
    if not af.exists():
        return []
    return [json.loads(line) for line in af.read_text().splitlines() if line.strip()]


def test_audit_file_has_mode_0600(delegate, fake_client):
    delegate.run(valid_brief())
    af = delegate.AUDIT_FILE
    assert af.exists()
    assert af.stat().st_mode & 0o777 == 0o600


def test_audit_does_not_store_brief_text(delegate, fake_client):
    secret_goal = "SECRET-GOAL-TEXT-XYZ"
    delegate.run(valid_brief(goal=secret_goal))
    af = delegate.AUDIT_FILE
    raw = af.read_text()
    assert secret_goal not in raw


def test_audit_does_not_store_tool_arguments(delegate, fake_client):
    secret_arg = "SECRET-TOOL-ARG-XYZ"
    brief = valid_brief()
    brief["constraints"] = [secret_arg]
    delegate.run(brief)
    raw = delegate.AUDIT_FILE.read_text()
    assert secret_arg not in raw


def test_audit_records_required_fields(audit_lines):
    assert len(audit_lines) >= 1
    for line in audit_lines:
        assert "ts" in line
        assert "task_id" in line
        assert line["route"] == "maas"
        assert line["model"] == MODEL
        assert "attempt" in line
        assert "outcome" in line
        assert "duration_s" in line
        assert "tokens_in" in line
        assert "tokens_out" in line


def test_audit_fallback_is_always_false(audit_lines):
    for line in audit_lines:
        assert line["fallback"] is False


def test_audit_never_contains_fallback_true(delegate, fake_client):
    fake_client.fail_always()
    delegate.run(valid_brief())
    raw = delegate.AUDIT_FILE.read_text()
    assert '"fallback": true' not in raw
    assert '"fallback":true' not in raw


# ---------------------------------------------------------------------------
# Brief schema
# ---------------------------------------------------------------------------


def test_schema_has_required_fields(schema):
    assert "task_type" in schema.get("required", [])
    assert "goal" in schema.get("required", [])


def test_schema_task_type_enum_includes_image(schema):
    props = schema["properties"]
    enum = props["task_type"]["enum"]
    assert "image" in enum
    assert "unit_test_generation" in enum


def test_schema_max_attempts_range(schema):
    props = schema["properties"]
    ma = props["max_attempts"]
    assert ma["type"] == "integer"
    assert ma["minimum"] == 1
    assert ma["maximum"] == 2


def test_delegate_validates_against_schema(delegate, fake_client):
    """A brief missing required fields is rejected as invalid_brief."""
    result = delegate.run({"task_type": "unit_test_generation"})
    assert result["status"] == "invalid_brief"
    assert fake_client.calls == []


def test_delegate_rejects_non_string_goal(delegate, fake_client):
    result = delegate.run({"task_type": "docs", "goal": 123})
    assert result["status"] == "invalid_brief"
    assert fake_client.calls == []


# ---------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------


VALID_STATUSES = {
    "success",
    "needs_escalation",
    "budget_exhausted",
    "capacity_error",
    "invalid_brief",
    "unsupported_capability",
}


def test_all_results_have_valid_status(delegate, fake_client):
    for result in (
        delegate.run(valid_brief()),
        delegate.run({"task_type": "image", "goal": "x"}),
        delegate.run({"task_type": "docs", "goal": 123}),
    ):
        assert result["status"] in VALID_STATUSES, result["status"]


# ---------------------------------------------------------------------------
# Regression tests for status-code extraction from real client stderr.
# Ensures 429/5xx retry logic is reachable in production (not just with fakes).
# ---------------------------------------------------------------------------


def test_extract_status_code_finds_http_errors(delegate):
    assert delegate._extract_status_code("Error: 429 rate limit") == 429
    assert delegate._extract_status_code("HTTP 500 internal error") == 500
    assert delegate._extract_status_code("status 503 unavailable") == 503
    assert delegate._extract_status_code("no error here") is None


def test_extract_retry_after_finds_hint(delegate):
    assert delegate._extract_retry_after("Retry-After: 5") == 5.0
    assert delegate._extract_retry_after("retry-after: 2.5") == 2.5
    assert delegate._extract_retry_after("no hint") is None


def test_real_client_retries_on_429_in_stderr(delegate, monkeypatch, tmp_path):
    """A real subprocess that exits non-zero with '429' in stderr must trigger
    retry logic (attempt count > 1), not fall through to 'no retry'."""
    calls = {"n": 0}

    def fake_run(argv, **kwargs):
        calls["n"] += 1
        class _P:
            returncode = 1
            stdout = ""
            stderr = "Error: 429 rate limit, Retry-After: 0"
        return _P()

    monkeypatch.setattr(delegate.subprocess, "run", fake_run)
    monkeypatch.setattr(delegate.time, "sleep", lambda _: None)
    result = delegate.run(valid_brief(max_attempts=2))
    assert calls["n"] == 2, "429 must trigger a retry, not break after 1 attempt"
    assert result["status"] == "needs_escalation"
