"""PRD RELEASE_V13 acceptance tests (S3-a / S3a-G2 / S3b-G / S4-G).

Drives the real adapter against a purpose-built fake upstream (not the
shared fixture) that can: emit malformed tool args on the streaming path,
answer tool-arg retries from a per-invocation plan (malformed | valid |
hang), and capture retry request bodies. No real upstream quota is touched
and no production failure is induced.

  S3a-G   first retry malformed, second valid → client gets a real
          tool_use; retry.attempted +2, succeeded +1.
  S3a-G2  retry hangs past the total watchdog → active_requests returns to
          0, reaped_slots unchanged, adapter process survives (no
          write-after-end crash).
  S3b-G   the retry nudge contains the escaping requirement and contains NO
          fragment of the malformed arguments.
  S4-G    request_end.repair carries tool_name for malformed-args requests.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "adapter" / "server.js"

CLIENT_KEY = "v13-client-key-0123456789abcdef"
TOOL_NAME = "get_weather"

# Matches the 13/13 observed failure shape: balanced braces, odd quote count,
# zero backslashes — inner double quotes left unescaped.
MALFORMED_ARGS = '{"command": "echo "unescaped""}'

UPSTREAM_JS = r"""
const http = require("node:http");
const fs = require("node:fs");
let n = 0;
const server = http.createServer(async (req, res) => {
  let body = "";
  for await (const c of req) body += c;
  let parsed = {};
  try { parsed = JSON.parse(body); } catch {}
  const isRetry = parsed.stream === false && parsed.tool_choice;
  if (isRetry) {
    n += 1;
    const cap = process.env.CAPTURE_FILE;
    if (cap) fs.appendFileSync(cap, body + "\n");
    const plan = JSON.parse(process.env.RETRY_PLAN || "[]");
    const step = plan[Math.min(n - 1, plan.length - 1)] || "valid";
    if (step === "hang") {
      setTimeout(() => { try { res.end(); } catch {} }, Number(process.env.HANG_MS || "15000"));
      return;
    }
    const args = step === "malformed"
      ? process.env.MALFORMED_ARGS
      : '{"city": "Beijing"}';
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      id: "retry-" + n, model: "glm-5.2",
      choices: [{ index: 0, message: { role: "assistant", content: null,
        tool_calls: [{ id: "call_r" + n, function: { name: "get_weather", arguments: args } }] },
        finish_reason: "tool_calls" }],
      usage: { prompt_tokens: 5, completion_tokens: 5 },
    }));
    return;
  }
  // Streaming path: one malformed tool call, clean tool_calls finish.
  res.writeHead(200, { "content-type": "text/event-stream" });
  const chunk = (o) => res.write("data: " + JSON.stringify(o) + "\n\n");
  chunk({ id: "c", model: "glm-5.2", choices: [{ index: 0, delta: { tool_calls: [
    { index: 0, id: "call_1", function: { name: "get_weather", arguments: process.env.MALFORMED_ARGS } } ] }, finish_reason: null }] });
  chunk({ choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }], usage: { prompt_tokens: 5, completion_tokens: 5 } });
  res.end("data: [DONE]\n\n");
});
server.listen(Number(process.env.PORT), "127.0.0.1", () => {
  console.log(JSON.stringify({ ready: true, port: Number(process.env.PORT) }));
});
"""


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("not ready")


class _Stack:
    """fake upstream + adapter under test, with stderr drain."""

    def __init__(self, tmp_path, *, retry_plan, extra_adapter_env=None,
                 hang_ms=15000, capture=False):
        self.tmp = tmp_path
        up_port = _free_port()
        up_js = tmp_path / "up.js"
        up_js.write_text(UPSTREAM_JS)
        up_env = dict(os.environ)
        up_env.update({
            "PORT": str(up_port),
            "MALFORMED_ARGS": MALFORMED_ARGS,
            "RETRY_PLAN": json.dumps(retry_plan),
            "HANG_MS": str(hang_ms),
        })
        self.capture_file = tmp_path / "retry_bodies.jsonl"
        if capture:
            up_env["CAPTURE_FILE"] = str(self.capture_file)
        self.up = subprocess.Popen(["node", str(up_js)], env=up_env,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        line = self.up.stdout.readline()
        assert json.loads(line)["ready"]
        self.up_port = up_port

        ad_port = _free_port()
        import tempfile
        fd, keyfile = tempfile.mkstemp(suffix=".key")
        with os.fdopen(fd, "w") as fh:
            fh.write(CLIENT_KEY + "\n")
        self.keyfile = Path(keyfile)
        ad_env = dict(os.environ)
        ad_env.update({
            "PROXY_PORT": str(ad_port),
            "PROXY_HOST": "127.0.0.1",
            "ANTHROPIC_PROXY_BASE_URL": f"http://127.0.0.1:{up_port}/v1/chat/completions",
            "CLAUDE_CODE_PROXY_API_KEY": "test-key",
            "MAAS_CLIENT_KEY_FILE": str(self.keyfile),
            "MAAS_TOOL_ARG_MODE": "enforce",
            "MAAS_CONNECT_TIMEOUT": "3",
            "MAAS_IDLE_TIMEOUT": "20",
            "MAAS_TOTAL_TIMEOUT": "60",
        })
        if extra_adapter_env:
            ad_env.update(extra_adapter_env)
        self.port = ad_port
        self.proc = subprocess.Popen(["node", str(CANDIDATE)], env=ad_env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.err_chunks: list[bytes] = []
        self._drain = threading.Thread(target=self._read_err, daemon=True)
        self._drain.start()
        _wait_ready(ad_port)

    def _read_err(self):
        try:
            for chunk in iter(lambda: self.proc.stderr.read1(4096), b""):
                self.err_chunks.append(chunk)
        except Exception:
            pass

    def request_end_lines(self) -> list[dict]:
        raw = b"".join(self.err_chunks).decode("utf-8", "replace")
        out = []
        for line in raw.splitlines():
            i = line.find("{")
            if i < 0:
                continue
            try:
                obj = json.loads(line[i:])
            except Exception:
                continue
            if obj.get("type") == "request_end":
                out.append(obj)
        return out

    def status(self) -> dict:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/status")
        data = json.loads(conn.getresponse().read())
        conn.close()
        return data

    def post_stream(self) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=90)
        body = json.dumps({
            "model": "glm-5.2", "max_tokens": 64, "stream": True,
            "tools": [{"name": TOOL_NAME, "description": "w",
                       "input_schema": {"type": "object",
                                        "properties": {"command": {"type": "string"}}}}],
            "messages": [{"role": "user", "content": "weather?"}],
        })
        conn.request("POST", "/v1/messages", body,
                     {"content-type": "application/json", "x-api-key": CLIENT_KEY})
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", "replace")
        conn.close()
        return resp.status, data

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.up.terminate()
        try:
            self.up.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.up.kill()
        self._drain.join(timeout=2)
        if self.keyfile.exists():
            self.keyfile.unlink()


# ---------------------------------------------------------------------------
# S3a-G: second retry succeeds
# ---------------------------------------------------------------------------


def test_s3a_g_second_retry_succeeds(tmp_path):
    stack = _Stack(tmp_path, retry_plan=["malformed", "valid"])
    try:
        status, body = stack.post_stream()
        time.sleep(0.5)
        st = stack.status()
        assert st["tool_args_retry"]["attempted"] == 2, st["tool_args_retry"]
        assert st["tool_args_retry"]["succeeded"] == 1, st["tool_args_retry"]
        # Client received a REAL tool_use with the valid args.
        assert '"type":"tool_use"' in body or '"type": "tool_use"' in body, body[:400]
        # The args arrive inside an SSE JSON frame, so quotes are escaped —
        # assert on the value, not on a raw-JSON literal.
        assert "Beijing" in body, body[:600]
        assert "degraded" not in body.lower() or "tool_use" in body
        recs = stack.request_end_lines()
        assert recs, "no request_end"
        repair = recs[-1].get("repair") or {}
        assert repair.get("retry") == "succeeded"
        assert repair.get("retry_attempts") == 2
    finally:
        stack.stop()


def test_s3a_g_disabled_budget_caps_at_one(tmp_path):
    """Reverse case: MAAS_TOOL_ARG_RETRIES=1 (the pre-V13 behavior) must
    stop after ONE retry — attempted == 1, degradation path taken."""
    stack = _Stack(tmp_path, retry_plan=["malformed", "valid"],
                   extra_adapter_env={"MAAS_TOOL_ARG_RETRIES": "1"})
    try:
        status, body = stack.post_stream()
        time.sleep(0.5)
        st = stack.status()
        assert st["tool_args_retry"]["attempted"] == 1, st["tool_args_retry"]
        # No tool_use with the valid payload reached the client.
        assert "Beijing" not in body
    finally:
        stack.stop()


# ---------------------------------------------------------------------------
# S3a-G2: watchdog fires while a retry is in flight
# ---------------------------------------------------------------------------


def test_s3a_g2_watchdog_during_retry_releases_slot(tmp_path):
    """Total watchdog (2s) fires mid-retry-hang (retry abort at 6s):
    active_requests must return to 0, reaped_slots must NOT grow, and the
    adapter process must survive the post-timeout emissions."""
    stack = _Stack(tmp_path, retry_plan=["hang", "hang"], hang_ms=8000,
                   extra_adapter_env={
                       "MAAS_CONNECT_TIMEOUT": "1",
                       "MAAS_TOTAL_TIMEOUT": "2",
                       "MAAS_TOOL_ARG_RETRY_TIMEOUT_MS": "6000",
                   })
    try:
        before_reaped = stack.status().get("reaped_slots", 0)
        status, body = stack.post_stream()  # blocks ~7s (2+ abort path)
        time.sleep(1.0)
        st = stack.status()
        assert st["active_requests"] == 0, f"slot leaked: {st['active_requests']}"
        assert st.get("reaped_slots", 0) == before_reaped, "reaper fired — cleanup path failed"
        assert stack.proc.poll() is None, "adapter crashed during watchdog/retry overlap"
        # The retry is still hanging at this point (aborts at 6s); the
        # request_end only lands when the post-retry cleanup finishes.
        recs = []
        deadline = time.time() + 15
        while time.time() < deadline:
            recs = stack.request_end_lines()
            if recs:
                break
            time.sleep(0.5)
        assert recs, "no request_end on the watchdog path"
        assert recs[-1]["state"] in ("total_timeout", "upstream_failed")
        assert recs[-1]["stop_reason"] is None
    finally:
        stack.stop()


# ---------------------------------------------------------------------------
# S3b-G: nudge targets the observed shape, never leaks args
# ---------------------------------------------------------------------------


def test_s3b_g_nudge_has_escape_rule_and_no_args_fragment(tmp_path):
    stack = _Stack(tmp_path, retry_plan=["valid"], capture=True)
    try:
        stack.post_stream()
        time.sleep(0.3)
        assert stack.capture_file.exists(), "retry body not captured"
        bodies = [json.loads(l) for l in stack.capture_file.read_text().splitlines() if l.strip()]
        assert bodies, "no retry bodies"
        text = json.dumps(bodies[0])
        # The escaping requirement is present (S3-b).
        assert "escaped with a backslash" in text, "nudge lacks the escaping rule"
        # And NO fragment of the malformed args is echoed back (the nudge
        # must teach the rule, not replay the broken payload).
        assert "unescaped" not in text, "malformed args fragment leaked into the nudge"
    finally:
        stack.stop()


# ---------------------------------------------------------------------------
# S4-G: repair carries tool_name
# ---------------------------------------------------------------------------


def test_s4_g_repair_has_tool_name(tmp_path):
    stack = _Stack(tmp_path, retry_plan=["valid"])
    try:
        stack.post_stream()
        time.sleep(0.3)
        recs = stack.request_end_lines()
        assert recs, "no request_end"
        repair = recs[-1].get("repair")
        assert repair is not None, "no repair block on a malformed-args request"
        assert repair.get("tool_name") == TOOL_NAME, repair
        # The name comes from the client's schema, not model output.
        assert isinstance(repair.get("tool_name"), str)
    finally:
        stack.stop()


def test_s4_g_static_tool_name_present():
    src = CANDIDATE.read_text()
    assert "tool_name" in src, "S4 (R3) regressed: repair lost tool_name"
