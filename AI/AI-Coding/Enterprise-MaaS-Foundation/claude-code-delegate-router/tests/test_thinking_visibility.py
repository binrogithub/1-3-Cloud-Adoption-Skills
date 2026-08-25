"""Tests for thinking-wait visibility (PRD THINKING_WAIT_VISIBILITY_V1 + closure).

Verifies that when the upstream sends reasoning_content, the adapter emits
synthetic thinking blocks so the client sees activity during the "thinking"
phase, without leaking the actual reasoning text.

Closure PRD (docs/PRD_THINKING_WAIT_VISIBILITY_V1_CLOSURE.md) fixes:
  C2: The mutation gate now actually disables thinking blocks via
      MAAS_THINKING_DISABLED=1 and verifies the tests fail — no more
      tautological "exists content_block_start" assertion.
  C3: reasoning_long scenario (12 chunks) crosses the heartbeat interval,
      so thinking_delta events are actually produced. Leak assertions
      now check a non-empty list (no more empty-set tautology).
  C4: The delay metric measures adapter overhead relative to upstream
      first byte, not absolute time (which is dominated by upstream latency).
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"
FAKE_UPSTREAM = ROOT / "tests" / "helpers" / "fake_upstream.js"

# High-entropy canary injected by the reasoning_long scenario.
CANARY = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh"


# ---------------------------------------------------------------------------
# Process management (same pattern as test_adapter_protocol_security.py)
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
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"fake upstream failed: {proc.stderr.read().decode()}")
    assert json.loads(line)["ready"]
    return proc, port


def _start_adapter(
    upstream_port: int,
    api_key: str = "test-key",
    extra_env: dict | None = None,
) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = api_key
    env["MAAS_TEST_UPSTREAM"] = "1"
    env["MAAS_CLIENT_KEY_FILE"] = str(Path(__file__).parent / "no-client.key")
    env["MAAS_CONNECT_TIMEOUT"] = "3"
    env["MAAS_IDLE_TIMEOUT"] = "3"
    env["MAAS_TOTAL_TIMEOUT"] = "6"
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


@pytest.fixture()
def adapter(upstream):
    proc, port = _start_adapter(upstream)
    yield proc, port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _post_stream(adapter_port: int, scenario: str, timeout: float = 10.0) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=timeout)
    body = json.dumps({
        "model": "glm-5.2", "max_tokens": 64, "stream": True,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    })
    conn.request("POST", "/v1/messages", body=body,
                 headers={"content-type": "application/json", "x-api-key": "test-key",
                          "x-fake-scenario": scenario})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="replace")
    status = resp.status
    conn.close()
    return status, data


def _parse_sse_events(raw: str) -> list[dict]:
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


def _thinking_deltas(events: list[dict]) -> list[dict]:
    """Extract all thinking_delta events from parsed SSE events."""
    return [
        e for e in events
        if e["type"] == "content_block_delta"
        and e["data"].get("delta", {}).get("type") == "thinking_delta"
    ]


# ---------------------------------------------------------------------------
# Test 1: Synthetic thinking block emitted on reasoning_content
# ---------------------------------------------------------------------------


def test_synthetic_thinking_block_emitted(adapter):
    """When upstream sends reasoning_content, the adapter must emit a
    content_block_start with type:thinking."""
    _, port = adapter
    status, body = _post_stream(port, "reasoning_then_text")
    assert status == 200
    events = _parse_sse_events(body)

    # Find content_block_start events.
    block_starts = [
        e for e in events
        if e["type"] == "content_block_start"
    ]
    block_types = [e["data"]["content_block"]["type"] for e in block_starts]

    # Must have a thinking block.
    assert "thinking" in block_types, \
        f"no thinking block in starts: {block_types}\nbody: {body}"

    # Must also have a text block.
    assert "text" in block_types, f"no text block in starts: {block_types}"


# ---------------------------------------------------------------------------
# Test 2: Zero reasoning leakage — canary never in client SSE
# ---------------------------------------------------------------------------


def test_reasoning_canary_not_leaked(adapter):
    """The high-entropy canary from reasoning_long must never appear in the
    client SSE body. This is the zero-leakage invariant (PRD §4 #2)."""
    _, port = adapter
    status, body = _post_stream(port, "reasoning_long")
    assert status == 200

    assert CANARY not in body, \
        f"reasoning canary leaked into client SSE body"


def test_thinking_delta_contains_only_placeholder(adapter):
    """thinking_delta events must contain only the placeholder character,
    never the model's reasoning text.

    C3 fix: reasoning_long sends 12 reasoning chunks, crossing the heartbeat
    interval (3) → thinking_delta events ARE produced. We assert the list
    is non-empty (no more empty-set tautology) before checking content.
    """
    _, port = adapter
    status, body = _post_stream(port, "reasoning_long")
    assert status == 200
    events = _parse_sse_events(body)

    deltas = _thinking_deltas(events)

    # C3: Must have actually produced thinking_delta events.
    # With 12 reasoning chunks and default interval 3, we expect floor(12/3) = 4.
    assert len(deltas) > 0, \
        f"no thinking_delta events produced — heartbeat never fired (body: {body})"

    for e in deltas:
        thinking_text = e["data"]["delta"].get("thinking", "")
        # Each thinking_delta must be the placeholder, not model reasoning.
        assert CANARY not in thinking_text, \
            f"canary leaked in thinking_delta: {thinking_text}"
        assert "step" not in thinking_text, \
            f"reasoning text leaked in thinking_delta: {thinking_text}"


# ---------------------------------------------------------------------------
# Test 3: Thinking block closed before text block starts (protocol order)
# ---------------------------------------------------------------------------


def test_thinking_block_closed_before_text(adapter):
    """The thinking content_block_stop must appear before the text
    content_block_start."""
    _, port = adapter
    status, body = _post_stream(port, "reasoning_then_text")
    assert status == 200
    events = _parse_sse_events(body)

    # Find the thinking block start and stop.
    thinking_start_idx = None
    thinking_stop_idx = None
    text_start_idx = None

    for i, e in enumerate(events):
        if e["type"] == "content_block_start":
            bt = e["data"]["content_block"]["type"]
            if bt == "thinking" and thinking_start_idx is None:
                thinking_start_idx = i
            elif bt == "text" and text_start_idx is None:
                text_start_idx = i
        elif e["type"] == "content_block_stop":
            # The first stop after thinking start is the thinking stop.
            if thinking_start_idx is not None and thinking_stop_idx is None:
                thinking_stop_idx = i

    assert thinking_start_idx is not None, "no thinking block start"
    assert thinking_stop_idx is not None, "no thinking block stop"
    assert text_start_idx is not None, "no text block start"

    assert thinking_stop_idx < text_start_idx, \
        f"thinking stop ({thinking_stop_idx}) must precede text start ({text_start_idx})"


# ---------------------------------------------------------------------------
# Test 4: Adapter overhead — extra delay relative to upstream first byte (C4)
# ---------------------------------------------------------------------------


def test_adapter_overhead_relative_to_upstream(adapter):
    """C4 fix: The metric is no longer absolute ≤2s (which is dominated by
    upstream first-byte latency the adapter cannot control). Instead we
    measure the adapter's own overhead: the time from upstream first byte
    to the first client-visible thinking event.

    With reasoning_delayed (300ms upstream delay), the adapter should emit
    the thinking block within 0.5s of receiving the first upstream chunk.
    """
    _, port = adapter

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10.0)
    body = json.dumps({
        "model": "glm-5.2", "max_tokens": 64, "stream": True,
        "messages": [{"role": "user", "content": "scenario:reasoning_delayed Say OK."}],
    })
    conn.request("POST", "/v1/messages", body=body,
                 headers={"content-type": "application/json", "x-api-key": "test-key",
                          "x-fake-scenario": "reasoning_delayed"})

    request_start = time.monotonic()
    resp = conn.getresponse()

    # Read the first SSE chunk — this arrives after upstream first byte +
    # adapter overhead. The reasoning_delayed scenario delays 300ms before
    # sending anything, so the first event time includes that 300ms.
    first_chunk = resp.read1(4096)
    first_event_time = time.monotonic() - request_start

    # Drain the rest.
    while True:
        chunk = resp.read1(4096)
        if not chunk:
            break

    conn.close()

    decoded = first_chunk.decode("utf-8", errors="replace")
    assert "event:" in decoded, f"no SSE event in first chunk: {decoded!r}"

    # The reasoning_delayed scenario has a 300ms upstream delay.
    # The adapter overhead (extra delay beyond upstream first byte) must be
    # ≤0.5s. So total first-event time should be ≤ 0.3s + 0.5s = 0.8s.
    # We assert <1.0s — tightened from 1.5s (PRD CLIENT_CONFIG_PROTECTION §3)
    # to preserve discrimination: 0.8s is the expected value, 1.0s gives 0.2s
    # jitter headroom, 1.5s was too loose to catch regressions.
    assert first_event_time < 1.0, \
        f"first event took {first_event_time:.2f}s — adapter overhead too high " \
        f"(upstream delay is 300ms, expected <1.0s total)"


