"""Normalize CSS/CES observations and retain data quality."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REQUIRED_METRICS = {
    "cluster_status", "disk_usage_pct", "jvm_heap_max", "cpu_max",
    "search_rate", "search_latency", "indexing_rate", "indexing_latency",
}

DEFAULT_UNITS = {
    "cluster_status": "enum",
    "disk_usage_pct": "percent", "jvm_heap_max": "percent", "cpu_max": "percent",
    "search_rate": "ops_per_second", "indexing_rate": "ops_per_second",
    "search_latency": "milliseconds", "indexing_latency": "milliseconds",
}


def quality_sample(metric: str, value: Any, *, observed_at: str | None,
                   source: str, window_minutes: int, error: str | None = None,
                   unit: str | None = None, aggregation: str = "latest",
                   dimensions: dict[str, Any] | None = None) -> dict[str, Any]:
    quality = "ok"
    numeric: float | int | None = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    freshness_seconds = None
    if error:
        quality = "error"
        numeric = None
    elif numeric is None:
        quality = "empty"
    elif observed_at is not None:
        try:
            if isinstance(observed_at, (int, float)):
                epoch = float(observed_at)
                if epoch > 100_000_000_000:
                    epoch /= 1000
                stamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
            else:
                stamp = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
            freshness_seconds = max(0, int(age))
            if age > 180:
                quality = "stale"
        except ValueError:
            quality = "invalid_timestamp"
    else:
        quality = "missing_timestamp"
    return {
        "metric": metric,
        "value": numeric,
        "source": source,
        "dimensions": dimensions or {"scope": "cluster"},
        "unit": unit or DEFAULT_UNITS.get(metric, "unknown"),
        "aggregation": aggregation,
        "observed_at": observed_at,
        "window_minutes": window_minutes,
        "freshness_seconds": freshness_seconds,
        "quality": quality,
        **({"error": error} if error else {}),
    }


def normalize_snapshot(raw: dict[str, Any], *, source: str = "fixture",
                       window_minutes: int = 10, freshness_seconds: int = 180) -> dict[str, Any]:
    observed_at = raw.get("observed_at")
    metrics = raw.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    raw_samples = raw.get("metric_samples", {})
    if not isinstance(raw_samples, dict):
        raw_samples = {}
    samples = {}
    for name in sorted(set(metrics) | REQUIRED_METRICS | set(raw_samples)):
        detail = raw_samples.get(name) if isinstance(raw_samples.get(name), dict) else {}
        sample = quality_sample(
            name, detail.get("value", metrics.get(name)),
            observed_at=detail.get("observed_at", observed_at),
            source=detail.get("source", source),
            window_minutes=int(detail.get("window_minutes", window_minutes)),
            error=detail.get("error"), unit=detail.get("unit"),
            aggregation=str(detail.get("aggregation", "latest")),
            dimensions=detail.get("dimensions") if isinstance(detail.get("dimensions"), dict) else None,
        )
        if sample["freshness_seconds"] is not None and sample["freshness_seconds"] > freshness_seconds:
            sample["quality"] = "stale"
        samples[name] = sample
    failures = [name for name, sample in samples.items() if sample["quality"] != "ok"]
    topology = raw.get("topology", {})
    if not isinstance(topology, dict):
        topology = {}
    normalized = {
        "schema_version": 2,
        "observed_at": observed_at,
        "window_minutes": window_minutes,
        "samples": samples,
        "metrics": {name: sample["value"] for name, sample in samples.items()},
        "quality": "ok" if not failures else "insufficient",
        "quality_failures": failures,
        "topology": topology,
        "evidence_refs": raw.get("evidence_refs", []),
        "snapshot_id": raw.get("snapshot_id"),
        "collected_at": raw.get("collected_at", observed_at),
        "source_quality": raw.get("source_quality", "ok"),
    }
    for key in ("metric_units_valid", "snapshot_available", "requested_window",
                "effective_window", "coverage", "pagination_complete"):
        if key in raw:
            normalized[key] = raw[key]
    normalized["metric_units_valid"] = bool(
        raw.get("metric_units_valid", all(sample["unit"] != "unknown" for sample in samples.values()))
    )
    normalized["coverage"] = raw.get("coverage", {
        "required": len(REQUIRED_METRICS),
        "valid": sum(sample["quality"] == "ok" for sample in samples.values()),
    })
    return normalized
