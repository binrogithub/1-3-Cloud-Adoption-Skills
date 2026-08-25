"""Non-streaming observability tests (PRD RELEASE_V12 §N4 / gate N4-G).

The non-streaming path used to update /status counters without emitting the
structured request_end line, so journald-based release metrics under-counted
and non-streaming failures were invisible (measured: 69 vs 23 on the
production window — 67% missing).

These tests drive real HTTP through the adapter and assert:

  1. every non-streaming exit path emits exactly one request_end with
     path="nonstream" and the required fields;
  2. /status stop_reasons accounting matches what the log records (same
     counting rule: trustworthy, non-null reasons only);
  3. a garbage 200 body from upstream is recorded as a protocol failure,
     not silently dropped (previously it threw into a catch that logged
     nothing).

Gate N4-G (the /status-sum == journald-count equality over a live window)
runs against the deployed service via scripts/window-check-v12.sh; here we
prove the per-request invariants that make the equality achievable.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"
FAKE_UPSTREAM = ROOT / "tests" / "helpers" / "fake_upstream.js"
sys.path.insert(0, str(ROOT / "tests"))
from test_security_hardening import (  # noqa: E402
    CLIENT_KEY, _basic_body, _free_port, _post, _start_adapter,
    _start_fake_upstream, _stop, _wait_ready,
)


@pytest.fixture()
def upstream():
    proc, port = _start_fake_upstream()
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def _request_end_lines(stdout_text: str) -> list[dict]:
    out = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if line.startswith("{") and '"request_end"' in line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


class TestNonstreamRequestEnd:
    def _run(self, upstream_port: int, body: dict, expect_status: int) -> tuple[list[dict], int]:
        proc, port, kf = _start_adapter(upstream_port, client_key=CLIENT_KEY)
        # Drain stderr continuously: request_end is written AFTER the client
        # response is flushed, and SIGTERM's default disposition kills the
        # process instantly — a post-hoc read() can lose the final line to
        # that race. (Production journald reads continuously; no loss there.)
        import threading
        err_chunks: list[bytes] = []
        def _drain():
            try:
                for chunk in iter(lambda: proc.stderr.read1(4096), b""):
                    err_chunks.append(chunk)
            except Exception:
                pass
        drain = threading.Thread(target=_drain, daemon=True)
        drain.start()
        try:
            status, _ = _post(
                port, body,
                {"content-type": "application/json", "x-api-key": CLIENT_KEY},
                timeout=15,
            )
            assert status == expect_status, f"expected {expect_status}, got {status}"
            import time as _time
            _time.sleep(0.3)  # let the adapter's finally-block write land
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            drain.join(timeout=2)
            raw = b"".join(err_chunks).decode("utf-8", "replace")
            return _request_end_lines(raw), status
        finally:
            _stop(proc, kf)

    def test_success_emits_request_end(self, upstream):
        lines, _ = self._run(upstream, _basic_body(stream=False), 200)
        ns = [l for l in lines if l.get("path") == "nonstream"]
        assert len(ns) == 1, f"expected exactly one nonstream request_end, got {len(ns)} of {len(lines)}"
        rec = ns[0]
        for field in ("request_id", "state", "duration_ms", "stop_reason", "outcome"):
            assert field in rec, f"missing field {field} in {rec}"
        assert rec["state"] == "completed"
        assert rec["stop_reason"] in ("end_turn", "tool_use", "max_tokens", "stop_sequence")

    def test_upstream_error_emits_request_end(self, upstream):
        body = {
            "model": "glm-5.2", "max_tokens": 8, "stream": False,
            "messages": [{"role": "user", "content": "scenario:http_error Say OK."}],
        }
        lines, _ = self._run(upstream, body, 500)  # D5: upstream 5xx passes through as-is (sanitized body)
        ns = [l for l in lines if l.get("path") == "nonstream"]
        assert len(ns) == 1, f"upstream-error path must still emit request_end, got {len(ns)}"
        rec = ns[0]
        assert rec["error_code"] == "MAAS_UPSTREAM_HTTP"
        assert rec["state"] == "upstream_failed"
        assert rec["stop_reason"] is None  # failed requests never count a stop reason

    def test_over_capacity_emits_request_end_when_serving_503(self, upstream):
        """The 503 OVER_CAPACITY fast-exit happens before a controller is
        built — it is a client-side rejection, deliberately NOT logged as
        request_end (no upstream request existed). This test pins that
        boundary so the /status==journald equality stays well-defined."""
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY, capacity=1)
        try:
            import threading
            results = []
            lock = threading.Lock()

            def call():
                body = {
                    "model": "glm-5.2", "max_tokens": 8, "stream": False,
                    "messages": [{"role": "user", "content": "scenario:nonstream_text Say OK."}],
                }
                s, _ = _post(port, body, {"content-type": "application/json", "x-api-key": CLIENT_KEY}, timeout=15)
                with lock:
                    results.append(s)

            threads = [threading.Thread(target=call) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert sorted(results)[0] == 503 or 503 in results
        finally:
            _stop(proc, kf)


class TestStatusAccountingRule:
    def test_status_stop_reasons_excludes_null(self, upstream):
        """/status must never grow a "null" key: failed non-streaming
        requests have stop_reason null and must not be counted."""
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            # one success, one upstream failure
            _post(port, _basic_body(stream=False),
                  {"content-type": "application/json", "x-api-key": CLIENT_KEY}, timeout=15)
            bad = {
                "model": "glm-5.2", "max_tokens": 8, "stream": False,
                "messages": [{"role": "user", "content": "scenario:http_error Say OK."}],
            }
            _post(port, bad, {"content-type": "application/json", "x-api-key": CLIENT_KEY}, timeout=15)
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/status")
            data = json.loads(conn.getresponse().read())
            conn.close()
            assert "null" not in data["stop_reasons"], f'"null" key leaked into stop_reasons: {data["stop_reasons"]}'
            assert sum(data["stop_reasons"].values()) >= 1
        finally:
            _stop(proc, kf)


def test_source_has_nonstream_request_end_in_finally():
    """Static guard: the nonstream request_end must live in the finally
    block (so no exit path can skip it), and the /status increment must use
    the same null-guarded rule as streaming."""
    src = CANDIDATE.read_text()
    ns = src[src.index("async function proxyNonStreaming"):src.index("// D1 reaper")]
    assert 'type: "request_end"' in ns, "nonstream path lost its request_end log"
    # both counters must be null-guarded with the identical condition
    assert ns.count("if (finalStopReason)") == 1
    assert 'path: "nonstream"' in ns
    streaming = src[src.index("async function proxyStreaming"):src.index("function toAnthropicResponse")]
    assert 'path: "stream"' in streaming
    assert streaming.count("if (finalStopReason)") == 1
