#!/usr/bin/env python3
"""Read-only verifier for the one published AutoOps service."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from autoops_contract import step_result
from autoops_context import resolve

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "service-verification.json"


def published_service_config(service: str, target: str) -> dict:
    """Resolve probe and unit data from the application binding first."""
    configured = json.loads(CONFIG.read_text(encoding="utf-8"))["services"].get(service)
    if not configured:
        return {}
    result = resolve(service=service, include_test=True)
    if result.get("status") != "RESOLVED":
        return configured
    context = result["context"]
    published_target = context["target"]["name"]
    if target not in {"local", published_target}:
        return {"targets": [published_target], "target_aliases": {"local": published_target}}
    bound = context.get("verification") if isinstance(context.get("verification"), dict) else {}
    merged = dict(configured)
    merged.update(bound)
    merged["systemd_unit"] = context.get("systemd_unit") or merged.get("systemd_unit")
    merged["targets"] = [published_target]
    merged["target_aliases"] = {"local": published_target}
    return merged


def unit_state(unit: str) -> str:
    completed = subprocess.run(["systemctl", "is-active", unit], text=True, capture_output=True, check=False)
    return completed.stdout.strip() or "unknown"


def unit_restart_count(unit: str) -> int | None:
    """Read the systemd restart counter used to validate the observation window."""
    completed = subprocess.run(["systemctl", "show", unit, "--property=NRestarts", "--value"],
                               text=True, capture_output=True, check=False)
    value = completed.stdout.strip()
    try:
        return int(value) if completed.returncode == 0 and value else None
    except ValueError:
        return None


def probe(url: str, attempts: int, interval_seconds: int) -> tuple[bool, list[str], float]:
    evidence: list[str] = []
    failures = 0
    for index in range(attempts):
        try:
            with urlopen(url, timeout=3) as response:
                evidence.append(f"http={response.status}")
                if response.status != 200:
                    failures += 1
        except HTTPError as error:
            failures += 1
            evidence.append(f"http={error.code}")
        except (URLError, TimeoutError) as error:
            failures += 1
            evidence.append(f"probe_error={type(error).__name__}")
        if index + 1 < attempts and interval_seconds:
            time.sleep(interval_seconds)
    return failures == 0, evidence, failures / attempts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--probe-url")
    parser.add_argument("--attempts", type=int)
    parser.add_argument("--interval-seconds", type=int)
    parser.add_argument("--action-completed-at", type=float)
    args = parser.parse_args(argv)
    config = published_service_config(args.service, args.target)
    if not config:
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id, capability="service.verify.v1", execution_status="FAILED", verification_status="NOT_APPLICABLE", error_code="SERVICE_NOT_PUBLISHED")))
        return 2
    if args.action_completed_at is not None:
        if args.action_completed_at <= 0 or args.action_completed_at > time.time():
            print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                         capability="service.verify.v1", execution_status="FAILED",
                                         verification_status="NOT_APPLICABLE", changed=False,
                                         error_code="INVALID_ACTION_COMPLETION_TIME")))
            return 2
    configured_targets = config.get("targets", [])
    aliases = config.get("target_aliases", {})
    resolved_target = aliases.get(args.target, args.target)
    if resolved_target not in configured_targets:
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                     capability="service.verify.v1", execution_status="FAILED",
                                     verification_status="NOT_APPLICABLE", changed=False,
                                     error_code="TARGET_NOT_PUBLISHED",
                                     detail={"target": args.target, "published_targets": configured_targets})))
        return 2
    state = unit_state(config["systemd_unit"])
    refs = [{"source": "systemd", "target": resolved_target, "service": args.service, "state": state,
             "action_completed_at": args.action_completed_at}]
    if state != "active":
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id, capability="service.verify.v1", execution_status="FAILED", verification_status="FAILED", changed=False, evidence_refs=refs, error_code="SERVICE_NOT_ACTIVE")))
        return 1
    url = args.probe_url or config.get("health_url")
    attempts = args.attempts if args.attempts is not None else config.get("probe_attempts", 3)
    interval = args.interval_seconds if args.interval_seconds is not None else config.get("probe_interval_seconds", 10)
    if not isinstance(attempts, int) or not 1 <= attempts <= 60 or not isinstance(interval, int) or not 0 <= interval <= 3600:
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                     capability="service.verify.v1", execution_status="FAILED",
                                     verification_status="NOT_APPLICABLE", changed=False,
                                     error_code="INVALID_VERIFICATION_WINDOW")))
        return 2
    if attempts < 7:
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                     capability="service.verify.v1", execution_status="PARTIAL",
                                     verification_status="INCONCLUSIVE", changed=False,
                                     evidence_refs=refs, error_code="INSUFFICIENT_SAMPLES",
                                     detail={"required_samples": 7, "requested_samples": attempts})))
        return 1
    restart_before = unit_restart_count(config["systemd_unit"])
    if config.get("require_restart_counter", True) and restart_before is None:
        refs.append({"source": "systemd", "restart_counter": None})
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                     capability="service.verify.v1", execution_status="PARTIAL",
                                     verification_status="INCONCLUSIVE", changed=False,
                                     evidence_refs=refs, error_code="RESTART_COUNTER_UNAVAILABLE")))
        return 1
    if not url:
        print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id, capability="service.verify.v1", execution_status="PARTIAL", verification_status="INCONCLUSIVE", changed=False, evidence_refs=refs, error_code="NO_HEALTH_PROBE")))
        return 1
    healthy, probe_refs, error_rate = probe(url, attempts, interval)
    restart_after = unit_restart_count(config["systemd_unit"])
    refs.append({"source": "health_probe", "url": url, "attempts": attempts,
                 "observations": probe_refs, "minimum_samples": 7,
                 "error_rate": error_rate,
                 "max_error_rate": config.get("max_http_error_rate", 0.0),
                 "observed_at": time.time()})
    refs.append({"source": "systemd_restart_counter", "before": restart_before, "after": restart_after})
    if restart_after is None:
        verdict, error_code = "INCONCLUSIVE", "RESTART_COUNTER_UNAVAILABLE"
    elif restart_after != restart_before:
        verdict, error_code = "FAILED", "SERVICE_RESTARTED_DURING_WINDOW"
    elif error_rate > float(config.get("max_http_error_rate", 0.0)):
        verdict, error_code = "FAILED", "HEALTH_PROBE_ERROR_RATE"
    elif not healthy or unit_state(config["systemd_unit"]) != "active":
        verdict, error_code = "FAILED", "HEALTH_PROBE_FAILED"
    else:
        verdict, error_code = "PASSED", None
    execution_status = "SUCCEEDED" if verdict == "PASSED" else "PARTIAL" if verdict == "INCONCLUSIVE" else "FAILED"
    print(json.dumps(step_result(task_id=args.task_id, step_id=args.step_id,
                                 capability="service.verify.v1", execution_status=execution_status,
                                 verification_status=verdict, changed=False, evidence_refs=refs,
                                 error_code=error_code)))
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
