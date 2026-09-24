#!/usr/bin/env python3
"""Report static capability and published application binding health.

This command only reads project configuration.  It does not probe a customer
host or invoke an adapter; runtime probes remain the responsibility of the
capability's published adapter and are reported separately by that adapter.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from autoops_context import resolve
from autoops_datasource_health import probe as probe_datasource
from observability_env import load_observability_environment

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "capability-registry.json"
VALID_STATUSES = {"READY", "DEGRADED", "UNAVAILABLE", "NOT_CONFIGURED"}
REQUIRED_FIELDS = ("role", "effect", "input_schema_version", "result_schema_version",
                   "resource_types", "invocation_kind", "required", "prerequisites")


def load_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("capability registry schema_version must be 1")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("capability registry capabilities must be an object")
    return payload


def static_health(capability_id: str, record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"status": "NOT_CONFIGURED", "reason": "capability record is not an object"}
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        return {"status": "NOT_CONFIGURED", "reason": "missing registry fields", "missing": missing}
    if record["effect"] not in {"read", "write"} or record["invocation_kind"] not in {
            "native_expert", "adapter", "project_route"}:
        return {"status": "NOT_CONFIGURED", "reason": "registry execution metadata is invalid"}
    if not isinstance(record["resource_types"], list) or not record["resource_types"]:
        return {"status": "NOT_CONFIGURED", "reason": "resource_types must be non-empty"}
    if not isinstance(record["required"], list) or not isinstance(record["prerequisites"], list):
        return {"status": "NOT_CONFIGURED", "reason": "required and prerequisites must be arrays"}
    if not (isinstance(record["input_schema_version"], int)
            and isinstance(record["result_schema_version"], int)):
        return {"status": "NOT_CONFIGURED", "reason": "schema versions must be integers"}
    if not record.get("adapter") and not record.get("job"):
        return {"status": "NOT_CONFIGURED", "reason": "no adapter or job is published"}
    if record.get("enabled", True) is not True:
        return {"status": "UNAVAILABLE", "reason": "capability is disabled"}
    return {"status": "READY", "reason": "static registry is valid"}


def needs_binding(record: dict[str, Any]) -> bool:
    return bool(set(record.get("resource_types", [])) & {
        "service", "file", "deployment", "event", "health_probe", "kubernetes_cluster",
        "kubernetes_workload",
    })


def binding_health(record: dict[str, Any], *, application: str | None, service: str | None,
                   target: str | None, include_test: bool, profile_dir: Path | None) -> dict[str, Any]:
    if not needs_binding(record):
        return {"status": "READY", "reason": "capability is host-scoped or self-contained"}
    if not (application or service or target):
        return {"status": "DEGRADED", "reason": "application or target binding was not selected"}
    resolved = resolve(application=application, service=service, target=target,
                       profile_dir=profile_dir, include_test=include_test)
    if resolved.get("status") == "RESOLVED":
        return {"status": "READY", "reason": "published application binding resolved",
                "profile_id": resolved["context"]["profile_id"],
                "scope_id": resolved["context"]["scope_id"]}
    return {"status": "NOT_CONFIGURED", "reason": resolved.get("error", resolved.get("error_code", "binding unavailable")),
            "resolution_status": resolved.get("status")}


def runtime_health(record: dict[str, Any]) -> dict[str, Any]:
    """Check only the configured datasource prerequisites for a capability."""
    prerequisites = set(record.get("prerequisites", []))
    source_by_prerequisite = {
        "prometheus_configured": "prometheus",
        "opensearch_configured": "opensearch",
    }
    checks = []
    if "noli_configured" in prerequisites:
        noli_env = load_observability_environment()
        configured = bool(noli_env.get("NOLI_BASE_URL") and noli_env.get("NOLI_BEARER_TOKEN"))
        checks.append({"status": "READY" if configured else "NOT_CONFIGURED",
                       "source": "noli", "reason": "NOLI endpoint and token configured" if configured
                       else "NOLI_BASE_URL and NOLI_BEARER_TOKEN are required"})
    for prerequisite, source in source_by_prerequisite.items():
        if prerequisite in prerequisites:
            checks.append(probe_datasource(source))
    if not checks:
        return {"status": "READY", "reason": "no network datasource prerequisite", "checks": []}
    if any(item["status"] == "NOT_CONFIGURED" for item in checks):
        status = "NOT_CONFIGURED"
    elif any(item["status"] == "READY" for item in checks) and all(item["status"] == "READY" for item in checks):
        status = "READY"
    elif any(item["status"] == "UNAVAILABLE" for item in checks):
        status = "UNAVAILABLE"
    else:
        status = "DEGRADED"
    return {"status": status, "reason": "runtime datasource prerequisite check", "checks": checks}


def inspect(registry: dict[str, Any], capability_ids: list[str], *, application: str | None,
            service: str | None, target: str | None, include_test: bool,
            profile_dir: Path | None, runtime: bool = False) -> dict[str, Any]:
    capabilities = registry["capabilities"]
    now = int(time.time())
    results = []
    for capability_id in capability_ids:
        record = capabilities.get(capability_id)
        static = static_health(capability_id, record)
        binding = binding_health(record, application=application, service=service,
                                 target=target, include_test=include_test, profile_dir=profile_dir) \
            if isinstance(record, dict) else {"status": "NOT_CONFIGURED", "reason": "capability is unknown"}
        live = runtime_health(record) if runtime and isinstance(record, dict) else {
            "status": "UNKNOWN", "reason": "runtime probe not requested", "checks": []}
        statuses = [static["status"], binding["status"]] + ([live["status"]] if runtime else [])
        status = "NOT_CONFIGURED" if "NOT_CONFIGURED" in statuses else \
            "UNAVAILABLE" if "UNAVAILABLE" in statuses else \
            "DEGRADED" if "DEGRADED" in statuses else "READY"
        results.append({"capability": capability_id, "status": status,
                        "static": static, "binding": binding, "runtime": live,
                        "prerequisites": record.get("prerequisites", []) if isinstance(record, dict) else []})
    return {"schema_version": 1, "checked_at": now, "valid_for_seconds": 300,
            "valid_until": now + 300, "application": application, "service": service,
            "target": target, "results": results,
            "status": "READY" if all(item["status"] == "READY" for item in results) else "DEGRADED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check published AutoOps capability and binding health.")
    parser.add_argument("--capability", action="append")
    parser.add_argument("--application")
    parser.add_argument("--service")
    parser.add_argument("--target")
    parser.add_argument("--include-test-profiles", action="store_true")
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--runtime", action="store_true",
                        help="Probe configured datasource prerequisites; default is static/read-only registry validation.")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        ids = args.capability or sorted(registry["capabilities"])
        payload = inspect(registry, ids, application=args.application, service=args.service,
                          target=args.target, include_test=args.include_test_profiles,
                          profile_dir=args.profile_dir, runtime=args.runtime)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": 1, "status": "NOT_CONFIGURED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] in VALID_STATUSES and payload["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
