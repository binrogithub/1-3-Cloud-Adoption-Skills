"""Tool args repair gates (PRD RELEASE_CLOSURE_V3 D1).

Tests the three-gate repair layer for truncated tool-call JSON:
  - Gate 1 (source): finishReason must be tool_use/end_turn, not max_tokens
  - Gate 2 (structure): only close unclosed brackets, last token must be complete value
  - Gate 3 (semantic): repaired result must pass input_schema validation

Critical constraint: tool_malformed ({"city":) must STILL FAIL — the repair
must not cross the "不得降级成 {}" contract line (test_adapter_contract.py:221).
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


def _post_stream_with_tools(adapter_port: int, scenario: str, tools: list | None = None,
                            timeout: float = 10.0) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=timeout)
    body_dict = {
        "model": "glm-5.2", "max_tokens": 64, "stream": True,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    }
    if tools:
        body_dict["tools"] = tools
    body = json.dumps(body_dict)
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


def _read_request_end(proc: subprocess.Popen) -> dict | None:
    """Read the first request_end structured-log line from adapter stderr."""
    import fcntl
    fd = proc.stderr.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    time.sleep(0.3)
    try:
        err = os.read(fd, 65536).decode("utf-8", errors="replace")
    except BlockingIOError:
        err = ""
    for line in err.strip().split("\n"):
        if '"request_end"' in line:
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


def _assert_no_tool_use_block(events: list[dict], scenario: str, mode: str):
    """Semantic invariant (both modes): no tool_use block emitted, no fabricated input."""
    tool_use_starts = [
        e for e in events if e.get("type") == "content_block_start"
        and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
    ]
    assert len(tool_use_starts) == 0, (
        f"{scenario} [{mode}]: tool_use block emitted — contract violation: {tool_use_starts}"
    )
    input_deltas = [
        e for e in events if e.get("type") == "content_block_delta"
        and e.get("data", {}).get("delta", {}).get("type") == "input_json_delta"
    ]
    assert len(input_deltas) == 0, (
        f"{scenario} [{mode}]: input_json_delta emitted — fabricated tool args: {input_deltas}"
    )


# ---------------------------------------------------------------------------
# D1 §3.1: Forward gate — repairable truncation
# ---------------------------------------------------------------------------


def test_tool_truncated_closeable_repaired(upstream):
    """D1 forward: '{"city":"Beijing"' (missing closing }) + finish_reason=tool_calls
    → repair succeeds, client receives tool_use with input == {"city":"Beijing"}.
    Requires enforce mode — observe mode records but doesn't apply the repair.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        status, body = _post_stream_with_tools(adapter_port, "tool_truncated_closeable")
        events = _parse_sse_events(body)

        # Should have a tool_use block with the repaired input.
        tool_deltas = [e for e in events if e.get("type") == "content_block_delta"
                       and e.get("data", {}).get("delta", {}).get("type") == "input_json_delta"]
        assert len(tool_deltas) >= 1, f"no tool_use delta found. Events: {[e.get('type') for e in events]}"

        input_json = tool_deltas[0]["data"]["delta"]["partial_json"]
        input_obj = json.loads(input_json)
        assert input_obj == {"city": "Beijing"}, \
            f"repaired input mismatch: {input_obj} — expected {{'city':'Beijing'}}"

        # Should complete successfully (message_stop present, no error).
        has_error = any(e.get("type") == "error" for e in events)
        assert not has_error, f"unexpected error after successful repair: {body[:300]}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D1 §3.2: Reverse gates — unresolvable args must not produce a tool_use block.
# Parametrized over observe/enforce (PRD RELEASE_V10 D2): the semantic invariant
# (no tool_use block, no fabricated input) holds in both modes.  Each mode has
# additional mode-specific assertions.
# ---------------------------------------------------------------------------

# (scenario, description) for the three structural reverse gates.
_REVERSE_SCENARIOS = [
    ("tool_malformed", '{"city": key without value → gate 2 rejects'),
    ("tool_truncated_midstring", '{"city":"Beij unterminated string → gate 2 rejects'),
    ("tool_truncated_by_length", '{"city":"Beijing" + finish_reason=length → gate 1 rejects'),
]


