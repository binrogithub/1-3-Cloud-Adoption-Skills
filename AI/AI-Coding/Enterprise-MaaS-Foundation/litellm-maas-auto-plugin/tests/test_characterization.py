#!/usr/bin/env python3
"""Characterization tests for plugin convergence (PRD-plugin-convergence §11.1).

These tests capture externally visible behavior that MUST be preserved during
the convergence refactor. If any of these fails after a refactor, the refactor
changed behavior. They are the golden-output safety net.

Run: python3 -m pytest tests/test_characterization.py
"""

import asyncio
import importlib.util
import json
import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── litellm stub ─────────────────────────────────────────────────────────────
import logging

litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
if not hasattr(litellm, "token_counter"):
    litellm.token_counter = lambda **kwargs: 100
_log_mod = types.ModuleType("litellm._logging")
_log_mod.verbose_proxy_logger = logging.getLogger("char_test")
sys.modules.setdefault("litellm._logging", _log_mod)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
_cl = types.ModuleType("litellm.integrations.custom_logger")


class CustomLogger:
    pass


_cl.CustomLogger = CustomLogger
sys.modules.setdefault("litellm.integrations.custom_logger", _cl)

# ── Load sidecar ─────────────────────────────────────────────────────────────
SIDECAR_CALLBACK = ROOT / "litellm_plugins" / "sidecar" / "callback.py"
os.environ.setdefault("TOOL_ARG_PREMIUM_REPAIR", "true")
if "sidecar" not in sys.modules:
    _spec_sc = importlib.util.spec_from_file_location("sidecar", SIDECAR_CALLBACK)
    sidecar = importlib.util.module_from_spec(_spec_sc)
    sys.modules["sidecar"] = sidecar
    _spec_sc.loader.exec_module(sidecar)
else:
    sidecar = sys.modules["sidecar"]

glm_lb = types.ModuleType("glm_loop_breaker")
glm_lb._tool_call_sequence = lambda msgs: []
glm_lb.detect_cycle = lambda seq: (0, 0)
sys.modules["glm_loop_breaker"] = glm_lb

# ── Load tool_argument_guard ─────────────────────────────────────────────────
os.environ["TOOL_ARG_GUARD_MODE"] = "enforce"
os.environ["TOOL_ARG_PREMIUM_REPAIR"] = "false"
_tag_path = ROOT / "litellm_plugins" / "tool_argument_guard" / "callback.py"
if "tool_argument_guard" in sys.modules:
    _tag_module = sys.modules["tool_argument_guard"]
else:
    _tag_spec = importlib.util.spec_from_file_location("tool_argument_guard", _tag_path)
    _tag_module = importlib.util.module_from_spec(_tag_spec)
    sys.modules["tool_argument_guard"] = _tag_module
    _tag_spec.loader.exec_module(_tag_module)

# ── Load stream guard ────────────────────────────────────────────────────────
_asg_path = ROOT / "litellm_plugins" / "anthropic_stream_guard" / "callback.py"
_asg_existing = None
for _k, _v in sys.modules.items():
    if _k.startswith("asg_callback") and hasattr(_v, "proxy_handler_instance"):
        _asg_existing = _v
        break
if _asg_existing is not None:
    _cbmod = _asg_existing
else:
    _asg_spec = importlib.util.spec_from_file_location("asg_callback_char", _asg_path)
    _cbmod = importlib.util.module_from_spec(_asg_spec)
    _asg_spec.loader.exec_module(_cbmod)

proxy_handler_instance = _cbmod.proxy_handler_instance
_sse = _cbmod._sse

# ── Load smart_router ────────────────────────────────────────────────────────
_router_path = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
_router_spec = importlib.util.spec_from_file_location("smart_router_char", _router_path)
router = importlib.util.module_from_spec(_router_spec)
_router_spec.loader.exec_module(router)

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL %s" % name)


def sse(e):
    return _sse(e)


async def feed(items):
    for e in items:
        yield e


async def run_stream(items, request_data=None):
    out = []
    async for c in proxy_handler_instance.async_post_call_streaming_iterator_hook(
        user_api_key_dict=None, response=feed(items), request_data=request_data or {}
    ):
        out.append(c)
    return out


def parse_all(chunks):
    evs = []
    for c in chunks:
        if isinstance(c, (bytes, bytearray)):
            text = c.decode()
        else:
            text = str(c)
        for ln in text.split("\n"):
            if ln.startswith("data: "):
                try:
                    evs.append(json.loads(ln[6:]))
                except json.JSONDecodeError:
                    pass
    return evs


BASH_SCHEMA = {
    "type": "object",
    "properties": {"command": {"type": "string"}},
    "required": ["command"],
    "additionalProperties": False,
}

TASKUPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "taskId": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
    },
    "required": ["taskId", "status"],
    "additionalProperties": False,
}

TOOLS = [
    {"name": "Bash", "input_schema": BASH_SCHEMA},
    {"name": "TaskUpdate", "input_schema": TASKUPDATE_SCHEMA},
]


