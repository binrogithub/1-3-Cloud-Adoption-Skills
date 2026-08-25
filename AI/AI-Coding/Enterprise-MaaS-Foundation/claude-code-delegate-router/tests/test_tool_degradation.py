"""Safe degradation gates (PRD RELEASE_V7 X1).

Tests that in enforce mode, unresolvable tool args produce a text block
with a safe message instead of killing the stream.  The tool is NOT executed.

Three gates:
  §3.1 forward: tool_malformed in enforce → 1 text block explaining the
                skipped call, AND an error frame so the agent loop does not
                stop silently (PRD LOOP_CONTINUITY_V1 L1-B)
  §3.2 reverse: same scenario → NO tool_use block emitted at all
  §3.3 observe: same scenario in observe → behavior identical to current
                (1 error frame, no text degradation) — proves the switch is real
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"
FAKE_UPSTREAM = ROOT / "tests" / "helpers" / "fake_upstream.js"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"port {port} not ready")


def _start_fake_upstream() -> tuple[subprocess.Popen, int]:
    port = _free_port()
    proc = subprocess.Popen(
        ["node", str(FAKE_UPSTREAM), "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"fake upstream failed: {proc.stderr.read().decode()}")
    assert json.loads(line)["ready"]
    return proc, port


def _start_adapter(upstream_port: int, extra_env: dict | None = None) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_TEST_UPSTREAM"] = "1"
    env["MAAS_CLIENT_KEY_FILE"] = str(Path(__file__).parent / "no-client.key")
    env["MAAS_CONNECT_TIMEOUT"] = "5"
    env["MAAS_IDLE_TIMEOUT"] = "30"
    env["MAAS_TOTAL_TIMEOUT"] = "60"
    env["MAAS_MAX_CONCURRENCY"] = "8"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        ["node", str(CANDIDATE)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _wait_ready(port)
    return proc, port


@pytest.fixture()
def upstream():
    proc, port = _start_fake_upstream()
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send_stream(adapter_port: int, scenario: str, timeout: float = 10.0) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=timeout)
    body = json.dumps({
        "model": "glm-5.2", "max_tokens": 64, "stream": True,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    })
    conn.request("POST", "/v1/messages", body=body,
                 headers={"content-type": "application/json", "x-api-key": "test-key",
                          "x-fake-scenario": scenario})
    try:
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", errors="replace")
        return resp.status, data
    except Exception as exc:
        return -1, repr(exc)
    finally:
        conn.close()


def _parse_sse_events(raw: str) -> list[dict]:
    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        evt = {}
        for line in block.split("\n"):
            if line.startswith("event:"):
                evt["type"] = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    evt["data"] = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    evt["data"] = line[5:].strip()
        if evt:
            events.append(evt)
    return events


# ---------------------------------------------------------------------------
# X1 §3.1: Forward gate — enforce mode produces text degradation, not error
# ---------------------------------------------------------------------------


def test_enforce_degrades_to_text_and_signals_error(upstream):
    """X1 §3.1 as amended by PRD LOOP_CONTINUITY_V1 L1-B.

    When retry is disabled (MAAS_TOOL_ARG_RETRY=0), tool_malformed in enforce
    mode → a text block with the safe message AND an error frame.  The text
    alone is not enough: a turn that ends with stop_reason end_turn and only
    that text terminates the Claude Code agent loop, and was measured at 0%
    self-recovery against 32% for a hard error.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})  # isolate L1-B degradation path
    try:
        status, body = _send_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # An error frame MUST be present — the turn must not end silently.
        has_error = any(e.get("type") == "error" for e in events)
        assert has_error, (
            f"enforce degradation emitted no error frame — the agent loop "
            f"would stop silently: {body[:300]}"
        )

        # Has a text block with the safe degradation message.
        text_deltas = [e for e in events if e.get("type") == "content_block_delta"
                       and e.get("data", {}).get("delta", {}).get("type") == "text_delta"]
        assert len(text_deltas) >= 1, f"no text_delta found. Events: {[e.get('type') for e in events]}"
        assert "未被执行" in text_deltas[0]["data"]["delta"]["text"], \
            f"safe degradation text missing: {text_deltas[0]['data']['delta']['text'][:100]}"

        # No silent end_turn: that is exactly the stop that killed the loop.
        message_deltas = [e for e in events if e.get("type") == "message_delta"]
        for md in message_deltas:
            stop_reason = md.get("data", {}).get("delta", {}).get("stop_reason")
            assert stop_reason != "end_turn", \
                "degraded turn ended with a silent end_turn"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# X1 §3.2: Reverse/invariant gate — no tool_use block emitted
