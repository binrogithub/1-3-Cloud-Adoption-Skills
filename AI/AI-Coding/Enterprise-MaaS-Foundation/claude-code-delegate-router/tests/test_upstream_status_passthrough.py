"""G7 tests (PRD UPSTREAM_PROFILE_V1 D5): upstream 4xx statuses pass through.

Field finding: Zhipu rate-limit responses (HTTP 429) reached the client as
502, so Claude Code could not distinguish "back off and retry" from "upstream
down". Root cause (narrower than the PRD's catch-path hypothesis): the
!upstream.ok branch called ctrl._fail BEFORE sending the response — _fail
fires the onTimeout callback, which sent the mapped 502 template first; the
subsequent sendJson(upstream.status, ...) was a no-op (headersSent).

Fix: send the pass-through response first, then _fail. Verified here for
both paths (streaming and non-streaming) via the fake upstream's
rate_limited scenario (429 + Retry-After) and http_error (500).

  G7: upstream 429 -> client receives 429 (not 502) on both paths.
      Reverse case: the pre-fix ordering produced 502 (reproduced during
      implementation — see PRD §2 D5).
"""
from __future__ import annotations

import http.client
import json
import subprocess
from pathlib import Path

import pytest

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_security_hardening import (  # noqa: E402
    CLIENT_KEY, _start_fake_upstream, _start_adapter, _stop,
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


def _post(port: int, scenario: str, stream: bool) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    body = json.dumps({
        "model": "glm-5.2", "max_tokens": 8, "stream": stream,
        "messages": [{"role": "user", "content": f"scenario:{scenario} Say OK."}],
    })
    conn.request("POST", "/v1/messages", body,
                 {"content-type": "application/json", "x-api-key": CLIENT_KEY})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


class TestG7UpstreamStatusPassthrough:
    def test_nonstream_429_passthrough(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            status, body = _post(port, "rate_limited", stream=False)
            assert status == 429, (
                f"upstream 429 must pass through, got {status}: {body[:150]}"
            )
            obj = json.loads(body)
            assert obj["error"]["type"] == "api_error"  # sanitized, not raw
        finally:
            _stop(proc, kf)

    def test_stream_429_passthrough(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            status, body = _post(port, "rate_limited", stream=True)
            assert status == 429, (
                f"upstream 429 must pass through, got {status}: {body[:150]}"
            )
        finally:
            _stop(proc, kf)

    def test_nonstream_5xx_stays_5xx(self, upstream):
        proc, port, kf = _start_adapter(upstream, client_key=CLIENT_KEY)
        try:
            status, _ = _post(port, "http_error", stream=False)
            assert 500 <= status < 600, f"5xx must remain 5xx, got {status}"
            assert status != 429
        finally:
            _stop(proc, kf)

    def test_source_ordering_guard(self):
        """Static guard: in both !upstream.ok branches, sendJson must appear
        BEFORE ctrl._fail — the pre-fix ordering is the regression."""
        src = (ROOT / "adapter" / "server.js").read_text()
        for fn in ("proxyNonStreaming", "proxyStreaming"):
            start = src.index(f"async function {fn}")
            end = src.index("\n}", start) + 2
            # find the !upstream.ok block within the function
            block_start = src.index("!upstream.ok", start)
            block = src[block_start:block_start + 700]
            send_pos = block.index("sendJson(res, status")
            fail_pos = block.index("ctrl._fail(ErrorCodes.UPSTREAM_HTTP")
            assert send_pos < fail_pos, (
                f"{fn}: sendJson(upstream.status) must precede ctrl._fail — "
                "otherwise _fail's callback writes the mapped 502 first"
            )
