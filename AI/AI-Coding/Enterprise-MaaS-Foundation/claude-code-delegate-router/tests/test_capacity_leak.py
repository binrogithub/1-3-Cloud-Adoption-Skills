"""Capacity-leak reverse gates (PRD RELEASE_CLOSURE_V2 D2/R1).

Proves that the concurrency slot is released even when the post-stream code
path throws.  Uses a test hook (MAAS_TEST_THROW_AFTER=for_await) that injects
a throw after the for-await loop — this directly exercises the leak path,
NOT the client-abort path (which releases normally and has zero discrimination).

Both tests MUST FAIL before the D1 structural fix (cleanup in finally).
After D1, the finally block guarantees cleanup runs → both PASS.
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


# ---------------------------------------------------------------------------
# Process management (same pattern as test_keepalive.py)
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
    capacity: int = 8,
    extra_env: dict | None = None,
) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_CONNECT_TIMEOUT"] = "5"
    env["MAAS_IDLE_TIMEOUT"] = "30"
    env["MAAS_TOTAL_TIMEOUT"] = "60"
    env["MAAS_MAX_CONCURRENCY"] = str(capacity)
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


def _get_status(adapter_port: int) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", adapter_port, timeout=5.0)
    conn.request("GET", "/status")
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return data


def _send_stream(adapter_port: int, scenario: str = "reasoning_then_text",
                 timeout: float = 10.0) -> tuple[int, str]:
    """Send a streaming request and read the full response. Returns (status, body)."""
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


# ---------------------------------------------------------------------------
# D2: Capacity-leak reverse gates
# ---------------------------------------------------------------------------


def test_injective_throw_leaks_slot(upstream):
    """D2 injective gate: A throw in the post-stream code path must NOT leak
    the concurrency slot.

    Uses MAAS_TEST_THROW_AFTER=for_await to inject a throw after the for-await
    loop.  Pre-fix (cleanup not in finally): the throw skips cleanup(),
    active_requests stays 1 → FAIL.  Post-fix (finally): cleanup runs
    regardless → active_requests == 0 → PASS.

    This test does NOT use client-abort — that path releases normally and
    has zero discrimination against the defect.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        capacity=8,
        extra_env={"MAAS_TEST_THROW_AFTER": "for_await"},
    )
    try:
        # Send one request that will trigger the throw.
        status, body = _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)

        # Give the adapter a moment to process the throw and (if fixed) cleanup.
        time.sleep(1.0)

        status_data = _get_status(adapter_port)
        active = status_data["active_requests"]
        assert active == 0, \
            f"concurrency slot leaked after throw: active_requests={active} " \
            f"(capacity={status_data['capacity']}) — cleanup not in finally block"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_saturation_two_leaks_block_third(upstream):
    """D2 saturation gate: Two leaked slots must NOT block a third request.

    With capacity=2, trigger 2 throw-leak paths.  Pre-fix: both slots leak,
    active_requests=2, third request gets 503 → FAIL.  Post-fix: slots
    released, third request gets 200 → PASS.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        capacity=2,
        extra_env={"MAAS_TEST_THROW_AFTER": "for_await", "MAAS_TEST_THROW_AFTER_N": "2"},
    )
    try:
        # Trigger 2 leak paths.
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)

        # Check that slots are not leaked.
        status_data = _get_status(adapter_port)
        active = status_data["active_requests"]

        # Send a third request — it must be served (200), not rejected (503).
        status3, body3 = _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        assert status3 == 200, \
            f"third request rejected (status={status3}) — capacity leaked: " \
            f"active_requests was {active}, capacity=2. " \
            f"Body: {body3[:200]}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D4: Hang path + reaper reverse gates
# ---------------------------------------------------------------------------


def test_idle_hang_releases_slot(upstream):
    """D4 hang gate: An idle-hang (upstream silence, no exception) must release
    the concurrency slot via the watchdog (onTimeout → cleanup), not leak it.

    This tests the actual production failure mode (2h20m hang with no socket),
    NOT the throw path tested above.  Uses the `silence` scenario which never
    sends any data, triggering MAAS_IDLE_TIMEOUT.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        capacity=8,
        extra_env={
            "MAAS_IDLE_TIMEOUT": "3",
            "MAAS_TOTAL_TIMEOUT": "10",
        },
    )
    try:
        # Send a request against the silence scenario — upstream never responds.
        status, body = _send_stream(adapter_port, "silence", timeout=15.0)

        # Wait for idle timeout + margin.
        time.sleep(5.0)

        status_data = _get_status(adapter_port)
        active = status_data["active_requests"]
        assert active == 0, \
            f"concurrency slot leaked after idle hang: active_requests={active} — " \
            f"watchdog cleanup path not working"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_reaper_releases_orphan_slot(upstream):
    """D4 reaper gate: An orphan slot (cleanup skips both release AND delete)
    must be reaped by the reaper, and reaped_slots must increment.

    Uses MAAS_TEST_SKIP_CLEANUP=1 which makes cleanup a no-op for the guard
    and activeControllers, leaving the entry for the reaper to find.
    The reaper is a V2 safety net that has never been exercised by any test.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        capacity=8,
        extra_env={
            "MAAS_TEST_SKIP_CLEANUP": "1",
            "MAAS_CONNECT_TIMEOUT": "1",
            "MAAS_TOTAL_TIMEOUT": "1",
            "MAAS_REAPER_INTERVAL": "1",
            "NODE_ENV": "test",
        },
    )
    try:
        # Send a normal request — it completes, but cleanup is a no-op.
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)

        # The slot should still be in activeControllers (cleanup skipped delete).
        status_before = _get_status(adapter_port)
        assert status_before["active_requests"] >= 1, \
            f"orphan slot not in activeControllers: active_requests={status_before['active_requests']}"

        # Wait for reaper to fire (threshold = 1s + 60s = 61s, reaper every 1s).
        time.sleep(63.0)

        status_after = _get_status(adapter_port)
        assert status_after["reaped_slots"] >= 1, \
            f"reaper did not fire: reaped_slots={status_after['reaped_slots']}"
        assert status_after["active_requests"] == 0, \
            f"orphan slot not reaped: active_requests={status_after['active_requests']}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
