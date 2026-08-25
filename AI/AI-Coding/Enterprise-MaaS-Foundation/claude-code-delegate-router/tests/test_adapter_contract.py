"""External-contract red/green harness for the MaaS adapter (G-CLOSE1, G-CLOSE2).

Starts a fake upstream + an adapter as child processes on ephemeral loopback
ports, drives real HTTP sockets, and asserts the contract. The same suite runs
against the frozen legacy artifact (must FAIL — red) and the candidate
(adapter/server.js — must PASS — green).

This proves the defect and its fix through the real HTTP/SSE path, not internal
class imports.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"
LEGACY = ROOT / "tests" / "fixtures" / "legacy_server.js"
FAKE_UPSTREAM = ROOT / "tests" / "helpers" / "fake_upstream.js"


# ---------------------------------------------------------------------------
# Process management helpers
# ---------------------------------------------------------------------------


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
    # Wait for the "ready" JSON line.
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"fake upstream failed: {proc.stderr.read().decode()}")
    data = json.loads(line)
    assert data["ready"], f"fake upstream not ready: {data}"
    return proc, port


def _start_adapter(server_js: Path, upstream_port: int, adapter_port: int | None = None) -> tuple[subprocess.Popen, int]:
    port = adapter_port or _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_TEST_UPSTREAM"] = "1"
    env["MAAS_CLIENT_KEY_FILE"] = str(Path(__file__).parent / "no-client.key")
    env["MAAS_CONNECT_TIMEOUT"] = "2"
    env["MAAS_IDLE_TIMEOUT"] = "2"
    env["MAAS_TOTAL_TIMEOUT"] = "4"
    env["MAAS_MAX_CONCURRENCY"] = "8"
    env["MAAS_MAX_TOOL_ARGS_BYTES"] = "262144"
    proc = subprocess.Popen(
        ["node", str(server_js)],
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


@pytest.fixture()
def candidate_adapter(upstream):
    proc, port = _start_adapter(CANDIDATE, upstream)
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def legacy_adapter(upstream):
    proc, port = _start_adapter(LEGACY, upstream)
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _post_stream(adapter_port: int, scenario: str, stream: bool = True, timeout: float = 10.0) -> tuple[int, str]:
    """POST a streaming request with the given fake scenario. Returns (status, body).

    The scenario is sent both as an x-fake-scenario header (forwarded by the
    candidate adapter) and embedded in the first user message content as
    "scenario:<name>" (forwarded by every adapter, including the frozen legacy
    artifact that does not propagate custom headers).
    """
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=timeout)
    body = json.dumps({
        "model": "glm-5.2",
        "max_tokens": 64,
        "stream": stream,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    })
    headers = {"content-type": "application/json", "x-api-key": "test-key", "x-fake-scenario": scenario}
    conn.request("POST", "/v1/messages", body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="replace")
    status = resp.status
    conn.close()
    return status, data


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE data lines into a list of event dicts."""
    events = []
    for block in re.split(r"\r?\n\r?\n", raw):
        etype = None
        edata = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                etype = line[6:].strip()
            elif line.startswith("data:"):
                edata = line[5:].strip()
        if edata and edata != "[DONE]":
            try:
                events.append({"type": etype, "data": json.loads(edata)})
            except json.JSONDecodeError:
                events.append({"type": etype, "data": edata})
    return events


# ===========================================================================
# GREEN: candidate adapter passes the contract
# ===========================================================================


