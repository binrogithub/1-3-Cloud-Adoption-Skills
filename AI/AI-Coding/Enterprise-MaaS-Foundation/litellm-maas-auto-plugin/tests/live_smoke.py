#!/usr/bin/env python3
"""Live probes for Claude Code -> LiteLLM -> Huawei MaaS GLM-5.1.

Usage:
    LITELLM_KEY=sk-... python3 tests/live_smoke.py all
    python3 tests/live_smoke.py message
    python3 tests/live_smoke.py stream
    python3 tests/live_smoke.py tools

The key is resolved from LITELLM_KEY, ANTHROPIC_API_KEY, or KEY_FILE.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
MODEL = os.environ.get("CLAUDE_CODE_MODEL", "claude-opus-4-6")
KEY_FILE = os.environ.get(
    "KEY_FILE",
    "/root/LiteLLM-Huawei-MaaS-Proxy/.claude-code-key.json",
)


def load_key():
    key = os.environ.get("LITELLM_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        with open(KEY_FILE, encoding="utf-8") as handle:
            value = json.load(handle).get("key")
            if value:
                return value
    except (OSError, ValueError, AttributeError):
        pass
    raise SystemExit(
        "No virtual key found. Set LITELLM_KEY or KEY_FILE; "
        "do not use the MaaS or LiteLLM master key."
    )


KEY = load_key()


def post(body, timeout=120):
    request = urllib.request.Request(
        BASE_URL + "/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8"), time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), time.time() - started
    except Exception as exc:
        return -1, "{}: {}".format(type(exc).__name__, exc), time.time() - started


def show(name, status, elapsed, detail):
    print("{}: {} (HTTP {}, {:.1f}s)".format(
        name,
        "PASS" if status == 200 else "FAIL",
        status,
        elapsed,
    ))
    if detail:
        print("  " + detail)
    return status == 200


def probe_message():
    status, raw, elapsed = post({
        "model": MODEL,
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Reply with MESSAGE_OK only."}],
    })
    try:
        payload = json.loads(raw)
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        valid = status == 200 and payload.get("type") == "message" and bool(text)
        detail = "type={}, text={!r}".format(payload.get("type"), text[:80])
    except (ValueError, AttributeError):
        valid = False
        detail = raw[:200]
    show("message", 200 if valid else status, elapsed, detail)
    return valid


def probe_stream():
    status, raw, elapsed = post({
        "model": MODEL,
        "max_tokens": 64,
        "stream": True,
        "thinking": {"type": "enabled", "budget_tokens": 1024},
        "messages": [{"role": "user", "content": "Reply with STREAM_OK only."}],
    })
    event_types = re.findall(r'"type"\s*:\s*"([^"]+)"', raw)
    valid = (
        status == 200
        and "message_start" in event_types
        and "message_stop" in event_types
        and event_types.index("message_start") < event_types.index("message_stop")
    )
    detail = "events={}, terminal={}".format(
        len(event_types),
        "message_stop" in event_types,
    )
    show("stream", 200 if valid else status, elapsed, detail)
    return valid


def probe_tools():
    status, raw, elapsed = post({
        "model": MODEL,
        "max_tokens": 300,
        "tools": [{
            "name": "echo_check",
            "description": "Echo a short string to verify structured tool calling.",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }],
        "messages": [{
            "role": "user",
            "content": (
                "Call the echo_check tool with text set to ok. "
                "Do not answer in plain text."
            ),
        }],
    })
    has_tool = bool(re.search(r'"type"\s*:\s*"tool_use"', raw))
    raw_markup = bool(re.search(r"<tool_call|<arg_key>|</[A-Za-z_]+_tool>", raw))
    valid = status == 200 and has_tool and not raw_markup
    if has_tool:
        detail = "structured tool_use received"
    elif raw_markup:
        detail = "raw tool markup received; provider function calling is unavailable"
    else:
        detail = "no tool_use block; response={!r}".format(raw[:160])
    show("tools", 200 if valid else status, elapsed, detail)
    return valid


PROBES = {
    "message": probe_message,
    "stream": probe_stream,
    "tools": probe_tools,
}


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    if requested == "all":
        names = ["message", "stream", "tools"]
    elif requested in PROBES:
        names = [requested]
    else:
        raise SystemExit("Usage: {} [all|message|stream|tools]".format(sys.argv[0]))

    results = [PROBES[name]() for name in names]
    print("summary: {}/{} passed".format(sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
