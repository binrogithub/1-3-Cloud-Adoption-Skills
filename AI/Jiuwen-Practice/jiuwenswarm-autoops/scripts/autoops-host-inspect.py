#!/usr/bin/env python3
"""Run the published E01 host inspection as a read-only project adapter."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from autoops_context import resolve
from autoops_contract import step_result


def systemctl(*args: str) -> tuple[int, str]:
    completed = subprocess.run(["systemctl", *args], text=True,
                               capture_output=True, check=False)
    return completed.returncode, completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect one published service without changing host state.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--service", required=True)
    args = parser.parse_args(argv)

    context_result = resolve(service=args.service, target=args.target, include_test=True)
    if context_result.get("status") != "RESOLVED":
        payload = step_result(task_id=args.task_id, step_id="inspect-host",
                              capability="host.inspect.v1",
                              execution_status="FAILED", changed=False,
                              error_code="SERVICE_SCOPE_UNAVAILABLE",
                              detail={"context": context_result})
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    context = context_result["context"]
    unit = context.get("systemd_unit")
    if not unit:
        payload = step_result(task_id=args.task_id, step_id="inspect-host",
                              capability="host.inspect.v1",
                              execution_status="FAILED", changed=False,
                              error_code="SYSTEMD_UNIT_NOT_PUBLISHED")
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    active_code, active_state = systemctl("is-active", unit)
    load_code, load_state = systemctl("show", unit, "--property=LoadState", "--value")
    sub_code, sub_state = systemctl("show", unit, "--property=SubState", "--value")
    status = "SUCCEEDED" if active_code == 0 and load_code == 0 and sub_code == 0 else "PARTIAL"
    payload = step_result(
        task_id=args.task_id,
        step_id="inspect-host",
        capability="host.inspect.v1",
        execution_status=status,
        changed=False,
        detail={
            "service": args.service,
            "systemd_unit": unit,
            "active_state": active_state or "unknown",
            "unit_load_state": load_state or "unknown",
            "sub_state": sub_state or "unknown",
            "target": args.target,
            "source": "systemd",
            "commands": ["systemctl is-active", "systemctl show LoadState", "systemctl show SubState"],
            "return_codes": {"is_active": active_code, "load_state": load_code, "sub_state": sub_code},
            "profile_id": context.get("profile_id"),
            "profile_revision": context.get("profile_revision"),
        },
    )
    payload.update({"service": args.service, "systemd_unit": unit,
                    "active_state": active_state or "unknown",
                    "unit_load_state": load_state or "unknown",
                    "sub_state": sub_state or "unknown", "target": args.target})
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if status in {"SUCCEEDED", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
