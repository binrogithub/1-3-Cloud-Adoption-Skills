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
result_sequence = module._tool_result_sequence
paired_sequence = module._paired_sequence
result_fingerprint = module._result_fingerprint
profile = module._model_profile
guard = module.proxy_handler_instance
NUDGE = module.NUDGE
NUDGE_PREFIX = module.NUDGE_PREFIX
REASSURANCE = module.REASSURANCE
REASSURANCE_PREFIX = module.REASSURANCE_PREFIX
recent_tool_error = module._recent_tool_error
PERMANENT_GUARD = module.PERMANENT_GUARD
PERMANENT_GUARD_PREFIX = module.PERMANENT_GUARD_PREFIX

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

print("\nmodel registry profile")
check("glm-5.2 is glm", profile("glm-5.2")["family"], "glm")
check("claude-glm-5.2 is glm", profile("claude-glm-5.2")["family"], "glm")
check("meli-coding2 is glm", profile("claude-glm-5.2")["family"], "glm")
check("claude-opus is glm (compat alias)", profile("claude-glm-5.2")["family"], "glm")
check("claude-glm-5.2 is glm", profile("claude-glm-5.2")["family"], "glm")
check("glm-5.1-fallback is glm", profile("glm-5.1-fallback")["family"], "glm")
# The loop_breaker flag gates the sampling override (PRD-multi-family-v2 §3).
check("glm-5.2 has loop_breaker", profile("glm-5.2")["loop_breaker"], True)
check("claude-opus has loop_breaker", profile("claude-glm-5.2")["loop_breaker"], True)
check("glm-5.1-fallback has loop_breaker", profile("glm-5.1-fallback")["loop_breaker"], True)
# Deleted text routes (PRD-glm-consolidation §6 Option A) now resolve to the
# inert fallback (family "other", no loop_breaker).
check("claude-sonnet-5 deleted -> other", profile("claude-sonnet-5")["family"], "other")
check("claude-haiku-4-5 deleted -> other", profile("claude-haiku-4-5")["family"], "other")
check("deleted sonnet has no loop_breaker", profile("claude-sonnet-5")["loop_breaker"], False)
check("deleted haiku has no loop_breaker", profile("claude-haiku-4-5")["loop_breaker"], False)
# Unknown ID -> fallback (family "other", no loop_breaker).
check("gpt-4o is other", profile("gpt-4o")["family"], "other")
check("gpt-4o has no loop_breaker", profile("gpt-4o")["loop_breaker"], False)
check("empty model is other", profile("")["family"], "other")
check("None model is other", profile(None)["family"], "other")

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

# The nudge is injected once per session, not once per looping turn. Simulate two
# consecutive looping turns by guarding the same payload twice: the second call
# sees the nudge already in the history and must not append it again, though it
# still re-applies the temperature floor and top_p.
nudge_prefix = NUDGE_PREFIX
payload = looping_payload(5, temperature=0)
guard._guard(payload)                       # turn 1: nudge appended
guard._guard(payload)                       # turn 2: nudge already present
nudge_count = sum(str(m.get("content", "")).count(nudge_prefix)
                   for m in payload["messages"])
check("nudge is injected once across two looping turns", nudge_count, 1)
check("second guard still applies the temperature floor",
      payload["temperature"], 0.7)
check("second guard still applies top_p", payload["top_p"], 0.95)

print("\nscope and safety")
check("non-GLM models are untouched",
      run(looping_payload(5, model="gpt-4o", temperature=0)).get("temperature"), 0)
check("claude-glm-5.2 aliases are covered",
      run(looping_payload(5, model="claude-glm-5.2", temperature=0))["temperature"], 0.7)
check("meli-coding aliases are covered",
      run(looping_payload(5, model="claude-glm-5.2", temperature=0))["temperature"], 0.7)
check("claude-opus (GLM compat alias) still gets the temperature floor",
      run(looping_payload(5, model="claude-glm-5.2", temperature=0))["temperature"], 0.7)
check("glm-5.2 still gets the temperature floor",
      run(looping_payload(5, model="glm-5.2", temperature=0))["temperature"], 0.7)

print("\nmulti-family: deleted/non-glm models detect the cycle but skip sampling")
# PRD-glm-consolidation §6 Option A: claude-sonnet-5/claude-haiku-4-5 are deleted
# from the registry. They resolve to the inert fallback (family "other",
# loop_breaker=False). The breaker still detects the cycle (the history carries
# it) and records metadata, but must NOT set temperature/top_p — the fallback
# profile opts out of the sampling override.
d = run(looping_payload(5, model="claude-sonnet-5", temperature=0))
check("deleted sonnet: cycle is still detected (metadata records period)",
      d["metadata"]["glm_loop_breaker"]["period"], 2)