@pytest.mark.parametrize("mode", ["observe", "enforce"])
@pytest.mark.parametrize("scenario,desc", _REVERSE_SCENARIOS)
def test_unresolvable_args_no_tool_use(upstream, mode, scenario, desc):
    """D1 reverse (PRD RELEASE_V10 D2): unresolvable tool args must never produce
    a tool_use block or fabricated input — in BOTH observe and enforce modes.

    observe: hard-fail (error frame, outcome upstream_failed).
    enforce: safe-degrade (text block, outcome completed, degraded true).
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": mode})
    try:
        status, body = _post_stream_with_tools(adapter_port, scenario)
        events = _parse_sse_events(body)

        # Semantic invariant (both modes): no tool_use block, no fabricated input.
        _assert_no_tool_use_block(events, scenario, mode)

        if mode == "observe":
            # Hard fail: error frame present.
            has_error = any(e.get("type") == "error" for e in events)
            assert has_error, (
                f"{scenario} [observe]: expected error frame (hard fail): {body[:300]}"
            )
            # Structured log: outcome upstream_failed, degraded false.
            entry = _read_request_end(adapter_proc)
            assert entry is not None, f"{scenario} [observe]: no request_end log"
            assert entry.get("outcome") == "upstream_failed", (
                f"{scenario} [observe]: outcome={entry.get('outcome')} expected upstream_failed"
            )
            assert entry.get("degraded") is False, (
                f"{scenario} [observe]: degraded={entry.get('degraded')} expected False"
            )
        else:
            # enforce: safe degradation — no error, message_stop, stop_reason end_turn.
            has_error = any(e.get("type") == "error" for e in events)
            assert not has_error, (
                f"{scenario} [enforce]: unexpected error in degradation: {body[:300]}"
            )
            has_message_stop = any(e.get("type") == "message_stop" for e in events)
            assert has_message_stop, (
                f"{scenario} [enforce]: no message_stop — stream did not end cleanly: {body[:300]}"
            )
            message_deltas = [e for e in events if e.get("type") == "message_delta"]
            if message_deltas:
                stop_reason = message_deltas[0].get("data", {}).get("delta", {}).get("stop_reason")
                assert stop_reason == "end_turn", (
                    f"{scenario} [enforce]: stop_reason={stop_reason} expected end_turn"
                )
            # Structured log: outcome completed, degraded true.
            entry = _read_request_end(adapter_proc)
            assert entry is not None, f"{scenario} [enforce]: no request_end log"
            assert entry.get("degraded") is True, (
                f"{scenario} [enforce]: degraded={entry.get('degraded')} expected True"
            )
            assert entry.get("outcome") == "completed", (
                f"{scenario} [enforce]: outcome={entry.get('outcome')} expected completed"
            )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D1 §3.3: Schema gate — missing required field (parametrized over modes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["observe", "enforce"])
def test_schema_gate_no_tool_use(upstream, mode):
    """D1 schema gate (PRD RELEASE_V10 D2): repaired args missing a required
    field → gate 3 rejects.  No tool_use block in either mode.

    Schema requires city+unit; repair only produces city.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": mode})
    try:
        tools = [{
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {
                "type": "object",
                "required": ["city", "unit"],
                "properties": {
                    "city": {"type": "string"},
                    "unit": {"type": "string"},
                },
            },
        }]
        status, body = _post_stream_with_tools(
            adapter_port, "tool_truncated_closeable", tools=tools)
        events = _parse_sse_events(body)

        # Semantic invariant: no tool_use block, no fabricated input.
        _assert_no_tool_use_block(events, "schema_gate", mode)

        if mode == "observe":
            has_error = any(e.get("type") == "error" for e in events)
            assert has_error, (
                f"schema_gate [observe]: expected error frame: {body[:300]}"
            )
        else:
            has_error = any(e.get("type") == "error" for e in events)
            assert not has_error, (
                f"schema_gate [enforce]: unexpected error in degradation: {body[:300]}"
            )
            has_message_stop = any(e.get("type") == "message_stop" for e in events)
            assert has_message_stop, (
                f"schema_gate [enforce]: no message_stop: {body[:300]}"
            )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
