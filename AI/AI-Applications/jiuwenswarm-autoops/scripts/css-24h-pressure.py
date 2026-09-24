#!/usr/bin/env python3
"""Run a bounded 24-hour CSS business-pressure validation.

This is a project-owned test harness.  It generates traffic only to an
explicit customer-owned HTTP load endpoint and observes the registered CSS
profile through ``css-live-pressure.py``.  It never writes to CSS by default.
Real CSS actions require a second explicit mode and confirmation so that a
traffic test cannot accidentally become an autoscaling test.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

from css_config import load_credentials, load_profile, safe_profile_summary
from css_cloud import CssCloudError, cluster_snapshot
from css_action_ledger import resource_key
from css_reconcile import reconcile_action
from css_run_state import (STATE_SCHEMA_VERSION, atomic_write, digest,
                           checkpoint_path, load_checkpoint, reconcile_action_status,
                           unresolved_actions)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "config" / "css" / "pressure-24h.example.json"
DEFAULT_DURATION = 86400
MAX_DURATION = 172800


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"plan must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink evidence path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def positive_int(value: Any, name: str, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if result < 1 or maximum is not None and result > maximum:
        suffix = f"..{maximum}" if maximum is not None else " above 0"
        raise ValueError(f"{name} must be in 1{suffix}")
    return result


def validate_plan(plan: dict[str, Any], duration: int, profile: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != 1:
        raise ValueError("unsupported pressure plan schema_version")
    expected_region = str(plan.get("expected_region", "")).strip()
    if expected_region and profile.get("region") != expected_region:
        raise ValueError(
            f"profile region {profile.get('region')} does not match expected region {expected_region}"
        )
    load = plan.get("load")
    if not isinstance(load, dict):
        raise ValueError("plan.load is required")
    url = str(load.get("url", "")).strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("load.url must be an HTTP(S) URL with a host")
        if parsed.username or parsed.password:
            raise ValueError("load.url must not contain credentials")
    method = str(load.get("method", "GET")).upper()
    if method not in {"GET", "POST"}:
        raise ValueError("load.method must be GET or POST")
    positive_int(load.get("timeout_seconds", 10), "load.timeout_seconds", 120)
    positive_int(load.get("concurrency", 4), "load.concurrency", 100)
    phases = plan.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("plan.phases must contain at least one phase")
    for phase in phases:
        if not isinstance(phase, dict) or not str(phase.get("name", "")).strip():
            raise ValueError("each phase requires a name")
        positive_int(phase.get("duration_seconds"), f"phase {phase.get('name')} duration_seconds")
        rps = float(phase.get("requests_per_second", 0))
        if rps < 0 or rps > 1000:
            raise ValueError("phase requests_per_second must be from 0 through 1000")
        concurrency = phase.get("concurrency", load.get("concurrency", 4))
        positive_int(concurrency, f"phase {phase.get('name')} concurrency", 100)
    if duration < 60 or duration > MAX_DURATION:
        raise ValueError(f"duration must be from 60 through {MAX_DURATION} seconds")
    guardrails = plan.get("guardrails", {})
    if not isinstance(guardrails, dict):
        raise ValueError("plan.guardrails must be an object")
    error_rate = float(guardrails.get("max_error_rate", 0.20))
    if not 0 <= error_rate <= 1:
        raise ValueError("guardrails.max_error_rate must be from 0 through 1")
    positive_int(guardrails.get("bad_cycles", 3), "guardrails.bad_cycles", 100)
    node_wave = plan.get("node_wave")
    normalized_wave = None
    if node_wave is not None:
        if not isinstance(node_wave, dict):
            raise ValueError("plan.node_wave must be an object")
        targets = node_wave.get("targets")
        if not isinstance(targets, list) or len(targets) < 2:
            raise ValueError("plan.node_wave.targets must contain at least two targets")
        normalized_targets = []
        for target in targets:
            normalized_targets.append(positive_int(target, "node_wave target", 100))
        hold_seconds = positive_int(node_wave.get("hold_seconds", 900),
                                    "node_wave.hold_seconds", MAX_DURATION)
        max_actions = positive_int(node_wave.get("max_actions", len(normalized_targets) - 1),
                                   "node_wave.max_actions", 1000)
        max_cycles = positive_int(node_wave.get("max_cycles", 1), "node_wave.max_cycles", 1000)
        max_scale_in_step = positive_int(node_wave.get("max_scale_in_step", 1),
                                         "node_wave.max_scale_in_step", 10)
        repeat = node_wave.get("repeat", max_cycles > 1)
        if not isinstance(repeat, bool):
            raise ValueError("node_wave.repeat must be a boolean")
        normalized_wave = {"targets": normalized_targets, "hold_seconds": hold_seconds,
                           "max_actions": max_actions, "max_cycles": max_cycles,
                           "repeat": repeat,
                           "max_scale_in_step": max_scale_in_step}
        if not normalized_wave["repeat"]:
            normalized_wave["max_cycles"] = 1
    max_css_actions = positive_int(
        plan.get("max_css_actions",
                 normalized_wave["max_actions"] * normalized_wave["max_cycles"]
                 if normalized_wave else 2),
        "max_css_actions", 10000,
    )
    if normalized_wave and max_css_actions < normalized_wave["max_actions"]:
        raise ValueError("max_css_actions must be at least node_wave.max_actions")
    return {
        "schema_version": 1,
        "profile": safe_profile_summary(profile),
        "expected_region": expected_region,
        "duration_seconds": duration,
        "poll_interval_seconds": positive_int(plan.get("poll_interval_seconds", 60), "poll_interval_seconds", 3600),
        "load": {
            "url_configured": bool(url),
            "method": method,
            "timeout_seconds": int(load.get("timeout_seconds", 10)),
            "concurrency": int(load.get("concurrency", 4)),
            "tls_verify": bool(load.get("tls_verify", True)),
        },
        "phases": [
            {"name": str(item["name"]),
             "duration_seconds": int(item["duration_seconds"]),
             "requests_per_second": float(item.get("requests_per_second", 0)),
             "concurrency": int(item.get("concurrency", load.get("concurrency", 4)))}
            for item in phases
        ],
        "guardrails": {
            "max_error_rate": error_rate,
            "max_p95_latency_ms": float(guardrails.get("max_p95_latency_ms", 5000)),
            "bad_cycles": int(guardrails.get("bad_cycles", 3)),
        },
        "node_wave": normalized_wave,
        "max_css_actions": max_css_actions,
        "business_configured": bool(plan.get("business_config_file")),
    }


def load_headers(load: dict[str, Any], plan_path: Path) -> dict[str, str]:
    headers = {"User-Agent": "JiuwenSwarm-AutoOps-CSS-24h/1"}
    headers_path = load.get("headers_file")
    if headers_path:
        path = Path(str(headers_path))
        if not path.is_absolute():
            path = plan_path.parent / path
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"headers_file must be a regular file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("headers_file must contain a JSON object")
        for key, item in value.items():
            if not isinstance(key, str) or not isinstance(item, str):
                raise ValueError("headers_file keys and values must be strings")
            headers[key] = item
    return headers


def load_body(load: dict[str, Any], plan_path: Path) -> bytes | None:
    body_path = load.get("body_file")
    if not body_path:
        return None
    path = Path(str(body_path))
    if not path.is_absolute():
        path = plan_path.parent / path
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"body_file must be a regular file: {path}")
    return path.read_bytes()


def request_once(url: str, method: str, headers: dict[str, str], body: bytes | None,
                timeout: float, tls_verify: bool) -> tuple[bool, int, float]:
    started = time.perf_counter()
    request = urllib.request.Request(url, data=body if method == "POST" else None,
                                     headers=headers, method=method)
    try:
        context = None
        if not tls_verify:
            context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            response.read(1024)
            return 200 <= response.status < 400, response.status, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        return False, exc.code, (time.perf_counter() - started) * 1000
    except (OSError, urllib.error.URLError, TimeoutError):
        return False, 0, (time.perf_counter() - started) * 1000


def phase_load(url: str, method: str, headers: dict[str, str], body: bytes | None,
               timeout: float, tls_verify: bool, phase: dict[str, Any], deadline: float,
               stop_event: threading.Event | None = None) -> dict[str, Any]:
    requested_rps = float(phase["requests_per_second"])
    max_workers = int(phase["concurrency"])
    counts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    latencies: deque[float] = deque(maxlen=10000)
    futures: set[Future[tuple[bool, int, float]]] = set()
    submitted = 0
    started = time.monotonic()
    next_request = started
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while (time.monotonic() < deadline or futures) and not (stop_event and stop_event.is_set()):
            now = time.monotonic()
            while requested_rps > 0 and now < deadline and len(futures) < max_workers and now >= next_request:
                futures.add(executor.submit(request_once, url, method, headers, body, timeout, tls_verify))
                submitted += 1
                next_request += 1.0 / requested_rps
                now = time.monotonic()
            if futures:
                completed, futures = wait(futures, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in completed:
                    ok, status, latency = future.result()
                    counts["success" if ok else "error"] += 1
                    statuses[str(status)] += 1
                    latencies.append(latency)
            elif requested_rps <= 0:
                time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
            elif next_request > time.monotonic():
                time.sleep(min(0.2, next_request - time.monotonic()))
    values = sorted(latencies)
    p95 = values[min(len(values) - 1, int(len(values) * 0.95))] if values else None
    return {
        "name": phase["name"],
        "duration_seconds": round(time.monotonic() - started, 3),
        "target_requests_per_second": requested_rps,
        "submitted": submitted,
        "completed": sum(counts.values()),
        "success": counts["success"],
        "error": counts["error"],
        "error_rate": round(counts["error"] / max(1, sum(counts.values())), 6),
        "p95_latency_ms": round(p95, 2) if p95 is not None else None,
        "mean_latency_ms": round(mean(latencies), 2) if latencies else None,
        "status_counts": dict(statuses),
    }


def run_pressure_worker(*, url: str, method: str, headers: dict[str, str],
                        body: bytes | None, timeout: float, tls_verify: bool,
                        phases: list[dict[str, Any]], poll_interval: int,
                        finish_epoch: float, guardrails: dict[str, Any],
                        state: dict[str, Any], state_lock: threading.Lock,
                        stop_event: threading.Event) -> None:
    """Keep generating the phase plan while the controller reconciles CSS actions."""
    try:
        while time.time() < finish_epoch and not stop_event.is_set():
            with state_lock:
                phase_index = int(state["phase_index"])
                phase_elapsed = float(state["phase_elapsed_seconds"])
                phase = dict(phases[phase_index])
            remaining_phase = float(phase["duration_seconds"]) - phase_elapsed
            segment = min(float(poll_interval), remaining_phase,
                          max(0.0, finish_epoch - time.time()))
            if segment <= 0:
                with state_lock:
                    state["phase_index"] = (phase_index + 1) % len(phases)
                    state["phase_elapsed_seconds"] = 0.0
                continue
            phase["duration_seconds"] = segment
            result = phase_load(url, method, headers, body, timeout, tls_verify,
                                phase, time.monotonic() + segment, stop_event)
            with state_lock:
                state["phases"].append(result)
                state["phases"] = state["phases"][-3000:]
                elapsed = float(result["duration_seconds"])
                state["phase_elapsed_seconds"] = phase_elapsed + elapsed
                if state["phase_elapsed_seconds"] >= float(phases[phase_index]["duration_seconds"]) - 0.001:
                    state["phase_index"] = (phase_index + 1) % len(phases)
                    state["phase_elapsed_seconds"] = 0.0
                recent = list(state["phases"][-int(guardrails["bad_cycles"]):])
                bad = lambda item: (
                    item["error_rate"] > guardrails["max_error_rate"] or
                    item["p95_latency_ms"] is not None and
                    item["p95_latency_ms"] > guardrails["max_p95_latency_ms"]
                )
                if len(recent) >= int(guardrails["bad_cycles"]) and all(map(bad, recent)):
                    state["stopped_reason"] = "BUSINESS_GUARDRAIL_BREACHED"
                    stop_event.set()
    except Exception as exc:
        with state_lock:
            state["stopped_reason"] = "LOAD_WORKER_FAILED"
            state["worker_error"] = type(exc).__name__
        stop_event.set()


def css_observation(args: argparse.Namespace, state_dir: Path, execute: bool,
                    probe_url: str | None = None, probe_headers_file: str | None = None,
                    probe_tls_verify: bool = True, probe_timeout: int = 10,
                    target_nodes: int | None = None,
                    business_config_file: str | None = None,
                    max_scale_in_step: int = 1) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts" / "css-live-pressure.py"),
               "--profile-id", args.profile_id, "--config-dir", str(args.config_dir),
               "--state-dir", str(state_dir / "css-live-pressure"),
               "--iterations", "1", "--interval-seconds", "0", "--max-actions", "1"]
    if execute:
        command.append("--execute")
    if probe_url:
        command.extend(("--probe-url", probe_url, "--probe-timeout", str(probe_timeout)))
    if probe_headers_file:
        command.extend(("--probe-headers-file", probe_headers_file))
    if business_config_file:
        command.extend(("--business-config", business_config_file))
    command.append("--probe-tls-verify" if probe_tls_verify else "--no-probe-tls-verify")
    if target_nodes is not None:
        command.extend(("--target-nodes", str(target_nodes)))
    command.extend(("--max-scale-in-step", str(max_scale_in_step)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        value = {"status": "INVALID_OUTPUT", "exit_code": completed.returncode}
    value["recorded_at"] = now_iso()
    value["process_exit_code"] = completed.returncode
    return value


def plan_output(plan: dict[str, Any], normalized: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {"status": "PLAN_ONLY", "run_id": run_id, "plan": normalized,
            "traffic_writes": False, "css_writes": False,
            "message": "Provide --execute with a configured load URL to send traffic."}


def reconcile_existing_actions(profile: dict[str, Any], config_dir: Path | None,
                               database: Path, resource: str,
                               business_config_file: str | None = None) -> list[dict[str, Any]]:
    actions = unresolved_actions(database, resource)
    if not actions:
        return []
    if business_config_file:
        outcomes = []
        for action in actions:
            command = [
                sys.executable, str(ROOT / "scripts" / "css-live-pressure.py"),
                "--profile-id", str(action.get("profile_id") or profile.get("profile_id")),
                "--config-dir", str(config_dir) if config_dir else "",
                "--state-dir", str(database.parent),
                "--business-config", business_config_file,
                "--reconcile-operation-id", str(action["operation_id"]),
            ]
            command = [part for part in command if part]
            try:
                completed = subprocess.run(command, text=True, capture_output=True,
                                           check=False, timeout=1900)
                result = json.loads(completed.stdout)
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                outcomes.append({"operation_id": action["operation_id"], "status": "UNKNOWN",
                                 "reason_codes": ["RECOVERY_RECONCILIATION_FAILED"],
                                 "error": str(exc)})
                continue
            outcomes.append({"operation_id": action["operation_id"],
                             "previous_status": action["status"],
                             "status": result.get("status", "UNKNOWN"),
                             "reason_codes": result.get("reason_codes", []),
                             "cloud_writes": False})
        return outcomes
    credentials = load_credentials(profile, config_dir)
    try:
        topology = cluster_snapshot(profile, credentials)
    except CssCloudError as exc:
        return [{"operation_id": item["operation_id"], "status": "UNKNOWN",
                 "reason_codes": ["RECONCILIATION_READ_FAILED"], "error": str(exc)}
                for item in actions]
    outcomes = []
    for action in actions:
        result = reconcile_action({"target_nodes": action.get("target_nodes")}, topology,
                                  {"status": "UNVERIFIED"})
        status = str(result.get("status", "UNKNOWN"))
        try:
            status = reconcile_action_status(database, action["operation_id"], status)
        except ValueError as exc:
            result = {**result, "ledger_error": str(exc)}
            status = "UNKNOWN"
        outcomes.append({"operation_id": action["operation_id"],
                         "previous_status": action["status"], "status": status,
                         "reason_codes": result.get("reason_codes", []),
                         "current_nodes": topology.get("data_node_count"),
                         "target_nodes": action.get("target_nodes")})
    return outcomes


def advance_wave(node_wave: dict[str, Any], *, wave_index: int, cycle_index: int,
                 cycle_actions: int, total_actions: int, hold_elapsed: bool,
                 target_reached: bool, total_action_budget: int) -> dict[str, Any]:
    """Advance only after the previous target is observed stable for its hold."""
    result = {"wave_index": wave_index, "cycle_index": cycle_index,
              "cycle_actions": cycle_actions, "advanced": False}
    if not hold_elapsed or not target_reached or total_actions >= total_action_budget:
        return result
    targets = node_wave["targets"]
    if wave_index + 1 < len(targets):
        if cycle_actions >= node_wave["max_actions"]:
            return result
        result.update(wave_index=wave_index + 1, advanced=True)
        return result
    if node_wave["repeat"] and cycle_index + 1 < node_wave["max_cycles"]:
        result.update(wave_index=0, cycle_index=cycle_index + 1,
                      cycle_actions=0, advanced=True)
    return result


def observed_wave_target_reached(observation: dict[str, Any], node_wave: dict[str, Any],
                                wave_index: int) -> bool:
    """Only the observed data-node count can complete a wave target.

    A successful intermediate E01 action (for example 2→3 while aiming for 10)
    is not evidence that the requested wave target has been reached.
    """
    targets = node_wave.get("targets", [])
    if not isinstance(wave_index, int) or not 0 <= wave_index < len(targets):
        return False
    records = observation.get("records", [])
    if not isinstance(records, list) or not records:
        return False
    snapshot = records[-1].get("snapshot", {})
    topology = snapshot.get("topology", {}) if isinstance(snapshot, dict) else {}
    current = topology.get("data_node_count") if isinstance(topology, dict) else None
    return isinstance(current, int) and current == int(targets[wave_index])


def wave_action_blocked(observation: dict[str, Any]) -> bool:
    """Stop traffic immediately when an intended wave step cannot proceed."""
    for record in observation.get("records", []):
        if not isinstance(record, dict):
            continue
        decision = record.get("decision", {})
        if (isinstance(decision, dict)
                and decision.get("decision") in {"scale_out", "scale_in"}
                and decision.get("status") in {"BLOCKED", "RECOMMENDATION"}):
            return True
        runbook = record.get("runbook", {})
        if isinstance(runbook, dict) and runbook and runbook.get("status") not in {
                "SUBMITTED", "RECONCILING", "SUCCEEDED"}:
            return True
        reconciliation = record.get("reconciliation", {})
        if isinstance(reconciliation, dict) and reconciliation.get("status") in {
                "CAPACITY_READY", "DEGRADED", "FAILED", "UNKNOWN", "BLOCKED"}:
            return True
    return False

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a guarded 24-hour CSS business-pressure test.")
    parser.add_argument("--profile-id", default="css-santiago")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--state-dir", type=Path, default=Path(".runtime/css-24h-pressure"))
    parser.add_argument("--resume-run-id", help="Resume this nonterminal run after validating its checkpoint.")
    parser.add_argument("--new-run", action="store_true",
                        help="Create a new run; blocked while this CSS resource has unresolved actions.")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--execute", action="store_true", help="Send traffic to the plan's explicit load URL.")
    parser.add_argument("--css-actions", choices=("observe", "execute"), default="observe")
    parser.add_argument("--confirm-css-writes", action="store_true",
                        help="Required with --css-actions execute; permits E01 writes if policy allows them.")
    parser.add_argument("--confirm-business-impact", action="store_true",
                        help="Required with --execute because this sends real traffic.")
    args = parser.parse_args(argv)
    run_id = f"css-24h-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    try:
        if args.css_actions == "execute" and not args.confirm_css_writes:
            raise ValueError("--css-actions execute requires --confirm-css-writes")
        if args.execute and not args.confirm_business_impact:
            raise ValueError("--execute requires --confirm-business-impact")
        profile = load_profile(args.profile_id, args.config_dir)
        plan = read_json(args.plan)
        normalized = validate_plan(plan, args.duration_seconds, profile)
        args.state_dir.mkdir(parents=True, exist_ok=True)
        resource = resource_key(profile)
        ledger_path = Path(os.environ.get("AUTOOPS_CSS_ACTION_DB") or
                           (args.state_dir / "css-live-pressure" / "css-actions.sqlite3"))
        headers = load_headers(plan["load"], args.plan)
        body = load_body(plan["load"], args.plan)
        business_config_file = plan.get("business_config_file")
        if business_config_file:
            business_config_path = Path(str(business_config_file))
            if not business_config_path.is_absolute():
                business_config_path = args.plan.parent / business_config_path
            if business_config_path.is_symlink() or not business_config_path.is_file():
                raise ValueError("business_config_file must point to a regular file")
            business_config_file = str(business_config_path)
        business_digest = None
        if business_config_file:
            business_digest = digest(read_json(Path(business_config_file)))
        plan_digest = digest({"plan": plan, "duration_seconds": args.duration_seconds,
                              "business_config_digest": business_digest})
        recovery = reconcile_existing_actions(profile, args.config_dir, ledger_path, resource,
                                              business_config_file)
        remaining_actions = unresolved_actions(ledger_path, resource)
        if remaining_actions:
            return print(json.dumps({
                "status": "RECOVERY_BLOCKED", "error_code": "UNRESOLVED_CSS_ACTIONS",
                "message": "Existing CSS actions were read-only reconciled; business verification is required before new writes.",
                "reconciliation": recovery,
                "operation_ids": [item["operation_id"] for item in remaining_actions],
                "secrets_included": False,
            }, ensure_ascii=False)) or 1
        output = plan_output(plan, normalized, run_id)
        if not args.execute:
            if args.evidence:
                write_json(args.evidence, output)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        url = str(plan["load"].get("url", "")).strip()
        if not url:
            raise ValueError("--execute requires plan.load.url")
        probe_headers_file = plan["load"].get("headers_file")
        if probe_headers_file:
            probe_headers_path = Path(str(probe_headers_file))
            if not probe_headers_path.is_absolute():
                probe_headers_path = args.plan.parent / probe_headers_path
            probe_headers_file = str(probe_headers_path)
        preflight_ok, preflight_status, preflight_latency = request_once(
            url, normalized["load"]["method"], headers, body,
            normalized["load"]["timeout_seconds"], normalized["load"]["tls_verify"],
        )
        if not preflight_ok:
            result = {
                "schema_version": 1, "status": "BLOCKED_LOAD_PREFLIGHT",
                "run_id": run_id, "profile": safe_profile_summary(profile),
                "execution_level": "BUSINESS_E2E_REAL",
                "preflight": {"http_status": preflight_status,
                              "latency_ms": round(preflight_latency, 2),
                              "reason": "load endpoint did not return 2xx/3xx"},
                "traffic_writes": False, "css_write_mode": args.css_actions,
                "css_actions_submitted": 0, "secrets_included": False,
                "load_endpoint_included": False,
            }
            if args.evidence:
                write_json(args.evidence, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        resume_state = None
        if args.resume_run_id:
            run_id = args.resume_run_id
            resume_state = load_checkpoint(
                checkpoint_path(args.state_dir, run_id), plan_digest=plan_digest,
                profile_id=args.profile_id, duration_seconds=args.duration_seconds,
            )
        elif not args.new_run:
            resumable = []
            incompatible = []
            for candidate in args.state_dir.glob("*.checkpoint.json"):
                try:
                    value = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if value.get("status") == "RUNNING" and value.get("profile_id") == args.profile_id:
                    if value.get("plan_digest") == plan_digest:
                        resumable.append((candidate, value))
                    else:
                        incompatible.append(candidate.name)
            if incompatible:
                raise ValueError("an unfinished run exists with a different plan; inspect it before starting another")
            if len(resumable) > 1:
                raise ValueError("multiple matching RUNNING checkpoints; choose --resume-run-id")
            if resumable:
                checkpoint_file, resume_state = resumable[0]
                run_id = str(resume_state.get("run_id", checkpoint_file.name.removesuffix(".checkpoint.json")))
        checkpoint = checkpoint_path(args.state_dir, run_id)
        started = (datetime.fromisoformat(resume_state["started_at"].replace("Z", "+00:00")).timestamp()
                   if resume_state else time.time())
        finish = started + args.duration_seconds
        observations: list[dict[str, Any]] = list((resume_state or {}).get("observations", []))
        phases: list[dict[str, Any]] = list((resume_state or {}).get("phases", []))
        phase_index = int((resume_state or {}).get("phase_index", 0))
        phase_elapsed = float((resume_state or {}).get("phase_elapsed_seconds", 0))
        pressure_state = {"phase_index": phase_index,
                          "phase_elapsed_seconds": phase_elapsed,
                          "phases": phases, "stopped_reason": None}
        pressure_lock = threading.Lock()
        pressure_stop = threading.Event()

        def pressure_snapshot() -> dict[str, Any]:
            with pressure_lock:
                return {"phase_index": pressure_state["phase_index"],
                        "phase_elapsed_seconds": pressure_state["phase_elapsed_seconds"],
                        "phases": list(pressure_state["phases"]),
                        "stopped_reason": pressure_state.get("stopped_reason"),
                        "worker_error": pressure_state.get("worker_error")}

        pressure_worker: threading.Thread | None = None
        last_poll = 0.0
        stopped_reason = None
        guardrails = normalized["guardrails"]
        total_css_actions = int((resume_state or {}).get("total_css_actions", 0))
        css_actions_enabled = bool((resume_state or {}).get(
            "css_actions_enabled", args.css_actions == "execute")) and args.css_actions == "execute"
        css_actions_suspended_at = (resume_state or {}).get("css_actions_suspended_at")
        node_wave = normalized.get("node_wave")
        wave_index = int((resume_state or {}).get("wave_index", 0))
        cycle_index = int((resume_state or {}).get("cycle_index", 0))
        cycle_actions = int((resume_state or {}).get("cycle_actions", 0))
        wave_target_reached = bool((resume_state or {}).get("wave_target_reached", False))
        hold_value = (resume_state or {}).get("wave_hold_started")
        wave_hold_started = (datetime.fromisoformat(hold_value.replace("Z", "+00:00")).timestamp()
                             if hold_value else started)
        if resume_state:
            if time.time() >= finish:
                raise ValueError("checkpoint duration already elapsed; refusing to restart an expired run")
        else:
            atomic_write(checkpoint, {
                "schema_version": STATE_SCHEMA_VERSION, "status": "RUNNING", "run_id": run_id,
                "profile_id": args.profile_id, "plan_digest": plan_digest,
                "duration_seconds": args.duration_seconds,
                "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat().replace("+00:00", "Z"),
                "elapsed_seconds": 0, "phase_index": phase_index,
                "phase_elapsed_seconds": phase_elapsed, "phases": [], "observations": [],
                "css_actions_enabled": css_actions_enabled,
                "css_actions_suspended_at": css_actions_suspended_at,
                "total_css_actions": total_css_actions, "cycle_actions": cycle_actions,
                "node_wave": node_wave, "wave_index": wave_index, "cycle_index": cycle_index,
                "wave_target_reached": wave_target_reached,
                "wave_hold_started": datetime.fromtimestamp(wave_hold_started, timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        pressure_worker = threading.Thread(
            target=run_pressure_worker,
            kwargs={"url": url, "method": normalized["load"]["method"],
                    "headers": headers, "body": body,
                    "timeout": normalized["load"]["timeout_seconds"],
                    "tls_verify": normalized["load"]["tls_verify"],
                    "phases": normalized["phases"],
                    "poll_interval": normalized["poll_interval_seconds"],
                    "finish_epoch": finish, "guardrails": guardrails,
                    "state": pressure_state, "state_lock": pressure_lock,
                    "stop_event": pressure_stop},
            name="css-24h-pressure-worker", daemon=True,
        )
        pressure_worker.start()
        while time.time() < finish:
            if pressure_stop.is_set():
                stopped_reason = pressure_snapshot().get("stopped_reason") or "PRESSURE_STOPPED"
                break
            if time.time() - last_poll >= normalized["poll_interval_seconds"] or not observations:
                wave_target = None
                if node_wave:
                    hold_elapsed = time.time() - wave_hold_started >= node_wave["hold_seconds"]
                    advanced = advance_wave(
                        node_wave, wave_index=wave_index, cycle_index=cycle_index,
                        cycle_actions=cycle_actions, total_actions=total_css_actions,
                        hold_elapsed=hold_elapsed, target_reached=wave_target_reached,
                        total_action_budget=normalized["max_css_actions"],
                    )
                    if advanced["advanced"]:
                        wave_index = advanced["wave_index"]
                        cycle_index = advanced["cycle_index"]
                        cycle_actions = advanced["cycle_actions"]
                        wave_target_reached = False
                        wave_hold_started = time.time()
                    wave_target = node_wave["targets"][wave_index]
                with ThreadPoolExecutor(max_workers=1) as controller_executor:
                    observation_future = controller_executor.submit(
                        css_observation, args, args.state_dir, css_actions_enabled, url,
                        probe_headers_file, normalized["load"]["tls_verify"],
                        normalized["load"]["timeout_seconds"], wave_target,
                        business_config_file,
                        node_wave["max_scale_in_step"] if node_wave else 1,
                    )
                    while not observation_future.done():
                        progress = pressure_snapshot()
                        try:
                            heartbeat = json.loads(checkpoint.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            heartbeat = {}
                        heartbeat.update({
                            "status": "RUNNING", "controller_action_in_progress": True,
                            "controller_started_at": heartbeat.get("controller_started_at") or now_iso(),
                            "elapsed_seconds": round(time.time() - started, 3),
                            "phase_index": progress["phase_index"],
                            "phase_elapsed_seconds": progress["phase_elapsed_seconds"],
                            "phases": progress["phases"][-3000:],
                            "pressure_guardrail_stop": pressure_stop.is_set(),
                            "pressure_stop_reason": progress.get("stopped_reason"),
                        })
                        atomic_write(checkpoint, heartbeat)
                        time.sleep(1)
                    observation = observation_future.result()
                observations.append(observation)
                last_poll = time.time()
                if observation.get("status") != "COMPLETED":
                    stopped_reason = "CSS_TELEMETRY_UNAVAILABLE"
                    pressure_stop.set()
                    break
                new_actions = int(observation.get("submitted_actions", 0) or 0)
                total_css_actions += new_actions
                cycle_actions += new_actions
                if css_actions_enabled and total_css_actions >= normalized["max_css_actions"]:
                    css_actions_enabled = False
                    css_actions_suspended_at = now_iso()
                if node_wave:
                    was_at_target = wave_target_reached
                    wave_target_reached = observed_wave_target_reached(
                        observation, node_wave, wave_index
                    )
                    if wave_target_reached and not was_at_target:
                        wave_hold_started = time.time()
                load_progress = pressure_snapshot()
                phases = load_progress["phases"]
                phase_index = load_progress["phase_index"]
                phase_elapsed = load_progress["phase_elapsed_seconds"]
                atomic_write(checkpoint, {
                    "schema_version": STATE_SCHEMA_VERSION, "status": "RUNNING", "run_id": run_id,
                    "profile_id": args.profile_id, "plan_digest": plan_digest,
                    "duration_seconds": args.duration_seconds,
                    "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat().replace("+00:00", "Z"),
                    "elapsed_seconds": round(time.time() - started, 3),
                    "phase_index": phase_index, "phase_elapsed_seconds": phase_elapsed,
                    "phases": phases[-3000:], "observations": observations[-20:],
                    "css_actions_enabled": css_actions_enabled,
                    "css_actions_suspended_at": css_actions_suspended_at,
                    "total_css_actions": total_css_actions, "cycle_actions": cycle_actions,
                    "node_wave": node_wave, "wave_index": wave_index, "cycle_index": cycle_index,
                    "wave_target_reached": wave_target_reached,
                    "wave_hold_started": datetime.fromtimestamp(wave_hold_started, timezone.utc).isoformat().replace("+00:00", "Z"),
                })
                if node_wave and wave_action_blocked(observation):
                    stopped_reason = "CSS_WAVE_ACTION_BLOCKED"
                    css_actions_enabled = False
                    css_actions_suspended_at = now_iso()
                    pressure_stop.set()
                    break
            pressure_stop.wait(min(1.0, max(0.0, finish - time.time())))
        pressure_stop.set()
        if pressure_worker:
            pressure_worker.join(timeout=15)
        load_progress = pressure_snapshot()
        phases = load_progress["phases"]
        phase_index = load_progress["phase_index"]
        phase_elapsed = load_progress["phase_elapsed_seconds"]
        stopped_reason = stopped_reason or load_progress.get("stopped_reason")
        if load_progress.get("worker_error"):
            stopped_reason = stopped_reason or "LOAD_WORKER_FAILED"
        result = {
            "schema_version": 1,
            "status": "STOPPED_GUARDRAIL" if stopped_reason else "COMPLETED",
            "run_id": run_id,
            "profile": safe_profile_summary(profile),
            "execution_level": "BUSINESS_E2E_REAL",
            "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat().replace("+00:00", "Z"),
            "finished_at": now_iso(),
            "requested_duration_seconds": args.duration_seconds,
            "elapsed_seconds": round(time.time() - started, 3),
            "stopped_reason": stopped_reason,
            "traffic_writes": True,
            "css_write_mode": args.css_actions,
            "preflight": {"http_status": preflight_status,
                          "latency_ms": round(preflight_latency, 2)},
            "css_actions_submitted": total_css_actions,
            "css_actions_enabled_at_finish": css_actions_enabled,
            "css_actions_suspended_at": css_actions_suspended_at,
            "max_css_actions": normalized["max_css_actions"],
            "node_wave": node_wave,
            "wave_index": wave_index,
            "cycle_index": cycle_index,
            "total_cycles": node_wave["max_cycles"] if node_wave else 1,
            "phases": phases,
            "css_observations": observations,
            "secrets_included": False,
            "load_endpoint_included": False,
        }
        if args.evidence:
            write_json(args.evidence, result)
        try:
            final_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            final_checkpoint = {}
        final_checkpoint.update({"schema_version": STATE_SCHEMA_VERSION,
                                 "status": "STOPPED_GUARDRAIL" if stopped_reason else "COMPLETED",
                                 "run_id": run_id, "profile_id": args.profile_id,
                                 "plan_digest": plan_digest, "duration_seconds": args.duration_seconds,
                                 "finished_at": now_iso(), "elapsed_seconds": round(time.time() - started, 3),
                                 "total_css_actions": total_css_actions,
                                 "css_actions_enabled": css_actions_enabled,
                                 "cycle_index": cycle_index, "wave_index": wave_index})
        atomic_write(checkpoint, final_checkpoint)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not stopped_reason else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "INPUT_ERROR", "run_id": run_id, "error": str(exc),
                  "secrets_included": False}
        print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