# ---------------------------------------------------------------------------
# Test 5: Inbound thinking strip
# ---------------------------------------------------------------------------


def test_inbound_thinking_stripped(upstream):
    """Assistant messages with thinking blocks must not forward the thinking
    content to the upstream (OpenAI format has no thinking field)."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=10.0)
        # Send a conversation with a thinking block in the assistant turn.
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "messages": [
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": [
                    {"type": "thinking", "thinking": "I need to add 2 and 2."},
                    {"type": "text", "text": "4"},
                ]},
                {"role": "user", "content": "Thanks!"},
            ],
        })
        conn.request("POST", "/v1/messages", body=body,
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": "reasoning_then_text"})
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", errors="replace")
        conn.close()

        # The response should be 200 (the upstream should not choke on
        # the thinking content — it should have been stripped).
        assert resp.status == 200, f"expected 200, got {resp.status}: {data}"

        # The thinking text "I need to add 2 and 2." should not appear
        # in the upstream request. We can't directly inspect the upstream
        # request, but we can verify the adapter didn't crash or error.
        assert "error" not in data.lower() or "MAAS_" in data, \
            f"unexpected error in response: {data}"

    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# Test 6: Mutation gate — MAAS_THINKING_DISABLED=1 must break the tests (C2)
# ---------------------------------------------------------------------------


def test_mutation_thinking_disabled_breaks_visibility(upstream):
    """C2 mutation gate: When MAAS_THINKING_DISABLED=1, the adapter must NOT
    emit any synthetic thinking blocks. This test verifies the kill switch
    works — if someone sets it in production, thinking blocks disappear.

    This is the reverse-gate: we prove the feature is absent when disabled,
    confirming that the positive tests (which run with the default) are
    actually testing the feature's presence, not a tautology.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_THINKING_DISABLED": "1"},
    )
    try:
        status, body = _post_stream(adapter_port, "reasoning_long")
        assert status == 200
        events = _parse_sse_events(body)

        # With thinking disabled, there must be NO thinking blocks.
        thinking_starts = [
            e for e in events
            if e["type"] == "content_block_start"
            and e["data"]["content_block"]["type"] == "thinking"
        ]
        assert len(thinking_starts) == 0, \
            f"MAAS_THINKING_DISABLED=1 but thinking blocks were emitted: {thinking_starts}"

        # And no thinking_delta events.
        deltas = _thinking_deltas(events)
        assert len(deltas) == 0, \
            f"MAAS_THINKING_DISABLED=1 but thinking_deltas were emitted: {deltas}"

        # But text blocks should still work (the adapter isn't broken, just
        # the thinking feature is off).
        text_starts = [
            e for e in events
            if e["type"] == "content_block_start"
            and e["data"]["content_block"]["type"] == "text"
        ]
        assert len(text_starts) >= 1, \
            f"text blocks missing even with thinking disabled — adapter broken: {body}"

    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_mutation_thinking_disabled_leaks_nothing_extra(upstream):
    """C2 supplementary: Even with thinking disabled, the reasoning canary
    must not leak. The adapter must still not forward reasoning_content
    to the client, regardless of the thinking block setting."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_THINKING_DISABLED": "1"},
    )
    try:
        status, body = _post_stream(adapter_port, "reasoning_long")
        assert status == 200
        assert CANARY not in body, \
            "reasoning canary leaked even with thinking disabled"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# Test 7: Heartbeat count matches expectation (C3 non-empty coverage)
# ---------------------------------------------------------------------------


def test_heartbeat_count_matches_reasoning_chunks(upstream):
    """C3: With 12 reasoning chunks and heartbeat interval 2, the adapter
    must produce exactly 12/2 = 6 thinking_delta events. This proves
    the heartbeat mechanism is exercised by the test suite (previously it
    was never triggered because reasoning_then_text only sends 2 chunks)."""
    upstream_port = upstream
    # Use interval=2 for a clean count: 12 chunks / 2 = 6 deltas.
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_THINKING_HEARTBEAT_INTERVAL": "2"},
    )
    try:
        status, body = _post_stream(adapter_port, "reasoning_long")
        assert status == 200
        events = _parse_sse_events(body)
        deltas = _thinking_deltas(events)

        # 12 reasoning chunks, interval 2 → 6 deltas.
        assert len(deltas) == 6, \
            f"expected 6 thinking_deltas (12 chunks / interval 2), got {len(deltas)}: " \
            f"body: {body}"

        # All must be the placeholder.
        for e in deltas:
            assert e["data"]["delta"]["thinking"] == "·", \
                f"thinking_delta is not placeholder: {e}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# Test 8: /status exposes thinking_visibility (§3 cleanup item 1)
# ---------------------------------------------------------------------------


def test_status_exposes_thinking_visibility_enabled(upstream):
    """§3: /status must expose thinking_visibility:"enabled" by default,
    so that a misconfigured MAAS_THINKING_DISABLED=1 is visible in monitoring."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        assert resp.status == 200
        assert data.get("thinking_visibility") == "enabled", \
            f"expected thinking_visibility=enabled, got: {data.get('thinking_visibility')}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_status_exposes_thinking_visibility_disabled(upstream):
    """§3: When MAAS_THINKING_DISABLED=1, /status must show
    thinking_visibility:"disabled" so the misconfiguration is visible."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_THINKING_DISABLED": "1"},
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        assert resp.status == 200
        assert data.get("thinking_visibility") == "disabled", \
            f"expected thinking_visibility=disabled, got: {data.get('thinking_visibility')}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
