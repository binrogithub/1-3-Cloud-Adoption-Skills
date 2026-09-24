#!/usr/bin/env python3
"""Independently verify a published Kubernetes workload's business probe.

The Kubernetes adapter owns resource postconditions.  This adapter owns the
read-only application probe, so Deployment Ready cannot be mistaken for
business recovery.  The URL and sampling policy always come from the
published workload binding; callers cannot supply an arbitrary probe URL.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from autoops_contract import step_result

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("AUTOOPS_KUBERNETES_WORKLOADS_FILE",
                            str(ROOT / "config" / "kubernetes" / "workloads.json")))


def published_probe(cluster_name: str, workload_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cluster = config["clusters"][cluster_name]
        workload = cluster["workloads"][workload_id]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None, "PUBLISHED_WORKLOAD_NOT_FOUND"
    if cluster.get("enabled") is not True:
        return None, "CLUSTER_NOT_ENABLED"
    probe = workload.get("business_verification")
    if not isinstance(probe, dict) or not isinstance(probe.get("health_url"), str) \
            or not probe["health_url"].strip():
        return None, "NO_BUSINESS_PROBE"
    return probe, None


def probe(url: str, attempts: int, interval_seconds: int) -> tuple[list[dict[str, Any]], float]:
    evidence: list[dict[str, Any]] = []
    failures = 0
    for index in range(attempts):
        observed_at = time.time()
        try:
            with urlopen(url, timeout=3) as response:
                ok = response.status == 200
                evidence.append({"observed_at": observed_at, "http_status": response.status, "ok": ok})
                failures += 0 if ok else 1
        except HTTPError as error:
            failures += 1
            evidence.append({"observed_at": observed_at, "http_status": error.code, "ok": False})
        except (URLError, TimeoutError) as error:
            failures += 1
            evidence.append({"observed_at": observed_at, "probe_error": type(error).__name__, "ok": False})
        if index + 1 < attempts and interval_seconds:
            time.sleep(interval_seconds)
    return evidence, failures / attempts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a published Kubernetes business health probe.")
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--step-id", default="verify-business")
    parser.add_argument("--action-completed-at", type=float, required=True)
    args = parser.parse_args(argv)
    base = {"task_id": args.task_id, "step_id": args.step_id,
            "capability": "service.verify.v1", "changed": False}
    config, error_code = published_probe(args.cluster, args.workload)
    if error_code:
        status = "INCONCLUSIVE" if error_code in {"NO_BUSINESS_PROBE", "CLUSTER_NOT_ENABLED"} else "NOT_APPLICABLE"
        code = 1 if status == "INCONCLUSIVE" else 2
        print(json.dumps(step_result(**base, execution_status="SUCCEEDED" if code == 1 else "FAILED",
                                     verification_status=status, error_code=error_code,
                                     detail={"cluster": args.cluster, "workload": args.workload}), ensure_ascii=False))
        return code
    attempts = config.get("probe_attempts", 7)
    interval = config.get("probe_interval_seconds", 10)
    if not isinstance(attempts, int) or not 1 <= attempts <= 60 \
            or not isinstance(interval, int) or not 0 <= interval <= 3600:
        print(json.dumps(step_result(**base, execution_status="FAILED", verification_status="NOT_APPLICABLE",
                                     error_code="INVALID_VERIFICATION_WINDOW"), ensure_ascii=False))
        return 2
    evidence, error_rate = probe(config["health_url"], attempts, interval)
    max_error_rate = float(config.get("max_http_error_rate", 0.0))
    post_action = [item for item in evidence if item["observed_at"] >= args.action_completed_at]
    if len(post_action) != len(evidence):
        verdict, error_code = "INCONCLUSIVE", "PRE_ACTION_EVIDENCE"
    elif error_rate > max_error_rate:
        verdict, error_code = "FAILED", "HEALTH_PROBE_ERROR_RATE"
    else:
        verdict, error_code = "PASSED", None
    refs = [{"source": "kubernetes_business_probe", "url": config["health_url"],
             "attempts": attempts, "observations": evidence,
             "action_completed_at": args.action_completed_at,
             "max_error_rate": max_error_rate}]
    print(json.dumps(step_result(**base, execution_status="SUCCEEDED", verification_status=verdict,
                                 evidence_refs=refs, error_code=error_code), ensure_ascii=False))
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
