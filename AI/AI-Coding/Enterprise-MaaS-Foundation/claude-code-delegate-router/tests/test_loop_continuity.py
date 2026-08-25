"""Loop continuity gates (PRD LOOP_CONTINUITY_V1 G1–G6).

Each gate must have discrimination power: it must FAIL when the fix is reverted.
G5's current value is 6 (not 0), so it is already red under the old code — no
reverse case needs constructing.

G1: malformed args → client gets SSE error OR a real tool_use after retry;
    never a silent end_turn with only degradation text.
G2: two tool calls (first malformed, second valid) → second is still emitted.
G3: retry produces a real tool_use (1 message_start); already-streamed text
    → no retry, no duplicate body.
G4: normalize_failed path → request_end.repair !== null with all fields.
G5: full JSONL scan: stop_reason=end_turn + content = [text] + text =
    SAFE_DEGRADATION_TEXT → count 0.
G6: /status.stop_reasons exists and counts sum to request_end total.
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
SAFE_DEGRADATION_TEXT = "所请求的工具调用未被执行：模型生成的参数不符合该工具的接口约定。可以用修正后的参数重试。"


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


def _post_stream(adapter_port: int, scenario: str, tools: list | None = None,
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


# ---------------------------------------------------------------------------
# G1: no silent end_turn with only degradation text
# M2 (PRD LOOP_CONTINUITY_V2): split into two tests — retry path (L1-A) and
# no-retry path (L1-B).  The old single G1 had no discrimination power against
# L1-B rollback because retry success produced a tool_use regardless.
# ---------------------------------------------------------------------------


def test_g1_retry_path(upstream):
    """G1 retry path (L1-A): malformed args with retry enabled → client gets a
    real tool_use (retry succeeded) or an error (retry failed), never a silent
    end_turn with only degradation text."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        status, body = _post_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # The turn must NOT end with end_turn + only degradation text.
        message_deltas = [e for e in events if e.get("type") == "message_delta"]
        for md in message_deltas:
            stop_reason = md.get("data", {}).get("delta", {}).get("stop_reason")
            assert stop_reason != "end_turn", (
                f"G1-retry FAIL: silent end_turn on degraded turn: {body[:300]}"
            )

        # Either an error frame (L1-B after retry failed) or a real tool_use.
        has_error = any(e.get("type") == "error" for e in events)
        has_tool_use = any(
            e.get("type") == "content_block_start"
            and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
            for e in events
        )
        assert has_error or has_tool_use, (
            f"G1-retry FAIL: neither error nor tool_use: {body[:300]}"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_g1_no_retry_must_error(upstream):
    """G1 no-retry path (L1-B, M2-G): malformed args with retry DISABLED →
    client MUST receive an SSE error frame and MUST NOT see end_turn.

    Reverse case: if L1-B is reverted (end_turn instead of _setProtocolError),
    this test FAILS because there is no error frame and stop_reason is end_turn.
    The old single G1 did NOT fail under this revert because retry was enabled
    and succeeded — this test closes that gap."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})
    try:
        status, body = _post_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # An error frame MUST be present — L1-B's core guarantee.
        has_error = any(e.get("type") == "error" for e in events)
        assert has_error, (
            f"G1-no-retry FAIL: no error frame — L1-B reverted, the agent loop "
            f"would stop silently: {body[:300]}"
        )

        # stop_reason must NOT be end_turn.
        message_deltas = [e for e in events if e.get("type") == "message_delta"]
        for md in message_deltas:
            stop_reason = md.get("data", {}).get("delta", {}).get("stop_reason")
            assert stop_reason != "end_turn", (
                f"G1-no-retry FAIL: silent end_turn — L1-B reverted: {body[:300]}"
            )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# G2: subsequent valid tool calls are not dropped
# ---------------------------------------------------------------------------


def test_g2_subsequent_valid_tool_not_dropped(upstream):
    """G2: two tool calls (first malformed, second valid) → second is emitted."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})  # disable retry to test L2 in isolation
    try:
        tools = [
            {"name": "get_weather", "description": "Get weather",
             "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}}},
            {"name": "get_time", "description": "Get time",
             "input_schema": {"type": "object", "properties": {"zone": {"type": "string"}}}},
        ]
        status, body = _post_stream(adapter_port, "tool_malformed_then_valid", tools=tools)
        events = _parse_sse_events(body)

        # The second tool call (get_time, valid) must be emitted.
        tool_use_starts = [
            e for e in events if e.get("type") == "content_block_start"
            and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
        ]
        tool_names = [e["data"]["content_block"]["name"] for e in tool_use_starts]
        assert "get_time" in tool_names, (
            f"G2 FAIL: second valid tool call dropped. tool_use blocks: {tool_names}. "
            f"Body: {body[:400]}"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# G3: retry produces real tool_use; already-streamed text → no retry
# ---------------------------------------------------------------------------


def test_g3_retry_produces_real_tool_use(upstream):
    """G3: first attempt malformed, retry returns valid → client gets exactly
    1 message_start and a real tool_use."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        tools = [{"name": "get_weather", "description": "Get weather",
                  "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}}}]
        status, body = _post_stream(adapter_port, "tool_malformed", tools=tools)
        events = _parse_sse_events(body)

        # Exactly 1 message_start.
        message_starts = [e for e in events if e.get("type") == "message_start"]
        assert len(message_starts) == 1, (
            f"G3 FAIL: expected 1 message_start, got {len(message_starts)}"
        )

        # A real tool_use with valid input.
        tool_use_starts = [
            e for e in events if e.get("type") == "content_block_start"
            and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
        ]
        assert len(tool_use_starts) >= 1, (
            f"G3 FAIL: no tool_use after retry. Body: {body[:300]}"
        )

        # /status should show retry attempted + succeeded.
        time.sleep(0.3)
        st = _status(adapter_port)
        retry = st.get("tool_args_retry", {})
        assert retry.get("attempted", 0) >= 1, f"G3: retry not attempted: {retry}"
        assert retry.get("succeeded", 0) >= 1, f"G3: retry not succeeded: {retry}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_g3_no_duplicate_text_after_retry(upstream):
    """M3-G (PRD LOOP_CONTINUITY_V2): when text has already been streamed to
    the client before a malformed tool call, the non-streaming retry must NOT
    cause that text to appear twice.  The adapter uses a non-streaming
    directed retry (stream:false + tool_choice), so only tool_calls[0].args
    are consumed — the already-streamed text is never re-emitted.

    Reverse case: if the retry were changed to a streaming re-ask that replays
    the full response, the text "Let me check the weather." would appear twice.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        status, body = _post_stream(adapter_port, "text_then_malformed_tool")
        events = _parse_sse_events(body)

        # Collect all text deltas and concatenate.
        text_deltas = [
            e for e in events if e.get("type") == "content_block_delta"
            and e.get("data", {}).get("delta", {}).get("type") == "text_delta"
        ]
        full_text = "".join(
            e.get("data", {}).get("delta", {}).get("text", "") for e in text_deltas
        )

        # The streamed text must appear exactly once (not duplicated by retry).
        expected = "Let me check the weather."
        assert full_text.count(expected) == 1, (
            f"M3-G FAIL: streamed text appeared {full_text.count(expected)} times "
            f"(expected 1). Full text: {full_text[:200]}"
        )

        # Exactly 1 message_start — retry must not start a new message.
        message_starts = [e for e in events if e.get("type") == "message_start"]
        assert len(message_starts) == 1, (
            f"M3-G FAIL: {len(message_starts)} message_start events (expected 1)"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# G4: normalize_failed path has repair info
# ---------------------------------------------------------------------------


def test_g4_normalize_failed_has_repair_info(upstream):
    """G4: normalize_failed path → request_end.repair !== null with all fields."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        # tool_truncated_closeable with a schema requiring city+unit:
        # repair closes to {"city":"Beijing"} but normalize fails on missing unit.
        tools = [{
            "name": "get_weather", "description": "Get weather",
            "input_schema": {
                "type": "object",
                "required": ["city", "unit"],
                "properties": {"city": {"type": "string"}, "unit": {"type": "string"}},
            },
        }]
        status, body = _post_stream(adapter_port, "tool_truncated_closeable", tools=tools)
        time.sleep(0.5)

        entry = _read_request_end(adapter_proc)
        assert entry is not None, "G4: no request_end log"
        repair = entry.get("repair")
        assert repair is not None, (
            f"G4 FAIL: repair is null on normalize_failed path: {entry}"
        )
        # Must have the standard diagnostic fields.
        for field in ("attempted", "gate", "schema", "mode"):
            assert field in repair, f"G4: missing {field} in repair: {repair}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# G5: no silent end_turn + only degradation text (structural check)
# ---------------------------------------------------------------------------


def test_g5_no_silent_end_turn_only_degradation_text(upstream):
    """G5: a degraded turn must never end with stop_reason=end_turn and a body
    whose only content is the SAFE_DEGRADATION_TEXT.  Under the old code this
    was 6 occurrences; under the fix it must be 0."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})  # force degradation path
    try:
        status, body = _post_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # Collect all text deltas.
        text_deltas = [
            e for e in events if e.get("type") == "content_block_delta"
            and e.get("data", {}).get("delta", {}).get("type") == "text_delta"
        ]
        text_content = "".join(
            e.get("data", {}).get("delta", {}).get("text", "") for e in text_deltas
        )

        # Check stop_reason.
        message_deltas = [e for e in events if e.get("type") == "message_delta"]
        stop_reason = None
        if message_deltas:
            stop_reason = message_deltas[0].get("data", {}).get("delta", {}).get("stop_reason")

        # The forbidden pattern: end_turn + only degradation text.
        is_silent_end = (
            stop_reason == "end_turn"
            and text_content.strip() == SAFE_DEGRADATION_TEXT.strip()
            and not any(
                e.get("type") == "content_block_start"
                and e.get("data", {}).get("content_block", {}).get("type") == "tool_use"
                for e in events
            )
        )
        assert not is_silent_end, (
            f"G5 FAIL: silent end_turn with only degradation text. "
            f"stop_reason={stop_reason}, text={text_content[:100]}"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# G6: /status.stop_reasons exists and counts sum to request_end total
# ---------------------------------------------------------------------------


def test_g6_stop_reasons_in_status(upstream):
    """G6: /status.stop_reasons exists and is a dict of stop_reason → count."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce"})
    try:
        # Send a normal request to populate stop_reasons.
        _post_stream(adapter_port, "reasoning_then_text")
        time.sleep(0.5)

        st = _status(adapter_port)
        assert "stop_reasons" in st, f"G6: stop_reasons missing from /status: {st}"
        assert isinstance(st["stop_reasons"], dict), f"G6: stop_reasons not a dict: {st['stop_reasons']}"
        # At least one stop_reason should be counted.
        assert len(st["stop_reasons"]) >= 1, f"G6: stop_reasons empty: {st['stop_reasons']}"
        # The normal request should have end_turn.
        assert "end_turn" in st["stop_reasons"], f"G6: end_turn missing: {st['stop_reasons']}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_g6_degraded_no_tool_emitted_counter(upstream):
    """G6 companion: /status.degraded_no_tool_emitted exists and increments
    when a degraded turn emits zero tool_use blocks."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "enforce",
                                  "MAAS_TOOL_ARG_RETRY": "0"})
    try:
        before = _status(adapter_port).get("degraded_no_tool_emitted", 0)
        # tool_malformed with retry disabled → degrade, no tool_use emitted.
        _post_stream(adapter_port, "tool_malformed")
        time.sleep(0.5)
        after = _status(adapter_port).get("degraded_no_tool_emitted", 0)
        assert after >= before + 1, (
            f"G6: degraded_no_tool_emitted did not increment: {before} → {after}"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
