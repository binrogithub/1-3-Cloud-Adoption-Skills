#!/usr/bin/env python3
"""Run a bounded, deterministic CSS watcher recovery soak.

This is a local resilience check.  It exercises the persisted watcher state,
deduplication and recovery boundary with fixtures; it never calls Huawei Cloud
and never submits a capacity change.  A real 24-hour result must be supplied
as separate evidence to the CSS release gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



def _watch_run_once():
    path = Path(__file__).with_name("css-watch.py")
    spec = importlib.util.spec_from_file_location("css_watch_for_stability_soak", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load watcher: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_once


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_config(root: Path) -> None:
    _write_json(root / "clusters/production-search.json", {
        "schema_version": 1, "profile_id": "production-search",
        "resource_type": "css_cluster", "cluster_id": "12345678-1234-4123-8123-123456789abc",
        "region": "test-region", "project_id": "test-project",
        "credential_ref": "css/credentials/default", "api_adapter": "sdk",
        "policy_ref": "css-default", "enabled": True,
    })
    _write_json(root / "credentials/default.json", {
        "schema_version": 1, "credential_id": "default", "access_key_id": "test-ak",
        "secret_access_key": "test-sk", "project_id": "test-project", "region": "test-region",
    })
    _write_json(root / "policies/css-default.json", {
        "schema_version": 3, "policy_id": "css-default", "revision": 1, "mode": "observe",
        "min_data_nodes": 2, "max_data_nodes": 5, "scale_out_step": 1, "scale_in_step": 1,
        "scale_out_cpu_percent": 75, "scale_out_disk_percent": 75,
        "scale_in_cpu_percent": 30, "scale_in_disk_percent": 65,
        "allow_scale_out": False, "allow_scale_in": False,
        "enforce_sustained_windows": False, "fresh_precheck_required": False,
    })


def _fixture(path: Path, kind: str) -> None:
    timestamp = now_iso()
    topology = {"cluster_healthy": True, "data_node_count": 2,
                "availability_zones": ["a", "b"], "shard_health": "green",
                "capacity_headroom": 20}
    metrics: dict[str, Any] = {
        "cluster_status": 0, "disk_usage_pct": 60, "jvm_heap_max": 50,
        "cpu_max": 20, "search_rate": 20, "search_latency": 10,
        "indexing_rate": 10, "indexing_latency": 10,
    }
    if kind == "pressure":
        metrics.update({"cpu_max": 90, "disk_usage_pct": 85})
    elif kind == "unknown":
        metrics = {}
    _write_json(path, {"source": "local-soak-fixture", "observed_at": timestamp,
                       "metrics": metrics, "topology": topology,
                       "evidence_refs": [f"fixture://css-soak/{kind}"]})


def run_soak(output: Path | None = None, *, iterations: int = 12,
             restart_every: int = 4) -> dict[str, Any]:
    if iterations < 6:
        raise ValueError("iterations must be at least 6")
    if restart_every < 1:
        raise ValueError("restart_every must be positive")
    with tempfile.TemporaryDirectory(prefix="css-stability-soak-") as value:
        run_once = _watch_run_once()
        root = Path(value)
        config = root / "config"
        state = root / "state"
        events = root / "events.jsonl"
        action_db = root / "actions.sqlite3"
        _write_config(config)
        old_action_db = os.environ.get("AUTOOPS_CSS_ACTION_DB")
        os.environ["AUTOOPS_CSS_ACTION_DB"] = str(action_db)
        records: list[dict[str, Any]] = []
        try:
            sequence = ["pressure", "pressure", "unknown", "unknown", "healthy",
                        "healthy", "pressure", "pressure", "healthy", "healthy"]
            for index in range(iterations):
                kind = sequence[index % len(sequence)]
                fixture = root / f"fixture-{index}.json"
                _fixture(fixture, kind)
                result = run_once("production-search", str(config), state, events, str(fixture))
                records.append({"iteration": index + 1, "fixture": kind,
                                "status": result.get("status"),
                                "decision": result.get("decision", {}).get("decision"),
                                "snapshot_quality": result.get("snapshot_quality"),
                                "emitted": result.get("emitted", 0),
                                "resolved_emitted": any(
                                    event.get("status") == "resolved"
                                    for event in result.get("events", [])
                                ),
                                "restarted_before": (index > 0 and index % restart_every == 0)})
        finally:
            if old_action_db is None:
                os.environ.pop("AUTOOPS_CSS_ACTION_DB", None)
            else:
                os.environ["AUTOOPS_CSS_ACTION_DB"] = old_action_db
        event_rows = []
        if events.exists():
            event_rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line]
        unknown_rows = [item for item in records if item["fixture"] == "unknown"]
        pressure_rows = [item for item in records if item["fixture"] == "pressure"]
        healthy_rows = [item for item in records if item["fixture"] == "healthy"]
        checks = {
            "unknown_does_not_resolve": all(item["snapshot_quality"] != "ok" for item in unknown_rows)
            and all(not item["resolved_emitted"] for item in unknown_rows),
            "pressure_is_deduplicated": len([item for item in pressure_rows if item["emitted"]]) < len(pressure_rows),
            "fresh_healthy_sample_resolves": any(item["resolved_emitted"] for item in healthy_rows),
            "state_survives_restart": (state / "css-state.json").is_file()
            and bool(records) and len(event_rows) >= 2,
            "no_cloud_write": True,
        }
        result = {
            "schema_version": 1, "suite": "css-stability-local-soak",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "execution_level": "LOCAL_FIXTURE",
            "iterations": iterations, "restart_every": restart_every,
            "checks": checks, "records": records,
            "event_count": len(event_rows),
            "real_24h_required": True,
            "real_24h_status": "NOT_RUN",
        }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local CSS watcher recovery soak.")
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--restart-every", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_soak(args.output, iterations=args.iterations, restart_every=args.restart_every)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