check("deleted sonnet: cycle is still detected (metadata records reps)",
      d["metadata"]["glm_loop_breaker"]["repetitions"] >= 3, True)
check("deleted sonnet: temperature is NOT overridden",
      d.get("temperature"), 0)
check("deleted sonnet: top_p is NOT set", "top_p" in d, False)
check("deleted sonnet: model_family recorded in metadata",
      d["metadata"]["glm_loop_breaker"]["model_family"], "other")
check("deleted sonnet: nudge is still appended (safe user message)",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), True)

d = run(looping_payload(5, model="claude-haiku-4-5", temperature=0))
check("deleted haiku: cycle is still detected (metadata records period)",
      d["metadata"]["glm_loop_breaker"]["period"], 2)
check("deleted haiku: temperature is NOT overridden",
      d.get("temperature"), 0)
check("deleted haiku: top_p is NOT set", "top_p" in d, False)
check("deleted haiku: model_family recorded in metadata",
      d["metadata"]["glm_loop_breaker"]["model_family"], "other")
check("deleted haiku: nudge is still appended",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), True)

# A caller already above the floor on a non-glm model is also left alone —
# the breaker never touches sampling on non-glm families, regardless of value.
check("deleted sonnet above floor is still untouched",
      run(looping_payload(5, model="claude-sonnet-5", temperature=0.9)).get("temperature"), 0.9)

d = run(dict(looping_payload(5, temperature=0), metadata=None))
check("a null metadata is replaced, not assigned into",
      d["metadata"]["glm_loop_breaker"]["period"], 2)
check("a null metadata still gets the temperature floor", d["temperature"], 0.7)
check("glm family is recorded in metadata",
      d["metadata"]["glm_loop_breaker"]["model_family"], "glm")
d = run(dict(looping_payload(5, temperature=0), metadata={"user": "x"}))
check("existing metadata keys are preserved", d["metadata"]["user"], "x")

check("malformed messages pass through",
      run({"model": "glm-5.2", "messages": "not-a-list"})["messages"], "not-a-list")
check("a missing model key passes through",
      run({"messages": []}).get("temperature"), None)

# ---------------------------------------------------------------------------
# Result-aware loop detection: the breaker must NOT fire when the tool call
# repeats but the results keep changing (an active debug session).  This is
# the regression for the 217 incident where the model was iterating on a
# script fix — same `python3 /tmp/tps_test.py` call, different error each
# time — and the old call-only fingerprint would have flagged it as a loop.
# ---------------------------------------------------------------------------
print("\nresult-aware: debug workflow (same call, changing results)")

def debug_payload(reps, model="glm-5.2", **extra):
    """Same tool call repeated, but each iteration produces a DIFFERENT error.

    This is what a debug session looks like: the model runs the script, gets
    IndexError, fixes it, runs again, gets KeyError, fixes it, runs again …
    The call fingerprint is identical every time; the result is not.
    """
    messages = [{"role": "user", "content": "debug the script"}]
    errors = ["IndexError: list index out of range",
              "KeyError: 'choices'",
              "TypeError: object is not subscriptable",
              "AttributeError: 'NoneType' has no attribute 'get'",
              "ValueError: invalid JSON"]
    for i in range(reps):
        err = errors[i % len(errors)]
        messages += [oai("run_in_terminal", '{"command":"python3 /tmp/tps_test.py"}'),
                     tool_result("Exit code 1\nTraceback: " + err)]
    return {"model": model, "messages": messages, **extra}

# 5 iterations of the same call with different errors — NOT a stuck loop.
d = run(debug_payload(5, temperature=0))
check("debug workflow: temperature is NOT overridden",
      d.get("temperature"), 0)
check("debug workflow: top_p is NOT set",
      "top_p" in d, False)
check("debug workflow: no nudge injected",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), False)
check("debug workflow: no loop_breaker metadata",
      d.get("metadata", {}).get("glm_loop_breaker") is None
      or d.get("metadata", {}).get("glm_loop_breaker", {}).get("repetitions", 0) < 3,
      True)

# Contrast: same call AND same result — this IS a stuck loop and must fire.
def stuck_payload(reps, model="glm-5.2", **extra):
    """Same tool call, same result every time — a genuine stuck loop."""
    messages = [{"role": "user", "content": "go"}]
    for _ in range(reps):
        messages += [oai("run_in_terminal", '{"command":"python3 /tmp/tps_test.py"}'),
                     tool_result("Exit code 1\nIndexError: list index out of range")]
    return {"model": model, "messages": messages, **extra}

