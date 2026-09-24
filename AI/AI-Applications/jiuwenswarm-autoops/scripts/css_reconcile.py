"""Pure CSS action reconciliation rules used by E01 and E09."""
from __future__ import annotations

from typing import Any


def reconcile_action(action: dict[str, Any], topology: dict[str, Any],
                     verification: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the next durable action state from observed cloud state."""
    verification = verification or {}
    target = action.get("target_nodes")
    nodes = topology.get("data_node_count")
    statuses = [str(item.get("status")) for item in topology.get("instances", [])
                if item.get("type") == "ess"]
    if topology.get("cluster_healthy") is not True:
        return _result("RECONCILING", "CLUSTER_NOT_HEALTHY")
    if not isinstance(nodes, int) or not isinstance(target, int):
        return _result("UNKNOWN", "CURRENT_NODE_COUNT_UNKNOWN")
    if nodes != target:
        return _result("RECONCILING", "TARGET_NODE_COUNT_NOT_REACHED",
                       current_nodes=nodes, target_nodes=target)
    if len(statuses) != target:
        return _result("RECONCILING", "ESS_NODE_STATUS_INCOMPLETE",
                       current_nodes=nodes, target_nodes=target,
                       node_statuses=statuses)
    if any(status != "200" for status in statuses):
        return _result("RECONCILING", "ESS_NODE_NOT_AVAILABLE", node_statuses=statuses)
    if topology.get("actions") or topology.get("action_progress"):
        return _result("RECONCILING", "ACTIVE_CLOUD_ACTION")
    verification_status = str(
        verification.get("status", verification.get("business_verification_status", "UNVERIFIED"))
    ).upper()
    if verification_status in {"UNVERIFIED", "UNKNOWN", "PENDING", "NOT_CONFIGURED", "INSUFFICIENT_SAMPLES"}:
        return _result("CAPACITY_READY", "BUSINESS_VERIFICATION_PENDING",
                       capacity_change_status="CAPACITY_READY",
                       business_verification_status=verification_status)
    if verification_status in {"FAILED", "DEGRADED", "INCONCLUSIVE"}:
        return _result("DEGRADED", "BUSINESS_VERIFICATION_FAILED",
                       capacity_change_status="CAPACITY_READY",
                       business_verification_status=verification_status)
    if verification_status not in {"VERIFIED", "PASSED", "SUCCEEDED"}:
        return _result("UNVERIFIED", "BUSINESS_VERIFICATION_UNKNOWN",
                       capacity_change_status="CAPACITY_READY",
                       business_verification_status=verification_status)
    return _result("SUCCEEDED", "RECONCILED", business_verification_status=verification_status)


def _result(status: str, reason_code: str, **values: Any) -> dict[str, Any]:
    return {"status": status, "reason_codes": [reason_code], **values}
