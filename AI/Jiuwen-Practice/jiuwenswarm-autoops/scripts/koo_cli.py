"""Small, secret-free adapter for Huawei Cloud KooCLI (``hcloud``).

This module is project glue. It never invokes a shell and never passes AK/SK
on a command line. Authentication is delegated to a preconfigured KooCLI
profile (or its default profile). CSS writes are exposed only to the E01
Runbook through :func:`scale_cluster`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class KooCliError(RuntimeError):
    """A KooCLI invocation failed or returned an unreadable response."""


def uses_koo_cli(profile: dict[str, Any]) -> bool:
    value = str(profile.get("api_adapter", "sdk")).strip().casefold()
    return value in {"koo-cli", "koocli", "hcloud"}


def _cli_path(profile: dict[str, Any]) -> str:
    configured = str(profile.get("koo_cli_path", "")).strip()
    value = configured or os.environ.get("AUTOOPS_KOO_CLI", "").strip()
    if value:
        return value
    return shutil.which("hcloud") or "/usr/local/bin/hcloud"


def _profile_name(profile: dict[str, Any]) -> str:
    return str(profile.get("koo_cli_profile", "")).strip() or os.environ.get(
        "AUTOOPS_KOO_CLI_PROFILE", ""
    ).strip()


def _base_command(profile: dict[str, Any], service: str, operation: str) -> list[str]:
    command = [_cli_path(profile), service, operation, "--cli-output=json"]
    region = str(profile.get("region", "")).strip()
    project_id = str(profile.get("project_id", "")).strip()
    domain_id = str(profile.get("domain_id", "")).strip()
    if region:
        command.append(f"--cli-region={region}")
    if project_id:
        command.append(f"--project_id={project_id}")
    if domain_id:
        command.append(f"--cli-domain-id={domain_id}")
    profile_name = _profile_name(profile)
    if profile_name:
        command.append(f"--cli-profile={profile_name}")
    auth_mode = str(profile.get("koo_cli_mode", "AKSK")).strip()
    if auth_mode:
        command.append(f"--cli-mode={auth_mode}")
    return command


def _json_payload(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        raise KooCliError("KooCLI returned an empty response")
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise KooCliError(f"KooCLI returned a non-JSON response: {text[:1200]}")


def _response_body(value: Any) -> Any:
    """Unwrap common KooCLI/API envelopes while preserving plain responses."""
    if not isinstance(value, dict):
        return value
    error_code = _value(value, "error_code", "errorCode", "code", default=None)
    if error_code not in (None, "", 0, "200", 200):
        raise KooCliError(f"KooCLI returned error {error_code}: {_value(value, 'message', 'error_msg', default='')}")
    for key in ("body", "result", "data"):
        candidate = value.get(key)
        if isinstance(candidate, (dict, list)):
            return candidate
    return value


def _run(profile: dict[str, Any], service: str, operation: str,
         params: dict[str, Any] | None = None) -> dict[str, Any]:
    command = _base_command(profile, service, operation)
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value, start=1):
                command.append(f"--{key}.{index}={item}")
        else:
            command.append(f"--{key}={value}")
    timeout = max(1, int(profile.get("koo_cli_timeout_seconds", 45)))
    environment = os.environ.copy()
    # JiuwenSwarm role workers may use a task-specific HOME.  A registered
    # profile can pin the KooCLI home that owns the authenticated profile
    # without putting credentials in a task, command line, or log.
    cli_home = str(profile.get("koo_cli_home", "")).strip()
    if cli_home:
        environment["HOME"] = cli_home
        environment.setdefault("USERPROFILE", cli_home)
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise KooCliError(f"KooCLI executable is unavailable: {_cli_path(profile)}") from exc
    except subprocess.TimeoutExpired as exc:
        raise KooCliError(f"KooCLI timed out after {timeout}s: {service} {operation}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "command failed").strip()
        raise KooCliError(f"KooCLI {service} {operation} failed: {detail[:1200]}")
    payload = _json_payload(completed.stdout)
    body = _response_body(payload)
    if isinstance(body, dict):
        return {**body, "_koo_cli_response": payload}
    return {"data": body, "_koo_cli_response": payload}


def _value(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _request_id(response: dict[str, Any]) -> str | None:
    value = _value(response, "request_id", "requestId", "job_id", "jobId", default=None)
    return str(value) if value else None


def cluster_snapshot(profile: dict[str, Any]) -> dict[str, Any]:
    response = _run(profile, "CSS", "ShowClusterDetail", {
        "cluster_id": profile["cluster_id"],
    })
    instances = []
    for item in _value(response, "instances", default=[]) or []:
        instances.append({
            "id": _value(item, "id", default=""),
            "name": _value(item, "name", default=""),
            "type": _value(item, "type", "instance_type", default=""),
            "status": _value(item, "status", default=""),
            "az": _value(item, "availability_zone", "az", default=""),
        })
    data_nodes = [item for item in instances if item["type"] == "ess"]
    status = str(_value(response, "status", "cluster_status", default="unknown")).casefold()
    return {
        "cluster_id": _value(response, "id", "cluster_id", default=profile["cluster_id"]),
        "cluster_status": status,
        "cluster_healthy": status in {"200", "running", "available", "green", "ready"},
        "data_node_count": len(data_nodes),
        "instances": instances,
        "actions": list(_value(response, "actions", default=[]) or []),
        "action_progress": dict(_value(response, "action_progress", default={}) or {}),
        "failed_reason": _value(response, "failed_reason", default=None),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "api_adapter": "koo-cli",
    }


def metric_sample(profile: dict[str, Any], name: str, *, now_ms: int | None = None) -> dict[str, Any]:
    now = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    response = _run(profile, "CES", "ShowMetricData", {
        "namespace": "SYS.ES",
        "metric_name": name,
        "dim.0": f"cluster_id,{profile['cluster_id']}",
        "from": now - 10 * 60 * 1000,
        "to": now,
        "period": 60,
        "filter": "average",
    })
    points = sorted(_value(response, "datapoints", default=[]) or [],
                    key=lambda item: _value(item, "timestamp", default=0) or 0,
                    reverse=True)
    point = points[0] if points else None
    return {
        "value": _value(point, "average", "value", default=None) if point else None,
        "observed_at": _value(point, "timestamp", "time", default=None) if point else None,
        "unit": _value(point, "unit", "unit_name", default=None) if point else None,
        "aggregation": "average",
        "source": "ces",
        "window_minutes": 10,
        "quality": "ok" if point else "empty",
    }


def metric(profile: dict[str, Any], name: str, *, now_ms: int | None = None) -> Any:
    """Compatibility scalar API; callers needing quality use metric_sample."""
    return metric_sample(profile, name, now_ms=now_ms).get("value")


def ces_metrics(profile: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in names:
        try:
            values[name] = metric(profile, name)
        except KooCliError:
            values[name] = None
    return values


def ces_metric_samples(profile: dict[str, Any], names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Return values with provider timestamps so stale points remain visible."""
    values: dict[str, dict[str, Any]] = {}
    for name in names:
        try:
            values[name] = metric_sample(profile, name)
        except KooCliError as exc:
            values[name] = {"value": None, "quality": "error", "error": str(exc), "source": "ces"}
    return values


def scale_cluster(profile: dict[str, Any], direction: str, delta: int) -> dict[str, Any]:
    if direction == "scale_out":
        return _run(profile, "CSS", "UpdateExtendInstanceStorage", {
            "cluster_id": profile["cluster_id"],
            "grow.1.type": "ess",
            "grow.1.nodesize": delta,
            "grow.1.disksize": 0,
            "is_auto_pay": 1,
        })
    if direction == "scale_in":
        return _run(profile, "CSS", "UpdateShrinkCluster", {
            "cluster_id": profile["cluster_id"],
            "shrink.1.type": "ess",
            "shrink.1.reducedNodeNum": delta,
            "operation_type": "vm",
            "cluster_load_check": "true",
        })
    raise KooCliError(f"unsupported CSS scaling direction: {direction}")


def request_id(response: dict[str, Any]) -> str | None:
    return _request_id(response)
