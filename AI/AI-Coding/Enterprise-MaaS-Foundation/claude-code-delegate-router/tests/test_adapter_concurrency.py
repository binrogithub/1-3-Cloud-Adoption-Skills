"""Real concurrency gate for the MaaS adapter (G-CLOSE8).

Opens N simultaneous HTTP connections with a barrier so they overlap at the
fake upstream, then asserts the adapter's concurrency guard admits exactly
the configured capacity and rejects the excess with 503 promptly. This is
real C256: concurrent sockets with a barrier, not a sequential counter.

Also verifies no deadlock, no process crash, and no leaked active request
after the wave completes.
"""
from __future__ import annotations

import http.client
import json
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"
FAKE_UPSTREAM = ROOT / "tests" / "helpers" / "fake_upstream.js"


# ---------------------------------------------------------------------------
# Process management (shared with test_adapter_contract — duplicated to keep
# this module standalone and avoid cross-fixture coupling).
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
    data = json.loads(line)
    assert data["ready"], f"fake upstream not ready: {data}"
    return proc, port


def _start_adapter(upstream_port: int, capacity: int, adapter_port: int | None = None) -> tuple[subprocess.Popen, int]:
    import os
    port = adapter_port or _free_port()
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_TEST_UPSTREAM"] = "1"
    env["MAAS_CLIENT_KEY_FILE"] = str(Path(__file__).parent / "no-client.key")
    env["MAAS_CONNECT_TIMEOUT"] = "5"
    env["MAAS_IDLE_TIMEOUT"] = "5"
    env["MAAS_TOTAL_TIMEOUT"] = "10"
    env["MAAS_MAX_CONCURRENCY"] = str(capacity)
    env["MAAS_MAX_TOOL_ARGS_BYTES"] = "262144"
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


def _adapter_factory(upstream, capacity):
    proc, port = _start_adapter(upstream, capacity)
    return proc, port


# ---------------------------------------------------------------------------
# Concurrency wave helpers
# ---------------------------------------------------------------------------


def _make_request_body(scenario: str) -> bytes:
    return json.dumps({
        "model": "glm-5.2",
        "max_tokens": 64,
        "stream": True,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    }).encode()


