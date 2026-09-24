"""Headless client for the dedicated LLMWiki JiuwenSwarm instance.

Uses only the public CLI: `jiuwenswarm chat --mode code --jsonl`. Event shape verified on
247 (2026-09-23): {"type":"event","event":"chat.delta|chat.final|chat.usage_metadata|
chat.tool_call|chat.tool_result|...","payload":{...}}. Exit codes: 0 ok, 1 business failure,
3 gateway down.
"""
from __future__ import annotations

import ast
import json
import re
import os
import subprocess
import time
from dataclasses import dataclass, field

from .config import Config


class JiuwenError(RuntimeError):
    def __init__(self, kind: str, msg: str):
        super().__init__(f"{kind}: {msg}")
        self.kind = kind          # gateway_down | agent_failed | timeout | role_not_dispatched | not_installed


@dataclass
class RunResult:
    content: str
    session_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: float | None = None
    latency_ms: float | None = None
    tool_calls: list[dict] = field(default_factory=list)
    role_dispatched: bool = False
    main_final: str = ""
    reasoning: str = ""                  # chat.reasoning stream (display only, never stored)
    events: int = 0


def build_env(cfg: Config) -> dict:
    env = dict(os.environ)
    env["JIUWENSWARM_DATA_DIR"] = str(cfg.path(cfg.jiuwen.data_dir))
    env["GATEWAY_PORT"] = str(cfg.jiuwen.gateway_port)
    return env


def run(cfg: Config, prompt: str, on_event=None) -> RunResult:
    """Headless run; `on_event(parsed_event_dict)` fires per event line as it arrives
    (streaming mode, PRD V2 R2-5). Exit-code semantics unchanged."""
    j = cfg.jiuwen
    argv = [j.bin, "chat", "--mode", j.mode, "--jsonl", "--timeout", str(j.timeout_s), prompt]
    deadline = j.timeout_s + 30
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=build_env(cfg))
    except FileNotFoundError as e:
        raise JiuwenError("not_installed", j.bin) from e
    lines: list[str] = []
    rc = -1
    try:
        for line in p.stdout:                       # type: ignore[union-attr]
            lines.append(line)
            if on_event is not None:
                ev = _try_event(line)
                if ev is not None:
                    try:
                        on_event(ev)
                    except Exception:               # a UI callback must never kill the run
                        pass
            if time.monotonic() - t0 > deadline:
                p.kill()
                raise JiuwenError("timeout", f"no result after {deadline}s")
        rc = p.wait(timeout=30)
    except subprocess.TimeoutExpired as e:
        p.kill()
        raise JiuwenError("timeout", f"no result after {deadline}s") from e
    finally:
        for stream in (p.stdout, p.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass
    stderr = ""
    try:
        stderr = p.stderr.read() if p.stderr else ""     # type: ignore[union-attr]
    except Exception:
        pass
    if rc == 3:
        raise JiuwenError("gateway_down", f"LLMWiki gateway on port {j.gateway_port} unreachable")
    res = parse_events(lines, role=j.role)
    if rc != 0:
        raise JiuwenError("agent_failed", (res.content or stderr or "").strip()[:500])
    if j.require_role_dispatch and not res.role_dispatched:
        raise JiuwenError("role_not_dispatched",
                          f"answer did not come from the '{j.role}' sub-agent; refusing it")
    return res


def _try_event(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return None
    return ev if isinstance(ev, dict) else None


def parse_events(lines, role: str = "llmwiki") -> RunResult:
    res = RunResult(content="")
    deltas: list[str] = []
    role_outputs: list[str] = []
    final: str | None = None
    error: str | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        res.events += 1
        # --json mode emits a single {"ok":..., "content":...}
        if "ok" in ev and "event" not in ev:
            if ev.get("ok"):
                final = ev.get("content", "")
            else:
                error = ev.get("error", "")
            continue
        name = ev.get("event", "")
        pl = ev.get("payload") or {}
        res.session_id = pl.get("session_id", res.session_id)
        if name == "chat.delta":
            deltas.append(pl.get("content", ""))
        elif name == "chat.reasoning":
            res.reasoning += pl.get("content", "")
        elif name == "chat.final":
            final = pl.get("content", "")
        elif name == "chat.error":
            error = pl.get("content") or pl.get("error") or json.dumps(pl)[:300]
        elif name == "chat.tool_call":
            res.tool_calls.append(pl.get("tool_call") or pl)
        elif name == "chat.tool_result":
            out = _role_output(pl, role)
            if out is not None:
                res.role_dispatched = True
                role_outputs.append(out)
        elif name == "chat.usage_metadata":
            meta = pl.get("metadata") or {}
            um = meta.get("usage_metadata") or {}
            res.input_tokens += int(um.get("input_tokens") or 0)
            res.output_tokens += int(um.get("output_tokens") or 0)
            res.ttft_ms = meta.get("ttft_ms", res.ttft_ms)
            res.latency_ms = meta.get("total_latency_ms", res.latency_ms)
    res.main_final = final if final is not None else "".join(deltas)
    # The role's own output is authoritative; the main agent's final text may paraphrase it.
    res.content = role_outputs[-1] if role_outputs else res.main_final
    if error and not res.content:
        res.content = f"[agent error] {error}"
    return res


_RESULT_RE = re.compile(r"^success=(True|False) data=(\{.*\}) error=(.*)$", re.S)


def _role_output(payload: dict, role: str) -> str | None:
    """Return the sub-agent output if this tool_result is a successful dispatch to `role`.

    Observed on 247 (code mode): tool_name "Agent", result is a Python repr string
      "success=True data={'output': '...', 'agent_id': 'llmwiki'} error=None".
    Agent mode ("task_tool") is recognised too, but in 0.2.3 it fails before running the role.
    """
    if payload.get("tool_name") not in ("Agent", "task_tool"):
        return None
    result = payload.get("result")
    data = None
    if isinstance(result, dict):
        data = result.get("data", result)
        ok = result.get("success", True)
    elif isinstance(result, str):
        m = _RESULT_RE.match(result.strip())
        if not m:
            return None
        ok = m.group(1) == "True"
        try:
            data = ast.literal_eval(m.group(2))
        except (ValueError, SyntaxError):
            return None
    else:
        return None
    if not ok or not isinstance(data, dict):
        return None
    if data.get("agent_id") != role or not isinstance(data.get("output"), str):
        return None
    return data["output"]
