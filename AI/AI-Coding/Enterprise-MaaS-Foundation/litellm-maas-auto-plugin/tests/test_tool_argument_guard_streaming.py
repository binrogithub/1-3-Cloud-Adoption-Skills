#!/usr/bin/env python3
"""Streaming integration tests for the Tool Argument Guard
(PRD-tool-argument-guard §8, §11, §17.2).

These tests run with TOOL_ARG_GUARD_MODE=enforce so the guard buffers tool
blocks, validates, normalizes, repairs, and rejects. The base stream guard
tests (test_anthropic_stream_guard.py) run in observe mode and verify
byte-identity is preserved.

Run: python3 tests/test_tool_argument_guard_streaming.py
"""

import asyncio
import json
import logging
import os
import sys
import types
from pathlib import Path

# Set enforce mode BEFORE importing the stream guard (it reads env at import).
os.environ["TOOL_ARG_GUARD_MODE"] = "enforce"
# Disable Premium repair in streaming tests (unit-test, no live model).
os.environ["TOOL_ARG_PREMIUM_REPAIR"] = "false"

if "litellm" not in sys.modules:
    litellm = types.ModuleType("litellm")
    logging_module = types.ModuleType("litellm._logging")
    integrations = types.ModuleType("litellm.integrations")
    custom_logger = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:
        pass

    logging_module.verbose_proxy_logger = logging.getLogger("tag_streaming_test")
    custom_logger.CustomLogger = CustomLogger
    sys.modules.setdefault("litellm", litellm)
    sys.modules.setdefault("litellm._logging", logging_module)
    sys.modules.setdefault("litellm.integrations", integrations)
    sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)

# Load tool_argument_guard into sys.modules as 'tool_argument_guard' so the
# stream guard's `import tool_argument_guard` finds it (in deployment it is
# mounted as /app/tool_argument_guard.py; in tests we use importlib).
import importlib.util  # noqa: E402

_repo = Path(__file__).resolve().parents[1]
_tag_path = _repo / "litellm_plugins" / "tool_argument_guard" / "callback.py"
_tag_spec = importlib.util.spec_from_file_location("tool_argument_guard", _tag_path)
_tag_module = importlib.util.module_from_spec(_tag_spec)
sys.modules["tool_argument_guard"] = _tag_module
_tag_spec.loader.exec_module(_tag_module)

# Now import the stream guard (it will find tool_argument_guard in sys.modules).
_asg_path = _repo / "litellm_plugins" / "anthropic_stream_guard" / "callback.py"
_asg_spec = importlib.util.spec_from_file_location("asg_callback_streaming", _asg_path)
_cbmod = importlib.util.module_from_spec(_asg_spec)
_asg_spec.loader.exec_module(_cbmod)

proxy_handler_instance = _cbmod.proxy_handler_instance
_sse = _cbmod._sse

# Verify the guard loaded in enforce mode.
assert _cbmod._TAG_ENFORCE, "guard must be in enforce mode for these tests"
assert _cbmod._TAG is not None, "tool_argument_guard must be importable"


def sse(e):
    return _sse(e)


async def feed(items):
    for e in items:
        yield e


async def run(items, request_data=None):
    out = []
    async for c in proxy_handler_instance.async_post_call_streaming_iterator_hook(
        user_api_key_dict=None, response=feed(items), request_data=request_data or {}
    ):
        out.append(c)
    return out


def parse_all(chunks):
    evs = []
    for c in chunks:
        assert isinstance(c, (bytes, bytearray)), f"non-bytes leaked: {type(c)}"
        for ln in c.decode().split("\n"):
            if ln.startswith("data: "):
                evs.append(json.loads(ln[6:]))
    return evs


PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("%s: PASS" % name)
    else:
        FAIL += 1
        print("%s: FAIL" % name)


# ── Schemas ─────────────────────────────────────────────────────────────────

TASKUPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
    },
    "required": ["taskId", "status"],
    "additionalProperties": False,
}

BASH_SCHEMA = {
    "type": "object",
    "properties": {"command": {"type": "string"}},
    "required": ["command"],
    "additionalProperties": False,
}

