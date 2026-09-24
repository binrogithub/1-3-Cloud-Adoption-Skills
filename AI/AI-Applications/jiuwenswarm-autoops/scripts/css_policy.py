"""Deterministic CSS scaling policy checks."""
from __future__ import annotations

from typing import Any

from css_capability import validate_plan


def _number(snapshot: dict[str, Any], name: str) -> float | None:
    value = snapshot.get("metrics", {}).get(name)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _history_ready(snapshot: dict[str, Any], policy: dict[str, Any], direction: str) -> bool:
    """Check a sustained window when the policy explicitly enables it."""
    if not policy.get("enforce_sustained_windows", False):
        return True
    history = snapshot.get("history")
    if not isinstance(history, list):
        return False
    required = int(policy.get(
        "scale_out_required_samples" if direction == "scale_out" else "scale_in_required_samples",
        3 if direction == "scale_out" else 10,
    ))
    window_minutes = int(policy.get(
        "scale_out_window_minutes" if direction == "scale_out" else "scale_in_stable_minutes",
        5 if direction == "scale_out" else 30,
    ))
    usable = [item for item in history if isinstance(item, dict) and item.get("quality") == "ok"]
    if len(usable) < required:
        return False
    latest = usable[-1].get("observed_at")
    if not latest:
        return False
    # The caller persists samples at its polling frequency. The count and
    # configured window together prevent a single old point from passing.
    return len(usable) >= min(required, max(1, window_minutes))


def _blocked(reason: str, **values: Any) -> dict[str, Any]:
    return {"decision": "hold", "status": "BLOCKED", "reason_codes": [reason], "delta": 0, **values}


