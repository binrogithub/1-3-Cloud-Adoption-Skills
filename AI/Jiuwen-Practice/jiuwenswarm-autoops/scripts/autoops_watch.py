#!/usr/bin/env python3
"""Single-node AutoOps value watcher.

The watcher owns lifecycle, bounded event intake, watermarks and incident
deduplication. It does not collect logs, call an LLM, execute shell, or decide
whether a repair is safe. Those actions remain published adapters invoked by
ProjectManager.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from autoops_runtime_config import resolve_runtime

from autoops_task_store import TaskStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "monitoring" / "autoops-demo-watch.json"
DEFAULT_STATE = ROOT / ".runtime" / "autoops-watch"
MAX_INTERVAL = 3600
MAX_HEALTH_QUEUE_SCAN = 10000


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"file must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def load_policy(path: Path) -> dict[str, Any]:
    policy = load_json(path)
    spec = policy.get("spec")
    if policy.get("kind") != "MonitoringPolicy" or not isinstance(spec, dict):
        raise ValueError("policy must be a MonitoringPolicy object")
    interval = spec.get("poll_interval_seconds", 300)
    maximum = spec.get("max_events_per_run", 100)
    if not isinstance(interval, int) or not 1 <= interval <= MAX_INTERVAL:
        raise ValueError("poll_interval_seconds must be from 1 through 3600")
    if not isinstance(maximum, int) or not 1 <= maximum <= 1000:
        raise ValueError("max_events_per_run must be from 1 through 1000")
    if not isinstance(spec.get("profile_ref"), str) or not spec["profile_ref"]:
        raise ValueError("policy profile_ref is required")
    investigation = spec.get("investigation", {})
    if not isinstance(investigation, dict):
        raise ValueError("policy investigation must be an object")
    overlap = investigation.get("watermark_overlap_minutes", 2)
    max_backfill = investigation.get("max_backfill_minutes", 1440)
    if not isinstance(overlap, int) or not 0 <= overlap <= 120:
        raise ValueError("watermark_overlap_minutes must be from 0 through 120")
    if not isinstance(max_backfill, int) or not 1 <= max_backfill <= 10080:
        raise ValueError("max_backfill_minutes must be from 1 through 10080")
    return policy


def state_path(state_dir: Path) -> Path:
    return state_dir / "state.json"


def default_runtime_paths() -> tuple[Path, Path, Path]:
    runtime = resolve_runtime()
    return (Path(runtime["watch_state_dir"]), Path(runtime["events_file"]),
            Path(runtime["config_root"]) / "monitoring" / "autoops-demo-watch.json")


def load_state(state_dir: Path) -> dict[str, Any]:
    path = state_path(state_dir)
    if not path.exists():
        return {"status": "active", "file_offset": 0, "watermark": None,
                "source_watermarks": {}, "deliveries": {}, "incidents": {},
                "last_run_at": None, "next_run_at": None, "errors": []}
    state = load_json(path)
    state.setdefault("status", "active")
    state.setdefault("file_offset", 0)
    state.setdefault("watermark", None)
    state.setdefault("source_watermarks", {})
    if not isinstance(state["source_watermarks"], dict):
        raise ValueError("state source_watermarks must be an object")
    state.setdefault("deliveries", {})
    state.setdefault("incidents", {})
    state.setdefault("next_run_at", None)
    state.setdefault("errors", [])
    return state


def _timestamp_epoch(value: Any) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def _pending_queue(events_file: Path, offset: int) -> tuple[int | None, bool]:
    """Count unread event lines with a bounded scan for a health response."""
    if events_file.is_symlink() or (events_file.exists() and not events_file.is_file()):
        return None, False
    if not events_file.exists():
        return 0, False
    count = 0
    capped = False
    with events_file.open("r", encoding="utf-8") as stream:
        stream.seek(max(0, offset))
        for line in stream:
            if line.strip():
                count += 1
                if count >= MAX_HEALTH_QUEUE_SCAN:
                    capped = True
                    break
    return count, capped


def health_snapshot(state: dict[str, Any], events_file: Path | None = None) -> dict[str, Any]:
    """Return bounded self-health evidence without invoking an external tool."""
    metrics = state.get("health", {})
    if not isinstance(metrics, dict):
        metrics = {}
    queue_depth = metrics.get("queue_depth") if isinstance(metrics.get("queue_depth"), int) else None
    queue_depth_capped = bool(metrics.get("queue_depth_capped", False))
    if events_file is not None:
        queue_depth, queue_depth_capped = _pending_queue(events_file, int(state.get("file_offset", 0)))
    watermark_epochs = [
        _timestamp_epoch(record.get("watermark"))
        for record in state.get("source_watermarks", {}).values()
        if isinstance(record, dict)
    ]
    watermark_epochs = [value for value in watermark_epochs if value is not None]
    source_lag_seconds = None
    if watermark_epochs:
        source_lag_seconds = max(0, int(time.time() - max(watermark_epochs)))
    recent_errors = state.get("errors", [])
    if not isinstance(recent_errors, list):
        recent_errors = []
    health_status = "degraded" if recent_errors or queue_depth_capped else "ok"
    return {
        "status": health_status,
        "lifecycle": str(state.get("status", "active")),
        "queue_depth": queue_depth,
        "queue_depth_capped": queue_depth_capped,
        "source_lag_seconds": source_lag_seconds,
        "last_run_at": state.get("last_run_at"),
        "next_run_at": state.get("next_run_at"),
        "last_run_duration_ms": metrics.get("last_run_duration_ms"),
        "last_events_read": metrics.get("last_events_read", 0),
        "last_errors": len(recent_errors),
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def save_state(state_dir: Path, state: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    destination = state_path(state_dir)
    fd, temporary_name = tempfile.mkstemp(prefix="state.", suffix=".tmp", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def stable_hash(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()[:32]


def next_query_start(timestamp: str, overlap_minutes: int, max_backfill_minutes: int) -> str | None:
    """Return an overlap start bounded by the policy's backfill window."""
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    value = value.astimezone(timezone.utc) - timedelta(minutes=overlap_minutes)
    floor = datetime.now(timezone.utc) - timedelta(minutes=max_backfill_minutes)
    return max(value, floor).isoformat().replace("+00:00", "Z")


