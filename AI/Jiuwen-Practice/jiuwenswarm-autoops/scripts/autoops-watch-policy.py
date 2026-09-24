#!/usr/bin/env python3
"""Create, update, or inspect a published AutoOps monitoring policy."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autoops_context import NAME_RE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "monitoring" / "autoops-demo-watch.json"


def regular(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink policy path: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"policy path is not a regular file: {path}")


def read_policy(path: Path) -> dict:
    regular(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid policy: {path}") from exc
    if not isinstance(value, dict) or value.get("kind") != "MonitoringPolicy" \
            or not isinstance(value.get("metadata"), dict) or not isinstance(value.get("spec"), dict):
        raise ValueError("policy must be a MonitoringPolicy object")
    return value


def validate_inputs(profile_ref: str, services: list[str], target: str, interval: int,
                    timezone_name: str, recovery_mode: str) -> None:
    if not NAME_RE.fullmatch(profile_ref):
        raise ValueError("profile_ref must be a published identifier")
    if not services or any(not NAME_RE.fullmatch(service) for service in services):
        raise ValueError("at least one service identifier is required")
    if not NAME_RE.fullmatch(target):
        raise ValueError("target must be a published identifier")
    if not 1 <= interval <= 3600:
        raise ValueError("interval must be from 1 through 3600 seconds")
    if not timezone_name or len(timezone_name) > 64 or any(char in timezone_name for char in "\n\r"):
        raise ValueError("timezone is invalid")
    if recovery_mode not in {"inspect", "preauthorized"}:
        raise ValueError("recovery mode is invalid")


def next_run(interval: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat().replace("+00:00", "Z")


def build_policy(args: argparse.Namespace, revision: int) -> dict:
    services = list(dict.fromkeys(args.service))
    validate_inputs(args.profile_ref, services, args.target, args.interval, args.timezone, args.recovery_mode)
    policy_id = args.policy_id
    if not NAME_RE.fullmatch(policy_id):
        raise ValueError("policy_id must be a published identifier")
    return {
        "apiVersion": "autoops.jiuwen/v1",
        "kind": "MonitoringPolicy",
        "metadata": {"name": policy_id, "revision": revision},
        "spec": {
            "profile_ref": args.profile_ref,
            "targets": [args.target],
            "services": services,
            "poll_interval_seconds": args.interval,
            "timezone": args.timezone,
            "schedule": {"next_run_at": next_run(args.interval)},
            "trigger": {"source": "alertmanager", "condition": args.condition},
            "incident": {"deduplication": "source-alert-target-starts_at"},
            "investigation": {"initial_window_minutes": 1440, "max_backtrace_minutes": 10080,
                              "watermark_overlap_minutes": 2, "max_backfill_minutes": 1440},
            "recovery": {"mode": args.recovery_mode, "max_actions_per_incident": 1},
            "notifications": {"outbox_file": args.outbox_file},
        },
    }


def atomic_write(path: Path, policy: dict) -> None:
    regular(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(policy, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage a published AutoOps monitoring policy.")
    parser.add_argument("--action", choices=("create", "update", "status"), required=True)
    parser.add_argument("--policy", type=Path, default=Path(os.environ.get("AUTOOPS_WATCH_POLICY_FILE", str(DEFAULT_POLICY))))
    parser.add_argument("--policy-id", default="autoops-watch")
    parser.add_argument("--profile-ref")
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--target", default="local")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--condition", default="published Alertmanager firing event")
    parser.add_argument("--recovery-mode", choices=("inspect", "preauthorized"), default="inspect")
    parser.add_argument("--outbox-file", default="/var/lib/jiuwenswarm-autoops/notifications.jsonl")
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            policy = read_policy(args.policy)
            spec = policy["spec"]
            return print(json.dumps({"status": "READY", "policy": policy,
                                     "listener": {"source": spec.get("trigger", {}).get("source", "unknown"),
                                                   "condition": spec.get("trigger", {}).get("condition"),
                                                   "event_listener": "autoops_alertmanager_webhook + autoops_alert_dispatch"},
                                     "next_run_at": spec.get("schedule", {}).get("next_run_at")},
                                    ensure_ascii=False)) or 0
        if not args.profile_ref:
            raise ValueError("--profile-ref is required for create/update")
        exists = args.policy.exists()
        if args.action == "create" and exists:
            return print(json.dumps({"status": "ALREADY_EXISTS", "policy": str(args.policy)}, ensure_ascii=False)) or 2
        if args.action == "update" and not exists:
            return print(json.dumps({"status": "NOT_FOUND", "policy": str(args.policy)}, ensure_ascii=False)) or 1
        revision = 1
        if exists:
            current = read_policy(args.policy)
            revision = int(current["metadata"].get("revision", 0)) + 1
        policy = build_policy(args, revision)
        atomic_write(args.policy, policy)
        print(json.dumps({"status": "CREATED" if not exists else "UPDATED", "policy": policy,
                          "listener": {"source": "alertmanager",
                                        "event_listener": "autoops_alertmanager_webhook + autoops_alert_dispatch"},
                          "next_run_at": policy["spec"]["schedule"]["next_run_at"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
