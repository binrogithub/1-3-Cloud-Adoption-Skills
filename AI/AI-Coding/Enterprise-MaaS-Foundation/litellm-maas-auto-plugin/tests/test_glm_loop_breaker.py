"""Self-contained regression tests for glm_loop_breaker.

    python3 tests/test_glm_loop_breaker.py

No proxy, no API key, no litellm install required.
"""

import asyncio
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "glm_loop_breaker" / "callback.py"

custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm", types.ModuleType("litellm"))
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)
spec = importlib.util.spec_from_file_location("glm_loop_breaker", CALLBACK)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

detect_cycle = module.detect_cycle
tool_call_sequence = module._tool_call_sequence
guard = module.proxy_handler_instance
NUDGE = module.NUDGE

FAILURES = []


def check(name, got, want):
    if got == want:
        print("  ok    %s" % name)
    else:
        print("  FAIL  %s: got %r, want %r" % (name, got, want))
        FAILURES.append(name)


def oai(name, args, call_id="call_x"):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": name, "arguments": args}}
        ],
    }


def anthropic(name, inp):
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "tu_x", "name": name, "input": inp}],
    }


def tool_result(text="done"):
    return {"role": "tool", "tool_call_id": "call_x", "content": text}


def run(data):
    return asyncio.run(guard.async_pre_call_hook(None, None, data, "completion"))


def looping_payload(reps, model="glm-5.2", **extra):
    """A history holding `reps` completed read_page -> sleep iterations."""
    messages = [{"role": "user", "content": "go"}]
    for _ in range(reps):
        messages += [oai("run_in_terminal", '{"command":"sleep 5"}'), tool_result()]
        messages += [oai("read_page", '{"url":"x"}'), tool_result("Loading...")]
    return {"model": model, "messages": messages, **extra}


print("detect_cycle")
check("no repetition", detect_cycle(["a", "b", "c", "d"]), (0, 0))
check("period 1", detect_cycle(["x", "a", "a", "a"]), (1, 3))
check("period 2 (the production shape)",
      detect_cycle(["a", "b", "a", "b", "a", "b"]), (2, 3))
check("period 3", detect_cycle(["a", "b", "c"] * 3), (3, 3))
check("cycle must sit at the tail", detect_cycle(["a", "a", "a", "z"]), (0, 0))
check("too short to judge", detect_cycle(["a"]), (0, 0))

print("\ntool call fingerprints")
seq = tool_call_sequence([oai("read_page", '{"u":1}'), tool_result(),
                          oai("read_page", '{"u":1}')])
check("identical calls share a fingerprint", seq[0] == seq[1], True)
seq = tool_call_sequence([oai("read_page", '{"u":1}'), oai("read_page", '{"u":2}')])
check("differing arguments differ", seq[0] != seq[1], True)
check("call id is excluded",
      tool_call_sequence([oai("t", "{}", call_id="A")]),
      tool_call_sequence([oai("t", "{}", call_id="B")]))
check("anthropic tool_use blocks are read",
      len(tool_call_sequence([anthropic("read_page", {"u": 1})])), 1)

print("\npre-call hook")
check("a single iteration is left alone",
      run(looping_payload(1, temperature=0)).get("temperature"), 0)

d = run(looping_payload(3, temperature=0))
check("a looping request gets the temperature floor", d["temperature"], 0.7)
check("a looping request gets top_p", d["top_p"], 0.95)
check("audit metadata records the period", d["metadata"]["glm_loop_breaker"]["period"], 2)
check("audit metadata records repetitions",
      d["metadata"]["glm_loop_breaker"]["repetitions"] >= 3, True)

check("a caller already above the floor keeps its temperature",
      run(looping_payload(3, temperature=0.9))["temperature"], 0.9)

d = run(looping_payload(5, temperature=0))
check("a persistent loop also gets the redirect instruction",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), True)
check("the instruction does not create two consecutive user turns",
      d["messages"][-1]["role"] == "user" and d["messages"][-2]["role"] != "user", True)

print("\nscope and safety")
check("non-GLM models are untouched",
      run(looping_payload(5, model="gpt-4o", temperature=0)).get("temperature"), 0)
check("coding-auto aliases are covered",
      run(looping_payload(5, model="coding-auto", temperature=0))["temperature"], 0.7)
check("meli-coding aliases are covered",
      run(looping_payload(5, model="meli-coding-fast", temperature=0))["temperature"], 0.7)
d = run(dict(looping_payload(5, temperature=0), metadata=None))
check("a null metadata is replaced, not assigned into",
      d["metadata"]["glm_loop_breaker"]["period"], 2)
check("a null metadata still gets the temperature floor", d["temperature"], 0.7)
d = run(dict(looping_payload(5, temperature=0), metadata={"user": "x"}))
check("existing metadata keys are preserved", d["metadata"]["user"], "x")

check("malformed messages pass through",
      run({"model": "glm-5.2", "messages": "not-a-list"})["messages"], "not-a-list")
check("a missing model key passes through",
      run({"messages": []}).get("temperature"), None)

print()
if FAILURES:
    print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all checks passed")