class TestCandidateGreen:
    """G-CLOSE2: the candidate adapter passes the external contract."""

    def test_reasoning_then_text_succeeds(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "reasoning_then_text")
        assert status == 200
        events = _parse_sse_events(body)
        types = [e["type"] for e in events]
        assert "message_start" in types
        assert "message_stop" in types
        # Reasoning content must NOT appear in client output.
        assert "thinking step" not in body

    def test_eof_no_finish_fails_not_success(self, candidate_adapter):
        """G-CLOSE5: EOF without finish reason must not fake success."""
        status, body = _post_stream(candidate_adapter, "eof_no_finish")
        events = _parse_sse_events(body)
        # Must NOT have a clean message_stop indicating success.
        # Either an error event or no message_stop.
        has_error = any(e["type"] == "error" for e in events)
        has_stop = any(e["type"] == "message_stop" for e in events)
        # If there's a message_stop, it must be a synthesized error path, not success.
        # The candidate should NOT report a clean end_turn success.
        assert has_error or not has_stop, "EOF without finish faked success"

    def test_finish_missing_terminals_synthesizes(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "finish_missing_terminals")
        assert status == 200
        events = _parse_sse_events(body)
        types = [e["type"] for e in events]
        assert "message_stop" in types

    def test_silence_idle_timeout(self, candidate_adapter):
        """G-CLOSE3: permanent silence → idle timeout."""
        status, body = _post_stream(candidate_adapter, "silence", timeout=8)
        # Should fail with idle timeout (504 or SSE error).
        assert status in (200, 504)
        # The body should indicate a timeout error, not success.
        assert "timeout" in body.lower() or "error" in body.lower()

    def test_tool_valid(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "tool_valid")
        assert status == 200
        events = _parse_sse_events(body)
        # Should contain a tool_use block.
        assert any("tool_use" in str(e) for e in events)

    def test_tool_malformed_not_degraded_to_empty(self, candidate_adapter):
        """G-CLOSE5: malformed tool args must NOT emit a tool_use block.
        Strengthened in V7: was 'not degraded to {}', now 'no tool_use block
        at all' — forbids any fabricated input, not just empty {}."""
        status, body = _post_stream(candidate_adapter, "tool_malformed")
        events = _parse_sse_events(body)
        # No tool_use block may be emitted on malformed args.
        has_tool_use = any(
            e.get("type") == "content_block_start"
            and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
            for e in events
        )
        assert not has_tool_use, \
            "tool_use block emitted on malformed args — contract violation"

    def test_status_endpoint_loopback(self, candidate_adapter):
        """G-CLOSE7: /status is available on loopback."""
        conn = http.client.HTTPConnection("127.0.0.1", candidate_adapter, timeout=5)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        assert resp.status == 200
        assert "active_requests" in data
        assert "timeout_config" in data
        assert "version" in data

    def test_health_endpoint(self, candidate_adapter):
        conn = http.client.HTTPConnection("127.0.0.1", candidate_adapter, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        assert resp.status == 200
        assert data["status"] == "ok"

    def test_nonstream_text(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "nonstream_text", stream=False)
        assert status == 200
        data = json.loads(body)
        assert data["type"] == "message"
        assert data["role"] == "assistant"


# ===========================================================================
# RED: legacy adapter fails the contract (G-CLOSE2 red proof)
# ===========================================================================


class TestLegacyRed:
    """G-CLOSE2: the frozen legacy artifact must FAIL the contract.

    These tests assert the legacy adapter's known defects. They are expected to
    FAIL (i.e., the assertion that the legacy does the WRONG thing passes).
    """

    def test_legacy_eof_fakes_success(self, legacy_adapter):
        """The legacy adapter fakes success on EOF without finish reason."""
        status, body = _post_stream(legacy_adapter, "eof_no_finish")
        events = _parse_sse_events(body)
        types = [e["type"] for e in events]
        # Legacy unconditionally sends message_stop even without finish reason.
        assert "message_stop" in types, "legacy should fake success (this is the defect)"

    def test_legacy_no_status_endpoint(self, legacy_adapter):
        """The legacy adapter has no /status endpoint."""
        conn = http.client.HTTPConnection("127.0.0.1", legacy_adapter, timeout=5)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 404, "legacy should lack /status (this is the defect)"

    def test_legacy_tool_malformed_degrades_to_empty(self, legacy_adapter):
        """The legacy adapter degrades malformed tool args to {}."""
        status, body = _post_stream(legacy_adapter, "tool_malformed")
        events = _parse_sse_events(body)
        # Legacy parses with catch{} -> input = {}. Use compact separators so
        # the substring match is robust to json.dumps whitespace.
        compact = [json.dumps(e, separators=(",", ":")) for e in events]
        assert any('"input":{}' in c for c in compact), \
            "legacy should degrade malformed args to {} (this is the defect)"

    def test_legacy_silence_no_idle_failure(self, legacy_adapter):
        """The legacy adapter has no idle timeout — it hangs or fakes success."""
        # Legacy has no idle watchdog. We just confirm it doesn't produce a
        # timeout error code (it has no such concept).
        try:
            status, body = _post_stream(legacy_adapter, "silence", timeout=5)
            # Legacy either hangs (timeout on our side) or eventually fakes success.
            # Either way, no MAAS_IDLE_TIMEOUT.
            assert "MAAS_IDLE_TIMEOUT" not in body
        except (socket.timeout, http.client.HTTPException, ConnectionError):
            # Legacy hung — also a defect (no bounded failure).
            pass


# ===========================================================================
# Terminal message_delta — the event that carries stop_reason and usage
#
# Regression gate: the adapter recorded the upstream finish_reason through
# feedMessageDelta(), which marked the message_delta slot consumed without ever
# writing the event, so finalize() skipped it. Every stream then reached Claude
# Code with no stop_reason and no output usage (modelUsage {}), and a tool turn
# lost its stop_reason="tool_use". The old suite only counted message_stop, so
# it stayed green through the whole defect.
# ===========================================================================


class TestTerminalMessageDelta:
    def test_stream_emits_message_delta_before_message_stop(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "reasoning_then_text")
        assert status == 200
        types = [e["type"] for e in _parse_sse_events(body)]
        assert types.count("message_delta") == 1, f"message_delta count: {types.count('message_delta')} in {types}"
        assert types.index("message_delta") < types.index("message_stop"), \
            f"message_delta must precede message_stop: {types}"

    def test_message_delta_carries_stop_reason_and_usage(self, candidate_adapter):
        status, body = _post_stream(candidate_adapter, "reasoning_then_text")
        assert status == 200
        deltas = [e["data"] for e in _parse_sse_events(body) if e["type"] == "message_delta"]
        assert deltas, "no message_delta event"
        delta = deltas[0]
        assert delta["delta"]["stop_reason"] == "end_turn", delta
        assert "usage" in delta, delta
        assert delta["usage"]["output_tokens"] == 5, delta

    def test_tool_call_stream_reports_tool_use_stop_reason(self, candidate_adapter):
        """A tool turn must arrive with stop_reason=tool_use or the client never runs the tool."""
        status, body = _post_stream(candidate_adapter, "tool_valid")
        assert status == 200
        deltas = [e["data"] for e in _parse_sse_events(body) if e["type"] == "message_delta"]
        assert deltas, "tool stream emitted no message_delta"
        assert deltas[0]["delta"]["stop_reason"] == "tool_use", deltas[0]

    def test_synthesized_terminals_include_message_delta(self, candidate_adapter):
        """Even when upstream sends no [DONE], the synthesized terminals include message_delta."""
        status, body = _post_stream(candidate_adapter, "finish_missing_terminals")
        assert status == 200
        types = [e["type"] for e in _parse_sse_events(body)]
        assert "message_delta" in types, types