def tool_stream(name, args_json, tool_id="tu_1", index=0):
    return [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": index,
             "content_block": {"type": "tool_use", "id": tool_id, "name": name, "input": {}}}),
        sse({"type": "content_block_delta", "index": index,
             "delta": {"type": "input_json_delta", "partial_json": args_json}}),
        sse({"type": "content_block_stop", "index": index}),
        sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]


def text_stream(text="Hello"):
    return [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]


# ── C1: text-only stream is byte-identical (no tools declared) ───────────────

def test_text_stream_byte_identical():
    """C1: a text-only stream with no tools declared passes through unchanged."""
    raw = text_stream("Hello world")
    out = asyncio.run(run_stream(raw, {}))
    check("C1 text stream byte-identical", out == raw)


# ── C2: valid tool call is byte-identical ────────────────────────────────────

def test_valid_tool_byte_identical():
    """C2: a schema-valid tool call replays byte-identically (PASS outcome)."""
    raw = tool_stream("Bash", '{"command":"ls -la"}')
    out = asyncio.run(run_stream(raw, {"tools": TOOLS}))
    check("C2 valid tool byte-identical", out == raw)


# ── C3: normalized tool call emits canonical delta ───────────────────────────

def test_normalized_tool_canonical_delta():
    """C3: task_id→taskId + done→completed normalization emits one canonical delta."""
    raw = tool_stream("TaskUpdate", '{"task_id":"t1","status":"done"}')
    out = asyncio.run(run_stream(raw, {"tools": TOOLS}))
    evs = parse_all(out)
    deltas = [e for e in evs if e.get("type") == "content_block_delta"
              and (e.get("delta") or {}).get("type") == "input_json_delta"]
    check("C3 normalized one delta", len(deltas) == 1)
    if deltas:
        args = json.loads(deltas[0]["delta"]["partial_json"])
        check("C3 taskId normalized", args.get("taskId") == "t1")
        check("C3 status completed", args.get("status") == "completed")
        check("C3 task_id removed", "task_id" not in args)


# ── C4: rejected tool emits text blocker + end_turn ──────────────────────────

def test_rejected_tool_text_blocker():
    """C4: an unresolvable tool call is rejected with text + end_turn."""
    raw = tool_stream("TaskUpdate", '{"status":"pending"}')  # missing taskId
    out = asyncio.run(run_stream(raw, {"tools": TOOLS}))
    evs = parse_all(out)
    tool_starts = [e for e in evs if e.get("type") == "content_block_start"
                   and (e.get("content_block") or {}).get("type") == "tool_use"]
    text_starts = [e for e in evs if e.get("type") == "content_block_start"
                   and (e.get("content_block") or {}).get("type") == "text"]
    check("C4 rejected no tool_use", len(tool_starts) == 0)
    check("C4 rejected has text", len(text_starts) == 1)
    md = [e for e in evs if e.get("type") == "message_delta"]
    if md:
        check("C4 rejected end_turn", md[-1]["delta"]["stop_reason"] == "end_turn")


# ── C5: mixed valid+invalid streaming emits zero tool blocks ─────────────────

def test_mixed_streaming_zero_tool_blocks():
    """C5: a mixed valid+invalid set emits zero tool_use blocks (atomic)."""
    raw = [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": 0,
             "content_block": {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}}),
        sse({"type": "content_block_delta", "index": 0,
             "delta": {"type": "input_json_delta", "partial_json": '{"command":"ls"}'}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "content_block_start", "index": 1,
             "content_block": {"type": "tool_use", "id": "tu_2", "name": "TaskUpdate", "input": {}}}),
        sse({"type": "content_block_delta", "index": 1,
             "delta": {"type": "input_json_delta", "partial_json": '{"status":"pending"}'}}),
        sse({"type": "content_block_stop", "index": 1}),
        sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]
    out = asyncio.run(run_stream(raw, {"tools": TOOLS}))
    evs = parse_all(out)
    tool_starts = [e for e in evs if e.get("type") == "content_block_start"
                   and (e.get("content_block") or {}).get("type") == "tool_use"]
    check("C5 mixed zero tool_use", len(tool_starts) == 0)


# ── C6: all selectors route to GLM mainline ──────────────────────────────────

def test_all_selectors_route_to_glm():
    """C6: native selectors (default/opus/sonnet/haiku) are REJECTED by the
    router — they must not be remapped to GLM. Only claude-glm-5.2 routes
    through the gateway. PRD-release-closure §3.1."""
    litellm.token_counter = lambda **kwargs: 100
    mainline = router.MAINLINE_MODEL
    check("C6 mainline is GLM", "glm" in mainline.lower())
    for selector in ("default", "opus", "sonnet", "haiku"):
        data = {"model": selector, "messages": [{"role": "user", "content": "hi"}]}
        rejected = False
        try:
            router.route_request(data, None)
        except Exception:
            rejected = True
        check("C6 selector %s rejected (non-GLM)" % selector, rejected)
    # claude-glm-5.2 should be accepted.
    data = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
    result = router.route_request(data, None)
    check("C6 claude-glm-5.2 accepted", isinstance(result, dict) and "model" in result)


# ── C7: non-stream OpenAI rejection removes tool_calls ───────────────────────

