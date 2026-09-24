#!/usr/bin/env python3
"""Shared validation and result helpers for read-only observability adapters."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "config" / "observability-policy.json"
SERVICE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def load_policy() -> dict[str, Any]:
    with POLICY_FILE.open(encoding="utf-8") as stream:
        policy = json.load(stream)
    if not isinstance(policy, dict):
        raise ValueError("observability policy must be an object")
    return policy


def validate_service(service: str) -> str:
    if not SERVICE_PATTERN.fullmatch(service or ""):
        raise ValueError("service must contain 1-63 letters, digits, dot, underscore, or hyphen")
    return service


def validate_window_limit(minutes: int, limit: int, *, max_minutes: int, max_limit: int) -> None:
    if not 1 <= minutes <= max_minutes:
        raise ValueError(f"since-minutes must be an integer from 1 through {max_minutes}")
    if not 1 <= limit <= max_limit:
        raise ValueError(f"limit must be an integer from 1 through {max_limit}")


def window(minutes: int) -> tuple[int, int, str, str]:
    end = int(time.time())
    start = end - minutes * 60
    start_iso = datetime.fromtimestamp(start, timezone.utc).isoformat().replace("+00:00", "Z")
    end_iso = datetime.fromtimestamp(end, timezone.utc).isoformat().replace("+00:00", "Z")
    return start, end, start_iso, end_iso


def explicit_window(start_iso: str | None, end_iso: str | None, minutes: int) -> tuple[int, int, str, str]:
    """Return a validated UTC window; when omitted, use the last ``minutes``."""
    if not start_iso and not end_iso:
        return window(minutes)
    if not start_iso or not end_iso:
        raise ValueError("start and end must be provided together")
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("start and end must be ISO-8601 timestamps") from exc
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("end must be after start and both timestamps must include a timezone")
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    return (int(start.timestamp()), int(end.timestamp()),
            start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z"))


def evidence_ref(source: str, material: Any) -> str:
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{source}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def result(*, source: str, status: str, service: str, since_minutes: int, limit: int,
           items: list[dict[str, Any]], material: Any, **extra: Any) -> dict[str, Any]:
    _, _, start_iso, end_iso = window(since_minutes)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": source,
        "status": status,
        "service": service,
        "window": {"start": start_iso, "end": end_iso, "requested_minutes": since_minutes},
        "limit": limit,
        "count": len(items),
        "items": items,
        "evidence_ref": evidence_ref(source, material),
        "observed_at": end_iso,
    }
    payload.update(extra)
    return payload
