#!/usr/bin/env python3
"""Run one bounded observability flow for each service in a shared task.

This is a project-owned glue adapter for cross-service requests. It keeps the
TUI/ProjectManager contract at one operational command while preserving each
service's evidence and making the shared target/window explicit.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Correlate bounded observability flows for multiple services.")
    parser.add_argument("--service", action="append", required=True)
    parser.add_argument("--target", default="local")
    parser.add_argument("--tenant", default="")
    parser.add_argument("--since-minutes", type=int, default=1440)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    if len(args.service) < 2 or any(not SERVICE_PATTERN.fullmatch(item) for item in args.service):
        print(json.dumps({"status": "invalid", "error_code": "INVALID_SERVICES"}, ensure_ascii=False))
        return 2
    if not 1 <= args.since_minutes <= 1440 or not 1 <= args.limit <= 200:
        print(json.dumps({"status": "invalid", "error_code": "INVALID_INPUT"}, ensure_ascii=False))
        return 2

    # One correlation task owns one exact window. Passing the same boundaries
    # to every child avoids each child calculating its own ``now`` timestamp.
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(minutes=args.since_minutes)
    start_iso = window_start.isoformat().replace("+00:00", "Z")
    end_iso = window_end.isoformat().replace("+00:00", "Z")

    results = {}
    exit_codes = []
    for service in args.service:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "observability-investigate.py"),
            "--service", service,
            "--target", args.target,
            "--tenant", args.tenant,
            "--since-minutes", str(args.since_minutes),
            "--limit", str(args.limit),
            "--start", start_iso, "--end", end_iso,
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        exit_codes.append(completed.returncode)
        try:
            results[service] = json.loads(completed.stdout.strip())
        except json.JSONDecodeError:
            results[service] = {
                "status": "unavailable",
                "error_code": "ADAPTER_NO_JSON",
                "error": completed.stderr.strip()[-500:] or "adapter returned no JSON",
            }

    statuses = [item.get("status") for item in results.values()]
    if all(status == "no_anomaly" for status in statuses):
        status, decision = "no_anomaly", "stop"
    elif any(status in {"trace_ready", "trace"} for status in statuses):
        status, decision = "correlation_ready", "trace"
    elif any(status in {"unavailable", "invalid", "trace_incomplete"} for status in statuses):
        status, decision = "incomplete", "needs_human"
    else:
        status, decision = "correlation_inconclusive", "needs_human"
    payload = {
        "schema_version": 1,
        "status": status,
        "decision": decision,
        "services": args.service,
        "target": args.target,
        "tenant": args.tenant,
        "searched_minutes": args.since_minutes,
        "shared_window": {"start": start_iso, "end": end_iso,
                          "requested_minutes": args.since_minutes},
        "limit": args.limit,
        "results": results,
        "open_search_called": any(item.get("open_search_called") for item in results.values()),
        "retryable": any(code not in (0, 1) for code in exit_codes),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if status in {"no_anomaly", "correlation_ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
