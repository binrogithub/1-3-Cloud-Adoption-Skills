#!/usr/bin/env python3
"""Bounded CSS/CES watcher for the css_auto role.

This process observes a registered CSS profile and emits normalized events for
the existing AutoOps dispatcher. It never changes CSS capacity and never calls
an LLM. E01 remains the only mutation boundary.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from css_cloud import CssCloudError, ces_metric_samples, ces_metrics, cluster_snapshot
from css_config import config_dir, effective_policy, load_credentials, load_profile
from css_metrics import normalize_snapshot
from css_policy import evaluate
from css_action_ledger import open_action_db, resource_key


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"state must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"state must be a JSON object: {path}")
    return value


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def action_clocks(profile: dict[str, Any]) -> dict[str, float | None]:
    """Read persisted direction clocks without making a cloud call."""
    try:
        connection = open_action_db()
        try:
            rows = connection.execute(
                "SELECT direction, submitted_at, intent_recorded_at FROM css_actions "
                "WHERE (resource_key=? OR profile_id=?) ORDER BY rowid DESC LIMIT 20",
                (resource_key(profile), profile.get("profile_id")),
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return {"last_scale_out_epoch": None, "last_scale_in_epoch": None, "last_action_epoch": None}
    values: dict[str, float | None] = {
        "last_scale_out_epoch": None, "last_scale_in_epoch": None, "last_action_epoch": None,
    }
    for row in rows:
        value = row[1] or row[2]
        try:
            epoch = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError):
            continue
        values["last_action_epoch"] = max(values["last_action_epoch"] or epoch, epoch)
        key = "last_scale_out_epoch" if row[0] == "scale_out" else "last_scale_in_epoch"
        if values[key] is None:
            values[key] = epoch
    return values


def observe(profile_id: str, directory: str | None, fixture_path: str | None,
            history: list[dict[str, Any]] | None = None,
            clocks: dict[str, float | None] | None = None) -> dict[str, Any]:
    profile = load_profile(profile_id, directory)
    credentials = load_credentials(profile, directory)
    policy = effective_policy(profile, directory)
    if fixture_path:
        fixture = load_json(Path(fixture_path), {})
        raw = fixture
    else:
        topology = cluster_snapshot(profile, credentials)
        values = ces_metric_samples(profile, credentials)
        metric_names = {
            "disk_usage_pct": "disk_util", "jvm_heap_max": "max_jvm_heap_usage",
            "cpu_max": "max_cpu_usage", "search_rate": "SearchRate",
            "search_latency": "SearchLatency", "indexing_rate": "IndexingRate",
            "indexing_latency": "IndexingLatency",
        }
        metric_samples = {target: dict(values.get(source, {})) for target, source in metric_names.items()}
        raw = {
            "source": "huaweicloud-css-ces",
            "observed_at": topology["observed_at"],
            "metrics": {
                "cluster_status": 0 if topology["cluster_healthy"] else 3,
                **{name: sample.get("value") for name, sample in metric_samples.items()},
            },
            "metric_samples": metric_samples,
            "topology": topology,
        }
    snapshot = normalize_snapshot(raw, source=raw.get("source", "fixture"),
                                  window_minutes=int(raw.get("window_minutes", 10)))
    decision = evaluate(snapshot, policy, history=history, **(clocks or {}))
    return {"profile": profile, "policy": policy, "snapshot": snapshot, "decision": decision}


def event_for(profile: dict[str, Any], policy: dict[str, Any], snapshot: dict[str, Any],
              decision: dict[str, Any], status: str = "firing",
              directory: str | None = None) -> dict[str, Any]:
    observed_at = snapshot.get("observed_at") or now_iso()
    action = str(decision.get("decision", "investigate"))
    reason_codes = [str(item) for item in decision.get("reason_codes", [])]
    return {
        "id": f"css-{profile['profile_id']}-{action}-{snapshot.get('observed_at') or observed_at}",
        "source": "css",
        "status": status,
        "alertname": f"CSSAutoOps{action.title().replace('_', '')}",
        "service": "css-autoops",
        "target": profile["profile_id"],
        "scope_id": profile["cluster_id"],
        "profile_id": profile["profile_id"],
        "cluster_id": profile["cluster_id"],
        "config_dir": str(config_dir(directory)),
        "starts_at": observed_at,
        "labels": {
            "profile_id": profile["profile_id"],
            "cluster_id": profile["cluster_id"],
            "decision": action,
            "policy_revision": str(policy.get("revision", 0)),
        },
        "annotations": {
            "reason_codes": reason_codes,
            "delta": int(decision.get("delta", 0)),
            "mode": policy.get("mode", "observe"),
            "evidence_refs": snapshot.get("evidence_refs", []),
        },
    }


def run_once(profile_id: str, directory: str | None, state_dir: Path,
             events_file: Path, fixture_path: str | None) -> dict[str, Any]:
    state_path = state_dir / "css-state.json"
    lock = acquire_lock(state_dir / "css-watch.lock")
    if lock is None:
        return {"status": "ALREADY_RUNNING", "profile_id": profile_id, "emitted": 0}
    try:
        state = load_json(state_path, {"status": "active", "active_alert": None,
                                       "last_decision": None, "last_observed_at": None,
                                       "last_error": None, "runs": 0})
        if state.get("status", "active") != "active":
            return {"status": str(state["status"]), "profile_id": profile_id, "emitted": 0}
        try:
            history = state.get("history", [])
            if not isinstance(history, list):
                history = []
            profile_for_clock = load_profile(profile_id, directory)
            result = observe(
                profile_id, directory, fixture_path,
                history=history, clocks=action_clocks(profile_for_clock),
            )
        except CssCloudError as exc:
            state.update({"runs": int(state.get("runs", 0)) + 1,
                          "last_error": "CSS_DATASOURCE_UNAVAILABLE",
                          "last_observed_at": now_iso()})
            save_json(state_path, state)
            return {"status": "UNAVAILABLE", "profile_id": profile_id,
                    "error_code": "CSS_DATASOURCE_UNAVAILABLE", "error": str(exc), "emitted": 0}
        snapshot = result["snapshot"]
        decision = result["decision"]
        profile = result["profile"]
        policy = result["policy"]
        history.append({"observed_at": snapshot.get("observed_at"),
                        "quality": snapshot.get("quality"),
                        "metrics": snapshot.get("metrics", {})})
        history = history[-max(100, int(policy.get("scale_in_required_samples", 10)) * 4):]
        action = str(decision.get("decision", "hold"))
        previous = state.get("active_alert")
        emitted = []
        if action in {"scale_out", "scale_in", "investigate"} and decision.get("status") in {"PLANNED", "RECOMMENDATION", "BLOCKED"}:
            event = event_for(profile, policy, snapshot, decision, directory=directory)
            fingerprint = json.dumps({"profile": profile["profile_id"], "action": action,
                                       "reason_codes": event["annotations"]["reason_codes"]}, sort_keys=True)
            if previous != fingerprint:
                append_event(events_file, event)
                emitted.append(event)
                state["active_alert"] = fingerprint
        elif previous and snapshot.get("quality") == "ok" and action == "hold":
            resolved = event_for(profile, policy, snapshot,
                                 {"decision": "hold", "reason_codes": ["PRESSURE_CLEARED"], "delta": 0},
                                 status="resolved", directory=directory)
            append_event(events_file, resolved)
            emitted.append(resolved)
            state["active_alert"] = None
        state.update({"runs": int(state.get("runs", 0)) + 1,
                      "last_decision": decision,
                      "last_observed_at": snapshot.get("observed_at") or now_iso(),
                      "last_error": None, "history": history})
        save_json(state_path, state)
        return {"status": "PROCESSED", "profile_id": profile["profile_id"],
                "decision": decision, "snapshot_quality": snapshot["quality"],
                "emitted": len(emitted), "events": emitted}
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def change_status(state_dir: Path, status: str) -> dict[str, Any]:
    path = state_dir / "css-state.json"
    state = load_json(path, {"status": "active", "runs": 0})
    state["status"] = status
    state["status_changed_at"] = now_iso()
    save_json(path, state)
    return {"status": status, "state_file": str(path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch one registered Huawei Cloud CSS profile.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--config-dir")
    parser.add_argument("--state-dir", type=Path, default=Path(".runtime/css-watch"))
    parser.add_argument("--events-file", type=Path, default=Path(".runtime/events.jsonl"))
    parser.add_argument("--fixture")
    parser.add_argument("--action", choices=("run", "status", "pause", "resume", "stop"), default="run")
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            print(json.dumps(load_json(args.state_dir / "css-state.json", {"status": "active"}), ensure_ascii=False))
            return 0
        if args.action in {"pause", "resume", "stop"}:
            print(json.dumps(change_status(args.state_dir, {"pause": "paused", "resume": "active", "stop": "stopped"}[args.action]), ensure_ascii=False))
            return 0
        print(json.dumps(run_once(args.profile_id, args.config_dir, args.state_dir,
                                  args.events_file, args.fixture), ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