def test_openai_nonstream_rejection_removes_tool_calls():
    """C7: OpenAI rejection empties tool_calls and sets finish_reason=stop."""
    async def _t():
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"function": {"name": "TaskUpdate", "arguments": '{"status":"pending"}'}},
                    ]
                },
                "finish_reason": "tool_calls",
            }]
        }
        await _cbmod._validate_non_stream_tools({"tools": TOOLS}, response)
        tc = response["choices"][0]["message"].get("tool_calls", [])
        check("C7 OpenAI tool_calls empty", len(tc) == 0)
        check("C7 OpenAI finish_reason stop", response["choices"][0]["finish_reason"] == "stop")
    asyncio.run(_t())


# ── C8: non-stream Anthropic rejection replaces tool_use with text ───────────

def test_anthropic_nonstream_rejection_replaces_with_text():
    """C8: Anthropic rejection replaces all tool_use blocks with text + end_turn."""
    async def _t():
        response = {
            "content": [
                {"type": "tool_use", "name": "TaskUpdate", "id": "tu_1", "input": {"status": "pending"}},
            ],
            "stop_reason": "tool_use",
        }
        await _cbmod._validate_non_stream_tools({"tools": TOOLS}, response)
        tool_blocks = [b for b in response["content"] if b.get("type") == "tool_use"]
        check("C8 Anthropic zero tool_use", len(tool_blocks) == 0)
        check("C8 Anthropic end_turn", response["stop_reason"] == "end_turn")
    asyncio.run(_t())


# ── C9: decide() atomic — any reject → all reject ────────────────────────────

def test_decide_atomic_reject():
    """C9: decide() returns REJECTED with all per_tool outcomes = reject if any rejects."""
    async def _t():
        sm = _tag_module.SchemaMap(TOOLS)
        decision = await _tag_module.decide([
            {"index": 0, "name": "Bash", "tool_id": "t1", "args": {"command": "ls"}},
            {"index": 1, "name": "TaskUpdate", "tool_id": "t2", "args": {"status": "pending"}},
        ], sm)
        check("C9 atomic REJECTED", decision.outcome == _tag_module.DecisionOutcome.REJECTED)
        check("C9 all reject", all(tr.outcome == "reject" for tr in decision.per_tool))
    asyncio.run(_t())


# ── C10: decide() PASS when all valid ────────────────────────────────────────

def test_decide_pass_all_valid():
    """C10: decide() returns PASS when all tools are schema-valid."""
    async def _t():
        sm = _tag_module.SchemaMap(TOOLS)
        decision = await _tag_module.decide([
            {"index": 0, "name": "Bash", "tool_id": "t1", "args": {"command": "ls"}},
            {"index": 1, "name": "TaskUpdate", "tool_id": "t2",
             "args": {"taskId": "t1", "status": "pending"}},
        ], sm)
        check("C10 all valid PASS", decision.outcome == _tag_module.DecisionOutcome.PASS)
    asyncio.run(_t())


# ── C11: residency china-only blocks egress ──────────────────────────────────

def test_residency_china_only_blocks_egress():
    """C11: a china-only residency policy denies egress (check_egress raises 403)."""
    policy = sidecar.ResidencyPolicy("china-only")
    check("C11 china-only is_china_only", policy.is_china_only)
    check("C11 china-only blocks egress", not policy.allows_egress)
    raised = False
    try:
        policy.check_egress("vision")
    except sidecar.SidecarPolicyDenied as e:
        raised = True
        check("C11 denial 403", e.http_status == 403)
    check("C11 check_egress raises", raised)


# ── C12: typed errors carry correct HTTP status ──────────────────────────────

def test_typed_errors_http_status():
    """C12: internal typed errors carry the correct HTTP status for the adapter."""
    check("C12 InvalidImageInput 400", sidecar.InvalidImageInput.http_status == 400)
    check("C12 ImageLimitExceeded 413", sidecar.ImageLimitExceeded.http_status == 413)
    check("C12 SidecarPolicyDenied 403", sidecar.SidecarPolicyDenied.http_status == 403)
    check("C12 VisionSidecarUnavailable 502", sidecar.VisionSidecarUnavailable.http_status == 502)


# ── Run all tests ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_text_stream_byte_identical,
    test_valid_tool_byte_identical,
    test_normalized_tool_canonical_delta,
    test_rejected_tool_text_blocker,
    test_mixed_streaming_zero_tool_blocks,
    test_all_selectors_route_to_glm,
    test_openai_nonstream_rejection_removes_tool_calls,
    test_anthropic_nonstream_rejection_replaces_with_text,
    test_decide_atomic_reject,
    test_decide_pass_all_valid,
    test_residency_china_only_blocks_egress,
    test_typed_errors_http_status,
]

for _t in ALL_TESTS:
    try:
        _t()
    except Exception as e:
        FAIL += 1
        print("  ERROR %s: %s: %s" % (_t.__name__, type(e).__name__, e))


def test_characterization_all_pass():
    """Pytest entry point: assert every characterization check succeeded."""
    assert FAIL == 0, "%d characterization checks failed" % FAIL


if __name__ == "__main__":
    print("\n%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
