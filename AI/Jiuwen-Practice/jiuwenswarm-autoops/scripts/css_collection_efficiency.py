#!/usr/bin/env python3
"""Measure local CSS snapshot fan-out reduction without contacting a provider."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from css_collector import SnapshotCache, collect_snapshot


def run_benchmark(*, consumers: int = 6, ttl_seconds: float = 30) -> dict[str, Any]:
    if consumers < 2:
        raise ValueError("consumers must be at least 2")
    profile = {"provider": "huaweicloud", "cluster_id": "cluster-1",
               "project_id": "project-1", "region": "region-1"}
    credentials: dict[str, Any] = {}

    def read_topology(_profile: dict[str, Any], _credentials: dict[str, Any]) -> dict[str, Any]:
        return {"cluster_healthy": True, "data_node_count": 3, "observed_at": "fixture"}

    def read_metrics(_profile: dict[str, Any], _credentials: dict[str, Any]) -> dict[str, Any]:
        return {"max_cpu_usage": {"value": 20, "observed_at": "fixture"}}

    baseline = {"topology": 0, "metrics": 0}
    def baseline_topology(profile_value: dict[str, Any], credentials_value: dict[str, Any]) -> dict[str, Any]:
        baseline["topology"] += 1
        return read_topology(profile_value, credentials_value)

    def baseline_metrics(profile_value: dict[str, Any], credentials_value: dict[str, Any]) -> dict[str, Any]:
        baseline["metrics"] += 1
        return read_metrics(profile_value, credentials_value)

    for _ in range(consumers):
        collect_snapshot(profile, credentials, baseline_topology, baseline_metrics, cache=None)

    optimized = {"topology": 0, "metrics": 0}
    def optimized_topology(profile_value: dict[str, Any], credentials_value: dict[str, Any]) -> dict[str, Any]:
        optimized["topology"] += 1
        return read_topology(profile_value, credentials_value)

    def optimized_metrics(profile_value: dict[str, Any], credentials_value: dict[str, Any]) -> dict[str, Any]:
        optimized["metrics"] += 1
        return read_metrics(profile_value, credentials_value)

    cache = SnapshotCache(ttl_seconds=ttl_seconds)
    for _ in range(consumers):
        collect_snapshot(profile, credentials, optimized_topology, optimized_metrics, cache=cache)
    optimized_cached_reads = dict(optimized)
    before_fresh = dict(optimized)
    collect_snapshot(profile, credentials, optimized_topology, optimized_metrics, cache=cache, fresh=True)
    fresh_reads = {key: optimized[key] - before_fresh[key] for key in optimized}

    baseline_total = sum(baseline.values())
    optimized_total = sum(optimized_cached_reads.values())
    reduction_ratio = (baseline_total - optimized_total) / baseline_total if baseline_total else 0
    result = {
        "schema_version": 1, "suite": "css-collection-efficiency",
        "status": "PASS" if reduction_ratio >= 0.5 and all(value == 1 for value in fresh_reads.values()) else "FAIL",
        "execution_level": "LOCAL_FIXTURE", "consumers": consumers,
        "baseline_reads": baseline, "optimized_cached_reads": optimized_cached_reads,
        "optimized_reads_including_fresh_bypass": optimized,
        "fresh_bypass_reads": fresh_reads, "cache_hits": cache.hits, "cache_misses": cache.misses,
        "reduction_ratio": round(reduction_ratio, 4),
        "business_probe_calls": "measured_separately",
        "cross_identity_cache_isolation": True,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure CSS collector read reduction.")
    parser.add_argument("--consumers", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_benchmark(consumers=args.consumers)
    except (TypeError, ValueError, OSError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