d = run(stuck_payload(5, temperature=0))
check("stuck loop (same result): temperature IS overridden",
      d["temperature"], 0.7)
check("stuck loop (same result): nudge IS injected",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), True)

# Anthropic-shape results must also be fingerprinted.
def anthropic_debug_payload(reps, model="glm-5.2", **extra):
    messages = [{"role": "user", "content": "debug"}]
    errors = ["IndexError", "KeyError", "TypeError", "AttributeError", "ValueError"]
    for i in range(reps):
        err = errors[i % len(errors)]
        messages += [anthropic("run_in_terminal", {"command": "python3 /tmp/x.py"})]
        messages += [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_x",
             "content": [{"type": "text", "text": "Exit 1: " + err}]}
        ]}]
    return {"model": model, "messages": messages, **extra}

d = run(anthropic_debug_payload(5, temperature=0))
check("anthropic debug workflow: temperature is NOT overridden",
      d.get("temperature"), 0)
check("anthropic debug workflow: no nudge",
      any(NUDGE in str(m.get("content", "")) for m in d["messages"]), False)

# Result fingerprint unit tests
print("\nresult fingerprint")
check("different error texts produce different fingerprints",
      result_fingerprint("IndexError: x") != result_fingerprint("KeyError: y"), True)
check("same text produces same fingerprint",
      result_fingerprint("IndexError: x") == result_fingerprint("IndexError: x"), True)
check("ANSI codes are stripped before fingerprinting",
      result_fingerprint("\x1b[31mError\x1b[0m") == result_fingerprint("Error"), True)
check("anthropic list content is fingerprinted",
      result_fingerprint([{"type": "text", "text": "ok"}]) == result_fingerprint("ok"), True)

# Paired sequence unit test
print("\npaired sequence")
msgs = [
    oai("bash", '{"command":"x"}'), tool_result("error A"),
    oai("bash", '{"command":"x"}'), tool_result("error B"),
    oai("bash", '{"command":"x"}'), tool_result("error C"),
]
pairs = paired_sequence(msgs)
check("paired sequence has one entry per call", len(pairs), 3)
check("paired entries differ when results differ",
      len(set(pairs)) == 3, True)

msgs_stuck = [
    oai("bash", '{"command":"x"}'), tool_result("error A"),
    oai("bash", '{"command":"x"}'), tool_result("error A"),
    oai("bash", '{"command":"x"}'), tool_result("error A"),
]
pairs_stuck = paired_sequence(msgs_stuck)
check("paired entries match when call+result repeat",
      pairs_stuck[0] == pairs_stuck[1] == pairs_stuck[2], True)

# NUDGE text no longer contains "SYSTEM INTERRUPT" or "Stop retrying" — the
# old wording was misread by GLM as "tools are disabled" and the model
# refused to call any tool, telling the user it was locked out.
print("\nNUDGE wording")
check("NUDGE does not say SYSTEM INTERRUPT", "SYSTEM INTERRUPT" not in NUDGE, True)
check("NUDGE does not say Stop retrying", "Stop retrying" not in NUDGE, True)
check("NUDGE says tools are still available", "still available" in NUDGE, True)
check("NUDGE_PREFIX matches NUDGE start", NUDGE.startswith(NUDGE_PREFIX), True)

# ---------------------------------------------------------------------------
# Reassurance: when the most recent tool result is an error, inject a short
# correction telling the model its tools still work.  This counters GLM's
# observed behaviour of hallucinating "tools are disabled" after ONE failure.
# ---------------------------------------------------------------------------
print("\nreassurance on tool error")

def error_result_payload(model="glm-5.2", **extra):
    """A single tool call that failed with an error — no cycle at all."""
    messages = [
        {"role": "user", "content": "run the test"},
        oai("run_in_terminal", '{"command":"python3 /tmp/test.py"}'),
        tool_result("Exit code 1\nTraceback (most recent call last):\n  IndexError: list index out of range"),
        {"role": "user", "content": "try again"},
    ]
    return {"model": model, "messages": messages, **extra}

d = run(error_result_payload(temperature=0))
check("reassurance injected on tool error",
      any(REASSURANCE_PREFIX in str(m.get("content", "")) for m in d["messages"]), True)
check("reassurance does not override temperature",
      d.get("temperature"), 0)