TOOLS_WITH_SCHEMA = [
    {"name": "TaskUpdate", "input_schema": TASKUPDATE_SCHEMA},
    {"name": "Bash", "input_schema": BASH_SCHEMA},
]


def tool_stream(tool_name, args_json, tool_id="tu_1", index=0):
    """Build a minimal tool_use stream (start + delta + stop)."""
    return [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": index,
             "content_block": {"type": "tool_use", "id": tool_id, "name": tool_name, "input": {}}}),
        sse({"type": "content_block_delta", "index": index,
             "delta": {"type": "input_json_delta", "partial_json": args_json}}),
        sse({"type": "content_block_stop", "index": index}),
        sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]


# ── S1: valid tool call passes through byte-identically ────────────────────

valid_stream = tool_stream("Bash", '{"command":"ls -la"}')
out = asyncio.run(run(valid_stream, {"tools": TOOLS_WITH_SCHEMA}))
check("S1 valid tool byte-identical", out == valid_stream)

# ── S2: invalid tool call (wrong field name) is normalized ─────────────────

# task_id instead of taskId + status "done" instead of "completed"
invalid_stream = tool_stream("TaskUpdate", '{"task_id":"t1","status":"done"}')
out = asyncio.run(run(invalid_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
# Should have a tool_use block with repaired args
tool_starts = [e for e in evs if e.get("type") == "content_block_start"
               and (e.get("content_block") or {}).get("type") == "tool_use"]
check("S2 normalized has tool_use start", len(tool_starts) == 1)
# The delta should contain the canonical repaired JSON
deltas = [e for e in evs if e.get("type") == "content_block_delta"
          and (e.get("delta") or {}).get("type") == "input_json_delta"]
check("S2 normalized has input_json_delta", len(deltas) == 1)
if deltas:
    args = json.loads(deltas[0]["delta"]["partial_json"])
    check("S2 taskId normalized", args.get("taskId") == "t1")
    check("S2 status normalized", args.get("status") == "completed")
    check("S2 task_id removed", "task_id" not in args)

# ── S3: unresolvable invalid tool call is rejected with safe text ───────────

# Missing required taskId entirely — cannot be synthesized (PRD §9.2)
unresolvable_stream = tool_stream("TaskUpdate", '{"status":"pending"}')
out = asyncio.run(run(unresolvable_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
# Should have a text block (not tool_use) with rejection text
text_starts = [e for e in evs if e.get("type") == "content_block_start"
               and (e.get("content_block") or {}).get("type") == "text"]
check("S3 rejected has text start", len(text_starts) == 1)
text_deltas = [e for e in evs if e.get("type") == "content_block_delta"
               and (e.get("delta") or {}).get("type") == "text_delta"]
check("S3 rejected has text delta", len(text_deltas) >= 1)
if text_deltas:
    text = "".join(e["delta"]["text"] for e in text_deltas)
    check("S3 rejection text present", "not executed" in text)
# stop_reason should be end_turn (not tool_use)
md = [e for e in evs if e.get("type") == "message_delta"]
if md:
    check("S3 stop_reason end_turn", md[-1]["delta"]["stop_reason"] == "end_turn")

# ── S4: unknown tool is rejected ────────────────────────────────────────────

unknown_stream = tool_stream("NonexistentTool", '{"x":1}')
out = asyncio.run(run(unknown_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
text_starts = [e for e in evs if e.get("type") == "content_block_start"
               and (e.get("content_block") or {}).get("type") == "text"]
check("S4 unknown tool rejected", len(text_starts) == 1)

# ── S5: text + thinking before tool_use stream normally ────────────────────

mixed_stream = [
    sse({"type": "message_start", "message": {"id": "m1"}}),
    sse({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    sse({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Let me run"}}),
    sse({"type": "content_block_stop", "index": 0}),
    sse({"type": "content_block_start", "index": 1,
         "content_block": {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}}),
    sse({"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'}}),
    sse({"type": "content_block_stop", "index": 1}),
    sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
    sse({"type": "message_stop"}),
]
out = asyncio.run(run(mixed_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
# Text block should be present and correct
text_deltas = [e for e in evs if e.get("type") == "content_block_delta"
               and (e.get("delta") or {}).get("type") == "text_delta"]
check("S5 text before tool preserved", any("Let me run" in e["delta"]["text"] for e in text_deltas))
# Tool block should be valid and present
tool_deltas = [e for e in evs if e.get("type") == "content_block_delta"
               and (e.get("delta") or {}).get("type") == "input_json_delta"]
check("S5 tool delta present", len(tool_deltas) == 1)

# ── S6: syntactically malformed JSON is rejected ────────────────────────────

malformed_stream = tool_stream("Bash", '{"command":"ls')  # truncated
out = asyncio.run(run(malformed_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
text_starts = [e for e in evs if e.get("type") == "content_block_start"
               and (e.get("content_block") or {}).get("type") == "text"]
check("S6 malformed JSON rejected", len(text_starts) == 1)

# ── S7: split partial_json across multiple deltas ──────────────────────────

split_stream = [
    sse({"type": "message_start", "message": {"id": "m1"}}),
    sse({"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}}),
    sse({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"comm'}}),
    sse({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "and\":\"ls"}}),
    sse({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "\"}"}}),
    sse({"type": "content_block_stop", "index": 0}),
    sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
    sse({"type": "message_stop"}),
]
out = asyncio.run(run(split_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
tool_deltas = [e for e in evs if e.get("type") == "content_block_delta"
               and (e.get("delta") or {}).get("type") == "input_json_delta"]
# Valid tool call: original fragments replayed byte-identically (PRD §11.1).
# The fragments concatenate to valid JSON.
assembled = "".join(e["delta"]["partial_json"] for e in tool_deltas)
check("S7 split fragments present", len(tool_deltas) == 3)
try:
    args = json.loads(assembled)
    check("S7 split args correct", args.get("command") == "ls")
except json.JSONDecodeError:
    check("S7 split args correct", False)

# ── S8: no tools in request -> no buffering, passthrough ───────────────────

no_tools_stream = tool_stream("Bash", '{"command":"ls"}')
out = asyncio.run(run(no_tools_stream, {}))
check("S8 no tools passthrough", out == no_tools_stream)

# ── S9: additional property under additionalProperties:false is removed ─────

extra_stream = tool_stream("Bash", '{"command":"ls","junk":123}')
out = asyncio.run(run(extra_stream, {"tools": TOOLS_WITH_SCHEMA}))
evs = parse_all(out)
tool_deltas = [e for e in evs if e.get("type") == "content_block_delta"
               and (e.get("delta") or {}).get("type") == "input_json_delta"]
check("S9 extra field normalized", len(tool_deltas) == 1)
if tool_deltas:
    args = json.loads(tool_deltas[0]["delta"]["partial_json"])
    check("S9 junk removed", "junk" not in args)
    check("S9 command kept", args.get("command") == "ls")

# ── S10: concurrent streams with different schemas are isolated ────────────

async def concurrent():
    r1 = run(tool_stream("Bash", '{"command":"ls"}'), {"tools": TOOLS_WITH_SCHEMA})
    r2 = run(tool_stream("TaskUpdate", '{"taskId":"t1","status":"pending"}'), {"tools": TOOLS_WITH_SCHEMA})
    return await asyncio.gather(r1, r2)

r1, r2 = asyncio.run(concurrent())
evs1 = parse_all(r1)
evs2 = parse_all(r2)
check("S10 concurrent r1 has Bash", any(
    (e.get("content_block") or {}).get("name") == "Bash"
    for e in evs1 if e.get("type") == "content_block_start"
))
check("S10 concurrent r2 has TaskUpdate", any(
    (e.get("content_block") or {}).get("name") == "TaskUpdate"
    for e in evs2 if e.get("type") == "content_block_start"
))


def test_all_checks_pass():
    """Pytest entry point: assert every module-level check() succeeded."""
    assert FAIL == 0, "%d checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