def update_source_watermark(state: dict[str, Any], event: dict[str, Any], overlap_minutes: int,
                            max_backfill_minutes: int) -> None:
    source = str(event.get("source", "unknown")) or "unknown"
    timestamp = event.get("starts_at", event.get("timestamp"))
    if not timestamp:
        return
    timestamp = str(timestamp)
    record = state["source_watermarks"].setdefault(source, {
        "watermark": None, "next_query_start": None, "overlap_minutes": overlap_minutes,
        "max_backfill_minutes": max_backfill_minutes,
    })
    current = record.get("watermark")
    try:
        candidate_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        current_time = None if current is None else datetime.fromisoformat(str(current).replace("Z", "+00:00"))
        if candidate_time.tzinfo is None or (current_time is not None and current_time.tzinfo is None):
            raise ValueError
        newer = current is None or candidate_time.astimezone(timezone.utc) > current_time.astimezone(timezone.utc)
    except (TypeError, ValueError):
        newer = current is None or timestamp > str(current)
    if newer:
        record["watermark"] = timestamp
        record["next_query_start"] = next_query_start(timestamp, overlap_minutes, max_backfill_minutes)
        record["overlap_minutes"] = overlap_minutes
        record["max_backfill_minutes"] = max_backfill_minutes


def incident_identity(event: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str, str]:
    source = str(event.get("source", "unknown"))
    alertname = str(event.get("alertname", event.get("type", "event")))
    target = str(event.get("target", ""))
    service = str(event.get("service", ""))
    scope = str(event.get("scope_id", policy["spec"]["profile_ref"]))
    starts_at = str(event.get("starts_at", event.get("timestamp", "")))
    stable_labels = event.get("labels", {})
    if not isinstance(stable_labels, dict):
        stable_labels = {}
    labels = json.dumps({str(k): str(v) for k, v in sorted(stable_labels.items())
                         if str(k).lower() not in {"trace_id", "request_id", "pod"}},
                        ensure_ascii=False, sort_keys=True)
    incident_key = stable_hash(source, scope, service, target, alertname, labels)
    incident_id = "incident-" + stable_hash(incident_key, starts_at)
    delivery_id = str(event.get("id") or stable_hash(json.dumps(event, ensure_ascii=False, sort_keys=True)))
    return incident_key, incident_id, delivery_id


def read_events(events_file: Path, offset: int, limit: int) -> tuple[list[dict[str, Any]], int, list[str]]:
    if events_file.is_symlink() or not events_file.is_file():
        raise ValueError(f"events file must be a regular file: {events_file}")
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    with events_file.open("r", encoding="utf-8") as stream:
        stream.seek(offset)
        while len(events) < limit:
            line = stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append("invalid JSON event skipped")
                continue
            if not isinstance(event, dict):
                errors.append("non-object event skipped")
                continue
            events.append(event)
        new_offset = stream.tell()
    return events, new_offset, errors


