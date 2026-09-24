"""Provider-aware CSS scaling constraints."""
from __future__ import annotations

from typing import Any


def active_action(topology: dict[str, Any]) -> bool:
    """Return whether CSS reports an action that must be reconciled first."""
    return bool(topology.get("actions") or topology.get("action_progress"))


def constraints(policy: dict[str, Any], capability: dict[str, Any] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {}
    configured = policy.get("provider_constraints")
    if isinstance(configured, dict):
        value.update(configured)
    if isinstance(capability, dict):
        value.update(capability)
    return value


def minimum_current_nodes_for_scale_in(delta: int, rules: dict[str, Any]) -> int:
    """Calculate the minimum source topology required for a shrink."""
    explicit = rules.get("min_current_nodes_for_scale_in")
    minimum = int(explicit) if isinstance(explicit, int) else 1
    if rules.get("shrink_rule") == "reduced_nodes_less_than_half":
        minimum = max(minimum, (2 * int(delta)) + 1)
    return max(minimum, int(delta) + 1)


def validate_plan(topology: dict[str, Any], policy: dict[str, Any], direction: str,
                  delta: int, target_nodes: int | None = None,
                  capability: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic reason codes; an empty list means valid."""
    reasons: list[str] = []
    if delta < 1:
        return ["DELTA_INVALID"]
    if topology.get("cluster_healthy") is False:
        reasons.append("CLUSTER_NOT_HEALTHY")
    provider = constraints(policy, capability)
    if active_action(topology) and provider.get("require_no_active_action", True) is not False:
        reasons.append("ACTIVE_CLOUD_ACTION")
    current = topology.get("data_node_count")
    if not isinstance(current, int) or current < 1:
        reasons.append("CURRENT_NODE_COUNT_UNKNOWN")
        return reasons
    if "instances" in topology:
        ess_instances = [item for item in topology.get("instances", [])
                         if item.get("type") == "ess"]
        if len(ess_instances) != current or any(item.get("status") != "200" for item in ess_instances):
            reasons.append("ESS_NODE_NOT_AVAILABLE")
    if target_nodes is not None and target_nodes < 1:
        reasons.append("TARGET_NODE_COUNT_INVALID")
    supported_directions = provider.get("supported_directions")
    if isinstance(supported_directions, list) and direction not in supported_directions:
        reasons.append("PROVIDER_DIRECTION_UNSUPPORTED")
    if target_nodes is not None:
        expected_target = current + delta if direction == "scale_out" else current - delta
        if target_nodes != expected_target:
            reasons.append("TARGET_DELTA_MISMATCH")
    if direction == "scale_out":
        if target_nodes is not None and target_nodes > int(policy["max_data_nodes"]):
            reasons.append("MAX_NODE_BOUND")
        if delta > int(policy.get("scale_out_step", 1)):
            reasons.append("STEP_LIMIT")
    elif direction == "scale_in":
        if target_nodes is not None and target_nodes < int(policy["min_data_nodes"]):
            reasons.append("MIN_NODE_BOUND")
        if delta > int(policy.get("scale_in_step", 1)):
            reasons.append("STEP_LIMIT")
        if current < minimum_current_nodes_for_scale_in(delta, provider):
            reasons.append("PROVIDER_SCALE_IN_CONSTRAINT")
    else:
        reasons.append("DIRECTION_INVALID")
    return reasons


def classify_api_error(error: str) -> dict[str, Any]:
    """Classify known CSS errors without forcing retries."""
    text = str(error)
    if "CSS.0011" in text or "status_code:409" in text:
        return {"status": "RECONCILING", "error_code": "CSS.0011",
                "reason_code": "ACTIVE_CLOUD_ACTION", "retry": False}
    if "CSS.0001" in text:
        return {"status": "BLOCKED", "error_code": "CSS.0001",
                "reason_code": "PROVIDER_SCALE_IN_CONSTRAINT", "retry": False}
    lowered = text.casefold()
    if any(token in lowered for token in ("timed out", "timeout", "connection reset",
                                          "connection aborted", "empty response", "result unknown")):
        return {"status": "UNKNOWN", "error_code": "RESULT_UNKNOWN",
                "reason_code": "CLOUD_RESULT_UNKNOWN", "retry": False}
    return {"status": "FAILED", "error_code": "CSS_API_ERROR", "retry": False}
