"""glm_loop_breaker — request-side circuit breaker for GLM agent tool-call loops.

Why this exists
---------------
GLM self-reinforces off its own context. Once the message history contains a few
identical agent iterations, the model stops exploring and reproduces the pattern
verbatim — the agent burns turns forever on a step that is not working.

Two conditions decide whether it happens. Both were measured against a live
glm-5.2 route with a synthetic stuck-page agent, starting from a context seeded
with three completed loop iterations:

    provider thinking disabled          12 / 12 runs looped
    provider thinking enabled            1 /  6 runs looped

    temperature 0.0                      3 /  3 runs looped
    temperature 0.3                      2 /  3 runs looped
    temperature 1.0                      0 /  3 runs looped

Thinking is the dominant factor: deliberation budget is what lets the model
notice "I have tried this three times and nothing changed". With thinking off,
the model has no such budget, and at temperature 0 repeating the most similar
span already in context is the deterministic best continuation, so the client
cannot escape on its own.

**The primary fix is to keep provider thinking enabled on GLM routes** — see
`docs/PRD-glm-loop-breaker.md`. `anthropic_reasoning_filter` in this same kit is
what makes that safe for Claude Code clients: it keeps thinking on upstream and
strips the blocks from the response.

This plugin is the second line of defence, for the residual case and for
deployments that disable thinking deliberately to control cost or latency.

What it does
------------
Pre-call hook. Fingerprints the assistant tool calls already in the request and
checks whether the tail is a repeating cycle of period 1..3. On detection it
escalates:

    level 1 (cycle seen `trigger` times)   raise temperature to a floor, set top_p
    level 2 (cycle persists)               also append a redirect instruction

It never rejects a request and never raises: any internal error is swallowed and
the request passes through untouched.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

log = logging.getLogger("glm_loop_breaker")

# --- Model registry (PRD-multi-family-routing-v2 §3) --------------------------
# One source of truth for model capabilities, replacing the per-plugin
# _classify_model_family regex. The model ID is a primary key: exact lookup.
# Each plugin loads model_registry.json independently (standalone modules).
_FALLBACK_PROFILE = {
    "family": "other", "loop_breaker": False, "affinity": False,
    "reasoning_filter": False, "sampling_params": "pass",
}


def _registry_path():
    env = os.getenv("MODEL_REGISTRY_FILE")
    if env:
        return Path(env)
    cb = Path(__file__)
    for cand in (cb.with_name("model_registry.json"), cb.parents[1] / "model_registry.json"):
        if cand.exists():
            return cand
    return cb.with_name("model_registry.json")


def _load_registry():
    try:
        with _registry_path().open(encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict) or "models" not in raw:
            raise ValueError("registry missing 'models'")
        return raw
    except Exception:
        return {"fallback": dict(_FALLBACK_PROFILE), "models": {}}


REGISTRY = _load_registry()


def _model_profile(model_name):
    """Resolve a model ID to its capability profile (exact registry lookup).

    Unknown IDs return the inert fallback (loop_breaker False) and log a
    warning — a registry miss is a config bug (PRD-deployment-reconciliation P1-2).
    """
    name = str(model_name or "")
    models = REGISTRY.get("models") or {}
    if name in models:
        return models[name]
    if name:
        log.warning("model_registry miss: %s (using inert fallback)", name)
    return REGISTRY.get("fallback") or _FALLBACK_PROFILE


# Which models to guard at all, matched against the requested model name.
#
# The breaker detects cycles in the request history. A loop laid down on GLM
# survives a user switch to sonnet/haiku (the history travels with the
# request), so the guard runs on all claude-* families plus the GLM coding
# aliases. The SAMPLING override (temperature/top_p) is gated separately on
# the registry profile's loop_breaker flag — only models that accept sampling
# params get it; sonnet and haiku
# reject non-default sampling params with a 400 (PRD §3, Item 2).
#
# This pattern is the "should this model be guarded at all" gate, kept for
# backward compat (GLM_LOOP_MODEL_PATTERN). The family classifier decides what
# the guard *does*. Matching happens on the alias the caller asked for, so
# review this against your own model_list rather than assuming the default fits.
MODEL_PATTERN = re.compile(
    os.environ.get("GLM_LOOP_MODEL_PATTERN", r"glm|coding-|claude-"), re.I
)

# A cycle must repeat this many times before we act.
TRIGGER = int(os.environ.get("GLM_LOOP_TRIGGER", "3"))

# Repeats beyond this also get the redirect instruction.
NUDGE_TRIGGER = int(os.environ.get("GLM_LOOP_NUDGE_TRIGGER", "4"))

# Longest cycle we look for. read_page -> sleep -> read_page -> sleep is period 2.
MAX_PERIOD = int(os.environ.get("GLM_LOOP_MAX_PERIOD", "3"))

# Temperature forced on a looping request. 1.0 cleared the loop in every trial
# run; 0.7 is the conservative default so guarded traffic stays close to the
# caller's intent.
TEMP_FLOOR = float(os.environ.get("GLM_LOOP_TEMP_FLOOR", "0.7"))
TOP_P = float(os.environ.get("GLM_LOOP_TOP_P", "0.95"))

NUDGE = (
    "You have repeated the same tool call several times and the result has not "
    "changed. Repeating it again will not help. Try a different tool or a "
    "materially different approach, or stop and tell the user plainly what is "
    "blocking you and what you need from them. Your tools are still available."
)

# Distinctive prefix of NUDGE used for the once-per-session idempotency check.
# A full-string match is not required: the text may be merged into a longer
# user turn, so we look for this stable leading fragment instead.
NUDGE_PREFIX = "You have repeated the same tool call"

# Injected when a recent tool result was an error, to counter GLM's tendency to
# hallucinate "tools are disabled" after a single failure and refuse to retry.
# This is NOT the loop-breaker nudge — it fires on the FIRST error, not after
# a cycle. The message is merged into the last user turn (same as NUDGE) so it
# does not break role alternation.
REASSURANCE = (
    "A previous tool call returned an error. This is normal — the tool is still "
    "available and working. Fix the issue in your tool input and call the tool "
    "again. Do not tell the user that tools are disabled, blocked, or "
    "unavailable, because they are not."
)
REASSURANCE_PREFIX = "A previous tool call returned an error"

# Permanent guard injected into the system prompt of every GLM request.
# This is the primary defence against the "tools are disabled" hallucination:
# it does not wait for an error to occur, it pre-emptively tells the model
# the invariant every turn.  Short, declarative, and impossible to misread.
PERMANENT_GUARD = (
    "Your tools are never disabled, blocked, or suspended by the system. "
    "If a tool call fails, times out, or returns an error, that is a normal "
    "part of debugging — fix the input and call the tool again. Never tell "
    "the user that tools are unavailable, disabled, or that you cannot call "
    "tools, because none of those things are true."
)
PERMANENT_GUARD_PREFIX = "Your tools are never disabled"


def _inject_permanent_guard(data: dict) -> None:
    """Merge PERMANENT_GUARD into the system prompt of the request.

    LiteLLM passes the system prompt either as a top-level ``system`` field
    (Anthropic shape) or as the first message with role ``system`` (OpenAI
    shape).  We handle both, and skip if the guard is already present (e.g.
    the request was double-processed).
    """
    # Check if already present — use str() on the relevant fields, not
    # json.dumps(data), because data can contain non-serialisable objects
    # (CustomStreamWrapper, callbacks, etc.) that raise ValueError.
    _existing = str(data.get("system", ""))
    for m in data.get("messages", []) or []:
        if isinstance(m, dict):
            _existing += " " + str(m.get("content", ""))
    if PERMANENT_GUARD_PREFIX in _existing:
        return

    # Anthropic shape: top-level "system" field (string or list of blocks)
    system = data.get("system")
    if isinstance(system, str):
        data["system"] = f"{system}\n\n{PERMANENT_GUARD}" if system else PERMANENT_GUARD
        return
    if isinstance(system, list):
        system.append({"type": "text", "text": PERMANENT_GUARD})
        return

    # OpenAI shape: first message with role "system"
    messages = data.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str):
                    msg["content"] = f"{content}\n\n{PERMANENT_GUARD}" if content else PERMANENT_GUARD
                elif isinstance(content, list):
                    content.append({"type": "text", "text": PERMANENT_GUARD})
                return
        # No system message — prepend one
        messages.insert(0, {"role": "system", "content": PERMANENT_GUARD})


def _fingerprint(name: str, arguments: Any) -> str:
    """Identify a tool call by name plus arguments, ignoring the call id.

    Call ids are freshly generated every turn, so they must not enter the hash
    or every iteration looks unique.
    """
    if isinstance(arguments, (dict, list)):
        try:
            arguments = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            arguments = repr(arguments)
    raw = f"{name}|{arguments or ''}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:12]


def _result_fingerprint(content: Any) -> str:
    """Fingerprint a tool result so the breaker can tell a stuck loop (same
    result every time) from an active debug session (same call, different
    error/output each time).

    The result body can be large and varied (stdout, exit codes, tracebacks),
    so we hash a normalised prefix — enough to distinguish changing results
    without being defeated by trivial noise (timestamps, ANSI colours).
    """
    if isinstance(content, list):
        # Anthropic shape: [{"type": "text", "text": "..."}, ...]
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, dict) and block.get("type") == "tool_use_error":
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        raw = "\n".join(parts)
    elif isinstance(content, str):
        raw = content
    else:
        raw = repr(content)
    # Strip ANSI escape codes so coloured output doesn't create false diversity.
    raw = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    return hashlib.sha1(raw[:512].encode("utf-8", "replace")).hexdigest()[:12]


def _tool_call_sequence(messages: list) -> list:
    """Fingerprints of assistant tool calls, oldest first.

    Handles the OpenAI shape (`tool_calls`) and the Anthropic shape
    (`content` blocks of `type: tool_use`), since this gateway serves both.
    """
    seq = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue

        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            seq.append(_fingerprint(fn.get("name", ""), fn.get("arguments")))

        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    seq.append(_fingerprint(block.get("name", ""), block.get("input")))
    return seq


def _tool_result_sequence(messages: list) -> list:
    """Fingerprints of tool results, oldest first, aligned 1:1 with
    ``_tool_call_sequence``.

    A result slot is ``None`` when the corresponding call has no result yet
    (the assistant just issued it) or when the message shapes don't line up
    (malformed history).  ``None`` markers make ``_paired_sequence`` treat
    that iteration as non-repeating, which is the safe default.
    """
    seq = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")

        # OpenAI shape: role "tool", content is the result string.
        if role == "tool":
            seq.append(_result_fingerprint(msg.get("content", "")))
            continue

        # Anthropic shape: role "user" with content blocks of type "tool_result".
        if role == "user":
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        seq.append(_result_fingerprint(block.get("content", "")))
    return seq


def _paired_sequence(messages: list) -> list:
    """Combined call+result fingerprints, oldest first.

    Each entry is ``call_fp + ":" + result_fp``.  When a call has no matching
    result (just issued, or malformed history) the result half is ``"_"`` so
    the pair can never match a prior completed iteration — a pending call is
    not evidence of a stuck loop.

    This is what ``_guard`` feeds to ``detect_cycle``: a cycle now requires
    *both* the tool call and its result to repeat, so an active debug session
    (same command, different error each time) does not trip the breaker.
    """
    calls = _tool_call_sequence(messages)
    results = _tool_result_sequence(messages)

    # Results can outnumber calls when the history has tool messages without
    # preceding assistant tool_calls (edge case in some clients).  We align by
    # position from the start; extra results on either side are ignored by the
    # cycle detector because the paired entries won't match.
    pairs = []
    for i, call_fp in enumerate(calls):
        result_fp = results[i] if i < len(results) else "_"
        pairs.append(f"{call_fp}:{result_fp}")
    return pairs


def detect_cycle(seq: list, max_period: int = MAX_PERIOD) -> tuple:
    """Longest run of a repeating block at the tail of `seq`.

    Returns (period, repetitions). (0, 0) when the tail is not cyclic.

    Checking only consecutive duplicates is not enough: the production failure
    alternated between two tool calls, which a duplicate check walks past.
    """
    best = (0, 0)
    for period in range(1, max_period + 1):
        if len(seq) < period * 2:
            break
        reps = 1
        while True:
            span = period * (reps + 1)
            if span > len(seq):
                break
            tail = seq[-span:]
            if all(tail[i] == tail[i % period] for i in range(span)):
                reps += 1
            else:
                break
        if reps >= 2 and reps > best[1]:
            best = (period, reps)
    return best


def _nudge_present(data: dict) -> bool:
    """Has the redirect instruction already been injected this session?

    The nudge must be added once per session, not once per looping turn — over a
    long loop appending it every turn accumulates copies that waste tokens and
    dilute the signal. We detect a prior injection with a cheap substring check
    on the serialized content of every message, using NUDGE's distinctive prefix
    so a full-string match is not required (the text may have been merged into a
    longer user turn).
    """
    messages = data.get("messages")
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if NUDGE_PREFIX in str(msg.get("content", "")):
            return True
    return False


def _append_nudge(data: dict) -> None:
    """Add the redirect instruction without breaking role alternation.

    Anthropic-shaped payloads reject two consecutive user turns, so when the
    last message is already a user turn the text is merged into it.
    """
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return

    last = messages[-1]
    if isinstance(last, dict) and last.get("role") == "user":
        content = last.get("content")
        if isinstance(content, str):
            last["content"] = f"{content}\n\n{NUDGE}"
            return
        if isinstance(content, list):
            content.append({"type": "text", "text": NUDGE})
            return

    messages.append({"role": "user", "content": NUDGE})


def _recent_tool_error(messages: list) -> bool:
    """True if the most recent tool result in the history is an error.

    Checks the tail of the message list for the last tool result (OpenAI
    role=tool or Anthropic tool_result block) and returns True if it looks
    like an error: exit code != 0, "Traceback", "Error", "is_error": true,
    or a tool_use_error block.
    """
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")

        # OpenAI shape
        if role == "tool":
            return _result_is_error(msg.get("content", ""))

        # Anthropic shape
        if role == "user":
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        if block.get("is_error"):
                            return True
                        return _result_is_error(block.get("content", ""))
            # Plain user text — no tool result in this message, keep scanning
    return False


def _result_is_error(content) -> bool:
    """Heuristic: does this tool result content look like an error?"""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "tool_use_error":
                    return True
                if block.get("is_error"):
                    return True
                txt = str(block.get("text", ""))
                if _error_keywords(txt):
                    return True
        return False
    if isinstance(content, str):
        return _error_keywords(content)
    return False


def _error_keywords(text: str) -> bool:
    """Cheap keyword check for error-like tool output.

    Includes timeout phrasing — a timed-out tool call is not a success, and
    GLM treats it as a reason to give up just like an error.
    """
    if not text:
        return False
    lower = text[:500].lower()
    return any(kw in lower for kw in (
        "exit code 1", "exit code 2", "traceback", "error:",
        "exception", "failed", "is_error",
        "did not complete", "timed out", "timeout",
    ))


def _reassurance_present(data: dict) -> bool:
    """Has the reassurance already been injected this session?"""
    messages = data.get("messages")
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if isinstance(msg, dict) and REASSURANCE_PREFIX in str(msg.get("content", "")):
            return True
    return False


def _append_reassurance(data: dict) -> None:
    """Inject the reassurance text, merged into the last user turn."""
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return
    last = messages[-1]
    if isinstance(last, dict) and last.get("role") == "user":
        content = last.get("content")
        if isinstance(content, str):
            last["content"] = f"{content}\n\n{REASSURANCE}"
            return
        if isinstance(content, list):
            content.append({"type": "text", "text": REASSURANCE})
            return
    messages.append({"role": "user", "content": REASSURANCE})


class GLMLoopBreaker(CustomLogger):
    async def async_pre_call_hook(
        self, user_api_key_dict, cache, data: dict, call_type: str
    ):
        try:
            return self._guard(data)
        except Exception:  # noqa: BLE001 - a guard must never break a request
            log.exception("glm_loop_breaker: passing request through unmodified")
            return data

    def _guard(self, data: dict) -> dict:
        model = str(data.get("model") or "")
        if not MODEL_PATTERN.search(model):
            return data

        # ── Permanent guard: pre-empt the "tools are disabled" hallucination ─
        # Injected into the system prompt of EVERY request, not just on error.
        # This is the primary defence — the reassurance below is a secondary
        # reinforcement for the specific moment after a failure.
        _inject_permanent_guard(data)

        # The profile decides what the guard does, not whether it runs. The
        # cycle is in the history regardless of which model now serves it, so
        # we detect and record on every model MODEL_PATTERN matches. But the
        # sampling override (temperature/top_p) is gated on the registry's
        # loop_breaker flag: Sonnet and Haiku reject non-default sampling
        # parameters with a 400 (PRD §3, Item 2 / v2 §3).
        profile = _model_profile(model)
        family = profile.get("family", "other")

        messages = data.get("messages")
        if not isinstance(messages, list) or len(messages) < 4:
            return data

        # ── Reassurance: counter the "tools are disabled" hallucination ──────
        # GLM has a observed behaviour where a single tool error causes it to
        # claim "tools are temporarily disabled" and refuse to retry.  This
        # fires on the FIRST error (no cycle needed), injecting a short
        # correction so the model knows its tools still work.  Once per session.
        reassured = False
        if _recent_tool_error(messages) and not _reassurance_present(data):
            _append_reassurance(data)
            reassured = True
            log.warning("glm_loop_breaker: reassurance injected (recent tool error)")

        # ── Cycle detection ─────────────────────────────────────────────────
        # Detect cycles on the combined call+result sequence, not calls alone.
        # A repeating call with *changing* results is an active debug session,
        # not a stuck loop — the model is iterating on a fix and each attempt
        # produces a different error.  Only when both the call and its result
        # repeat does the breaker fire.
        seq = _paired_sequence(messages)
        period, reps = detect_cycle(seq)
        if not period or reps < TRIGGER:
            return data

        before = data.get("temperature")
        # Sampling override only for models whose profile opts in (loop_breaker).
        # On sonnet/haiku we detect the cycle and record metadata but leave
        # temperature/top_p untouched so the request does not 400.
        if profile.get("loop_breaker") and (before is None or float(before) < TEMP_FLOOR):
            data["temperature"] = TEMP_FLOOR
            data["top_p"] = TOP_P

        # The nudge is a user message, not a sampling parameter, so it is safe
        # on every family. Keep it on anthropic too (PRD §6 Item 2: prefer keep
        # the nudge, skip only the sampling override).
        nudged = False
        if reps >= NUDGE_TRIGGER and not _nudge_present(data):
            _append_nudge(data)
            nudged = True

        # A caller may send `"metadata": null`, in which case setdefault keeps the
        # None and assigning into it raises. Losing the audit record would also
        # make the intervention uncountable in spend logs.
        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            data["metadata"] = meta
        meta["glm_loop_breaker"] = {
            "period": period,
            "repetitions": reps,
            "model_family": family,
            "temperature_before": before,
            "temperature_after": data.get("temperature"),
            "nudged": nudged,
        }

        log.warning(
            "glm_loop_breaker: model=%s family=%s cycle period=%d reps=%d "
            "temperature %s -> %s nudged=%s",
            model, family, period, reps, before, data.get("temperature"), nudged,
        )
        return data


proxy_handler_instance = GLMLoopBreaker()
