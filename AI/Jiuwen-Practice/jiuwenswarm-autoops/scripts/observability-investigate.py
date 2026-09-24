#!/usr/bin/env python3
"""Coordinate E05 current evidence with E06 historical trace evidence.

The flow is deterministic: a clean 24-hour E05 window stops the flow. E06 is
queried only after E05 returns matching error evidence. No write capability is
available from this coordinator.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from observability_env import load_observability_environment
from autoops_task_store import TaskStore

ROOT = Path(__file__).resolve().parents[1]
OFFSET_WITHOUT_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


def run_json(command: list[str], env: dict[str, str]) -> tuple[int, dict]:
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        payload = {"status": "unavailable", "error_code": "ADAPTER_NO_JSON",
                   "error": completed.stderr.strip()[-500:] or "adapter returned no JSON"}
    return completed.returncode, payload


def iso_from_ns(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000_000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_evidence_timestamp(value: str) -> datetime | None:
    """Parse RFC 3339 and systemd short-iso timestamps on Python 3.9+."""
    normalized = OFFSET_WITHOUT_COLON.sub(r"\1:\2", value.replace("Z", "+00:00"))
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def iso_minus(iso: str, minutes: int) -> str:
    value = datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(minutes=minutes)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ns_from_iso(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1_000_000_000)


def query_logs(service: str, minutes: int, limit: int, env: dict[str, str],
               start_iso: str, end_iso: str) -> tuple[int, dict]:
    loki = ROOT / "scripts" / "loki-query.sh"
    local = ROOT / "scripts" / "local-journal-query.sh"
    loki_window = ["--start-ns", str(ns_from_iso(start_iso)), "--end-ns", str(ns_from_iso(end_iso))]
    journal_window = ["--since-at", start_iso, "--until", end_iso,
                      "--since-minutes", str(minutes)]
    if env.get("LOKI_BASE_URL"):
        code, payload = run_json([str(loki), "--service", service, *loki_window, "--limit", str(limit)], env)
        if payload.get("status") == "ok":
            return code, payload
        # An empty Loki result can mean that the service label is absent or
        # shipping is delayed. Probe the local journal before concluding that
        # the service is clean, so a local failure cannot be hidden by an
        # empty remote stream.
        local_code, local_payload = run_json(
            [str(local), "--service", service, *journal_window, "--limit", str(limit)], env
        )
        if isinstance(local_payload, dict):
            # A local fallback is useful for diagnosis, but it cannot erase a
            # configured Loki outage or an incomplete remote coverage signal.
            # Preserve that fact in the evidence contract so a clean-looking
            # local response is never reported as a complete 24-hour result.
            loki_status = payload.get("status", "unavailable")
            local_payload.setdefault("diagnostics", {})["loki_probe"] = {
                "status": loki_status,
                "error_code": payload.get("error_code"),
                "query_ref": payload.get("query_ref"),
            }
            # An empty filtered Loki stream is an expected label/shipper
            # condition and can be answered by a complete local journal. An
            # actual transport/auth/server failure is degraded coverage and
            # must remain visible to the caller.
            if loki_status != "empty":
                local_payload["coverage_status"] = "partial"
                local_payload["source_health"] = "degraded"
                local_payload["source_status"] = "degraded"
        return local_code, local_payload
    return run_json([str(local), "--service", service, *journal_window, "--limit", str(limit)], env)


def anomaly_anchor(current: dict) -> str | None:
    """Return the earliest observed anomaly timestamp in the current window."""
    timestamps = []
    for item in current.get("entries", []):
        value = item.get("timestamp_ns") or item.get("timestamp")
        if value:
            timestamps.append(str(value))
    if not timestamps:
        return None
    if current.get("source") == "loki":
        try:
            return iso_from_ns(min(int(value) for value in timestamps))
        except ValueError:
            return None
    parsed = [parsed for value in timestamps if (parsed := parse_evidence_timestamp(value)) is not None]
    return min(parsed).isoformat().replace("+00:00", "Z") if parsed else None


def previous_logs(service: str, current: dict, anchor: str | None, minutes: int,
                  limit: int, env: dict[str, str]) -> tuple[int, dict]:
    source = current.get("source")
    if source == "loki" and anchor and current.get("start_ns") and current.get("end_ns"):
        end_ns = int(datetime.fromisoformat(anchor.replace("Z", "+00:00")).timestamp() * 1_000_000_000)
        start_ns = end_ns - minutes * 60 * 1_000_000_000
        return run_json([str(ROOT / "scripts" / "loki-query.sh"), "--service", service,
                         "--start-ns", str(start_ns), "--end-ns", str(end_ns), "--limit", str(limit)], env)
    if anchor:
        return run_json([str(ROOT / "scripts" / "local-journal-query.sh"), "--service", service,
                         "--since-at", iso_minus(anchor, minutes), "--until", anchor,
                         "--since-minutes", str(minutes), "--limit", str(limit)], env)
    return 1, {"source": "local-journal", "status": "unavailable", "error_code": "WINDOW_ANCHOR_MISSING"}


def has_anomaly(payload: dict) -> bool:
    """Loki already filters error lines; local journal needs deterministic filtering."""
    if payload.get("source") == "loki":
        return payload.get("status") == "ok" and int(payload.get("entry_count", payload.get("count", 0))) > 0
    for item in payload.get("entries", payload.get("items", [])):
        line = str(item.get("line", item.get("source", "")))
        if any(term in line.lower() for term in ("error", "exception", "fatal", "panic", "failed", "timeout", "崩溃", "异常")):
            return True
    return False


def complete_log_evidence(payload: dict) -> bool:
    """Return true only when a non-empty log query has complete coverage."""
    if payload.get("status") != "ok":
        return False
    if not isinstance(payload.get("entries"), list) or not payload["entries"]:
        return False
    if payload.get("truncated") is True or payload.get("pagination_complete") is False:
        return False
    if payload.get("coverage_status") == "partial":
        return False
    if payload.get("source_health") not in (None, "ready"):
        return False
    if payload.get("source_status") not in (None, "ready"):
        return False
    return True


def persist_result(task_id: str, args: argparse.Namespace, payload: dict,
                   return_code: int = 0) -> int:
    """Persist one flow result so TUI reconnect can reuse its task identity."""
    result = dict(payload)
    result.setdefault("task_id", task_id)
    store = TaskStore()
    try:
        if store.get(task_id) is None:
            store.upsert(task_id, task_id, {
                "request": getattr(args, "request", "") or
                           f"investigate {args.service}",
                "service": args.service,
                "target": args.target,
                "operation_id": task_id,
            }, status="RECEIVED")
        store.record_result(task_id, result, return_code)
    finally:
        store.close()
    print(json.dumps(result, ensure_ascii=False))
    return return_code


def incomplete_result(service: str, target: str, tenant: str, minutes: int,
                      investigation_window: dict, current: dict, error_code: str) -> dict:
    return {
        "status": "inconclusive",
        "decision": "needs_more_evidence",
        "service": service,
        "target": target,
        "tenant": tenant,
        "searched_minutes": minutes,
        "open_search_called": False,
        "investigation_window": investigation_window,
        "error_code": error_code,
        "reason": "The log source returned incomplete coverage; the flow must not report a clean result.",
        "current_logs": current,
    }


def candidate_root_causes(current: dict, previous: dict, metrics: dict, events: dict) -> list[dict]:
    """Build auditable hypotheses from independent evidence sources.

    These are candidates only.  A historical match is evidence of recurrence,
    not proof that the historical change caused the current incident.
    """
    candidates = []
    if has_anomaly(current) and has_anomaly(previous):
        candidates.append({
            "candidate_id": "recurring_log_signature",
            "classification": "candidate",
            "reason": "The current and preceding windows both contain matching anomaly-class log evidence.",
            "evidence": ["current_logs", "previous_logs"],
        })

    metric_items = metrics.get("items", []) if isinstance(metrics, dict) else []
    metric_failure = False
    for item in metric_items:
        values = item.get("values") if isinstance(item, dict) else None
        if isinstance(values, list):
            samples = values
        elif values is None:
            samples = []
        else:
            samples = [values]
        for sample in samples:
            value = sample[-1] if isinstance(sample, (list, tuple)) and sample else sample
            try:
                if float(value) <= 0:
                    metric_failure = True
            except (TypeError, ValueError):
                continue
    if metric_failure:
        candidates.append({
            "candidate_id": "service_metric_degraded",
            "classification": "candidate",
            "reason": "The configured service health metric contains a non-positive sample.",
            "evidence": ["metrics"],
        })

    event_items = events.get("items", []) if isinstance(events, dict) else []
    if event_items:
        candidates.append({
            "candidate_id": "recent_change_correlation",
            "classification": "candidate",
            "reason": "A published event source returned a change or deployment in the bounded backtrace window.",
            "evidence": ["historical_events"],
            "warning": "Correlation only; the event is not declared the root cause without independent validation.",
        })
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run E05 current check and conditional E06 historical trace.")
    parser.add_argument("--service", required=True)
    parser.add_argument("--target", default="local")
    parser.add_argument("--tenant", default="")
    parser.add_argument("--since-minutes", type=int, default=1440)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--task-id")
    parser.add_argument("--continue-on-clean", action="store_true",
                        help="Continue with the fixed service_up metric profile when logs are clean.")
    args = parser.parse_args(argv)
    if not 1 <= args.since_minutes <= 1440 or not 1 <= args.limit <= 200:
        print(json.dumps({"status": "invalid", "error_code": "INVALID_INPUT",
                          "error": "since-minutes must be 1..1440 and limit 1..200"}, ensure_ascii=False))
        return 2
    task_id = args.task_id or f"pm-{uuid.uuid4().hex}"

    # The current journal fallback is local-only. Preserve a requested remote
    # target instead of silently querying the local host and mixing evidence.
    # A future Loki host-label adapter can replace this explicit boundary.
    if args.target != "local":
        print(json.dumps({
            "status": "unavailable",
            "decision": "needs_human",
            "service": args.service,
            "target": args.target,
            "open_search_called": False,
            "error_code": "TARGET_UNSUPPORTED",
            "error": "remote target requires a configured host-scoped adapter",
        }, ensure_ascii=False))
        return 1
    if bool(args.start) != bool(args.end):
        print(json.dumps({"status": "invalid", "error_code": "WINDOW_INCOMPLETE",
                          "error": "start and end must be supplied together"}, ensure_ascii=False))
        return 2
    if args.tenant:
        print(json.dumps({
            "status": "unavailable",
            "decision": "needs_human",
            "service": args.service,
            "target": args.target,
            "tenant": args.tenant,
            "open_search_called": False,
            "error_code": "TENANT_UNSUPPORTED",
            "error": "tenant-scoped evidence requires a configured tenant-aware adapter",
        }, ensure_ascii=False))
        return 1

    env = load_observability_environment()
    if args.start and args.end:
        try:
            window_start = datetime.fromisoformat(args.start.replace("Z", "+00:00")).astimezone(timezone.utc)
            window_end = datetime.fromisoformat(args.end.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            print(json.dumps({"status": "invalid", "error_code": "WINDOW_INVALID",
                              "error": "start and end must be ISO-8601 timestamps"}, ensure_ascii=False))
            return 2
        if window_end <= window_start:
            print(json.dumps({"status": "invalid", "error_code": "WINDOW_INVALID",
                              "error": "end must be later than start"}, ensure_ascii=False))
            return 2
    else:
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(minutes=args.since_minutes)
    start_iso = window_start.isoformat().replace("+00:00", "Z")
    end_iso = window_end.isoformat().replace("+00:00", "Z")
    investigation_window = {"start": start_iso, "end": end_iso,
                            "requested_minutes": args.since_minutes}
    current_code, current = query_logs(args.service, args.since_minutes, args.limit, env,
                                       start_iso, end_iso)
    current_status = current.get("status")
    if current_status == "empty":
        return persist_result(task_id, args, {
            **incomplete_result(args.service, args.target, args.tenant,
                                args.since_minutes, investigation_window,
                                current, "NO_LOG_EVIDENCE"),
            "reason": "The source query succeeded but returned no application evidence.",
        })
    if current_status == "ok" and not has_anomaly(current):
        if not complete_log_evidence(current):
            return persist_result(task_id, args, incomplete_result(
                args.service, args.target, args.tenant, args.since_minutes,
                investigation_window, current, "LOG_EVIDENCE_INCOMPLETE"))
        if args.continue_on_clean:
            metrics_command = [sys.executable, str(ROOT / "scripts" / "prometheus-query.py"),
                               "--service", args.service, "--profile", "service_up",
                               "--since-minutes", str(args.since_minutes), "--start", start_iso,
                               "--end", end_iso, "--limit", str(args.limit)]
            metrics_code, metrics = run_json(metrics_command, env)
            if metrics.get("status") != "ok":
                return persist_result(task_id, args, {
                    "status": "trace_incomplete",
                    "diagnosis_status": "PARTIAL",
                    "decision": "needs_human",
                    "service": args.service,
                    "target": args.target,
                    "tenant": args.tenant,
                    "searched_minutes": args.since_minutes,
                    "open_search_called": False,
                    "investigation_window": investigation_window,
                    "current_logs": current,
                    "metrics": metrics,
                    "historical_events": {"status": "not_requested"},
                    "root_cause_assessment": {
                        "status": "insufficient_evidence",
                        "candidates": [],
                        "requires_independent_validation": True,
                    },
                    "error_code": "METRICS_EVIDENCE_MISSING",
                    "reason": "The log branch is clean, but the required service metric evidence is unavailable or empty.",
                    "retryable": metrics_code != 0,
                }, 0 if metrics_code in (0, 1) else 1)
            candidates = candidate_root_causes(current, {}, metrics, {})
            return persist_result(task_id, args, {
                "status": "trace_ready",
                "diagnosis_status": "INCONCLUSIVE",
                "decision": "diagnose",
                "service": args.service,
                "target": args.target,
                "tenant": args.tenant,
                "searched_minutes": args.since_minutes,
                "open_search_called": False,
                "investigation_window": investigation_window,
                "current_logs": current,
                "metrics": metrics,
                "historical_events": {"status": "not_requested"},
                "root_cause_assessment": {
                    "status": "candidate" if candidates else "insufficient_evidence",
                    "candidates": candidates,
                    "requires_independent_validation": True,
                },
            })
        return persist_result(task_id, args, {"status": "no_anomaly", "decision": "stop", "service": args.service,
                          "target": args.target, "tenant": args.tenant,
                          "searched_minutes": args.since_minutes, "open_search_called": False,
                          "investigation_window": investigation_window,
                          "current_logs": current})
    if current_status != "ok":
        return persist_result(task_id, args, {"status": "unavailable", "decision": "needs_human", "service": args.service,
                          "target": args.target, "tenant": args.tenant,
                          "open_search_called": False, "investigation_window": investigation_window,
                          "current_logs": current}, current_code or 1)

    anchor = anomaly_anchor(current)
    if not anchor:
        return persist_result(task_id, args, {"status": "inconclusive", "decision": "needs_more_evidence", "service": args.service,
                          "target": args.target, "tenant": args.tenant,
                          "searched_minutes": args.since_minutes, "open_search_called": False,
                          "investigation_window": investigation_window,
                          "error_code": "ANOMALY_TIMESTAMP_MISSING", "current_logs": current})
    previous_code, previous = previous_logs(args.service, current, anchor, args.since_minutes, args.limit, env)
    metrics_command = [sys.executable, str(ROOT / "scripts" / "prometheus-query.py"),
                       "--service", args.service, "--profile", "service_up",
                       "--since-minutes", str(args.since_minutes), "--start", start_iso,
                       "--end", end_iso, "--limit", str(args.limit)]
    metrics_code, metrics = run_json(metrics_command, env)
    event_command = [sys.executable, str(ROOT / "scripts" / "opensearch-events-query.py"),
                     "--service", args.service, "--since-minutes", str(args.since_minutes),
                     "--limit", str(args.limit), "--keyword", "deploy", "--keyword", "change",
                     "--keyword", "config"]
    if anchor:
        event_command.extend(("--start", iso_minus(anchor, args.since_minutes), "--end", anchor))
    event_code, events = run_json(event_command, env)
    status = "trace_ready" if complete_log_evidence(current) \
        and (previous.get("status") == "empty" or complete_log_evidence(previous)) \
        and all(item.get("status") in {"ok", "empty"} for item in (metrics, events)) \
        else "trace_incomplete"
    candidates = candidate_root_causes(current, previous, metrics, events)
    result = {"status": status, "decision": "trace", "service": args.service,
                      "target": args.target, "tenant": args.tenant,
                      "searched_minutes": args.since_minutes, "open_search_called": True,
                      "investigation_window": investigation_window,
                      "current_logs": current, "metrics": metrics, "previous_logs": previous,
                      "historical_events": events,
                      "root_cause_assessment": {
                          "status": "candidate" if candidates else "insufficient_evidence",
                          "candidates": candidates,
                          "requires_independent_validation": True,
                      },
                      "retryable": any(code != 0 for code in (metrics_code, previous_code, event_code))}
    return persist_result(task_id, args, result,
                          0 if previous_code == 0 and metrics_code in (0, 1) and event_code in (0, 1) else 1)


if __name__ == "__main__":
    raise SystemExit(main())