def evaluate(snapshot: dict[str, Any], policy: dict[str, Any], *,
             now_epoch: float | None = None, last_scale_out_epoch: float | None = None,
             last_action_epoch: float | None = None,
             last_scale_in_epoch: float | None = None,
             history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if history is not None:
        snapshot = dict(snapshot)
        snapshot["history"] = history
    topology = snapshot.get("topology", {})
    current = topology.get("data_node_count")
    if not isinstance(current, int) or current < 1:
        return {"decision": "investigate", "status": "BLOCKED",
                "reason_codes": ["CURRENT_NODE_COUNT_UNKNOWN"], "delta": 0}
    if snapshot.get("quality") != "ok":
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["EVIDENCE_INSUFFICIENT"], "delta": 0}
    status = _number(snapshot, "cluster_status")
    if topology.get("cluster_healthy") is False or status is None or int(status) != 0:
        return {"decision": "investigate", "status": "BLOCKED",
                "reason_codes": ["CLUSTER_NOT_HEALTHY"], "delta": 0}
    topology_reasons = validate_plan(topology, policy, "scale_out", 1)
    if "ACTIVE_CLOUD_ACTION" in topology_reasons:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": topology_reasons, "delta": 0,
                "current_nodes": current}
    if topology_reasons:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": topology_reasons, "delta": 0,
                "current_nodes": current}
    if snapshot.get("metric_units_valid") is False:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["METRIC_UNIT_UNKNOWN"], "delta": 0}
    disk = _number(snapshot, "disk_usage_pct")
    cpu = _number(snapshot, "cpu_max")
    if disk is None or cpu is None:
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["CAPACITY_METRIC_MISSING"], "delta": 0}
    if last_action_epoch is not None and now_epoch is not None:
        cooldown = int(policy.get("scale_out_cooldown_minutes", 0)) * 60
        if now_epoch - last_action_epoch < cooldown:
            return {"decision": "hold", "status": "BLOCKED",
                    "reason_codes": ["SCALE_OUT_COOLDOWN_ACTIVE", "COOLDOWN_ACTIVE"],
                    "delta": 0, "current_nodes": current}
    minimum = int(policy["min_data_nodes"])
    if current < minimum:
        step = min(int(policy.get("scale_out_step", 1)), minimum - current)
        reason_codes = ["POLICY_MINIMUM_VIOLATED"]
        status = "PLANNED"
        if not policy.get("allow_scale_out", False):
            status = "RECOMMENDATION"
            reason_codes.append("WRITE_APPROVAL_REQUIRED")
        return {"decision": "scale_out", "status": status,
                "reason_codes": reason_codes, "current_nodes": current,
                "target_nodes": current + step, "delta": step}
    if (cpu >= float(policy.get("scale_out_cpu_percent", 75))
            or disk >= float(policy.get("scale_out_disk_percent", 75))):
        if not _history_ready(snapshot, policy, "scale_out"):
            return _blocked("SUSTAINED_PRESSURE_WINDOW_INSUFFICIENT", current_nodes=current)
        step = int(policy.get("scale_out_step", 1))
        target = min(int(policy["max_data_nodes"]), current + step)
        if target > current:
            reason_codes = ["SUSTAINED_RESOURCE_PRESSURE"]
            status = "PLANNED"
            if not policy.get("allow_scale_out", False):
                status = "RECOMMENDATION"
                reason_codes.append("WRITE_APPROVAL_REQUIRED")
            return {"decision": "scale_out", "status": status,
                    "reason_codes": reason_codes, "current_nodes": current,
                    "target_nodes": target, "delta": target - current}
        return {"decision": "hold", "status": "BLOCKED",
                "reason_codes": ["MAX_NODE_BOUND"], "delta": 0,
                "current_nodes": current, "target_nodes": current}
    if policy.get("allow_scale_in", False):
        if last_scale_out_epoch is not None and now_epoch is not None:
            delay = int(policy.get("scale_in_delay_after_scale_out_minutes", 0)) * 60
            if now_epoch - last_scale_out_epoch < delay:
                return _blocked("SCALE_OUT_PROTECTION", current_nodes=current)
        if last_scale_in_epoch is not None and now_epoch is not None:
            cooldown = int(policy.get("scale_in_cooldown_minutes", 0)) * 60
            if now_epoch - last_scale_in_epoch < cooldown:
                return _blocked("SCALE_IN_COOLDOWN_ACTIVE", current_nodes=current)
        if current <= int(policy["min_data_nodes"]):
            return {"decision": "hold", "status": "BLOCKED",
                    "reason_codes": ["MIN_NODE_BOUND"], "delta": 0}
        if policy.get("require_snapshot_for_scale_in", True) and snapshot.get("snapshot_available") is False:
            return _blocked("SNAPSHOT_REQUIRED", current_nodes=current)
        if policy.get("strict_scale_in_evidence", False):
            if policy.get("require_snapshot_for_scale_in", True) and snapshot.get("snapshot_available") is not True:
                return _blocked("SNAPSHOT_REQUIRED", current_nodes=current)
            topology_evidence = snapshot.get("topology", {})
            for field in ("availability_zones", "shard_health", "capacity_headroom"):
                if topology_evidence.get(field) is None:
                    return _blocked(f"{field.upper()}_UNKNOWN", current_nodes=current)
            if not _history_ready(snapshot, policy, "scale_in"):
                return _blocked("LOW_LOAD_WINDOW_INSUFFICIENT", current_nodes=current)
        if _number(snapshot, "search_rate") is None or _number(snapshot, "indexing_rate") is None:
            if policy.get("strict_scale_in_evidence", False):
                return _blocked("TRAFFIC_METRIC_UNKNOWN", current_nodes=current)
        if (_number(snapshot, "search_rate") or 0) > float(policy.get("scale_in_max_search_rate", 1000)):
            return _blocked("TRAFFIC_TOO_HIGH_FOR_SCALE_IN", current_nodes=current)
        if (_number(snapshot, "indexing_rate") or 0) > float(policy.get("scale_in_max_indexing_rate", 1000)):
            return _blocked("INDEXING_TOO_HIGH_FOR_SCALE_IN", current_nodes=current)
        if ((_number(snapshot, "search_latency") or 0) > float(policy.get("scale_in_max_search_latency", 200))
                or (_number(snapshot, "indexing_latency") or 0) > float(policy.get("scale_in_max_indexing_latency", 200))):
            return {"decision": "hold", "status": "BLOCKED",
                    "reason_codes": ["LATENCY_TOO_HIGH_FOR_SCALE_IN"], "delta": 0}
        if (_number(snapshot, "jvm_heap_max") or 0) > float(policy.get("scale_in_max_jvm_heap", 85)):
            return {"decision": "hold", "status": "BLOCKED",
                    "reason_codes": ["JVM_HEAP_TOO_HIGH_FOR_SCALE_IN"], "delta": 0}
        if cpu <= float(policy.get("scale_in_cpu_percent", 30)) and disk <= float(policy.get("scale_in_disk_percent", 65)):
            step = int(policy.get("scale_in_step", 1))
            target = max(int(policy["min_data_nodes"]), current - step)
            provider_reasons = validate_plan(topology, policy, "scale_in", current - target,
                                             target_nodes=target)
            if provider_reasons:
                return {"decision": "hold", "status": "BLOCKED",
                        "reason_codes": provider_reasons, "delta": 0,
                        "current_nodes": current, "target_nodes": target}
            return {"decision": "scale_in", "status": "PLANNED",
                    "reason_codes": ["SUSTAINED_LOW_LOAD"], "current_nodes": current,
                    "target_nodes": target, "delta": current - target}
    return {"decision": "hold", "status": "HOLD", "reason_codes": ["NO_POLICY_TRIGGER"], "delta": 0,
            "current_nodes": current}
