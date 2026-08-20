#!/usr/bin/env python3
"""Performance tests for plugin convergence (PRD-plugin-convergence §10, §11.4).

Measures latency, memory, and event-loop responsiveness on the local machine.
The absolute budgets (§10) require the deployed baseline on 124.81.97.217,
but this harness produces reproducible local measurements for before/after
comparison.

Run: python3 -m pytest tests/test_performance.py
"""

import asyncio
import importlib.util
import json
import os
import pathlib
import sys
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── litellm stub ─────────────────────────────────────────────────────────────
import logging

litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
if not hasattr(litellm, "token_counter"):
    litellm.token_counter = lambda **kwargs: 100
_log_mod = types.ModuleType("litellm._logging")
_log_mod.verbose_proxy_logger = logging.getLogger("perf_test")
sys.modules.setdefault("litellm._logging", _log_mod)
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
_cl = types.ModuleType("litellm.integrations.custom_logger")


class CustomLogger:
    pass


_cl.CustomLogger = CustomLogger
sys.modules.setdefault("litellm.integrations.custom_logger", _cl)

# ── Load modules ─────────────────────────────────────────────────────────────
SIDECAR_CALLBACK = ROOT / "litellm_plugins" / "sidecar" / "callback.py"
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

_asg_path = ROOT / "litellm_plugins" / "anthropic_stream_guard" / "callback.py"
_asg_existing = None
for _k, _v in sys.modules.items():
    if _k.startswith("asg_callback") and hasattr(_v, "proxy_handler_instance"):
        _asg_existing = _v
        break
if _asg_existing is not None:
    _cbmod = _asg_existing
else:
    _asg_spec = importlib.util.spec_from_file_location("asg_callback_perf", _asg_path)
    _cbmod = importlib.util.module_from_spec(_asg_spec)
    _asg_spec.loader.exec_module(_cbmod)

proxy_handler_instance = _cbmod.proxy_handler_instance
_sse = _cbmod._sse

# ── Helpers ──────────────────────────────────────────────────────────────────

BASH_SCHEMA = {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"], "additionalProperties": False}
TOOLS = [{"name": "Bash", "input_schema": BASH_SCHEMA}]


def sse(e):
    return _sse(e)


def text_stream(text="Hello"):
    return [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]


def tool_stream(args_json):
    return [
        sse({"type": "message_start", "message": {"id": "m1"}}),
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": args_json}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 4}}),
        sse({"type": "message_stop"}),
    ]


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


def percentile(values, p):
    """Compute the p-th percentile of a sorted list."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


# ── P1: text-path latency (no tools, no images) ─────────────────────────────

def test_text_path_latency():
    """§10.1: incremental plugin p95 latency for text path < 5ms, p99 < 10ms."""
    raw = text_stream("Hello world")
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        asyncio.run(run_stream(raw, {}))
        times.append((time.perf_counter() - t0) * 1000)
    p95 = percentile(times, 95)
    p99 = percentile(times, 99)
    print("  text path: p95=%.2fms p99=%.2fms (n=100)" % (p95, p99))
    # Budgets: p95 < 5ms, p99 < 10ms (§10.1). These are local measurements;
    # deployed budgets may differ. We assert no regression (p99 < 50ms locally).
    assert p99 < 50.0, "text path p99=%.2fms exceeds 50ms local bound" % p99


# ── P2: valid tool validation latency ───────────────────────────────────────

def test_valid_tool_validation_latency():
    """§10.2: validation after final tool fragment < 10ms p95 for normal payloads."""
    raw = tool_stream('{"command":"ls -la"}')
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        asyncio.run(run_stream(raw, {"tools": TOOLS}))
        times.append((time.perf_counter() - t0) * 1000)
    p95 = percentile(times, 95)
    print("  valid tool: p95=%.2fms (n=100)" % p95)
    assert p95 < 50.0, "valid tool p95=%.2fms exceeds 50ms local bound" % p95


# ── P3: byte-identity for valid tools (no overhead regression) ──────────────

def test_valid_tool_byte_identity():
    """§10.2: byte-identical valid streaming output (no regression)."""
    raw = tool_stream('{"command":"ls -la"}')
    out = asyncio.run(run_stream(raw, {"tools": TOOLS}))
    assert out == raw, "valid tool output must be byte-identical"


# ── P4: event-loop responsiveness during lock acquisition ────────────────────

def test_event_loop_responsiveness_during_lock():
    """§10.3/§11.4: event-loop responsiveness while another request waits for a claim."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cache = sidecar.CaptionCache(d)

        async def _t():
            progressed = []
            async with cache.cross_process_lock_async("test_sha"):
                # Run a background task — it should progress while we hold the lock.
                async def _bg():
                    for i in range(5):
                        await asyncio.sleep(0.005)
                        progressed.append(i)
                bg = asyncio.create_task(_bg())
                await asyncio.sleep(0.03)
                assert len(progressed) >= 3, "event loop stalled during lock (only %d ticks)" % len(progressed)
                await bg

        asyncio.run(_t())


# ── P5: RSS memory during sustained streaming ───────────────────────────────

def test_rss_no_unbounded_growth():
    """§10.1: no measurable unbounded memory growth during sustained streaming."""
    import resource
    raw = text_stream("x" * 1000)
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for _ in range(200):
        asyncio.run(run_stream(raw, {}))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    growth = rss_after - rss_before
    print("  RSS: before=%dKB after=%dKB growth=%dKB (200 streams)" % (rss_before, rss_after, growth))
    # ru_maxrss is a high-water mark, so it may not decrease. We assert no
    # unbounded growth (> 50MB would indicate a leak).
    assert growth < 50000, "RSS growth=%dKB exceeds 50MB — possible leak" % growth


if __name__ == "__main__":
    test_text_path_latency()
    print("  ok test_text_path_latency")
    test_valid_tool_validation_latency()
    print("  ok test_valid_tool_validation_latency")
    test_valid_tool_byte_identity()
    print("  ok test_valid_tool_byte_identity")
    test_event_loop_responsiveness_during_lock()
    print("  ok test_event_loop_responsiveness_during_lock")
    test_rss_no_unbounded_growth()
    print("  ok test_rss_no_unbounded_growth")
    print("\nAll performance tests passed.")
