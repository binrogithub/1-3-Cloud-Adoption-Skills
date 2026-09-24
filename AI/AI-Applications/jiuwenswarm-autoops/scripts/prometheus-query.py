#!/usr/bin/env python3
"""Read-only Prometheus query adapter using configured metric profiles."""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

from observability_contract import explicit_window, load_policy, result, validate_service, validate_window_limit, window


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def request_json(url: str, params: dict[str, str], timeout: int, headers: dict[str, str], verify_tls: bool) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url.rstrip('/')}/api/v1/query_range?{query}", headers=headers, method="GET")
    context = None if verify_tls else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Prometheus HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Prometheus connection or timeout failure") from exc
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise RuntimeError("Prometheus returned an unsuccessful response")
    return payload


def freshness(series: list[dict], end: int, max_staleness: int) -> dict:
    """Measure samples against the requested window end, not wall-clock text."""
    timestamps: list[float] = []
    sample_count = 0
    for item in series:
        values = item.get("values", item.get("value")) if isinstance(item, dict) else None
        if isinstance(values, list) and values and isinstance(values[0], list):
            candidates = values
        elif isinstance(values, list) and len(values) >= 2 and not isinstance(values[0], list):
            candidates = [values]
        else:
            candidates = []
        sample_count += len(candidates)
        for value in candidates:
            try:
                timestamps.append(float(value[0]))
            except (IndexError, TypeError, ValueError):
                continue
    if not timestamps:
        return {"status": "unknown", "sample_count": sample_count}
    latest = max(timestamps)
    age = max(0.0, float(end) - latest)
    return {"status": "fresh" if age <= max_staleness else "stale",
            "latest_sample": latest, "age_seconds": int(age),
            "sample_count": sample_count, "max_staleness_seconds": max_staleness}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query a fixed Prometheus metric profile.")
    parser.add_argument("--service", required=True)
    parser.add_argument("--profile", default="service_up")
    parser.add_argument("--since-minutes", type=int, default=15)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--step", type=int, default=60)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)

    try:
        policy = load_policy()
        defaults = policy["defaults"]
        prom = policy["prometheus"]
        service = validate_service(args.service)
        validate_window_limit(args.since_minutes, args.limit,
                               max_minutes=int(defaults["max_window_minutes"]),
                               max_limit=int(defaults["max_limit"]))
        if args.step < 1 or args.step > 3600:
            raise ValueError("step must be an integer from 1 through 3600")
        profile = prom["profiles"].get(args.profile)
        if not isinstance(profile, dict):
            raise ValueError(f"unknown metric profile: {args.profile}")
        service_label = str(prom.get("service_label", "service"))
        if not service_label.replace("_", "a").isalnum() or not service_label[0].isalpha():
            raise ValueError("invalid Prometheus service label in policy")
        query = str(profile["query"]).replace("{service_label}", service_label).replace("{service}", service)
        start, end, start_iso, end_iso = explicit_window(args.start, args.end, args.since_minutes)
        max_points = int(prom["max_points"])
        point_count = ((end - start) // args.step) + 1
        if point_count > max_points:
            raise ValueError(f"query would return {point_count} points; maximum is {max_points}")
        base_url = os.environ.get("PROMETHEUS_BASE_URL", "")
        if not base_url:
            raise RuntimeError("Prometheus datasource is not configured")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("PROMETHEUS_BASE_URL must be an HTTP(S) URL")
        timeout = int(os.environ.get("PROMETHEUS_TIMEOUT_SECONDS", defaults["timeout_seconds"]))
        if not 1 <= timeout <= 60:
            raise ValueError("PROMETHEUS_TIMEOUT_SECONDS must be from 1 through 60")
        headers = {"Accept": "application/json"}
        token = os.environ.get("PROMETHEUS_BEARER_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = request_json(base_url, {
            "query": query, "start": str(start), "end": str(end), "step": str(args.step),
        }, timeout, headers, os.environ.get("PROMETHEUS_VERIFY_TLS", "1") != "0")
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("resultType") not in {"matrix", "vector", "scalar", "string"}:
            raise RuntimeError("Prometheus returned an unexpected query_range response")
        series = data.get("result", [])
        if not isinstance(series, list):
            raise RuntimeError("Prometheus result is not a list")
        series = series[: min(args.limit, int(prom["max_series"]))]
        items = [{"metric": item.get("metric", {}), "values": item.get("values", item.get("value"))}
                 for item in series if isinstance(item, dict)]
        status = "empty" if not items else "ok"
        data_freshness = freshness(items, end, int(prom.get("max_staleness_seconds", 300)))
        payload_out = result(source="prometheus", status=status, service=service,
                             since_minutes=args.since_minutes, limit=args.limit,
                             items=items, material={"profile": args.profile, "query": query,
                                                     "start": start, "end": end},
                             profile=args.profile, query=query,
                             window={"start": start_iso, "end": end_iso,
                                     "requested_minutes": args.since_minutes,
                                     "step_seconds": args.step},
                             data_freshness=data_freshness,
                             series_count=len(items),
                             query_completed_at=datetime.fromtimestamp(
                                 time.time(), timezone.utc).isoformat().replace("+00:00", "Z"))
        return emit(payload_out)
    except (ValueError, KeyError, TypeError) as exc:
        return emit({"source": "prometheus", "status": "invalid", "error_code": "INVALID_INPUT", "error": str(exc)}, 2)
    except RuntimeError as exc:
        return emit({"source": "prometheus", "status": "unavailable", "error_code": "DATASOURCE_ERROR", "error": str(exc)}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
