"""Explainable capacity lead-time and pressure forecast helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any


def _epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) / 1000 if value > 100_000_000_000 else float(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def summarize_lead_times(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observed lead time without calling a small sample a P95."""
    values = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        submitted = _epoch(action.get("submitted_at"))
        capacity = _epoch(action.get("capacity_ready_at"))
        if submitted is not None and capacity is not None and capacity >= submitted:
            values.append(round(capacity - submitted, 3))
    return {
        "sample_count": len(values),
        "seconds": values,
        "median_seconds": median(values) if values else None,
        "p95_seconds": None if len(values) < 20 else sorted(values)[max(0, int(len(values) * .95) - 1)],
        "quality": "insufficient_samples" if len(values) < 20 else "usable",
    }


def forecast_capacity(snapshot: dict[str, Any], policy: dict[str, Any],
                      lead_time: dict[str, Any]) -> dict[str, Any]:
    """Return a planning hint; never creates a cloud action."""
    growth = snapshot.get("growth_per_hour")
    available = snapshot.get("capacity_headroom_units")
    if not isinstance(growth, (int, float)) or growth <= 0 or not isinstance(available, (int, float)):
        return {"status": "UNKNOWN", "reason_code": "CAPACITY_FORECAST_INPUT_INSUFFICIENT"}
    lead_minutes = float(policy.get("initial_capacity_lead_minutes", 15))
    if isinstance(lead_time.get("median_seconds"), (int, float)):
        lead_minutes = max(lead_minutes, float(lead_time["median_seconds"]) / 60)
    hours = lead_minutes / 60
    remaining_hours = available / float(growth)
    return {
        "status": "PRESSURE_FORECAST" if remaining_hours <= hours else "CAPACITY_ADEQUATE",
        "remaining_hours": round(remaining_hours, 3),
        "planning_lead_minutes": round(lead_minutes, 2),
        "lead_time_quality": lead_time.get("quality", "unknown"),
    }
