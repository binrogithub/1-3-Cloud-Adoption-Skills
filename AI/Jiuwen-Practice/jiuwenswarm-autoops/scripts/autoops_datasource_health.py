#!/usr/bin/env python3
"""Read-only identity and reachability checks for configured data sources."""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from observability_env import load_observability_environment


SOURCE_DEFINITIONS = {
    "loki": {"env": "LOKI_BASE_URL", "path": "/ready"},
    "prometheus": {"env": "PROMETHEUS_BASE_URL", "path": "/-/ready"},
    "opensearch": {"env": "OPENSEARCH_BASE_URL", "path": "/"},
}


def _endpoint(env: dict[str, str], source: str) -> str | None:
    value = env.get(SOURCE_DEFINITIONS[source]["env"], "").strip()
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return value.rstrip("/")


def _identity(source: str, status: int, body: bytes, content_type: str) -> tuple[bool, dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    if source == "loki":
        valid = status == 200 and "ready" in text.lower()
        return valid, {"probe_path": "/ready", "identity": "loki_ready"}
    if source == "prometheus":
        valid = status == 200 and "ready" in text.lower()
        return valid, {"probe_path": "/-/ready", "identity": "prometheus_ready"}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    valid = status == 200 and isinstance(value, dict) and isinstance(value.get("version"), dict)
    return valid, {"probe_path": "/", "identity": "opensearch_info", "content_type": content_type}


def probe(source: str, environment: dict[str, str] | None = None, *, timeout: float = 3.0) -> dict[str, Any]:
    """Probe one declared endpoint without changing its configuration."""
    if source not in SOURCE_DEFINITIONS:
        raise ValueError(f"unknown data source: {source}")
    # A supplied mapping is an explicit probe fixture/override. Do not merge
    # the caller's checkout-local env files into it, or a missing endpoint in
    # an isolated test could accidentally probe the host's real datasource.
    env = dict(environment) if environment is not None else load_observability_environment()
    base_url = _endpoint(env, source)
    checked_at = int(time.time())
    if not base_url:
        return {"source": source, "configured": False, "reachable": None,
                "identity_valid": None, "data_available": None,
                "capability_ready": False, "status": "NOT_CONFIGURED",
                "error_code": "ENDPOINT_NOT_CONFIGURED", "checked_at": checked_at}
    url = base_url + SOURCE_DEFINITIONS[source]["path"]
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
            body = response.read(65536)
            identity_valid, details = _identity(source, response.status, body,
                                                 response.headers.get("Content-Type", ""))
            status = "READY" if identity_valid else "DEGRADED"
            return {"source": source, "configured": True, "reachable": True,
                    "identity_valid": identity_valid, "data_available": None,
                    "capability_ready": identity_valid, "status": status,
                    "error_code": None if identity_valid else "COMPONENT_IDENTITY_INVALID",
                    "endpoint": base_url, "checked_at": checked_at, **details}
    except urllib.error.HTTPError as exc:
        return {"source": source, "configured": True, "reachable": True,
                "identity_valid": False, "data_available": None,
                "capability_ready": False, "status": "UNAVAILABLE",
                "error_code": "AUTHENTICATION_FAILED" if exc.code in {401, 403} else "HTTP_ERROR",
                "http_status": exc.code, "endpoint": base_url, "checked_at": checked_at}
    except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"source": source, "configured": True, "reachable": False,
                "identity_valid": None, "data_available": None,
                "capability_ready": False, "status": "UNAVAILABLE",
                "error_code": "ENDPOINT_UNREACHABLE", "error_type": type(exc).__name__,
                "endpoint": base_url, "checked_at": checked_at}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe configured AutoOps data source identity.")
    parser.add_argument("source", choices=tuple(SOURCE_DEFINITIONS))
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args(argv)
    if not 0.1 <= args.timeout <= 30:
        print(json.dumps({"status": "INPUT_ERROR", "error": "timeout must be from 0.1 through 30"}))
        return 2
    result = probe(args.source, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
