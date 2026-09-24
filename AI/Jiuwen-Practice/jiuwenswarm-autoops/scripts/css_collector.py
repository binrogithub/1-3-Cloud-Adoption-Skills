"""Shared, bounded CSS/CES snapshot cache.

The cache is keyed by provider identity and observation window. It is useful
for multiple roles in one process; callers performing a mutation must bypass
it and request a fresh topology snapshot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from css_action_ledger import resource_key


@dataclass
class SnapshotCache:
    ttl_seconds: float = 30
    _values: dict[tuple[str, int], tuple[float, dict[str, Any]]] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get(self, key: tuple[str, int], *, now: float | None = None) -> dict[str, Any] | None:
        current = time.monotonic() if now is None else now
        record = self._values.get(key)
        if record and current - record[0] <= self.ttl_seconds:
            self.hits += 1
            return record[1]
        if record:
            self._values.pop(key, None)
        self.misses += 1
        return None

    def put(self, key: tuple[str, int], value: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
        self._values[key] = (time.monotonic() if now is None else now, value)
        return value

    def clear(self) -> None:
        self._values.clear()


def collect_snapshot(profile: dict[str, Any], credentials: dict[str, Any],
                     topology_reader: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
                     metrics_reader: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
                     *, cache: SnapshotCache | None = None, window_minutes: int = 10,
                     fresh: bool = False) -> dict[str, Any]:
    """Collect one normalized raw snapshot, reusing only non-fresh reads."""
    key = (resource_key(profile), int(window_minutes))
    if cache is not None and not fresh:
        cached = cache.get(key)
        if cached is not None:
            return cached
    topology = topology_reader(profile, credentials)
    metric_samples = metrics_reader(profile, credentials)
    metric_names = {
        "disk_usage_pct": "disk_util", "jvm_heap_max": "max_jvm_heap_usage",
        "cpu_max": "max_cpu_usage", "search_rate": "SearchRate",
        "search_latency": "SearchLatency", "indexing_rate": "IndexingRate",
        "indexing_latency": "IndexingLatency",
    }
    canonical = {name: dict(metric_samples.get(provider, {}))
                 for name, provider in metric_names.items()}
    raw = {
        "source": "huaweicloud-css-ces", "observed_at": topology.get("observed_at"),
        "metrics": {"cluster_status": 0 if topology.get("cluster_healthy") else 3,
                    **{name: item.get("value") for name, item in canonical.items()}},
        "metric_samples": canonical, "topology": topology,
        "snapshot_id": f"{resource_key(profile)}:{topology.get('observed_at', '')}",
    }
    return cache.put(key, raw) if cache is not None else raw
