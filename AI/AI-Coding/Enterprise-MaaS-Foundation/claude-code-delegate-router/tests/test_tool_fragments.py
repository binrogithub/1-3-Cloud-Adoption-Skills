"""Tool-call fragment aggregation gates (PRD RELEASE_CLOSURE_V5 D2).

Tests that the adapter correctly assembles tool-call arguments split across
multiple streamed chunks when the upstream omits `index` from the delta.

The defect (V5 V1): `call.index ?? toolCalls.size` uses the Map size as the
key when index is absent.  Each fragment gets a different key (size increments),
splitting one call into N entries — each holding a non-JSON fragment.

Both tests MUST FAIL before the D1 fix (0 tool_use blocks + error frames).
After D1 (OpenAI streaming semantics: id/name starts a call, args-only
continues it), both PASS.
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


def _start_adapter(upstream_port: int) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_CONNECT_TIMEOUT"] = "5"
    env["MAAS_IDLE_TIMEOUT"] = "30"
    env["MAAS_TOTAL_TIMEOUT"] = "60"
    env["MAAS_MAX_CONCURRENCY"] = "8"
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


def _get_status(adapter_port: int) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
    conn.request("GET", "/status")
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return data


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
# D2: Fragment aggregation reverse gates
# ---------------------------------------------------------------------------


def test_fragments_no_index_assembles(upstream):
    """D2: One tool call split across 3 chunks with NO index must assemble
    into a single tool_use block with input == {"city":"Beijing"}.

    Pre-fix: 0 tool_use blocks + error frames (fragments split into 3 entries).
    Post-fix: 1 tool_use block, correct input, no errors.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        status, body = _send_stream(adapter_port, "tool_fragments_no_index")
        events = _parse_sse_events(body)

        # Must have exactly 1 tool_use block.
        tool_starts = [e for e in events if e.get("type") == "content_block_start"
                       and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"]
        assert len(tool_starts) == 1, \
            f"expected 1 tool_use block, got {len(tool_starts)}. " \
            f"Events: {[e.get('type') for e in events]}"

        # The input_json_delta must parse to {"city":"Beijing"}.
        tool_deltas = [e for e in events if e.get("type") == "content_block_delta"
                       and e.get("data", {}).get("delta", {}).get("type") == "input_json_delta"]
        assert len(tool_deltas) >= 1, "no input_json_delta found"
        input_obj = json.loads(tool_deltas[0]["data"]["delta"]["partial_json"])
        assert input_obj == {"city": "Beijing"}, \
            f"assembled input mismatch: {input_obj} — expected {{'city':'Beijing'}}"

        # No error frames.
        has_error = any(e.get("type") == "error" for e in events)
        assert not has_error, f"unexpected error: {body[:300]}"

        # /status error_counts must be empty.
        time.sleep(0.5)
        st = _get_status(adapter_port)
        assert st["error_counts"] == {}, \
            f"error_counts not empty: {st['error_counts']}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_two_calls_no_index_assembles(upstream):
    """D2: Two tool calls, each split across 2 chunks with NO index, must
    assemble into 2 tool_use blocks with correct inputs.

    Pre-fix: fragments split into 4 entries, parse failures.
    Post-fix: 2 tool_use blocks, inputs {"city":"Tokyo"} and {"zone":"JST"}.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        status, body = _send_stream(adapter_port, "tool_two_calls_no_index")
        events = _parse_sse_events(body)

        # Must have exactly 2 tool_use blocks.
        tool_starts = [e for e in events if e.get("type") == "content_block_start"
                       and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"]
        assert len(tool_starts) == 2, \
            f"expected 2 tool_use blocks, got {len(tool_starts)}. " \
            f"Events: {[e.get('type') for e in events]}"

        # Both inputs must be correct.
        tool_deltas = [e for e in events if e.get("type") == "content_block_delta"
                       and e.get("data", {}).get("delta", {}).get("type") == "input_json_delta"]
        assert len(tool_deltas) == 2, f"expected 2 input_json_delta, got {len(tool_deltas)}"
        inputs = [json.loads(d["data"]["delta"]["partial_json"]) for d in tool_deltas]
        assert {"city": "Tokyo"} in inputs, f"missing {{'city':'Tokyo'}} in {inputs}"
        assert {"zone": "JST"} in inputs, f"missing {{'zone':'JST'}} in {inputs}"

        # No error frames.
        has_error = any(e.get("type") == "error" for e in events)
        assert not has_error, f"unexpected error: {body[:300]}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
