"""LLM decision: scale-out / scale-in / hold based on full metrics."""

import json
import logging
import re

from openai import OpenAI

from config import Settings
from metrics import METRIC_DEFS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a CSS cluster elasticity controller. Only scale data nodes (ess).
Return strict JSON with this schema:
{"decision":"scale_out|scale_in|hold","delta":0,"reason":"string","cooldown_minutes":30}

Rules:
- scale_out when CPU, disk, JVM heap is high, or search/indexing latency is high, or thread pool queue is building up; delta is the scale step provided in the prompt.
- scale_in only when all resource metrics are low AND scale-in is not blocked by the guard; delta is the scale step.
- hold when metrics are moderate or scale-in is blocked.
- Consider JVM heap pressure, search/indexing latency, and thread pool queue/rejection as scaling signals, not just CPU and disk.
- Never change flavor. Never scale client or master nodes.
- Return JSON only, no prose or code fences."""


def _build_user_prompt(
    metrics: dict,
    current_nodes: int,
    min_nodes: int,
    max_nodes: int,
    scale_out_step: int,
    scale_in_step: int,
    scale_in_allowed: bool,
    last_action: str | None,
    last_action_time: str | None,
) -> str:
    lines = ["Current metrics:"]
    lines.append(f"  CPU: avg={metrics.get('cpu_avg', 0)}%, max={metrics.get('cpu_max', 0)}%")
    lines.append(f"  Disk: usage={metrics.get('disk_usage_pct', 0)}%, IO_util={metrics.get('disk_io_util_max', 0)}%")
    lines.append(f"  JVM Heap: max={metrics.get('jvm_heap_max', 0)}%, avg={metrics.get('jvm_heap_avg', 0)}%")
    lines.append(f"  JVM GC: old={metrics.get('jvm_old_gc_time_avg', 0)}ms, young={metrics.get('jvm_young_gc_time_avg', 0)}ms")
    lines.append(f"  Search: QPS={metrics.get('search_rate', 0)}, latency={metrics.get('search_latency', 0)}ms")
    lines.append(f"  Indexing: TPS={metrics.get('indexing_rate', 0)}, latency={metrics.get('indexing_latency', 0)}ms")
    lines.append(f"  Thread pool queue: search={metrics.get('tp_search_queue', 0)}, write={metrics.get('tp_write_queue', 0)}, force_merge={metrics.get('tp_force_merge_queue', 0)}, refresh={metrics.get('tp_refresh_queue', 0)}, generic={metrics.get('tp_generic_queue', 0)}, management={metrics.get('tp_management_queue', 0)}")
    lines.append(f"  Thread pool rejected: search={metrics.get('tp_search_rejected', 0)}, write={metrics.get('tp_write_rejected', 0)}, force_merge={metrics.get('tp_force_merge_rejected', 0)}, refresh={metrics.get('tp_refresh_rejected', 0)}, generic={metrics.get('tp_generic_rejected', 0)}, management={metrics.get('tp_management_rejected', 0)}")
    lines.append(f"  Pending tasks: {metrics.get('pending_tasks', 0)}, HTTP connections: {metrics.get('http_open_max', 0)}")
    lines.append(f"  Cluster status: {metrics.get('cluster_status', 0)}, Load avg: {metrics.get('load_avg_max', 0)}")
    lines.append("")
    lines.append(f"Current data nodes: {current_nodes}")
    lines.append(f"Min nodes: {min_nodes}, Max nodes: {max_nodes}")
    lines.append(f"Scale-out step: {scale_out_step}, Scale-in step: {scale_in_step}")
    lines.append(f"Scale-in allowed now: {scale_in_allowed}")
    lines.append(f"Last action: {last_action} at {last_action_time}")
    lines.append("Return JSON only.")
    return "\n".join(lines)


def _parse_decision(raw: str) -> dict:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        decision = data.get("decision", "hold")
        if decision not in ("scale_out", "scale_in", "hold"):
            decision = "hold"
        delta = max(0, int(data.get("delta", 0)))
        if decision == "hold":
            delta = 0
        return {
            "decision": decision,
            "delta": delta,
            "reason": data.get("reason", ""),
            "cooldown_minutes": max(0, int(data.get("cooldown_minutes", 30))),
        }
    except (json.JSONDecodeError, ValueError):
        return {"decision": "hold", "delta": 0, "reason": f"AI response parse error: {raw[:200]}", "cooldown_minutes": 30}


def ai_decide(
    settings: Settings,
    metrics: dict,
    current_nodes: int,
    scale_in_allowed: bool,
    last_action: str | None,
    last_action_time: str | None,
) -> dict:
    """Ask LLM for scaling decision. Returns parsed decision dict."""
    if not settings.openai_api_key:
        return {"decision": "hold", "delta": 0, "reason": "OPENAI_API_KEY not configured", "cooldown_minutes": 30}

    client = OpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key)
    user_prompt = _build_user_prompt(
        metrics, current_nodes,
        settings.min_nodes, settings.max_nodes,
        settings.scale_out_step, settings.scale_in_step,
        scale_in_allowed, last_action, last_action_time,
    )
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
        return _parse_decision(raw)
    except Exception as exc:
        logger.error("ai_decide_failed: %s", exc)
        return {"decision": "hold", "delta": 0, "reason": f"AI call failed: {exc}", "cooldown_minutes": 30}