# ---------------------------------------------------------------------------


def test_enforce_no_tool_use_block(upstream):
    """X1 §3.2: with retry disabled, tool_malformed in enforce mode → NO
    tool_use block emitted at all (degradation path).  With retry enabled
    (default), the adapter re-asks upstream and may emit a real tool_use —
    that path is tested in test_loop_continuity.py::test_g3."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})  # isolate degradation path
    try:
        status, body = _send_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # No tool_use block at all.
        tool_use_starts = [e for e in events if e.get("type") == "content_block_start"
                           and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"]
        assert len(tool_use_starts) == 0, \
            f"tool_use block emitted in degradation: {tool_use_starts}"

        # No input_json_delta (which carries the tool args).
        input_deltas = [e for e in events if e.get("type") == "content_block_delta"
                        and e.get("data", {}).get("delta", {}).get("type") == "input_json_delta"]
        assert len(input_deltas) == 0, \
            f"input_json_delta emitted in degradation: {input_deltas}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# X1 §3.3: Observe gate — behavior identical to current (hard fail)
# ---------------------------------------------------------------------------


def test_observe_still_hard_fails(upstream):
    """X1 §3.3: tool_malformed in observe mode → behavior identical to pre-V7
    (1 error frame, no text degradation block).  Proves the mode switch is real
    — observe doesn't change user-visible behavior."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        status, body = _send_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # Must have an error frame (hard fail, same as before).
        has_error = any(e.get("type") == "error" for e in events)
        assert has_error, \
            f"observe mode should still hard-fail (error frame expected): {body[:300]}"

        # Must NOT have a text degradation block.
        text_deltas = [e for e in events if e.get("type") == "content_block_delta"
                       and e.get("data", {}).get("delta", {}).get("type") == "text_delta"
                       and "未被执行" in e.get("data", {}).get("delta", {}).get("text", "")]
        assert len(text_deltas) == 0, \
            f"observe mode should not emit degradation text: {text_deltas}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# X2: Named classification for <tool_call markup
# ---------------------------------------------------------------------------