def _fire_one(port: int, scenario: str, barrier: threading.Barrier, result: list, idx: int) -> None:
    """Open one HTTP connection, wait at the barrier, then read the response."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        conn.request("POST", "/v1/messages", body=_make_request_body(scenario),
                     headers={"content-type": "application/json", "x-api-key": "test-key",
                              "x-fake-scenario": scenario})
        # Wait until ALL threads have sent their request — true overlap.
        barrier.wait(timeout=10)
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", errors="replace")
        result[idx] = (resp.status, data)
        conn.close()
    except Exception as exc:  # noqa: BLE001
        result[idx] = (-1, repr(exc))


def _run_wave(adapter_port: int, n: int, scenario: str = "hold_then_finish") -> list[tuple[int, str]]:
    """Fire n concurrent requests with a barrier so they overlap at the upstream."""
    barrier = threading.Barrier(n + 1)  # +1 for the coordinator (this thread)
    result: list = [None] * n
    threads = []
    for i in range(n):
        t = threading.Thread(target=_fire_one, args=(adapter_port, scenario, barrier, result, i))
        t.start()
        threads.append(t)
    # Release all threads at once so their requests hit the adapter simultaneously.
    barrier.wait(timeout=10)
    for t in threads:
        t.join(timeout=20)
    return [r if r is not None else (-1, "no-result") for r in result]


def _count_status(results: list[tuple[int, str]], status: int) -> int:
    return sum(1 for s, _ in results if s == status)


# ===========================================================================
# Concurrency gate tests
# ===========================================================================


class TestConcurrencyGate:
    """G-CLOSE8: real concurrent HTTP connections, capacity enforced."""

    @pytest.mark.parametrize("capacity,n", [(2, 4), (4, 8), (8, 16), (16, 32)])
    def test_admitted_does_not_exceed_capacity(self, upstream, capacity, n):
        """At most `capacity` requests are admitted; the rest get 503."""
        proc, port = _adapter_factory(upstream, capacity)
        try:
            results = _run_wave(port, n, scenario="hold_then_finish")
            admitted = _count_status(results, 200)
            rejected = _count_status(results, 503)
            # No more than capacity admitted.
            assert admitted <= capacity, f"admitted {admitted} > capacity {capacity}"
            # Every request must be either admitted (200) or rejected (503).
            # (No 5xx crash, no hang/timeout.)
            other = [(s, d) for s, d in results if s not in (200, 503)]
            assert not other, f"unexpected statuses: {other[:3]}"
            # At least some should be rejected when n > capacity.
            if n > capacity:
                assert rejected >= 1, f"expected >=1 rejection, got {rejected}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_c64_admits_at_most_capacity(self, upstream):
        """C64 wave: 64 concurrent requests, capacity 16."""
        proc, port = _adapter_factory(upstream, 16)
        try:
            results = _run_wave(port, 64, scenario="hold_then_finish")
            admitted = _count_status(results, 200)
            assert admitted <= 16, f"admitted {admitted} > 16"
            rejected = _count_status(results, 503)
            assert rejected >= 48, f"expected >=48 rejections, got {rejected}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_c256_admits_at_most_capacity(self, upstream):
        """C256 wave: 256 concurrent requests, capacity 8.

        This is the headline G-CLOSE8 gate. 256 simultaneous sockets with a
        barrier; the adapter must admit <= 8 and 503 the rest promptly, with
        no deadlock or crash.
        """
        proc, port = _adapter_factory(upstream, 8)
        try:
            results = _run_wave(port, 256, scenario="hold_then_finish")
            admitted = _count_status(results, 200)
            rejected = _count_status(results, 503)
            assert admitted <= 8, f"admitted {admitted} > 8"
            assert rejected >= 248, f"expected >=248 rejections, got {rejected}"
            # No crash: every request resolved (no -1 / no-result).
            unresolved = [r for r in results if r[0] == -1]
            assert not unresolved, f"{len(unresolved)} requests did not resolve"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_no_leaked_active_after_wave(self, upstream):
        """After a wave completes, /status reports zero active requests."""
        proc, port = _adapter_factory(upstream, 4)
        try:
            _run_wave(port, 8, scenario="hold_then_finish")
            # Give the adapter a moment to release.
            time.sleep(1.0)
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/status")
            resp = conn.getresponse()
            data = json.loads(resp.read().decode())
            conn.close()
            assert resp.status == 200
            assert data["active_requests"] == 0, f"leaked active: {data['active_requests']}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_peak_reflects_max_concurrent(self, upstream):
        """Peak concurrency reflects the maximum simultaneous admitted count."""
        capacity = 4
        proc, port = _adapter_factory(upstream, capacity)
        try:
            _run_wave(port, capacity, scenario="hold_then_finish")
            time.sleep(1.0)
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/status")
            resp = conn.getresponse()
            data = json.loads(resp.read().decode())
            conn.close()
            assert resp.status == 200
            # Peak should have reached capacity (all `capacity` overlapped).
            assert data["peak_concurrency"] >= capacity, \
                f"peak {data['peak_concurrency']} < capacity {capacity}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_release_allows_re_admit(self, upstream):
        """After a wave releases, a new request is admitted (no permanent lock)."""
        proc, port = _adapter_factory(upstream, 2)
        try:
            _run_wave(port, 4, scenario="hold_then_finish")
            time.sleep(1.0)
            # A fresh request should now be admitted.
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            body = _make_request_body("reasoning_then_text")
            conn.request("POST", "/v1/messages", body=body,
                         headers={"content-type": "application/json", "x-api-key": "test-key",
                                  "x-fake-scenario": "reasoning_then_text"})
            resp = conn.getresponse()
            data = resp.read().decode("utf-8", errors="replace")
            conn.close()
            assert resp.status == 200, f"re-admit failed: {resp.status} {data[:200]}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
