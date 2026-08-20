"""Tests for adapter/lifecycle.js — the Node RequestLifecycleController.

Uses Node as a child process to exercise the module. Deterministic: short
timers, no real network. Each script cleans up timers and exits explicitly so
pending setTimeout handles don't keep the event loop alive.
"""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "adapter" / "lifecycle.js"

# Wrapper that requires the module, runs the user script, then prints __result
# and exits. process.exit ensures pending timers don't hang the process.
_WRAPPER_PRE = (
    f"const m = require('{LIFECYCLE}');\n"
    "const __result = {};\n"
)
_WRAPPER_POST = (
    "\nprocess.stdout.write(JSON.stringify(__result));\nprocess.exit(0);\n"
)


def _run_node(script: str) -> dict:
    """Run a synchronous Node script; returns __result as JSON."""
    full = _WRAPPER_PRE + script + _WRAPPER_POST
    result = subprocess.run(
        ["node", "-e", full],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed: {result.stderr}\nscript:\n{full}")
    return json.loads(result.stdout)


def _run_node_async(script: str, wait_ms: int) -> dict:
    """Run a Node script with async timers; wait wait_ms then capture __result."""
    full = (
        _WRAPPER_PRE
        + script
        + f"\nsetTimeout(() => {{ process.stdout.write(JSON.stringify(__result)); process.exit(0); }}, {wait_ms});\n"
    )
    result = subprocess.run(
        ["node", "-e", full],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed: {result.stderr}\nscript:\n{full}")
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_initial_state_accepted():
    r = _run_node("Object.assign(__result, {state: (new m.RequestLifecycleController({})).state});")
    assert r["state"] == "accepted"


def test_states_enum_has_11():
    r = _run_node("__result.list = Object.values(m.State);")
    assert set(r["list"]) == {
        "accepted", "connecting", "upstream_active_hidden", "visible_streaming",
        "completing", "completed", "client_aborted", "connect_timeout",
        "idle_timeout", "total_timeout", "upstream_failed",
    }


def test_terminal_states():
    r = _run_node("__result.list = [...m.TERMINAL_STATES];")
    for s in ("completed", "client_aborted", "connect_timeout", "idle_timeout",
              "total_timeout", "upstream_failed"):
        assert s in r["list"]


# ---------------------------------------------------------------------------
# Active timers
# ---------------------------------------------------------------------------


def test_connect_timeout_fires():
    r = _run_node_async(textwrap.dedent("""
        const c = new m.RequestLifecycleController({connectTimeout: 30, idleTimeout: 1000, totalTimeout: 2000});
        c.startConnectTimer();
        setTimeout(() => { __result.state = c.state; __result.code = c.errorCode; }, 60);
    """), wait_ms=90)
    assert r["state"] == "connect_timeout"
    assert r["code"] == "MAAS_CONNECT_TIMEOUT"


def test_idle_timeout_fires_after_silence():
    r = _run_node_async(textwrap.dedent("""
        const c = new m.RequestLifecycleController({connectTimeout: 1000, idleTimeout: 30, totalTimeout: 2000});
        c.startConnectTimer();
        c.markConnected();
        setTimeout(() => { __result.state = c.state; __result.code = c.errorCode; }, 60);
    """), wait_ms=90)
    assert r["state"] == "idle_timeout"
    assert r["code"] == "MAAS_IDLE_TIMEOUT"


def test_reasoning_refreshes_idle():
    r = _run_node_async(textwrap.dedent("""
        const c = new m.RequestLifecycleController({connectTimeout: 1000, idleTimeout: 50, totalTimeout: 2000});
        c.startConnectTimer();
        c.markConnected();
        let n = 0;
        const iv = setInterval(() => { c.recordReasoning('think'); n++; }, 20);
        __result.n = 0;
        setTimeout(() => { clearInterval(iv); __result.n = n; __result.state = c.state; }, 100);
    """), wait_ms=130)
    assert r["state"] == "upstream_active_hidden"
    assert r["n"] >= 4


def test_total_timeout_not_refreshed():
    r = _run_node_async(textwrap.dedent("""
        const c = new m.RequestLifecycleController({connectTimeout: 1000, idleTimeout: 1000, totalTimeout: 40});
        c.startConnectTimer();
        c.markConnected();
        const iv = setInterval(() => c.recordReasoning('think'), 10);
        setTimeout(() => { clearInterval(iv); __result.state = c.state; __result.code = c.errorCode; }, 80);
    """), wait_ms=110)
    assert r["state"] == "total_timeout"
    assert r["code"] == "MAAS_TOTAL_TIMEOUT"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_abort_is_idempotent():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.abort(); c.abort(); c.abort();
        __result.state = c.state; __result.aborted = c.abortController.signal.aborted;
    """))
    assert r["state"] == "client_aborted"
    assert r["aborted"] is True


def test_abort_after_terminal_is_noop():
    r = _run_node_async(textwrap.dedent("""
        const c = new m.RequestLifecycleController({connectTimeout: 30, idleTimeout: 1000, totalTimeout: 2000});
        c.startConnectTimer();
        setTimeout(() => { c.abort(); __result.state = c.state; }, 60);
    """), wait_ms=90)
    assert r["state"] == "connect_timeout"


# ---------------------------------------------------------------------------
# SSE termination
# ---------------------------------------------------------------------------


def test_finish_reason_missing_terminals_synthesizes():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.feedMessageStart();
        c.feedBlockStart(0, 'text');
        c.feedBlockDelta(0, 'text_delta');
        c.feedMessageDelta('end_turn');
        const ev = c.finalize();
        __result.types = ev ? ev.map(e => e.type) : null;
        __result.state = c.state;
    """))
    assert "content_block_stop" in r["types"]
    assert "message_stop" in r["types"]
    assert r["state"] == "completed"