def test_tool_markup_classified_separately(upstream):
    """X2: args starting with <tool_call → protocol_error_reason:
    "tool_markup_as_args", tool_markup_seen increments.  Must NOT be
    classified as generic "tool_args_malformed"."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, "tool_markup_args", timeout=10.0)
        time.sleep(1.0)

        # Check /status for tool_markup_seen.
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
        conn.request("GET", "/status")
        status_data = json.loads(conn.getresponse().read().decode())
        conn.close()
        assert status_data.get("tool_markup_seen", 0) >= 1, \
            f"tool_markup_seen not incremented: {status_data.get('tool_markup_seen')}"

        # Check the structured log for the correct protocol_error_reason.
        import fcntl
        fd = adapter_proc.stderr.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        time.sleep(0.3)
        try:
            err = os.read(fd, 8192).decode("utf-8", errors="replace")
        except BlockingIOError:
            err = ""
        for line in err.strip().split("\n"):
            if "request_end" in line:
                entry = json.loads(line)
                assert entry.get("protocol_error_reason") == "tool_markup_as_args", \
                    f"expected tool_markup_as_args, got {entry.get('protocol_error_reason')}"
                break
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_normal_bad_json_not_classified_as_markup(upstream):
    """X2: normal bad JSON (tool_malformed, {"city":) → protocol_error_reason:
    "tool_args_malformed", NOT "tool_markup_as_args"."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, "tool_malformed", timeout=10.0)
        time.sleep(1.0)

        # tool_markup_seen should NOT increment for normal bad JSON.
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
        conn.request("GET", "/status")
        status_data = json.loads(conn.getresponse().read().decode())
        conn.close()
        assert status_data.get("tool_markup_seen", 0) == 0, \
            f"tool_markup_seen incremented for normal bad JSON: {status_data.get('tool_markup_seen')}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D3 (PRD RELEASE_V8): explicit degraded marker — bidirectional gate
# ---------------------------------------------------------------------------


def _read_request_end(adapter_proc: subprocess.Popen) -> dict | None:
    """Read the first request_end structured-log line from adapter stderr."""
    import fcntl
    fd = adapter_proc.stderr.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    time.sleep(0.3)
    try:
        err = os.read(fd, 65536).decode("utf-8", errors="replace")
    except BlockingIOError:
        err = ""
    for line in err.strip().split("\n"):
        if '"request_end"' in line or "request_end" in line:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "request_end":
                return entry
    return None


def _status(adapter_port: int) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
    conn.request("GET", "/status")
    data = json.loads(conn.getresponse().read().decode())
    conn.close()
    return data


def test_d3_enforce_marks_degraded_true(upstream):
    """D3 forward gate: enforce + tool_malformed (retry disabled) → degraded:true
    in request_end and tool_args_degraded increments on /status."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})  # isolate degradation path
    try:
        before = _status(adapter_port).get("tool_args_degraded", 0)
        _send_stream(adapter_port, "tool_malformed", timeout=10.0)
        time.sleep(0.5)

        entry = _read_request_end(adapter_proc)
        assert entry is not None, "no request_end structured log emitted"
        assert entry.get("degraded") is True, \
            f"enforce+tool_malformed must set degraded:true, got {entry.get('degraded')}"

        after = _status(adapter_port).get("tool_args_degraded", 0)
        assert after == before + 1, \
            f"tool_args_degraded must increment by 1: {before} -> {after}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_d3_observe_marks_degraded_false(upstream):
    """D3 reverse gate: observe + tool_malformed → degraded:false in request_end
    and tool_args_degraded stays unchanged (observe never degrades)."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        before = _status(adapter_port).get("tool_args_degraded", 0)
        _send_stream(adapter_port, "tool_malformed", timeout=10.0)
        time.sleep(0.5)

        entry = _read_request_end(adapter_proc)
        assert entry is not None, "no request_end structured log emitted"
        assert entry.get("degraded") is False, \
            f"observe must set degraded:false, got {entry.get('degraded')}"

        after = _status(adapter_port).get("tool_args_degraded", 0)
        assert after == before, \
            f"tool_args_degraded must not change in observe: {before} -> {after}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_d3_normal_request_not_degraded(upstream):
    """D3 invariant: a normal (non-malformed) request in enforce mode →
    degraded:false and tool_args_degraded unchanged.  Proves the marker is
    scoped to actual degradation, not set on every enforce request."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        before = _status(adapter_port).get("tool_args_degraded", 0)
        _send_stream(adapter_port, "tool_valid", timeout=10.0)
        time.sleep(0.5)

        entry = _read_request_end(adapter_proc)
        assert entry is not None, "no request_end structured log emitted"
        assert entry.get("degraded") is False, \
            f"normal request must not be degraded, got {entry.get('degraded')}"

        after = _status(adapter_port).get("tool_args_degraded", 0)
        assert after == before, \
            f"tool_args_degraded must not change for normal request: {before} -> {after}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
