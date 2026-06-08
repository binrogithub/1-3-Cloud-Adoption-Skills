"""Cluster health check and AI-powered diagnosis."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI

from config import Settings
from metrics import CesClient, collect_diagnosis_metrics, interpret_cluster_status, DIAGNOSIS_METRIC_DEFS
from css_executor import CssClient, get_cluster_detail

logger = logging.getLogger(__name__)

DIAGNOSIS_SYSTEM_PROMPT = """You are a CSS (Cloud Search Service / Elasticsearch) cluster operations expert.
The cluster is currently unhealthy. Analyze the root cause and provide actionable fix suggestions.

Return strict JSON with this schema:
{
  "root_cause": "string - primary root cause analysis",
  "severity": "critical|warning|info",
  "suggestions": ["suggestion1", "suggestion2"],
  "auto_fix_available": true/false,
  "auto_fix_action": "string - description of auto-fix action, or empty string"
}

Rules:
- Be specific about which node or metric is causing the issue.
- suggestions should be ordered by priority (most likely fix first).
- auto_fix_available=true only if there is a safe, reversible automated action.
- auto_fix_action should describe the exact operation, e.g. "restart_node:instance_id_xxx".
- Return JSON only, no prose or code fences."""


def check_cluster_health(
    css_client: CssClient,
    ces_client: CesClient,
    cluster_id: str,
    metrics: dict,
) -> dict:
    """Check cluster health from metrics and CSS API. Returns health info dict."""
    # Status from CES metric
    status_info = interpret_cluster_status(metrics.get("cluster_status", 3))

    # Status from CSS cluster detail API
    try:
        cluster_detail = get_cluster_detail(css_client, cluster_id)
        api_status = cluster_detail.get("status", "unknown")
        instances = cluster_detail.get("instances", [])
    except Exception as exc:
        logger.error("cluster_detail_failed: %s", exc)
        api_status = "unknown"
        instances = []

    # Determine unhealthy nodes
    unhealthy_nodes = []
    for inst in instances:
        if inst.get("status", "") not in ("running", "ACTIVE"):
            unhealthy_nodes.append({
                "id": inst.get("id", ""),
                "name": inst.get("name", ""),
                "type": inst.get("type", ""),
                "status": inst.get("status", ""),
            })

    is_healthy = status_info["healthy"] and api_status in ("running", "available", "green") and len(unhealthy_nodes) == 0

    return {
        "healthy": is_healthy,
        "ces_status": status_info,
        "api_status": api_status,
        "unhealthy_nodes": unhealthy_nodes,
        "node_count": len(instances),
    }


def collect_diagnosis_context(
    ces_client: CesClient,
    css_client: CssClient,
    cluster_id: str,
    metrics: dict,
    health: dict,
) -> dict:
    """Collect full diagnostic context when cluster is unhealthy."""
    # Extra CES metrics for diagnosis
    diag_metrics = collect_diagnosis_metrics(ces_client, cluster_id)

    # Abnormal metrics from regular collection
    abnormal = {}
    if metrics.get("cpu_avg", 0) >= 80:
        abnormal["cpu_avg"] = metrics["cpu_avg"]
    if metrics.get("cpu_max", 0) >= 90:
        abnormal["cpu_max"] = metrics["cpu_max"]
    if metrics.get("disk_usage_pct", 0) >= 85:
        abnormal["disk_usage_pct"] = metrics["disk_usage_pct"]
    if metrics.get("jvm_heap_max", 0) >= 85:
        abnormal["jvm_heap_max"] = metrics["jvm_heap_max"]
    if metrics.get("jvm_heap_avg", 0) >= 80:
        abnormal["jvm_heap_avg"] = metrics["jvm_heap_avg"]
    if metrics.get("search_latency", 0) >= 500:
        abnormal["search_latency"] = metrics["search_latency"]
    if metrics.get("indexing_latency", 0) >= 200:
        abnormal["indexing_latency"] = metrics["indexing_latency"]

    # Thread pool rejections
    rejections = {}
    for key, val in metrics.items():
        if "rejected" in key and val > 0:
            rejections[key] = val

    # Thread pool queue buildup
    queue_buildup = {}
    for key, val in metrics.items():
        if "queue" in key and val > 50:
            queue_buildup[key] = val

    return {
        "cluster_status": health["ces_status"],
        "api_status": health["api_status"],
        "unhealthy_nodes": health["unhealthy_nodes"],
        "abnormal_metrics": abnormal,
        "diagnosis_metrics": diag_metrics,
        "thread_pool_rejections": rejections,
        "thread_pool_queue_buildup": queue_buildup,
        "pending_tasks": metrics.get("pending_tasks", 0),
        "jvm_heap_max": metrics.get("jvm_heap_max", 0),
        "jvm_heap_avg": metrics.get("jvm_heap_avg", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_diagnosis_prompt(context: dict) -> str:
    lines = [
        f"集群 CES 状态: {context['cluster_status']}",
        f"集群 API 状态: {context['api_status']}",
    ]
    if context["unhealthy_nodes"]:
        lines.append("异常节点:")
        for node in context["unhealthy_nodes"]:
            lines.append(f"  - {node.get('name','?')} (type={node.get('type','?')}, status={node.get('status','?')})")
    if context["abnormal_metrics"]:
        lines.append("异常指标:")
        for k, v in context["abnormal_metrics"].items():
            lines.append(f"  - {k} = {v}")
    if context["thread_pool_rejections"]:
        lines.append("线程池拒绝:")
        for k, v in context["thread_pool_rejections"].items():
            lines.append(f"  - {k} = {v}")
    if context["thread_pool_queue_buildup"]:
        lines.append("线程池排队堆积:")
        for k, v in context["thread_pool_queue_buildup"].items():
            lines.append(f"  - {k} = {v}")
    if context["pending_tasks"] > 0:
        lines.append(f"主节点待处理任务: {context['pending_tasks']}")
    if context["jvm_heap_max"] > 0:
        lines.append(f"JVM 堆最大使用率: {context['jvm_heap_max']}%")
    if context["diagnosis_metrics"]:
        lines.append("诊断补充指标:")
        for k, v in context["diagnosis_metrics"].items():
            if v > 0:
                lines.append(f"  - {k} = {v}")
    lines.append("\nReturn JSON only.")
    return "\n".join(lines)


def _parse_diagnosis(raw: str) -> dict:
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
        severity = data.get("severity", "warning")
        if severity not in ("critical", "warning", "info"):
            severity = "warning"
        return {
            "root_cause": data.get("root_cause", ""),
            "severity": severity,
            "suggestions": data.get("suggestions", []),
            "auto_fix_available": bool(data.get("auto_fix_available", False)),
            "auto_fix_action": data.get("auto_fix_action", ""),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "root_cause": f"AI response parse error: {raw[:200]}",
            "severity": "warning",
            "suggestions": [],
            "auto_fix_available": False,
            "auto_fix_action": "",
        }


def ai_diagnose(settings: Settings, context: dict) -> dict:
    """Ask LLM for cluster diagnosis. Returns parsed diagnosis dict."""
    if not settings.openai_api_key or not settings.ai_diagnose_enabled:
        return {
            "root_cause": "AI diagnosis disabled or no API key",
            "severity": "info",
            "suggestions": [],
            "auto_fix_available": False,
            "auto_fix_action": "",
        }

    client = OpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key)
    user_prompt = _build_diagnosis_prompt(context)
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
        return _parse_diagnosis(raw)
    except Exception as exc:
        logger.error("ai_diagnose_failed: %s", exc)
        return {
            "root_cause": f"AI call failed: {exc}",
            "severity": "warning",
            "suggestions": [],
            "auto_fix_available": False,
            "auto_fix_action": "",
        }
