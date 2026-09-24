#!/usr/bin/env python3
"""Read bounded NOLI NOC incident evidence for the JiuwenSwarm NetOps role."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from observability_env import load_observability_environment

MAX_BYTES = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class AdapterError(Exception):
    def __init__(self, status: str, code: str, http_status: int | None = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.http_status = http_status


def base_url(environment: dict[str, str]) -> str:
    value = environment.get("NOLI_BASE_URL", "").strip().rstrip("/")
    if not value:
        raise AdapterError("NOT_CONFIGURED", "NOLI_BASE_URL_MISSING")
    parts = urlsplit(value)
    if parts.scheme not in {"https", "http"} or not parts.hostname or \
            parts.username or parts.password or parts.query or parts.fragment or ".." in parts.path:
        raise AdapterError("INPUT_ERROR", "NOLI_BASE_URL_INVALID")
    if parts.scheme == "http":
        try:
            loopback = ip_address(parts.hostname).is_loopback
        except ValueError:
            loopback = parts.hostname.casefold() == "localhost"
        if not loopback:
            raise AdapterError("INPUT_ERROR", "NOLI_HTTPS_REQUIRED")
    return value


def fetch_json(url: str, token: str, timeout: float) -> dict:
    request = Request(url, headers={"Authorization": f"Bearer {token}",
                                    "Accept": "application/json"}, method="GET")
    try:
        with build_opener(NoRedirect).open(request, timeout=timeout) as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        if code in {401, 403}:
            raise AdapterError("AUTH_FAILED", "NOLI_AUTH_FAILED", code) from None
        raise AdapterError("UNAVAILABLE", "NOLI_HTTP_ERROR", code) from None
    except (URLError, TimeoutError, OSError):
        raise AdapterError("UNAVAILABLE", "NOLI_REQUEST_FAILED") from None
    if len(data) > MAX_BYTES:
        raise AdapterError("UNAVAILABLE", "NOLI_RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise AdapterError("UNAVAILABLE", "NOLI_RESPONSE_INVALID") from None
    if not isinstance(payload, dict):
        raise AdapterError("UNAVAILABLE", "NOLI_RESPONSE_INVALID")
    return payload


def compact(value, depth: int = 0):
    """Bound untrusted dossier text before returning it to the Team Leader."""
    if depth > 3:
        return None
    if isinstance(value, str):
        return value[:500]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) <= 10**15 else None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [compact(item, depth + 1) for item in value[:8]]
    if isinstance(value, dict):
        return {str(key)[:80]: compact(item, depth + 1)
                for key, item in list(value.items())[:20]}
    return None


def incident_summary(row: dict) -> dict:
    sensors = row.get("sensors") if isinstance(row.get("sensors"), list) else []
    return {"id": str(row["id"])[:256], "key": compact(row.get("key")),
            "label": compact(row.get("label")), "severity": compact(row.get("severity")),
            "open": row.get("open") is True,
            "opened_at": compact(row.get("opened_at")),
            "closed_at": compact(row.get("closed_at")),
            "alerts": compact(row.get("alerts")),
            "sensors": [{"id": compact(item.get("id")), "name": compact(item.get("name"))}
                        for item in sensors[:10] if isinstance(item, dict)],
            "evidence_ref": f"noli:incident:{str(row['id'])[:256]}"}


def pool_matches(row: dict, pool: str) -> bool:
    key = row.get("key")
    if not isinstance(key, str):
        return False
    return key.rsplit("|", 1)[-1].split("#", 1)[0].casefold() == pool.casefold()


def board_is_fresh(value: str) -> bool:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        return -60 <= age <= 300
    except (AttributeError, TypeError, ValueError):
        return False


def inspect(*, minutes: int, limit: int, pool: str | None, incident_id: str | None,
            environment: dict[str, str]) -> dict:
    if not 1 <= minutes <= 1440 or not 1 <= limit <= 50 or \
            (pool is not None and not 1 <= len(pool) <= 128) or \
            (incident_id is not None and not 1 <= len(incident_id) <= 256):
        raise AdapterError("INPUT_ERROR", "NOLI_SCOPE_INVALID")
    base = base_url(environment)
    token = environment.get("NOLI_BEARER_TOKEN", "").strip()
    if not token:
        raise AdapterError("NOT_CONFIGURED", "NOLI_BEARER_TOKEN_MISSING")
    try:
        timeout = float(environment.get("NOLI_TIMEOUT_SECONDS", "10"))
    except ValueError:
        raise AdapterError("INPUT_ERROR", "NOLI_TIMEOUT_INVALID") from None
    if not 1 <= timeout <= 30:
        raise AdapterError("INPUT_ERROR", "NOLI_TIMEOUT_INVALID")

    window = f"{minutes}m"
    board = fetch_json(f"{base}/api/noc/board?{urlencode({'window': window})}", token, timeout)
    rows = board.get("incidents")
    if not isinstance(rows, list):
        raise AdapterError("UNAVAILABLE", "NOLI_BOARD_INVALID")
    source_rows = rows
    rows = [row for row in rows if isinstance(row, dict)
            and isinstance(row.get("id"), str) and 1 <= len(row["id"]) <= 256
            and isinstance(row.get("key"), str) and 1 <= len(row["key"]) <= 256]
    invalid_incidents = len(rows) != len(source_rows)
    if pool:
        rows = [row for row in rows if pool_matches(row, pool)]
    if incident_id:
        rows = [row for row in rows if row["id"] == incident_id]
    coverage_value = board.get("coverage_pct")
    coverage = (float(coverage_value) if isinstance(coverage_value, (int, float))
                and not isinstance(coverage_value, bool) else None)
    if coverage is not None and (not math.isfinite(coverage) or not 0 <= coverage <= 100):
        coverage = None
    gap_count_value = board.get("gap_count")
    gap_count = (gap_count_value if isinstance(gap_count_value, int)
                 and not isinstance(gap_count_value, bool) and gap_count_value >= 0 else None)
    groups = board.get("groups")
    groups_valid = isinstance(groups, list)
    nodata = False
    observed_sensors = 0
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("sensors"), list):
                groups_valid = False
                continue
            nodata = nodata or group.get("status") == "nodata"
            for sensor in group["sensors"]:
                if not isinstance(sensor, dict):
                    groups_valid = False
                    continue
                observed_sensors += 1
                nodata = nodata or sensor.get("status") == "nodata"
    sensors_total_value = board.get("sensors_total")
    sensors_total = (sensors_total_value if isinstance(sensors_total_value, int)
                     and not isinstance(sensors_total_value, bool) and sensors_total_value >= 0 else None)
    scope_observed = sensors_total is not None and sensors_total > 0 and sensors_total == observed_sensors
    index_available = board.get("index_available") if isinstance(board.get("index_available"), bool) else None
    invalid_board = (not groups_valid or not scope_observed or coverage is None or gap_count is None
                     or index_available is None)
    complete = (index_available is True and coverage == 100
                and gap_count == 0 and not nodata and not invalid_board and not invalid_incidents
                and board_is_fresh(board.get("generated_at")))
    if (incident_id or pool) and not rows:
        status = "empty"
    elif rows:
        status = "anomalies_found" if complete else "partial"
    else:
        status = "no_anomaly" if complete else "inconclusive"
    simulated = board.get("simulation") is True
    result = {"schema_version": 1, "status": status, "changed": False,
              "source": "synthetic_noli_compatible_api" if simulated else "noli:/api/noc/board",
              "window_minutes": minutes,
              "generated_at": compact(board.get("generated_at")),
              "simulated": simulated,
              "data_origin": compact(board.get("data_origin")) if simulated else "noli",
              "coverage_pct": coverage, "index_available": index_available,
              "gap_count": gap_count, "nodata": nodata, "complete": complete,
              "sensors_total": sensors_total, "invalid_incidents": invalid_incidents,
              "invalid_board": invalid_board,
              "total_matches": len(rows), "truncated": len(rows) > limit,
              "incidents": [incident_summary(row) for row in rows[:limit]],
              "scope": {"pool": pool, "incident_id": incident_id}}
    if incident_id and rows:
        dossier = fetch_json(
            f"{base}/api/noc/incident?{urlencode({'key': incident_id, 'window': window})}",
            token, timeout)
        result["dossier"] = {key: compact(dossier.get(key))
                             for key in ("agent", "timeline", "findings", "recommendation")}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read NOLI network incident evidence.")
    parser.add_argument("--window-minutes", type=int, default=480)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--pool")
    parser.add_argument("--incident-id")
    args = parser.parse_args(argv)
    try:
        result = inspect(minutes=args.window_minutes, limit=args.limit, pool=args.pool,
                         incident_id=args.incident_id,
                         environment=load_observability_environment())
    except AdapterError as exc:
        result = {"schema_version": 1, "status": exc.status, "error_code": exc.code,
                  "changed": False}
        if exc.http_status is not None:
            result["http_status"] = exc.http_status
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"anomalies_found", "no_anomaly", "empty", "partial", "inconclusive"} else 2 if result["status"] in {"INPUT_ERROR", "NOT_CONFIGURED"} else 1


if __name__ == "__main__":
    sys.exit(main())
