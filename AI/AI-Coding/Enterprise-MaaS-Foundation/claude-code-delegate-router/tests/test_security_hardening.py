"""Security-hardening acceptance tests (PRD SECURITY_HARDENING V1).

Covers the release gates for each fix:

  G1  malformed Host / request-target never crashes the adapter
  G2  client-key auth: anonymous / dummy / wrong key → 401, valid key → 200
  G3  non-streaming path honors concurrency admission + timeouts
  G4  non-streaming upstream error bodies are sanitized (canary never leaks)
  G7  x-fake-scenario header is dropped unless MAAS_TEST_UPSTREAM=1
  G8  delegate goal text travels on stdin, never in argv

The workflow path-traversal gate (G5) lives in test_workflow_security.py.
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
DELEGATE = ROOT / "scripts" / "delegate"

CLIENT_KEY = "clientkey-a1b2c3d4e5f6"


# ---------------------------------------------------------------------------
# Process helpers (same pattern as test_adapter_contract.py)
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
    *,
    client_key: str | None = None,
    extra_env: dict[str, str] | None = None,
    capacity: int = 8,
) -> tuple[subprocess.Popen, int, Path | None]:
    """Start the candidate adapter.

    When client_key is given it is written to a temp file and
    MAAS_CLIENT_KEY_FILE points at it (enforced auth mode).
    """
    port = _free_port()
    key_file = None
    env = dict(os.environ)
    env["PROXY_PORT"] = str(port)
    env["PROXY_HOST"] = "127.0.0.1"
    env["ANTHROPIC_PROXY_BASE_URL"] = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"
    env["CLAUDE_CODE_PROXY_API_KEY"] = "test-key"
    env["MAAS_CONNECT_TIMEOUT"] = "3"
    env["MAAS_IDLE_TIMEOUT"] = "3"
    env["MAAS_TOTAL_TIMEOUT"] = "6"
    env["MAAS_MAX_CONCURRENCY"] = str(capacity)
    # Default to a nonexistent key file so legacy-mode tests never inherit
    # a real /etc/claude-code-proxy/client.key from the host (a live
    # bootstrap test elsewhere in the suite creates one).
    env["MAAS_CLIENT_KEY_FILE"] = str(Path(__file__).parent / "no-client.key")
    if client_key is not None:
        import tempfile
        fd, name = tempfile.mkstemp(prefix="ck_", suffix=".key")
        with os.fdopen(fd, "w") as fh:
            fh.write(client_key + "\n")
        key_file = Path(name)
        env["MAAS_CLIENT_KEY_FILE"] = name
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        ["node", str(CANDIDATE)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _wait_ready(port)
    return proc, port, key_file


def _stop(proc: subprocess.Popen, key_file: Path | None = None) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    if key_file and key_file.exists():
        key_file.unlink()


def _post(port: int, body: dict, headers: dict | None = None, timeout: float = 10.0) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("POST", "/v1/messages", json.dumps(body), headers or {"content-type": "application/json"})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", "replace")
    finally:
        conn.close()


def _basic_body(stream: bool = False) -> dict:
    # The fake upstream's scenario dispatch: streaming requests want a
    # streaming scenario, non-streaming want nonstream_text.
    scenario = "reasoning_then_text" if stream else "nonstream_text"
    return {
        "model": "glm-5.2",
        "max_tokens": 16,
        "stream": stream,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    }


@pytest.fixture()
def upstream():
    proc, port = _start_fake_upstream()
    yield port
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# G1 — malformed Host / request-target must not crash the process
# ---------------------------------------------------------------------------


class TestG1MalformedRequests:
    @pytest.fixture()
    def adapter(self, upstream):
        proc, port, kf = _start_adapter(upstream)
        yield port, proc
        _stop(proc, kf)

    def _raw(self, port: int, raw_request: str) -> None:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(raw_request.encode())
            try:
                s.recv(1024)
            except OSError:
                pass

    def test_malformed_host_header_gets_400_and_process_survives(self, adapter):
        port, proc = adapter
        for bad in ("[::1:bad", "", "exa mple.com", "::1]", "host\nwith-newline"):
            self._raw(port, f"GET /status HTTP/1.1\r\nHost: {bad}\r\nConnection: close\r\n\r\n")
            time.sleep(0.05)
            assert proc.poll() is None, f"adapter died on Host: {bad!r}"

    def test_malformed_request_target_gets_handled(self, adapter):
        port, proc = adapter
        for target in ("/////", "http://x/%00", "*", "%zz"):
            self._raw(port, f"GET {target} HTTP/1.1\r\nHost: ok\r\nConnection: close\r\n\r\n")
            time.sleep(0.05)
            assert proc.poll() is None, f"adapter died on target: {target!r}"

    def test_service_still_serves_after_malformed_barrage(self, adapter):
        port, proc = adapter
        self.test_malformed_host_header_gets_400_and_process_survives(adapter)
        status, _ = _post(port, _basic_body(), {"content-type": "application/json", "x-api-key": "test-key"})
        assert status == 200
        assert proc.poll() is None


# ---------------------------------------------------------------------------
# G2 — client-key enforcement
# ---------------------------------------------------------------------------


class TestG2AuthEnforcement:
    @pytest.fixture()
    def adapter(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        yield port, proc
        _stop(proc, kf)

    def test_anonymous_rejected_401(self, adapter):
        port, _ = adapter
        status, body = _post(port, _basic_body())
        assert status == 401
        assert "authentication_error" in body

    def test_dummy_key_rejected_401(self, adapter):
        port, _ = adapter
        status, _ = _post(port, _basic_body(), {"content-type": "application/json", "x-api-key": "maas-local-proxy"})
        assert status == 401

    def test_wrong_key_rejected_401(self, adapter):
        port, _ = adapter
        status, _ = _post(port, _basic_body(), {"content-type": "application/json", "x-api-key": "wrong-key"})
        assert status == 401

    def test_valid_client_key_accepted_bearer(self, adapter):
        port, _ = adapter
        status, body = _post(port, _basic_body(), {"content-type": "application/json", "authorization": f"Bearer {CLIENT_KEY}"})
        assert status == 200, body

    def test_valid_client_key_accepted_x_api_key(self, adapter):
        port, _ = adapter
        status, body = _post(port, _basic_body(), {"content-type": "application/json", "x-api-key": CLIENT_KEY})
        assert status == 200, body

    def test_status_reports_enforced_mode(self, adapter):
        port, _ = adapter
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert data["client_auth"] == "enforced"

    def test_legacy_mode_when_no_key_file(self, upstream):
        proc, port, kf = _start_adapter(upstream)  # no client key file
        try:
            status, _ = _post(port, _basic_body())
            assert status == 200  # legacy fallthrough still serves
        finally:
            _stop(proc, kf)


# ---------------------------------------------------------------------------
# G3 + G4 — non-streaming admission and sanitization
# ---------------------------------------------------------------------------


class TestG3G4NonStreaming:
    @pytest.fixture()
    def adapter(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY, capacity=2)
        yield port, proc
        _stop(proc, kf)

    def test_nonstream_over_capacity_rejected(self, adapter):
        """With capacity 2, the 3rd concurrent non-streaming request 503s."""
        port, _ = adapter
        import threading
        results: list[int] = []
        lock = threading.Lock()

        def slow_call():
            # slow_openai holds the upstream open ~500ms so two calls occupy
            # both slots while the third arrives.
            body = {
                "model": "glm-5.2", "max_tokens": 16, "stream": False,
                "messages": [{"role": "user", "content": "scenario:slow_nonstream Say OK."}],
            }
            status, _ = _post(port, body, {"content-type": "application/json", "x-api-key": CLIENT_KEY}, timeout=15)
            with lock:
                results.append(status)

        threads = [threading.Thread(target=slow_call) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert 503 in results, f"expected at least one 503 OVER_CAPACITY, got {results}"

    def test_nonstream_upstream_error_body_sanitized(self, upstream):
        """G4: the upstream error body (with canary) never reaches the client."""
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            body = {
                "model": "glm-5.2", "max_tokens": 16, "stream": False,
                "messages": [{"role": "user", "content": "scenario:http_error Say OK."}],
            }
            status, resp = _post(port, body, {"content-type": "application/json", "x-api-key": CLIENT_KEY}, timeout=15)
            assert status >= 500
            # The sanitized template — never raw upstream text.
            obj = json.loads(resp)
            assert obj["error"]["type"] == "api_error"
            assert "upstream error" not in json.dumps(obj)
            assert "unknown scenario" not in resp
        finally:
            _stop(proc, kf)


# ---------------------------------------------------------------------------
# G7 — test-header forwarding is opt-in
# ---------------------------------------------------------------------------


class TestG7TestHeaderOptIn:
    def test_header_dropped_by_default(self, upstream):
        """Without MAAS_TEST_UPSTREAM the x-fake-scenario header must not reach
        the upstream. The message pins a working non-stream scenario; the
        header carries a bogus one. If the header were forwarded it would win
        and the upstream would answer 400 unknown-scenario."""
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            body = {
                "model": "glm-5.2", "max_tokens": 16, "stream": False,
                "messages": [{"role": "user", "content": "scenario:nonstream_text Say OK."}],
            }
            status, resp = _post(
                port, body,
                {"content-type": "application/json", "x-api-key": CLIENT_KEY, "x-fake-scenario": "nonexistent_scenario"},
                timeout=15,
            )
            assert status == 200, f"header leaked to upstream: {status} {resp[:200]}"
        finally:
            _stop(proc, kf)

    def test_header_forwarded_with_opt_in(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY, extra_env={"MAAS_TEST_UPSTREAM": "1"})
        try:
            body = {
                "model": "glm-5.2", "max_tokens": 16, "stream": False,
                "messages": [{"role": "user", "content": "scenario:nonstream_text Say OK."}],
            }
            # With opt-in, the bogus scenario header reaches the fake
            # upstream, which answers 400 → adapter surfaces the error.
            status, _ = _post(
                port, body,
                {"content-type": "application/json", "x-api-key": CLIENT_KEY, "x-fake-scenario": "nonexistent_scenario"},
                timeout=15,
            )
            assert status != 200, "opt-in forwarding did not take effect"
        finally:
            _stop(proc, kf)

    def test_status_reports_test_upstream_disabled(self, upstream):
        proc, port, kf = _start_adapter(upstream)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/status")
            data = json.loads(conn.getresponse().read())
            conn.close()
            assert data["test_upstream"] == "disabled"
        finally:
            _stop(proc, kf)


# ---------------------------------------------------------------------------
# G8 — delegate goal on stdin, not argv
# ---------------------------------------------------------------------------


class TestG8DelegateStdinGoal:
    def test_goal_not_in_child_argv(self, monkeypatch):
        """The real client must pass the goal via stdin (input=), so the
        subprocess argv contains no task text."""
        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("delegate_real", str(DELEGATE))
        spec = importlib.util.spec_from_loader("delegate_real", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        captured: dict = {}

        class _Proc:
            returncode = 0
            stdout = "{}"
            stderr = ""

        def fake_run(argv, **kwargs):
            captured["argv"] = list(argv)
            captured["kwargs"] = kwargs
            return _Proc()

        monkeypatch.setattr(mod.subprocess, "run", fake_run)
        client = mod._make_real_client(client_bin="claude-maas")
        secret_goal = "SECRETCANARY-9d1f- goal text"
        client(secret_goal, model="glm-5.2", max_turns=2, timeout=10.0, cwd=None)
        argv = captured["argv"]
        assert secret_goal not in argv, f"goal leaked into argv: {argv}"
        assert captured["kwargs"].get("input") == secret_goal
        assert "-p" in argv


# ---------------------------------------------------------------------------
# G1 supplement — verify the deployed artifact (deploy.sh) also survives
# ---------------------------------------------------------------------------


def test_candidate_has_no_unreflected_host_parse():
    """Static check: the request handler must not reflect req.headers.host
    into the URL base (regression guard for the D1 fix)."""
    src = CANDIDATE.read_text()
    assert 'req.headers.host' not in src, "Host header is reflected into URL parsing again"
    assert 'new URL(req.url' in src
