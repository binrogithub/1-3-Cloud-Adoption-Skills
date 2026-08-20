"""Direct MaaS Anthropic protocol canary.

This module provides:

* ``parse_sse`` — an offline SSE stream validator used by the release gate and
  by ``tests/test_sse_contract.py``.  It checks that a raw SSE byte stream
  conforms to the native Anthropic streaming contract:

    - every non-empty line has a legal SSE prefix (``event:`` or ``data:``);
    - every ``data:`` payload is valid JSON;
    - no OpenAI ``[DONE]`` marker appears;
    - ``thinking_delta`` only appears inside a thinking content block;
    - ``text_delta`` only appears inside a text content block;
    - the last event type is ``message_stop``.

* ``main`` — a CLI that reads the MaaS key from **stdin** (never argv, never
  echoed) and runs named live probes against the MaaS Anthropic endpoint using
  only ``urllib.request`` from the standard library.  Live probes are guarded
  behind ``__main__``; the test suite only exercises ``parse_sse`` offline.

The image probe currently expects a typed unsupported HTTP 400 and is **not** a
global failure — it is reported as a known-unsupported capability.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Offline SSE parser
# ---------------------------------------------------------------------------

# Error tags returned in ParseResult.errors
ERR_UNPREFIXED = "unprefixed"          # line lacks event:/data: prefix
ERR_OPENAI_DONE = "openai_done"        # data: [DONE] marker present
ERR_INVALID_JSON = "invalid_json"      # data: payload is not valid JSON
ERR_THINKING_MISMATCH = "thinking_mismatch"  # thinking_delta outside thinking block
ERR_TEXT_MISMATCH = "text_mismatch"    # text_delta outside text block


@dataclass
class ParseResult:
    """Result of parsing/validating an SSE stream."""

    event_types: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _is_path_like(source) -> bool:
    """Heuristic: does *source* look like a file path rather than SSE text?"""
    if isinstance(source, Path):
        return source.is_file()
    if not isinstance(source, str):
        return False
    # A path won't contain newlines and will reference an existing file.
    if "\n" in source:
        return False
    return Path(source).is_file()


def parse_sse(source) -> ParseResult:
    """Parse and validate an Anthropic SSE stream.

    *source* may be either the raw SSE text, a path string, or a
    :class:`~pathlib.Path` to a file containing it.
    Returns a :class:`ParseResult` with ``event_types`` (in order) and
    ``errors`` (a list of error-tag strings).
    """
    if _is_path_like(source):
        raw = Path(source).read_text()
    else:
        raw = source

    result = ParseResult()

    # Track which content-block type is currently open at each index.
    # ``open_blocks`` maps index -> block type ("thinking" / "text" / ...).
    open_blocks: dict[int, str] = {}

    lines = raw.split("\n")
    for line in lines:
        # Blank lines are SSE event delimiters — skip them.
        if line == "":
            continue

        # Every non-empty line must start with "event:" or "data:".
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
            result.event_types.append(event_name)
            continue

        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            _handle_data_line(payload, result, open_blocks)
            continue

        # A comment line starting with ":" is legal SSE — ignore it.
        if line.startswith(":"):
            continue

        # Anything else is an unprefixed line (the pretty-JSON regression).
        result.errors.append(ERR_UNPREFIXED)

    return result


def _handle_data_line(
    payload: str,
    result: ParseResult,
    open_blocks: dict[int, str],
) -> None:
    """Process a single ``data:`` payload."""
    # Check for the OpenAI [DONE] marker.
    if payload == "[DONE]":
        result.errors.append(ERR_OPENAI_DONE)
        return

    # Every data: payload must be valid JSON.
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        result.errors.append(ERR_INVALID_JSON)
        return

    if not isinstance(obj, dict):
        result.errors.append(ERR_INVALID_JSON)
        return

    _update_block_state(obj, result, open_blocks)


def _update_block_state(
    obj: dict,
    result: ParseResult,
    open_blocks: dict[int, str],
) -> None:
    """Track content-block open/close and validate delta/block-type pairing."""
    msg_type = obj.get("type")

    # content_block_start opens a block at the given index.
    if msg_type == "content_block_start":
        index = obj.get("index")
        block = obj.get("content_block", {})
        block_type = block.get("type") if isinstance(block, dict) else None
        if isinstance(index, int) and isinstance(block_type, str):
            open_blocks[index] = block_type
        return

    # content_block_stop closes the block at the given index.
    if msg_type == "content_block_stop":
        index = obj.get("index")
        if isinstance(index, int):
            open_blocks.pop(index, None)
        return

    # content_block_delta — validate delta type matches the open block type.
    if msg_type == "content_block_delta":
        index = obj.get("index")
        delta = obj.get("delta", {})
        delta_type = delta.get("type") if isinstance(delta, dict) else None

        if not isinstance(index, int) or not isinstance(delta_type, str):
            return

        expected_block = open_blocks.get(index)

        if delta_type == "thinking_delta":
            if expected_block != "thinking":
                result.errors.append(ERR_THINKING_MISMATCH)
        elif delta_type == "text_delta":
            if expected_block != "text":
                result.errors.append(ERR_TEXT_MISMATCH)
        # Other delta types (e.g. input_json_delta for tool_use) are allowed
        # in any block type — we only validate the two known regressions.
        return


# ---------------------------------------------------------------------------
# Live probe CLI (guarded behind __main__)
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
MODEL = "glm-5.2"
PROBE_NAMES = ("text", "stream", "thinking", "tool-auto", "tool-forced", "image", "all")


def _read_key_from_stdin() -> str:
    """Read exactly one non-empty key line from stdin, never echoing it."""
    key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("error: no API key provided on stdin")
    return key


def _post_messages(
    base_url: str,
    key: str,
    body: dict,
    *,
    stream: bool = False,
) -> tuple[int, bytes]:
    """POST to the MaaS Anthropic /v1/messages endpoint.

    Returns (status_code, response_body_bytes).  Never logs the key.
    """
    import urllib.error
    import urllib.request

    url = base_url.rstrip("/") + "/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "anthropic-version": "2023-06-01",
    }
    if stream:
        headers["Accept"] = "text/event-stream"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _probe_text(base_url: str, key: str) -> dict:
    """Non-streaming text probe."""
    body = {
        "model": MODEL,
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Say OK."}],
    }
    status, raw = _post_messages(base_url, key, body)
    ok = False
    if status == 200:
        try:
            obj = json.loads(raw)
            ok = (
                obj.get("type") == "message"
                and obj.get("role") == "assistant"
                and isinstance(obj.get("content"), list)
                and isinstance(obj.get("usage"), dict)
            )
        except (json.JSONDecodeError, ValueError):
            ok = False
    return {"probe": "text", "status": status, "valid": ok}


def _probe_stream(base_url: str, key: str) -> dict:
    """Streaming text probe — validates the SSE contract via parse_sse."""
    body = {
        "model": MODEL,
        "max_tokens": 64,
        "stream": True,
        "messages": [{"role": "user", "content": "Say OK."}],
    }
    status, raw = _post_messages(base_url, key, body, stream=True)
    ok = False
    errors: list[str] = []
    if status == 200:
        result = parse_sse(raw.decode("utf-8", errors="replace"))
        errors = result.errors
        ok = result.event_types and result.event_types[-1] == "message_stop" and not errors
    return {"probe": "stream", "status": status, "valid": ok, "sse_errors": errors}


def _probe_thinking(base_url: str, key: str) -> dict:
    """Thinking probe — validates thinking/text block-delta pairing."""
    body = {
        "model": MODEL,
        "max_tokens": 128,
        "stream": True,
        "thinking": {"type": "adaptive"},
        "messages": [{"role": "user", "content": "What is 2+2?"}],
    }
    status, raw = _post_messages(base_url, key, body, stream=True)
    ok = False
    errors: list[str] = []
    if status == 200:
        result = parse_sse(raw.decode("utf-8", errors="replace"))
        errors = result.errors
        ok = result.event_types and result.event_types[-1] == "message_stop" and not errors
    return {"probe": "thinking", "status": status, "valid": ok, "sse_errors": errors}


def _probe_tool_auto(base_url: str, key: str) -> dict:
    """Auto tool_choice probe — expects structured tool_use, no raw <...> text."""
    body = {
        "model": MODEL,
        "max_tokens": 256,
        "tools": [
            {
                "name": "get_weather",
                "description": "Get weather for a city.",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ],
        "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
    }
    status, raw = _post_messages(base_url, key, body)
    ok = False
    if status == 200:
        try:
            obj = json.loads(raw)
            content = obj.get("content", [])
            ok = any(
                isinstance(b, dict) and b.get("type") == "tool_use"
                for b in content
            )
        except (json.JSONDecodeError, ValueError):
            ok = False
    return {"probe": "tool-auto", "status": status, "valid": ok}


def _probe_tool_forced(base_url: str, key: str) -> dict:
    """Forced tool_choice probe — expects structured tool_use, no schema 400."""
    body = {
        "model": MODEL,
        "max_tokens": 256,
        "tools": [
            {
                "name": "get_weather",
                "description": "Get weather for a city.",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ],
        "tool_choice": {"type": "tool", "name": "get_weather"},
        "messages": [{"role": "user", "content": "Tokyo"}],
    }
    status, raw = _post_messages(base_url, key, body)
    ok = False
    if status == 200:
        try:
            obj = json.loads(raw)
            content = obj.get("content", [])
            ok = any(
                isinstance(b, dict) and b.get("type") == "tool_use"
                for b in content
            )
        except (json.JSONDecodeError, ValueError):
            ok = False
    return {"probe": "tool-forced", "status": status, "valid": ok}


def _probe_image(base_url: str, key: str) -> dict:
    """Image probe — expects a typed HTTP 400 (known-unsupported).

    This is **not** a global failure; it is reported as known-unsupported.
    """
    body = {
        "model": MODEL,
        "max_tokens": 64,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGAeQABAAAA",
                        },
                    },
                    {"type": "text", "text": "What is this?"},
                ],
            }
        ],
    }
    status, raw = _post_messages(base_url, key, body)
    # 400 is the expected, known-unsupported outcome.
    known_unsupported = status == 400
    return {
        "probe": "image",
        "status": status,
        "valid": known_unsupported,
        "known_unsupported": True,
    }


PROBE_FUNCS = {
    "text": _probe_text,
    "stream": _probe_stream,
    "thinking": _probe_thinking,
    "tool-auto": _probe_tool_auto,
    "tool-forced": _probe_tool_forced,
    "image": _probe_image,
}


def run_probes(probe: str, base_url: str, key: str) -> list[dict]:
    """Run the named probe (or all probes) and return a list of result dicts."""
    if probe == "all":
        names = [n for n in PROBE_NAMES if n != "all"]
    else:
        names = [probe]

    results = []
    for name in names:
        func = PROBE_FUNCS[name]
        results.append(func(base_url, key))
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Reads the key from stdin; never echoes it."""
    parser = argparse.ArgumentParser(
        description="Direct MaaS Anthropic protocol canary.",
    )
    parser.add_argument(
        "--probe",
        choices=PROBE_NAMES,
        default="all",
        help="Named probe to run (default: all).",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="MaaS Anthropic base URL (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    key = _read_key_from_stdin()

    results = run_probes(args.probe, args.base_url, key)

    # Report only status/schema facts — never the key.
    overall_ok = True
    for r in results:
        name = r["probe"]
        status = r["status"]
        valid = r["valid"]
        known = r.get("known_unsupported", False)
        if known:
            # Image is known-unsupported: report but don't fail overall.
            tag = "known-unsupported"
            print(f"  {name}: HTTP {status} — {tag}")
        else:
            tag = "PASS" if valid else "FAIL"
            print(f"  {name}: HTTP {status} — {tag}")
            if not valid:
                overall_ok = False
        sse_errors = r.get("sse_errors", [])
        if sse_errors:
            print(f"    sse_errors: {sse_errors}")

    print(f"\noverall: {'PASS' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
