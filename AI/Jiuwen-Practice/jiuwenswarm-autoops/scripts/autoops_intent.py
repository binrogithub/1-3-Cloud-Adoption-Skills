#!/usr/bin/env python3
"""Small, deterministic intent helpers used at the ProjectManager boundary.

The model remains responsible for understanding rich language.  These helpers
only normalize common scope and time phrases after the request reaches the
project-owned dispatcher; they never inspect a host or execute an action.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "autoops-input-policy.json"
DEFAULT_WINDOW_MINUTES = 1440  # compatibility fallback for an old install
HOST_LOG_TERMS = (
    "linux系统日志", "linux 系统日志", "linux日志", "linux 日志", "系统日志",
    "本机日志", "本机 linux", "本机linux", "host logs", "system logs", "linux logs",
    "journalctl", "journal 日志",
)
HOST_TARGETS = {"local", "localhost", "本机", "本地"}


def load_input_policy() -> dict[str, Any]:
    path = Path(os.environ.get("AUTOOPS_INPUT_POLICY_FILE", str(DEFAULT_POLICY))).expanduser()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"default_target": "local", "default_window_minutes": DEFAULT_WINDOW_MINUTES,
                "default_timezone": "Asia/Shanghai"}
    return value if isinstance(value, dict) else {"default_target": "local", "default_window_minutes": DEFAULT_WINDOW_MINUTES,
                                                    "default_timezone": "Asia/Shanghai"}


def is_host_system_request(request: str, *, service: str | None = None,
                           application: str | None = None,
                           log_path: str | None = None) -> bool:
    """Return true only for an explicit host/system-log request.

    An application named ``local`` is not treated as a host request when the
    caller has explicitly supplied an application or service scope.
    """
    if application or log_path:
        return False
    if service:
        return service.strip().casefold() in HOST_TARGETS and any(
            term in request.casefold() for term in HOST_LOG_TERMS
        )
    text = request.casefold()
    return any(term in text for term in HOST_LOG_TERMS) or (
        "日志" in text and any(term in text for term in ("本机", "linux", "系统"))
    )


def normalize_target(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    return "local" if normalized in HOST_TARGETS else value.strip()


def parse_time_window(request: str, explicit_minutes: int | None = None) -> dict[str, Any]:
    """Convert common operator time phrases into a bounded minute window."""
    text = request.casefold()
    policy = load_input_policy()
    timezone_name = str(policy.get("default_timezone", "Asia/Shanghai"))
    if explicit_minutes is not None:
        return {"minutes": explicit_minutes, "expression": f"{explicit_minutes} minutes",
                "source": "explicit_parameter", "timezone": timezone_name}
    if re.search(r"(?:24\s*小时|24\s*小時|24\s*hour|last\s+24|过去一天|最近一天)", text):
        return {"minutes": 1440, "expression": "最近24小时", "source": "operator_request",
                "timezone": timezone_name}
    if re.search(r"(?:最近|过去|last\s*)\s*(?:一|1)\s*(?:小时|小時|hour|h)", text):
        return {"minutes": 60, "expression": "最近1小时", "source": "operator_request",
                "timezone": timezone_name}
    match = re.search(r"(?:最近|过去|last\s*)\s*(\d+)\s*(分钟|分|min|minutes|小时|小時|hour|hours|h)", text)
    if match:
        value = int(match.group(1))
        if match.group(2) in {"小时", "小時", "hour", "hours", "h"}:
            value *= 60
        return {"minutes": value, "expression": match.group(0), "source": "operator_request",
                "timezone": timezone_name}
    if "今天" in text or "today" in text:
        now = datetime.now(ZoneInfo(timezone_name))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        minutes = max(1, int((now - start).total_seconds() // 60) + 1)
        return {"minutes": minutes, "expression": "今天", "source": "operator_request",
                "timezone": timezone_name, "start": start.isoformat(), "end": now.isoformat()}
    default_minutes = int(policy.get("default_window_minutes", DEFAULT_WINDOW_MINUTES))
    return {"minutes": default_minutes, "expression": f"最近{default_minutes // 60}小时",
            "source": "default_policy", "timezone": policy.get("default_timezone", "Asia/Shanghai")}


def parse_request(request: str, *, service: str | None = None,
                  application: str | None = None, target: str | None = None,
                  log_path: str | None = None,
                  explicit_minutes: int | None = None) -> dict[str, Any]:
    host_scope = is_host_system_request(request, service=service,
                                        application=application, log_path=log_path)
    target_value = normalize_target(target)
    if host_scope and target_value is None:
        target_value = str(load_input_policy().get("default_target", "local"))
    service_ref = None if host_scope and service and service.strip().casefold() in HOST_TARGETS else service
    window = parse_time_window(request, explicit_minutes)
    return {
        "schema_version": 2,
        "intent": "investigate",
        "scope": {
            "kind": "host_system" if host_scope else "application",
            "target_ref": target_value,
            "application_ref": application,
            "service_ref": service_ref,
            "path_ref": log_path,
        },
        "time": {
            "expression": window["expression"],
            "requested_minutes": window["minutes"],
            "source": window["source"],
            "timezone": window.get("timezone", "Asia/Shanghai"),
            **({key: window[key] for key in ("start", "end") if key in window}),
        },
        "mode": "read_only",
        "requested_action": None,
        "pending_slot": None,
    }
