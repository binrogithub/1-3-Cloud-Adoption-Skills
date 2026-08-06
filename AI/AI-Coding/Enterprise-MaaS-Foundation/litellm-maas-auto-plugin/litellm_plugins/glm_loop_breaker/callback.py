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
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

log = logging.getLogger("glm_loop_breaker")

# Which models to guard, matched against the requested model name.
#
# The default covers both the plain GLM aliases and the `*-coding-*` aliases
# some deployments expose (`coding-auto`, `meli-coding-fast`, ...), which often
# resolve to the same GLM upstream under a name that contains no "glm" at all.
# Matching happens on the alias the caller asked for, so review this against
# your own model_list rather than assuming the default fits.
MODEL_PATTERN = re.compile(
    os.environ.get("GLM_LOOP_MODEL_PATTERN", r"glm|coding-"), re.I
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
    "SYSTEM INTERRUPT: you have now repeated the same sequence of tool calls "
    "several times and the results have not changed. Repeating it again will "
    "not work. Stop retrying. Either (a) use a different tool or a materially "
    "different approach to get the information, or (b) stop and tell the user "
    "plainly what is blocking you and what you need from them. Do not call the "
    "same tool with the same arguments again."
)


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

        messages = data.get("messages")
        if not isinstance(messages, list) or len(messages) < 4:
            return data

        seq = _tool_call_sequence(messages)
        period, reps = detect_cycle(seq)
        if not period or reps < TRIGGER:
            return data

        before = data.get("temperature")
        if before is None or float(before) < TEMP_FLOOR:
            data["temperature"] = TEMP_FLOOR
            data["top_p"] = TOP_P

        nudged = False
        if reps >= NUDGE_TRIGGER:
            _append_nudge(data)
            nudged = True

        data.setdefault("metadata", {})["glm_loop_breaker"] = {
            "period": period,
            "repetitions": reps,
            "temperature_before": before,
            "temperature_after": data.get("temperature"),
            "nudged": nudged,
        }

        log.warning(
            "glm_loop_breaker: model=%s cycle period=%d reps=%d "
            "temperature %s -> %s nudged=%s",
            model, period, reps, before, data.get("temperature"), nudged,
        )
        return data


proxy_handler_instance = GLMLoopBreaker()