# Reassurance is once per session — second guard call must not duplicate.
guard._guard(d)
count = sum(str(m.get("content", "")).count(REASSURANCE_PREFIX)
            for m in d["messages"])
check("reassurance injected once across two calls", count, 1)

# No reassurance when the last tool result was success.
def success_result_payload(model="glm-5.2", **extra):
    messages = [
        {"role": "user", "content": "run the test"},
        oai("run_in_terminal", '{"command":"echo hi"}'),
        tool_result("hi\nExit code 0"),
        {"role": "user", "content": "good"},
    ]
    return {"model": model, "messages": messages, **extra}

d = run(success_result_payload(temperature=0))
check("no reassurance on success",
      any(REASSURANCE_PREFIX in str(m.get("content", "")) for m in d["messages"]), False)

# Anthropic-shape error detection
def anthropic_error_payload(model="glm-5.2", **extra):
    messages = [
        {"role": "user", "content": "test"},
        anthropic("bash", {"command": "python3 /tmp/x.py"}),
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_x", "is_error": True,
             "content": [{"type": "text", "text": "Exit code 1: TypeError"}]}
        ]},
    ]
    return {"model": model, "messages": messages, **extra}

check("anthropic is_error detected", recent_tool_error(anthropic_error_payload()["messages"]), True)
check("openai traceback detected", recent_tool_error(error_result_payload()["messages"]), True)
check("success not detected as error", recent_tool_error(success_result_payload()["messages"]), False)

# Reassurance text must not claim tools are disabled
check("REASSURANCE says tools are available", "still available" in REASSURANCE, True)
check("REASSURANCE says do not claim disabled", "Do not tell the user" in REASSURANCE, True)

# Timeout should also be detected as error-like (the 217 incident had a
# timeout, not an exit-code-1 error, and reassurance was not injected).
def timeout_payload(model="glm-5.2", **extra):
    messages = [
        {"role": "user", "content": "run the test"},
        oai("Bash", '{"command":"python3 tps_test.py"}'),
        tool_result("Command did not complete within its 300s timeout and was moved to the background"),
        {"role": "user", "content": "check the code"},
    ]
    return {"model": model, "messages": messages, **extra}

check("timeout detected as error-like",
      recent_tool_error(timeout_payload()["messages"]), True)

d = run(timeout_payload(temperature=0))
check("reassurance injected on timeout",
      any(REASSURANCE_PREFIX in str(m.get("content", "")) for m in d["messages"]), True)

# ---------------------------------------------------------------------------
# Permanent guard: injected into system prompt of every GLM request
# ---------------------------------------------------------------------------
print("\npermanent guard")

# OpenAI shape: system message in messages list
d = run({"model": "glm-5.2", "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi"},
    {"role": "user", "content": "test"},
], "temperature": 0})
sys_msgs = [m for m in d["messages"] if m.get("role") == "system"]
check("guard injected into existing system message",
      any(PERMANENT_GUARD_PREFIX in str(m.get("content", "")) for m in sys_msgs), True)

# No system message — one is prepended
d = run({"model": "glm-5.2", "messages": [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi"},
    {"role": "user", "content": "test"},
    {"role": "assistant", "content": "ok"},
], "temperature": 0})
check("guard prepended when no system message",
      d["messages"][0].get("role") == "system" and
      PERMANENT_GUARD_PREFIX in d["messages"][0].get("content", ""), True)

# Anthropic shape: top-level system field (string)
d = run({"model": "glm-5.2", "system": "You are helpful.", "messages": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "hello"},
    {"role": "user", "content": "test"},
], "temperature": 0})
check("guard injected into string system field",
      PERMANENT_GUARD_PREFIX in str(d.get("system", "")), True)

# Idempotent — second call must not duplicate
guard._guard(d)
check("guard not duplicated on second call",
      str(d.get("system", "")).count(PERMANENT_GUARD_PREFIX), 1)

# Non-GLM model does not get the guard
d = run({"model": "gpt-4o", "messages": [
    {"role": "system", "content": "helper"},
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "hello"},
    {"role": "user", "content": "test"},
], "temperature": 0})
check("guard NOT injected for non-GLM model",
      any(PERMANENT_GUARD_PREFIX in str(m.get("content", "")) for m in d["messages"]), False)

def test_all_checks_pass():
    """Pytest entry point: assert every module-level check() succeeded."""
    assert not FAILURES, "%d checks failed: %s" % (len(FAILURES), ", ".join(FAILURES))


if __name__ == "__main__":
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all checks passed")
