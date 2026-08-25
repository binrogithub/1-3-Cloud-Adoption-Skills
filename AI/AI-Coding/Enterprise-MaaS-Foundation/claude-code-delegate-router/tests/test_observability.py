"""Observability gates (PRD RELEASE_CLOSURE_V2 D3/R5).

Verifies that:
  1. Every request terminal writes a structured JSON log line to stdout.
  2. The log line does NOT leak reasoning canary or API key.
  3. /status includes error_counts and recent_errors after errors.
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
CANARY = "CANARY-7f3a9c2e1b8d4f60-xyzzy-plugh"


# ---------------------------------------------------------------------------
# Process management
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


def _start_adapter(upstream_port: int, stdout_file=None, extra_env=None) -> tuple[subprocess.Popen, int]:
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
        env=env, stdout=stdout_file or subprocess.PIPE, stderr=subprocess.PIPE,
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


def _send_stream(adapter_port: int, scenario: str,
                 timeout: float = 10.0) -> tuple[int, str]:
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


def _read_adapter_stderr(proc: subprocess.Popen) -> str:
    """Read all available adapter stderr (non-blocking via os.read).

    The structured request log goes to stderr (console.error) because Node.js
    block-buffers stdout when piped, but stderr is line-buffered.
    """
    import fcntl
    try:
        fd = proc.stderr.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        chunks = []
        while True:
            try:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                chunks.append(chunk)
            except BlockingIOError:
                break
            except OSError:
                break
        return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# D3 tests
# ---------------------------------------------------------------------------


def test_terminal_log_written(upstream):
    """D3: After a request completes, adapter stdout contains a request_end
    JSON line with the expected fields."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, \
            f"no request_end log line found in stderr. Got:\n{stderr[:500]}"

        entry = json.loads(log_lines[-1])
        assert entry["type"] == "request_end"
        assert "request_id" in entry
        assert "state" in entry
        assert "duration_ms" in entry
        assert "outcome" in entry
        assert "upstream_chunks" in entry
        assert "client_bytes" in entry
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_log_no_canary_leak(upstream):
    """D3: The structured log must never contain reasoning canary."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        _send_stream(adapter_port, "reasoning_long", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        assert CANARY not in stderr, \
            "reasoning canary leaked into adapter stderr (structured log)"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_log_no_key_leak(upstream):
    """D3: The structured log must never contain the API key."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        assert "test-key" not in stderr, \
            "API key leaked into adapter stderr (structured log)"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_status_error_counts_after_error(upstream):
    """D3: /status must include error_counts and recent_errors after an
    error-producing request (eof_no_finish → STREAM_EOF)."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        # eof_no_finish: upstream ends without finish_reason → STREAM_EOF error.
        _send_stream(adapter_port, "eof_no_finish", timeout=10.0)
        time.sleep(0.5)

        status = _get_status(adapter_port)
        assert "error_counts" in status, "missing error_counts in /status"
        assert "recent_errors" in status, "missing recent_errors in /status"
        assert "reaped_slots" in status, "missing reaped_slots in /status"

        # error_counts should have at least one entry.
        assert len(status["error_counts"]) >= 1, \
            f"error_counts empty after error request: {status['error_counts']}"

        # recent_errors should have at least one entry.
        assert len(status["recent_errors"]) >= 1, \
            f"recent_errors empty after error request: {status['recent_errors']}"

        # The most recent error should have a timestamp and code.
        last_err = status["recent_errors"][-1]
        assert "ts" in last_err
        assert "code" in last_err
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_error_counts_single_count(upstream):
    """D4 (PRD RELEASE_CLOSURE_V4): a single failed request must record its
    error code exactly once in error_counts, and exactly once in recent_errors.

    Pre-fix: _fail() calls _onTimeout which calls recordError, then the
    post-finalize path calls recordError again → count is 2. FAIL.
    Post-fix: recordError is idempotent by requestId → count is 1. PASS.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        # tool_malformed → JSON.parse fails → STREAM_PROTOCOL error (observe hard-fail).
        _send_stream(adapter_port, "tool_malformed", timeout=10.0)
        time.sleep(0.5)

        status = _get_status(adapter_port)
        ec = status["error_counts"]
        re_list = status["recent_errors"]

        # The error count for STREAM_PROTOCOL must be exactly 1.
        assert ec.get("MAAS_STREAM_PROTOCOL", 0) == 1, \
            f"error_counts double-counted: MAAS_STREAM_PROTOCOL={ec.get('MAAS_STREAM_PROTOCOL')} " \
            f"(expected 1). Full error_counts: {ec}"

        # recent_errors must have exactly 1 entry with this code.
        protocol_entries = [e for e in re_list if e.get("code") == "MAAS_STREAM_PROTOCOL"]
        assert len(protocol_entries) == 1, \
            f"recent_errors has {len(protocol_entries)} STREAM_PROTOCOL entries " \
            f"(expected 1). Full recent_errors: {re_list}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_client_bytes_forward_gate(upstream):
    """D3 forward gate: a normal request must log client_bytes > 0.

    Pre-fix (res.bytesWritten which is undefined on http.ServerResponse):
    client_bytes is always 0 → FAIL.  Post-fix (write-side counter): PASS.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(upstream_port)
    try:
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, "no request_end log line"

        entry = json.loads(log_lines[-1])
        assert entry["client_bytes"] > 0, \
            f"client_bytes is {entry['client_bytes']} — should be > 0 for a normal request"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_client_bytes_reverse_gate(upstream):
    """D3 reverse gate: silence scenario (keepalive pings only, no content)
    must have client_bytes distinguishable from a healthy request.

    A healthy request sends message_start + content blocks + message_stop.
    A silence request sends only message_start + keepalive pings.  The
    client_bytes for silence must be strictly less than for a healthy request,
    proving the field can distinguish the two.
    """
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port,
        extra_env={"MAAS_KEEPALIVE_INTERVAL": "2", "MAAS_IDLE_TIMEOUT": "10"},
    )
    try:
        # Healthy request.
        _send_stream(adapter_port, "reasoning_then_text", timeout=10.0)
        time.sleep(1.0)
        stderr_healthy = _read_adapter_stderr(adapter_proc)
        healthy_lines = [l for l in stderr_healthy.strip().split("\n") if '"request_end"' in l]
        assert len(healthy_lines) >= 1, "no healthy request_end log"
        healthy_bytes = json.loads(healthy_lines[-1])["client_bytes"]

        # Silence request (keepalive pings only, then idle timeout ends it).
        _send_stream(adapter_port, "silence", timeout=15.0)
        time.sleep(1.0)
        stderr_silence = _read_adapter_stderr(adapter_proc)
        silence_lines = [l for l in stderr_silence.strip().split("\n") if '"request_end"' in l]
        assert len(silence_lines) >= 1, "no silence request_end log"
        silence_bytes = json.loads(silence_lines[-1])["client_bytes"]

        assert silence_bytes < healthy_bytes, \
            f"silence client_bytes ({silence_bytes}) should be < healthy ({healthy_bytes}) — " \
            f"client_bytes cannot distinguish starvation from health"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# D2 (PRD RELEASE_CLOSURE_V4): reject-class classification + leak gate
# ---------------------------------------------------------------------------

# scenario -> expected reject_class
REJECT_CLASS_CASES = [
    ("tool_malformed", "end_of_input"),            # {"city":
    ("tool_truncated_midstring", "unterminated_string"),  # {"city":"Beij
    ("tool_single_quote", "dialect_property_name"),  # {'city':'Beijing'}
    ("tool_trailing_comma", "expected_quoted_name"),  # {"a":1,
    ("tool_not_json", "not_json"),                  # get_weather(city=Beijing)
]


@pytest.mark.parametrize("scenario,expected_class", REJECT_CLASS_CASES)
def test_reject_class_classification(upstream, scenario, expected_class):
    """D2 classification gate: each parse-error type maps to the correct
    reject_class enum in the structured log."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, scenario, timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, f"no request_end log for {scenario}"

        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        assert repair is not None, f"no repair field in log for {scenario}: {entry}"
        assert repair.get("reject_class") == expected_class, \
            f"{scenario}: reject_class={repair.get('reject_class')} expected {expected_class}"
        assert "args_len" in repair, f"{scenario}: missing args_len in repair"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_reject_class_expected_comma_or_close(upstream):
    """D2: tool_truncated_closeable with repair DISABLED produces
    expected_comma_or_close (the closeable form {"city":"Beijing" fails
    JSON.parse with "Expected ',' or '}'")."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "off"})
    try:
        _send_stream(adapter_port, "tool_truncated_closeable", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, "no request_end log"

        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        assert repair is not None, f"no repair field: {entry}"
        assert repair.get("reject_class") == "expected_comma_or_close", \
            f"reject_class={repair.get('reject_class')} expected expected_comma_or_close"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_reject_class_no_canary_leak(upstream):
    """D2 leak gate: canary embedded in non-JSON tool args must NOT appear
    in adapter stderr.  The "not_json" class embeds a payload excerpt in
    err.message — classifyParseError must map it without logging the raw
    message."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, "tool_not_json_canary", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        assert CANARY not in stderr, \
            "canary leaked into adapter stderr — raw err.message or args logged"

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, "no request_end log"
        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        assert repair is not None, f"no repair field: {entry}"
        assert repair.get("reject_class") == "not_json", \
            f"reject_class={repair.get('reject_class')} expected not_json"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