def run_once(policy_path: Path, state_dir: Path, events_file: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    state = load_state(state_dir)
    if state["status"] != "active":
        return {"status": state["status"], "processed": 0, "message": "watcher is not active"}
    started = time.monotonic()
    events, new_offset, errors = read_events(events_file, int(state.get("file_offset", 0)),
                                             int(policy["spec"]["max_events_per_run"]))
    store = TaskStore()
    processed = []
    duplicates = []
    investigation = policy["spec"].get("investigation", {})
    overlap_minutes = int(investigation.get("watermark_overlap_minutes", 2))
    max_backfill_minutes = int(investigation.get("max_backfill_minutes", 1440))
    for event in events:
        incident_key, incident_id, delivery_id = incident_identity(event, policy)
        if delivery_id in state["deliveries"]:
            duplicates.append(delivery_id)
            continue
        state["deliveries"][delivery_id] = int(time.time())
        previous = state["incidents"].get(incident_id)
        state["incidents"][incident_id] = {
            "incident_key": incident_key,
            "status": str(event.get("status", "firing")),
            "updated_at": int(time.time()),
        }
        store.upsert(incident_id, incident_key, {"event": event, "policy": policy["metadata"],
                                                 "incident_id": incident_id,
                                                 "watch_policy_id": policy["metadata"].get("name"),
                                                 "parent_watch_id": policy["metadata"].get("name")}, status="RECEIVED")
        store.event(incident_id, "watch.event", {"delivery_id": delivery_id,
                                                   "duplicate_incident": previous is not None,
                                                   "status": event.get("status", "firing")})
        processed.append({"incident_id": incident_id, "task_id": incident_id,
                          "watch_policy_id": policy["metadata"].get("name"),
                          "delivery_id": delivery_id, "duplicate_incident": previous is not None})
        update_source_watermark(state, event, overlap_minutes, max_backfill_minutes)
        timestamp = event.get("starts_at", event.get("timestamp"))
        if timestamp and (state["watermark"] is None or str(timestamp) > str(state["watermark"])):
            state["watermark"] = str(timestamp)
    store.close()
    state["file_offset"] = new_offset
    state["last_run_at"] = int(time.time())
    state["next_run_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(policy["spec"].get("poll_interval_seconds", 300)))).isoformat().replace("+00:00", "Z")
    state["errors"] = (state.get("errors", []) + errors)[-20:]
    state["health"] = {
        "last_run_duration_ms": int((time.monotonic() - started) * 1000),
        "last_events_read": len(events),
        "queue_depth": None,
        "queue_depth_capped": False,
    }
    health = health_snapshot(state, events_file)
    save_state(state_dir, state)
    return {"status": "processed", "processed": len(processed), "duplicates": len(duplicates),
            "incidents": processed, "watermark": state["watermark"],
            "source_watermarks": state["source_watermarks"], "errors": errors,
            "health": health}


def change_status(state_dir: Path, status: str) -> dict[str, Any]:
    state = load_state(state_dir)
    state["status"] = status
    state["status_changed_at"] = int(time.time())
    save_state(state_dir, state)
    return {"status": status, "state_file": str(state_path(state_dir))}


def main(argv: list[str] | None = None) -> int:
    runtime = resolve_runtime()
    parser = argparse.ArgumentParser(description="Run the bounded AutoOps watcher.")
    parser.add_argument("--policy", type=Path,
                        default=Path(runtime["config_root"]) / "monitoring" / "autoops-demo-watch.json")
    parser.add_argument("--state-dir", type=Path, default=Path(runtime["watch_state_dir"]))
    parser.add_argument("--events-file", type=Path, default=Path(runtime["events_file"]))
    parser.add_argument("--action", choices=("run", "status", "health", "pause", "resume", "stop"), default="run")
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            state = load_state(args.state_dir)
            print(json.dumps({**state, "health": health_snapshot(state)}, ensure_ascii=False))
            return 0
        if args.action == "health":
            state = load_state(args.state_dir)
            events_file = args.events_file or (args.state_dir.parent / "events.jsonl")
            print(json.dumps(health_snapshot(state, events_file), ensure_ascii=False))
            return 0
        if args.action == "pause":
            print(json.dumps(change_status(args.state_dir, "paused"), ensure_ascii=False))
            return 0
        if args.action == "resume":
            print(json.dumps(change_status(args.state_dir, "active"), ensure_ascii=False))
            return 0
        if args.action == "stop":
            print(json.dumps(change_status(args.state_dir, "stopped"), ensure_ascii=False))
            return 0
        if not args.events_file:
            raise ValueError("--events-file is required for a run")
        print(json.dumps(run_once(args.policy, args.state_dir, args.events_file), ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
