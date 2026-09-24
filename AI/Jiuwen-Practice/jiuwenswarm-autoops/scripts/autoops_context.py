#!/usr/bin/env python3
"""Resolve a user request to a published AutoOps service profile.

This module deliberately reads only the project-owned profile directory.  It
does not walk the host filesystem, execute systemctl, or infer a target from a
service name.  Discovery that requires host access belongs to a separately
published read-only adapter.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from autoops_runtime_config import resolve_runtime

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_DIR = ROOT / "config" / "service-profiles"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def _match(value: str | None, candidates: list[str]) -> bool:
    return bool(value) and value.casefold() in {item.casefold() for item in candidates}


def _load_profiles(profile_dir: Path) -> list[dict[str, Any]]:
    if not profile_dir.is_dir():
        return []
    profiles: list[dict[str, Any]] = []
    for path in sorted(profile_dir.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and isinstance(value.get("profile_id"), str):
            profiles.append(value)
    return profiles


def profile_dirs(profile_dir: Path | None) -> list[Path]:
    """Return only published profile directories, with user profiles first."""
    if profile_dir:
        return [Path(profile_dir).expanduser()]
    configured = os.environ.get("AUTOOPS_SERVICE_PROFILE_DIR")
    if configured:
        return [Path(configured).expanduser()]
    runtime = resolve_runtime()
    return [Path.home() / ".config" / "jiuwenswarm-autoops" / "service-profiles",
            Path(runtime["config_root"]) / "service-profiles",
            DEFAULT_PROFILE_DIR]


def _validate_profile(profile: dict[str, Any]) -> str | None:
    for field in ("profile_id", "application_id", "target_id", "scope_id"):
        if not isinstance(profile.get(field), str) or not profile[field]:
            return f"profile field is missing: {field}"
    if not NAME_RE.fullmatch(profile["target_id"]):
        return "profile target_id is invalid"
    if not isinstance(profile.get("services"), list) or not profile["services"]:
        return "profile must publish at least one service"
    visibility = profile.get("visibility", "customer")
    if visibility not in {"customer", "test", "internal"}:
        return "profile visibility must be customer, test, or internal"
    if profile.get("lifecycle", "active") not in {"active", "superseded"}:
        return "profile lifecycle must be active or superseded"
    for service in profile["services"]:
        if not isinstance(service, dict) or not isinstance(service.get("service_id"), str):
            return "profile service entry is invalid"
        if not NAME_RE.fullmatch(service["service_id"]):
            return "profile service_id is invalid"
    return None


def _visible(profile: dict[str, Any], include_test: bool) -> bool:
    visibility = profile.get("visibility", "customer")
    lifecycle = profile.get("lifecycle", "active")
    return lifecycle == "active" and (
        visibility == "customer" or (visibility == "test" and include_test)
    )


def _canonical_key(profile: dict[str, Any], service: dict[str, Any]) -> tuple[Any, ...]:
    """Build an identity that keeps real source/config conflicts visible."""
    source_signature = json.dumps(service.get("sources", []), ensure_ascii=False,
                                  sort_keys=True, separators=(",", ":"))
    return (
        profile.get("canonical_object_id") or profile.get("application_id"),
        service.get("service_id"), profile.get("target_id"),
        profile.get("environment", ""), profile.get("scope_id"),
        source_signature, service.get("prometheus_profile"),
        service.get("opensearch_profile"),
    )


def host_system_context(*, target: str = "local", environment: str = "",
                        scope_id: str = "host-system") -> dict[str, Any]:
    """Return the explicit local host scope used for system journal tasks."""
    return {
        "scope_kind": "host_system",
        "application_id": None,
        "application": "Linux 主机",
        "profile_id": "host-system-local",
        "profile_revision": 1,
        "service": None,
        "target": {"kind": "host", "name": target},
        "environment": environment,
        "scope_id": scope_id,
        "log_sources": [{"kind": "journal", "scope": "system", "required": True}],
        "provenance": {"scope": "host_system", "target": "explicit_or_local_default"},
    }


def _service(profile: dict[str, Any], requested: str | None) -> dict[str, Any] | None:
    for service in profile.get("services", []):
        aliases = [service.get("service_id", ""), *service.get("aliases", [])]
        if requested is None or _match(requested, aliases):
            return service
    return None


def _context(profile: dict[str, Any], service: dict[str, Any], *, log_path: str | None,
             target: str | None, environment: str | None, scope_id: str | None) -> dict[str, Any]:
    if target and target != profile["target_id"]:
        raise ValueError("target is not published for the selected application")
    actual_target = target or profile["target_id"]
    actual_environment = environment or profile.get("environment", "")
    actual_scope = scope_id or profile["scope_id"]
    sources = [dict(source) for source in service.get("sources", []) if isinstance(source, dict)]
    if log_path:
        matching = [source for source in sources if source.get("kind") == "file" and source.get("path") == log_path]
        if not matching:
            raise ValueError("log_path is not published for the selected application")
        sources = matching
    return {
        "application_id": profile["application_id"],
        "application": profile.get("application", profile["application_id"]),
        "display_name": profile.get("display_name", profile.get("application", profile["application_id"])),
        "profile_id": profile["profile_id"],
        "profile_revision": profile.get("revision", 1),
        "visibility": profile.get("visibility", "customer"),
        "service": service["service_id"],
        "systemd_unit": service.get("systemd_unit"),
        "target": {"kind": profile.get("target_kind", "host"), "name": actual_target},
        "environment": actual_environment,
        "scope_id": actual_scope,
        "log_sources": sources,
        "prometheus_profile": service.get("prometheus_profile"),
        "opensearch_profile": service.get("opensearch_profile"),
        "capabilities": service.get("capabilities", {}),
        "verification": service.get("verification"),
        "provenance": {
            "application": "service_profile",
            "service": "service_profile",
            "target": "explicit" if target else "service_profile",
            "scope_id": "explicit" if scope_id else "service_profile",
            "log_path": "explicit" if log_path else "service_profile",
        },
    }


def resolve(*, application: str | None = None, service: str | None = None,
            target: str | None = None, log_path: str | None = None,
            environment: str | None = None, scope_id: str | None = None,
            profile_dir: Path | None = None, include_test: bool = False) -> dict[str, Any]:
    profiles = []
    seen_profile_ids = set()
    for directory in profile_dirs(profile_dir):
        for profile in _load_profiles(directory):
            if profile["profile_id"] in seen_profile_ids:
                continue
            seen_profile_ids.add(profile["profile_id"])
            profiles.append(profile)
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for profile in profiles:
        error = _validate_profile(profile)
        if error:
            invalid.append({"profile_id": str(profile.get("profile_id", "unknown")), "error": error})
            continue
        if _visible(profile, include_test):
            valid.append(profile)

    candidates = []
    for profile in valid:
        aliases = [profile["application_id"], profile.get("application", ""),
                   profile.get("display_name", ""), *profile.get("aliases", [])]
        if application and not _match(application, aliases):
            continue
        selected = _service(profile, service)
        if service and selected is None:
            continue
        if selected:
            candidates.append((profile, selected))
        elif len(profile["services"]) == 1:
            candidates.append((profile, profile["services"][0]))
        else:
            candidates.extend((profile, item) for item in profile["services"])

    # Collapse exact duplicate published objects while keeping source/config
    # conflicts as separate candidates for a human to resolve.
    unique: dict[tuple[Any, ...], tuple[dict[str, Any], dict[str, Any]]] = {}
    duplicate_ids: dict[tuple[Any, ...], list[str]] = {}
    for profile, selected in candidates:
        key = _canonical_key(profile, selected)
        previous = unique.get(key)
        if previous is None or int(profile.get("revision", 1)) > int(previous[0].get("revision", 1)):
            unique[key] = (profile, selected)
        duplicate_ids.setdefault(key, []).append(profile["profile_id"])
    candidates = list(unique.values())

    if len(candidates) != 1:
        return {
            "schema_version": 1,
            "status": "AMBIGUOUS" if len(candidates) > 1 else "NOT_FOUND",
            "application": application,
            "service": service,
            "target": target,
            "candidates": [
                {"profile_id": p["profile_id"],
                 "application": p.get("application", p["application_id"]),
                 "display_name": p.get("display_name", p.get("application", p["application_id"])),
                 "service": s["service_id"], "target": p["target_id"],
                 "environment": p.get("environment", "")}
                for p, s in candidates
            ],
            "invalid_profiles": invalid,
            "deduplicated_profiles": [ids for ids in duplicate_ids.values() if len(set(ids)) > 1],
            "error_code": "SCOPE_AMBIGUOUS" if len(candidates) > 1 else "PROFILE_NOT_FOUND",
        }
    profile, selected = candidates[0]
    try:
        context = _context(profile, selected, log_path=log_path, target=target,
                           environment=environment, scope_id=scope_id)
    except ValueError as exc:
        message = str(exc)
        error_code = "TARGET_NOT_PUBLISHED" if message.startswith("target ") else "PATH_NOT_PUBLISHED"
        return {"schema_version": 1, "status": "INPUT_ERROR", "error_code": error_code, "error": message}
    return {"schema_version": 1, "status": "RESOLVED", "context": context, "invalid_profiles": invalid,
            "deduplicated_profiles": [ids for ids in duplicate_ids.values() if len(set(ids)) > 1]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve a published AutoOps ServiceProfile.")
    parser.add_argument("--application")
    parser.add_argument("--service")
    parser.add_argument("--target")
    parser.add_argument("--log-path")
    parser.add_argument("--environment")
    parser.add_argument("--scope-id")
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--include-test-profiles", action="store_true")
    args = parser.parse_args(argv)
    payload = resolve(application=args.application, service=args.service, target=args.target,
                      log_path=args.log_path, environment=args.environment, scope_id=args.scope_id,
                      profile_dir=args.profile_dir, include_test=args.include_test_profiles)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
