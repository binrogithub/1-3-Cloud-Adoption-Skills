#!/usr/bin/env python3
"""Dispatch one bounded Alertmanager incident to the read-only PM route."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from autoops_runtime_config import resolve_runtime

from autoops_context import NAME_RE
from autoops_task_store import TaskStore
from autoops_watch import incident_identity, load_json, load_policy, read_events

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "monitoring" / "autoops-demo-watch.json"
_RUNTIME = resolve_runtime()
DEFAULT_STATE = Path(_RUNTIME["watch_state_dir"])
DEFAULT_EVENTS = Path(_RUNTIME["events_file"])


def dispatch_state_path(state_dir: Path) -> Path:
    return state_dir / "dispatch-state.json"


def load_dispatch_state(state_dir: Path) -> dict[str, Any]:
    path = dispatch_state_path(state_dir)
    if not path.exists():
        return {"file_offset": 0, "deliveries": {}, "incidents": {}, "notifications": 0}
    state = load_json(path)
    state.setdefault("file_offset", 0)
    state.setdefault("deliveries", {})
    state.setdefault("incidents", {})
    state.setdefault("notifications", 0)
    return state


def save_dispatch_state(state_dir: Path, state: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix="dispatch-state.", suffix=".tmp", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, dispatch_state_path(state_dir))
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def append_notification(path: Path, notification: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            stream.write(json.dumps(notification, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_project_manager(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    service = str(event.get("service", ""))
    target = str(event.get("target", "")) or "local"
    if not NAME_RE.fullmatch(service) or not NAME_RE.fullmatch(target):
        return 2, {"status": "INPUT_ERROR", "error": "alert service or target is not a published identifier"}
    css_event = str(event.get("source", "")).lower() == "css"
    request = (f"CSS 集群告警触发：检查 profile {event.get('profile_id', target)} 的数据节点流量、容量和扩缩容建议"
               if css_event else
               f"告警触发：排查 {service} 根因，关联最近24小时日志、指标和历史事件")
    command = [
        sys.executable, str(ROOT / "scripts" / "autoops-project-manager.py"),
        "--request", request, "--service", service, "--target", target,
        "--since-minutes", "1440", "--limit", "100",
    ]
    if css_event and event.get("profile_id"):
        command.extend(("--css-profile", str(event["profile_id"])))
        if event.get("config_dir"):
            command.extend(("--css-config-dir", str(event["config_dir"])))
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                               capture_output=True, check=False, timeout=120)
    output = completed.stdout.strip()
    try:
        payload = json.loads(output) if output else {"status": "UNKNOWN", "error": "ProjectManager returned no JSON"}
    except json.JSONDecodeError:
        payload = {"status": "UNKNOWN", "error": "ProjectManager returned invalid JSON",
                   "transcript": output[-1000:]}
    return completed.returncode, payload


def run_recovery_flow(event: dict[str, Any], incident_id: str, preauthorization_id: str) -> tuple[int, dict[str, Any]]:
    service = str(event.get("service", ""))
    target = str(event.get("target", "")) or "local"
    command = [sys.executable, str(ROOT / "scripts" / "autoops-recovery-flow.py"),
               "--task-id", incident_id, "--incident-id", incident_id,
               "--request", f"告警触发：排查 {service} 根因并在证据充分时恢复服务",
               "--service", service, "--target", target,
               "--preauthorization-id", preauthorization_id]
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                               capture_output=True, check=False, timeout=240)
    try:
        payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {"status": "UNKNOWN"}
    except json.JSONDecodeError:
        payload = {"status": "UNKNOWN", "error": completed.stderr.strip()[-1000:] or "recovery flow returned invalid JSON"}
    return completed.returncode, payload


def run_verifier(event: dict[str, Any], incident_id: str) -> tuple[int, dict[str, Any]]:
    """Verify an Alertmanager recovery signal through the independent E09 adapter."""
    if str(event.get("source", "")).lower() == "css":
        profile_id = str(event.get("profile_id", ""))
        if not NAME_RE.fullmatch(profile_id):
            return 2, {"verification_status": "INCONCLUSIVE", "error": "CSS profile is not a published identifier"}
        command = [sys.executable, str(ROOT / "scripts" / "css-auto.py"), "verify",
                   "--profile-id", profile_id, "--task-id", incident_id]
        if event.get("config_dir"):
            command.extend(("--config-dir", str(event["config_dir"])))
        try:
            completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                                       capture_output=True, check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 2, {"verification_status": "INCONCLUSIVE", "error": str(exc)}
        try:
            payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        return completed.returncode, {
            "verification_status": "PASSED" if payload.get("status") == "VERIFIED" else "INCONCLUSIVE",
            "css_result": payload,
        }
    service = str(event.get("service", ""))
    target = str(event.get("target", "")) or "local"
    command = [sys.executable, str(ROOT / "scripts" / "verify-service-recovery.py"),
               "--task-id", incident_id, "--step-id", "verify-alert-resolved",
               "--target", target, "--service", service]
    try:
        completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                                   capture_output=True, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, {"verification_status": "INCONCLUSIVE", "error": str(exc)}
    try:
        payload = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {
            "verification_status": "INCONCLUSIVE", "error": "verifier returned no JSON"
        }
    except json.JSONDecodeError:
        payload = {"verification_status": "INCONCLUSIVE",
                   "error": completed.stderr.strip()[-1000:] or "verifier returned invalid JSON"}
    return completed.returncode, payload


def run_once(policy_path: Path, state_dir: Path, events_file: Path, outbox_file: Path,
             preauthorization_id: str = "") -> dict[str, Any]:
    policy = load_policy(policy_path)
    watcher_state_path = state_dir / "state.json"
    if watcher_state_path.exists():
        watcher_state = load_json(watcher_state_path)
        if watcher_state.get("status", "active") != "active":
            return {"status": watcher_state["status"], "processed": 0,
                    "duplicates": 0, "notifications": 0, "incidents": [], "errors": []}
    state = load_dispatch_state(state_dir)
    store = TaskStore()
    source = str(events_file.expanduser().resolve())
    state_offset = int(state["file_offset"])
    durable_offset = store.dispatch_watermark(source)
    if durable_offset is not None:
        state_offset = max(state_offset, durable_offset)
    events, new_offset, errors = read_events(events_file, state_offset,
                                             int(policy["spec"]["max_events_per_run"]))
    processed = []
    duplicates = 0
    deferred = False
    try:
        for event in events:
            incident_key, incident_id, delivery_id = incident_identity(event, policy)
            delivery_claim = store.claim_dispatch_delivery(delivery_id, incident_id, incident_key, event)
            if not delivery_claim["claimed"]:
                if delivery_claim["reason"] == "in_flight":
                    deferred = True
                else:
                    duplicates += 1
                continue
            if delivery_id in state["deliveries"]:
                store.finish_dispatch_delivery(delivery_id, {"source": "legacy-json-state"})
                duplicates += 1
                continue
            state["deliveries"][delivery_id] = int(time.time())
            status = str(event.get("status", "firing")).lower()
            incident = state["incidents"].setdefault(incident_id, {
                "status": status, "dispatched": False, "task_id": incident_id,
                "parent_watch_id": policy["metadata"].get("name"),
            })
            if status == "firing" and not incident.get("dispatched"):
                action_claim = store.claim_dispatch_action(incident_id, "firing", delivery_id)
                if not action_claim["claimed"]:
                    if action_claim["reason"] == "in_flight":
                        deferred = True
                    else:
                        store.finish_dispatch_delivery(delivery_id, {
                            "action": "firing", "reason": action_claim["reason"],
                        })
                        duplicates += 1
                    continue
                store.upsert(incident_id, incident_key, {
                    "event": event, "watch_policy_id": policy["metadata"].get("name"),
                    "parent_watch_id": policy["metadata"].get("name"), "task_id": incident_id,
                    "incident_id": incident_id,
                }, status="RECEIVED")
                store.set_status(incident_id, "INVESTIGATING")
                store.event(incident_id, "alert.investigation_started", {"delivery_id": delivery_id})
                try:
                    if preauthorization_id:
                        code, result = run_recovery_flow(event, incident_id, preauthorization_id)
                    else:
                        code, result = run_project_manager(event)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    code, result = 2, {"status": "FAILED", "error": str(exc)}
                flow_status = str(result.get("status", ""))
                adapter_result = result.get("adapter_result")
                observed_status = str(adapter_result.get("status", "")) if isinstance(adapter_result, dict) else flow_status
                waiting = flow_status in {"WAITING_EVIDENCE", "WAITING_APPROVAL"}
                # A read-only investigation can validly return partial or
                # unavailable evidence. It was dispatched and recorded; only
                # a transport/process failure is a dispatcher failure.
                investigation_recorded = code == 0 or flow_status.lower() in {
                    "no_anomaly", "trace_ready", "trace_incomplete", "inconclusive", "unavailable",
                }
                partial = observed_status.lower() in {"partial", "trace_incomplete", "inconclusive", "empty"}
                recovered = bool(preauthorization_id and flow_status == "COMPLETED" and code == 0
                                 and not partial)
                task_status = ("WAITING" if waiting else
                               ("PARTIAL" if partial else
                                ("COMPLETED" if code == 0 else "INCONCLUSIVE")))
                incident.update({"status": "WAITING" if waiting else ("RECOVERED" if recovered else ("DISPATCHED" if investigation_recorded else "FAILED")),
                                 "dispatched": True, "observed_at": int(time.time()),
                                 "result": result})
                store.set_status(incident_id, task_status)
                store.event(incident_id, "alert.investigation_finished", {"status": task_status, "result": result})
                notification = {"kind": "investigation", "incident_id": incident_id,
                                "service": event.get("service", ""), "target": event.get("target", "") or "local",
                                "status": incident["status"], "result": result,
                                "observed_at": int(time.time())}
                append_notification(outbox_file, notification)
                store.finish_dispatch_action(incident_id, "firing", {
                    "status": incident["status"], "task_status": task_status,
                    "result_status": flow_status,
                })
                store.finish_dispatch_delivery(delivery_id, {
                    "action": "firing", "status": incident["status"],
                })
                state["notifications"] += 1
                processed.append({"incident_id": incident_id, "status": incident["status"]})
            elif status == "resolved" and incident.get("dispatched") and not incident.get("resolved_notified"):
                action_claim = store.claim_dispatch_action(incident_id, "resolved", delivery_id)
                if not action_claim["claimed"]:
                    if action_claim["reason"] == "in_flight":
                        deferred = True
                    else:
                        store.finish_dispatch_delivery(delivery_id, {
                            "action": "resolved", "reason": action_claim["reason"],
                        })
                        duplicates += 1
                    continue
                # Alertmanager resolving means the alert condition cleared. It
                # is not proof that the business service recovered. Keep the
                # incident open until the independent E09 verifier reports a
                # passing business probe.
                verification_code, verification = run_verifier(event, incident_id)
                verified = verification_code == 0 and verification.get("verification_status") == "PASSED"
                incident.update({"status": "RECOVERED" if verified else "ALERT_RESOLVED_PENDING_VERIFICATION",
                                 "resolved_notified": True, "observed_at": int(time.time()),
                                 "verification_required": not verified, "verification": verification})
                store.upsert(incident_id, incident_key, {
                    "event": event, "watch_policy_id": policy["metadata"].get("name"),
                    "parent_watch_id": policy["metadata"].get("name"), "task_id": incident_id,
                    "incident_id": incident_id,
                }, status="RECEIVED")
                store.set_status(incident_id, "COMPLETED" if verified else "WAITING")
                store.event(incident_id, "alert.resolved_verified" if verified else "alert.resolved_verification_failed", {
                    "delivery_id": delivery_id, "verification_required": not verified,
                    "verification": verification,
                })
                append_notification(outbox_file, {"kind": "recovery", "incident_id": incident_id,
                                                   "service": event.get("service", ""),
                                                   "target": event.get("target", "") or "local",
                                                   "status": "RECOVERED" if verified else "ALERT_RESOLVED_PENDING_VERIFICATION",
                                                   "verification_required": not verified,
                                                   "verification": verification,
                                                   "observed_at": int(time.time())})
                store.finish_dispatch_action(incident_id, "resolved", {
                    "status": incident["status"],
                    "verification_status": verification.get("verification_status"),
                })
                store.finish_dispatch_delivery(delivery_id, {
                    "action": "resolved", "status": incident["status"],
                })
                state["notifications"] += 1
                processed.append({"incident_id": incident_id, "status": "RECOVERED" if verified else "RESOLVED"})
            else:
                store.finish_dispatch_delivery(delivery_id, {"status": "ignored"})
    finally:
        if not deferred:
            state["file_offset"] = new_offset
            store.set_dispatch_watermark(source, new_offset)
        else:
            state["file_offset"] = state_offset
        store.close()
    state["last_run_at"] = int(time.time())
    state["errors"] = (state.get("errors", []) + errors)[-20:]
    save_dispatch_state(state_dir, state)
    return {"status": "processed", "processed": len(processed), "duplicates": duplicates,
            "notifications": state["notifications"], "incidents": processed, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    runtime = resolve_runtime()
    parser = argparse.ArgumentParser(description="Dispatch Alertmanager incidents to AutoOps investigation.")
    parser.add_argument("--policy", type=Path,
                        default=Path(runtime["config_root"]) / "monitoring" / "autoops-demo-watch.json")
    parser.add_argument("--state-dir", type=Path, default=Path(runtime["watch_state_dir"]))
    parser.add_argument("--events-file", type=Path, default=Path(runtime["events_file"]))
    parser.add_argument("--outbox-file", type=Path, default=Path(runtime["outbox_file"]))
    parser.add_argument("--preauthorization-id", default="",
                        help="Optional published policy for the bounded recovery flow.")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_once(args.policy, args.state_dir, args.events_file, args.outbox_file,
                                  args.preauthorization_id), ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