def test_no_finish_reason_eof_fails():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.feedMessageStart();
        c.feedBlockStart(0, 'text');
        c.feedBlockDelta(0, 'text_delta');
        const ev = c.finalize();
        __result.events = ev; __result.state = c.state; __result.code = c.errorCode;
    """))
    assert r["events"] is None
    assert r["state"] == "upstream_failed"
    assert r["code"] == "MAAS_STREAM_EOF"


def test_index_opened_only_once():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.feedMessageStart();
        const a = c.feedBlockStart(0, 'text');
        c.feedBlockStop(0);
        const b = c.feedBlockStart(0, 'text');
        __result.a = a; __result.b = b; __result.pe = c.protocolError;
    """))
    assert r["a"] is True
    assert r["b"] is False
    assert r["pe"] is True


def test_protocol_error_blocks_success_finalization():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.feedMessageStart();
        c.feedBlockStart(0, 'text');
        c.feedBlockDelta(0, 'input_json_delta');
        const ev = c.finalize();
        __result.events = ev; __result.state = c.state; __result.code = c.errorCode;
    """))
    assert r["events"] is None
    assert r["state"] == "upstream_failed"


def test_duplicate_message_stop_rejected():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.feedMessageStart();
        c.feedBlockStart(0, 'text');
        c.feedBlockDelta(0, 'text_delta');
        c.feedMessageDelta('end_turn');
        const a = c.feedMessageStop();
        const b = c.feedMessageStop();
        __result.a = a; __result.b = b; __result.pe = c.protocolError;
    """))
    assert r["a"] is True
    assert r["b"] is False
    assert r["pe"] is True


# ---------------------------------------------------------------------------
# Concurrency guard
# ---------------------------------------------------------------------------


def test_concurrency_admit_and_reject():
    r = _run_node(textwrap.dedent("""
        const g = new m.ConcurrencyGuard(2);
        __result.a = g.tryAdmit(); __result.b = g.tryAdmit(); __result.c = g.tryAdmit();
        __result.active = g.active; __result.peak = g.peak;
    """))
    assert r["a"] is True
    assert r["b"] is True
    assert r["c"] is False
    assert r["active"] == 2
    assert r["peak"] == 2


def test_concurrency_release():
    r = _run_node(textwrap.dedent("""
        const g = new m.ConcurrencyGuard(1);
        g.tryAdmit();
        __result.before = g.tryAdmit();
        g.release();
        __result.after = g.tryAdmit();
        __result.active = g.active;
    """))
    assert r["before"] is False
    assert r["after"] is True
    assert r["active"] == 1


# ---------------------------------------------------------------------------
# Loopback check (fail-closed)
# ---------------------------------------------------------------------------


def test_loopback_allows_127():
    r = _run_node("__result.a = m.isLoopback('127.0.0.1'); __result.b = m.isLoopback('::1'); __result.c = m.isLoopback('::ffff:127.0.0.1');")
    assert r["a"] is True
    assert r["b"] is True
    assert r["c"] is True


def test_loopback_rejects_unknown_and_external():
    r = _run_node("__result.a = m.isLoopback('10.0.0.5'); __result.b = m.isLoopback(null); __result.c = m.isLoopback(undefined); __result.d = m.isLoopback('');")
    assert r["a"] is False
    assert r["b"] is False
    assert r["c"] is False
    assert r["d"] is False


# ---------------------------------------------------------------------------
# Sanitized metrics — no content
# ---------------------------------------------------------------------------


def test_metrics_no_reasoning_content():
    r = _run_node(textwrap.dedent("""
        const c = new m.RequestLifecycleController({});
        c.recordReasoning('SECRET-REASONING-LEAK');
        Object.assign(__result, c.metrics);
    """))
    s = json.dumps(r)
    assert "SECRET-REASONING-LEAK" not in s
    assert r["reasoning_chunks"] == 1
    assert r["reasoning_bytes"] > 0
