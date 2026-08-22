"""Tests for time-driven keepalive and client starvation visibility.

PRD: docs/PRD_TIME_DRIVEN_KEEPALIVE_V1.md

Verifies:
  D1: Time-driven keepalive — client byte interval ≤17s even on slow upstreams.
  D2: Client starvation state visible in /status.
  D3: Client abort recorded in /status (last_error_code + client_aborts count).
  D4: Idle timeout default is 150s (adapter fires before client stream timeout).

The two reverse gates (slow_reasoning, usage_only_trickle) MUST fail before the
fix — they are the proof that the test suite can now detect client starvation.
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

CANARY = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh"


# ---------------------------------------------------------------------------
# Process management (same pattern as test_thinking_visibility.py)
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
    env["MAAS_CONNECT_TIMEOUT"] = "5"
    env["MAAS_IDLE_TIMEOUT"] = "300"  # high so idle doesn't fire during slow tests
    env["MAAS_TOTAL_TIMEOUT"] = "600"
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


def _get_status(adapter_port: int) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
    conn.request("GET", "/status")
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return data


# ---------------------------------------------------------------------------
# D1: Time-driven keepalive — slow_reasoning reverse gate
# ---------------------------------------------------------------------------


def test_slow_reasoning_client_byte_interval(upstream):
    """D1 reverse gate §4.1: With slow_reasoning (1 reasoning chunk / 60s),
    the client must receive a byte at least every 17s (15s keepalive + 2s
    tolerance). Without time-driven keepalive, gaps would be ≈60s.

    We use a shorter keepalive interval (3s) and a faster slow_reasoning
    variant (10s between chunks) to keep the test under 30s wall-clock.

    Threshold is INTERVAL + 2s (constant jitter tolerance), NOT 2× INTERVAL.
    With the old setInterval+guard bug the worst-case gap is 2× INTERVAL = 6s,
    which exceeds the 5s bound → the test FAILS pre-fix, proving it can detect
    the defect.  Using INTERVAL=2 would make the bound 4s and the bug also 4s,
    giving zero discrimination — hence INTERVAL=3.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={
            "MAAS_KEEPALIVE_INTERVAL": "3",
            "MAAS_IDLE_TIMEOUT": "30",
        },
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=35.0)
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "messages": [{"role": "user", "content": "scenario:slow_reasoning Say OK."}],
        })
        conn.request("POST", "/v1/messages", body=body,
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": "slow_reasoning"})

        resp = conn.getresponse()
        timestamps = []
        deadline = time.monotonic() + 25  # read for up to 25s
        while time.monotonic() < deadline:
            chunk = resp.read1(4096)
            if not chunk:
                break
            timestamps.append(time.monotonic())

        conn.close()

        assert len(timestamps) >= 3, \
            f"too few client bytes received: {len(timestamps)}"

        # Compute: max gap between consecutive client bytes.
        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        max_gap = max(gaps)
        # Constant tolerance: INTERVAL(3s) + 2s jitter = 5s.  The 2s is a
        # constant for timer/TCP jitter, NOT a multiplier on INTERVAL.
        # Pre-fix (setInterval+guard): worst gap = 2×3 = 6s > 5s → FAIL.
        # Post-fix (self-rescheduling setTimeout): worst gap ≈ 3s + jitter ≤ 5s → PASS.
        assert max_gap <= 5.0, \
            f"client byte gap {max_gap:.1f}s exceeds keepalive bound (INTERVAL+2=5s) — " \
            f"time-driven keepalive not working. Gaps: {[f'{g:.1f}' for g in gaps]}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_usage_only_trickle_client_byte_interval(upstream):
    """D1 reverse gate §4.2: With usage_only_trickle (1 usage chunk / 30s,
    no content/reasoning), the client must still receive keepalive bytes.

    Uses 3s keepalive interval.  Threshold is INTERVAL + 2s = 5s (constant
    jitter tolerance).  See test_slow_reasoning_client_byte_interval for why
    INTERVAL=3 is required for discrimination (INTERVAL=2 gives bound==bug==4s).
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={
            "MAAS_KEEPALIVE_INTERVAL": "3",
            "MAAS_IDLE_TIMEOUT": "30",
        },
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=35.0)
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "messages": [{"role": "user", "content": "scenario:usage_only_trickle Say OK."}],
        })
        conn.request("POST", "/v1/messages", body=body,
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": "usage_only_trickle"})

        resp = conn.getresponse()
        timestamps = []
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            chunk = resp.read1(4096)
            if not chunk:
                break
            timestamps.append(time.monotonic())

        conn.close()

        assert len(timestamps) >= 3, \
            f"too few client bytes received: {len(timestamps)}"

        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        max_gap = max(gaps)
        assert max_gap <= 5.0, \
            f"client byte gap {max_gap:.1f}s exceeds keepalive bound (INTERVAL+2=5s) — " \
            f"ping-based keepalive not working. Gaps: {[f'{g:.1f}' for g in gaps]}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D1 §4.5: Zero leakage from keepalive events
# ---------------------------------------------------------------------------


def test_keepalive_zero_leakage(upstream):
    """D1 §4.5: Keepalive events must never leak reasoning content. We inject a
    high-entropy canary into reasoning_content, collect all client bytes, and
    assert the canary is absent. We also assert keepalive events were produced
    (no empty-set tautology).
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={
            "MAAS_KEEPALIVE_INTERVAL": "2",
            "MAAS_IDLE_TIMEOUT": "60",
        },
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=30.0)
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "messages": [{"role": "user", "content": "scenario:slow_reasoning_canary Say OK."}],
        })
        conn.request("POST", "/v1/messages", body=body,
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": "slow_reasoning_canary"})

        resp = conn.getresponse()
        all_bytes = b""
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            chunk = resp.read1(4096)
            if not chunk:
                break
            all_bytes += chunk

        conn.close()

        decoded = all_bytes.decode("utf-8", errors="replace")

        # Assert keepalive events were produced (non-empty).
        assert "event: ping" in decoded or "thinking_delta" in decoded, \
            "no keepalive events produced — empty-set tautology risk"

        # Assert canary never leaked.
        assert CANARY not in decoded, \
            "reasoning canary leaked into client SSE (including keepalive bytes)"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D3: Client abort must leave a trace
# ---------------------------------------------------------------------------


def test_client_abort_recorded(upstream):
    """D3 §4.3: When the client disconnects mid-stream, /status must show
    last_error_code == "MAAS_CLIENT_ABORTED" and client_aborts >= 1.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_IDLE_TIMEOUT": "10"},
    )
    try:
        conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=10.0)
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "messages": [{"role": "user", "content": "scenario:continuous_reasoning Say OK."}],
        })
        conn.request("POST", "/v1/messages", body=body,
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": "continuous_reasoning"})

        resp = conn.getresponse()
        # Read a tiny bit to confirm the stream started, then abort.
        resp.read1(128)
        conn.close()  # client disconnect mid-stream

        time.sleep(0.5)  # let the adapter process the close

        status = _get_status(adapter_port)
        assert status.get("last_error_code") == "MAAS_CLIENT_ABORTED", \
            f"expected MAAS_CLIENT_ABORTED, got: {status.get('last_error_code')}"
        assert status.get("client_aborts", 0) >= 1, \
            f"expected client_aborts >= 1, got: {status.get('client_aborts')}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D4: Idle timeout default is 150s
# ---------------------------------------------------------------------------


def test_idle_timeout_default_is_150(upstream):
    """D4: The default MAAS_IDLE_TIMEOUT must be 150s (down from 180s) so the
    adapter fires before Claude Code's ~180s stream timeout."""
    upstream_port = upstream
    # Start adapter WITHOUT MAAS_IDLE_TIMEOUT env → uses default.
    port = _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env.pop("MAAS_IDLE_TIMEOUT", None)
    proc = subprocess.Popen(
        ["node", str(CANDIDATE)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait_ready(port)
        status = _get_status(port)
        assert status["timeout_config"]["idle_ms"] == 150000, \
            f"expected idle_ms=150000, got: {status['timeout_config']['idle_ms']}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# D3: /status exposes client_aborts field
# ---------------------------------------------------------------------------


def test_status_exposes_client_aborts_field(adapter):
    """D3: /status must include a client_aborts field (integer >= 0)."""
    _, port = adapter
    status = _get_status(port)
    assert "client_aborts" in status, \
        f"client_aborts missing from /status: {list(status.keys())}"
    assert isinstance(status["client_aborts"], int), \
        f"client_aborts must be int, got: {type(status['client_aborts'])}"
    assert status["client_aborts"] >= 0