# ---------------------------------------------------------------------------
# V6 D1: Shape diagnostics (first_char_code, char_class_counts)
# ---------------------------------------------------------------------------

# scenario -> expected first_char_code (Unicode code point of first non-ws char)
SHAPE_CASES = [
    ("tool_not_json", 0x67),        # 'g' (get_weather...)
    ("tool_single_quote", 0x7B),    # { ({"'city'":...} starts with {)
    ("tool_malformed", 0x7B),       # { ({"city":)
    ("tool_truncated_midstring", 0x7B),  # { ({"city":"Beij)
]


@pytest.mark.parametrize("scenario,expected_code", SHAPE_CASES)
def test_shape_diagnostics_first_char_code(upstream, scenario, expected_code):
    """V6 D1: first_char_code correctly identifies the first non-whitespace
    character's Unicode code point for each bad-args shape."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, scenario, timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, f"no request_end log for {scenario}"

        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        assert repair is not None, f"no repair field: {entry}"
        assert "first_char_code" in repair, f"missing first_char_code: {repair}"
        assert repair["first_char_code"] == expected_code, \
            f"{scenario}: first_char_code={repair['first_char_code']} expected {expected_code}"
        assert "char_class_counts" in repair, f"missing char_class_counts: {repair}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_shape_diagnostics_char_class_counts(upstream):
    """V6 D1: char_class_counts correctly counts punctuation in bad args."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        # tool_malformed: {"city": → 1 brace_open, 1 double_quote (x2), 1 colon
        _send_stream(adapter_port, "tool_malformed", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, "no request_end log"

        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        counts = repair.get("char_class_counts", {})
        assert counts.get("brace_open", 0) >= 1, f"expected brace_open >= 1: {counts}"
        assert counts.get("double_quote", 0) >= 2, f"expected double_quote >= 2: {counts}"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()


def test_shape_diagnostics_no_canary_leak(upstream):
    """V6 D1 leak gate: canary in bad args → first_char_code recorded but
    stderr contains no canary text.  The code point is a number, not text."""
    upstream_port = upstream
    adapter_proc, adapter_port = _start_adapter(
        upstream_port, extra_env={"MAAS_TOOL_ARG_MODE": "observe"})
    try:
        _send_stream(adapter_port, "tool_not_json_canary", timeout=10.0)
        time.sleep(1.0)
        stderr = _read_adapter_stderr(adapter_proc)

        assert CANARY not in stderr, \
            "canary leaked into stderr — shape diagnostics must not log args text"

        log_lines = [l for l in stderr.strip().split("\n") if '"request_end"' in l]
        assert len(log_lines) >= 1, "no request_end log"
        entry = json.loads(log_lines[-1])
        repair = entry.get("repair")
        assert repair is not None, f"no repair field: {entry}"
        assert repair.get("first_char_code") == 0x67, \
            f"first_char_code={repair.get('first_char_code')} expected 0x67 ('g')"
    finally:
        adapter_proc.terminate()
        try:
            adapter_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            adapter_proc.kill()
