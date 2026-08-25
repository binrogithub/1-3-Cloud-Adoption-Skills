"""Env isolation gate (PRD RELEASE_V10 D1).

Proves that test adapter subprocesses are isolated from the production env file
(/etc/claude-code-proxy/maas.env).  Without isolation, loadEnvFile() injects
production MAAS_TOOL_ARG_MODE into tests that don't set it, making test results
a function of ops state rather than code.

Two gates:
  1. A test adapter started without MAAS_TOOL_ARG_MODE behaves as observe (default),
     NOT as whatever the production env file says.
  2. The test adapter does not hold the production API key value.
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
PROD_ENV_FILE = Path("/etc/claude-code-proxy/maas.env")


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
    """Start adapter WITHOUT setting MAAS_TOOL_ARG_MODE — relies on conftest
    isolation to prevent the production env file from injecting it."""
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
    # Deliberately do NOT set MAAS_TOOL_ARG_MODE.
    # conftest.py sets ENV_FILE to an empty file so loadEnvFile is a no-op.
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


def test_unset_mode_behaves_as_observe(upstream):
    """D1 gate 1: an adapter started without MAAS_TOOL_ARG_MODE must behave as
    observe (hard-fail on tool_malformed), NOT as whatever the production env
    file says.

    Without conftest isolation, if /etc/claude-code-proxy/maas.env contains
    MAAS_TOOL_ARG_MODE=enforce, this test would see safe degradation (200,
    no error, message_stop) instead of the expected hard failure.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        status, body = _send_stream(adapter_port, "tool_malformed")
        events = _parse_sse_events(body)

        # observe mode: tool_malformed must produce an error frame (hard fail).
        has_error = any(e.get("type") == "error" for e in events)
        assert has_error, (
            f"adapter without explicit MAAS_TOOL_ARG_MODE did not hard-fail — "
            f"production env file leaked into test. Body: {body[:300]}"
        )

        # Must NOT have degradation text (that's enforce behavior).
        text_deltas = [
            e for e in events if e.get("type") == "content_block_delta"
            and e.get("data", {}).get("delta", {}).get("type") == "text_delta"
            and "未被执行" in e.get("data", {}).get("delta", {}).get("text", "")
        ]
        assert len(text_deltas) == 0, (
            f"degradation text emitted without explicit enforce mode — "
            f"production env file leaked: {text_deltas}"
        )

        # Structured log must show mode=observe, degraded=false.
        entry = _read_request_end(adapter_proc)
        assert entry is not None, "no request_end log"
        repair = entry.get("repair", {})
        assert repair.get("mode") == "observe", (
            f"repair.mode={repair.get('mode')} expected 'observe' — "
            f"production env file leaked into test"
        )
        assert entry.get("degraded") is False, (
            f"degraded={entry.get('degraded')} expected False in observe mode"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_no_production_key_leaked(upstream):
    """D1 gate 2: the test adapter must not hold the production API key value.

    If the production env file contains a real CLAUDE_CODE_PROXY_API_KEY and
    the test doesn't explicitly set it, loadEnvFile would inject it.  We set
    test-key explicitly in _start_adapter, but this gate verifies the adapter
    process environ doesn't contain the production key as a side effect.
    """
    # Read the production env file to find the real key (if any).
    prod_key = None
    if PROD_ENV_FILE.exists():
        for line in PROD_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("CLAUDE_CODE_PROXY_API_KEY="):
                prod_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    if not prod_key:
        pytest.skip("no production API key in env file — gate vacuously satisfied")

    # The test adapter uses "test-key" (set in _start_adapter).  Verify the
    # structured log doesn't contain the production key.
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        _send_stream(adapter_port, "reasoning_then_text")
        time.sleep(0.5)

        import fcntl
        fd = adapter_proc.stderr.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        try:
            err = os.read(fd, 65536).decode("utf-8", errors="replace")
        except BlockingIOError:
            err = ""

        assert prod_key not in err, (
            "production API key found in adapter stderr — env file leaked"
        )
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
