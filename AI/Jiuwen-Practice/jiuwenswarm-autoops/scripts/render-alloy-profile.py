#!/usr/bin/env python3
"""Render a published ServiceProfile into an Alloy Loki source config.

This is project-owned glue. It emits Alloy configuration and never edits an
Alloy installation or copies credentials into the generated file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from autoops_context import NAME_RE


def regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"file must be a regular file: {path}")


def hcl(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_profile(path: Path) -> dict:
    regular(path)
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid ServiceProfile JSON: {exc.msg}") from exc
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise ValueError("ServiceProfile schema_version 1 is required")
    if profile.get("lifecycle", "active") != "active":
        raise ValueError("only active ServiceProfiles may be rendered")
    if profile.get("visibility", "customer") == "internal":
        raise ValueError("internal ServiceProfiles cannot be rendered")
    services = profile.get("services")
    if not isinstance(services, list) or not services:
        raise ValueError("ServiceProfile must contain services")
    return profile


def select_service(profile: dict, requested: str | None) -> dict:
    services = profile["services"]
    if requested:
        candidates = []
        for service in services:
            if not isinstance(service, dict):
                continue
            names = [service.get("service_id", ""), *(service.get("aliases") or [])]
            if requested in names:
                candidates.append(service)
        if len(candidates) != 1:
            raise ValueError(f"service is not uniquely published: {requested}")
        return candidates[0]
    if len(services) != 1:
        raise ValueError("profile has multiple services; --service is required")
    if not isinstance(services[0], dict):
        raise ValueError("service entry must be an object")
    return services[0]


def validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--loki-url must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("--loki-url cannot contain credentials, query, or fragment")
    return value.rstrip("/")


def validate_identifier(value: object, field: str) -> str:
    text = str(value or "")
    if not NAME_RE.fullmatch(text):
        raise ValueError(f"{field} must be a published identifier")
    return text


def validate_path(value: object) -> str:
    path = str(value or "")
    if not path.startswith("/") or any(char in path for char in "\r\n\""):
        raise ValueError("file source path must be an absolute safe path pattern")
    return path


def block_label(value: str, suffix: str) -> str:
    """Convert a published identifier into a valid Alloy block label."""
    label = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return f"{label}_{suffix}"


def journal_unit(value: object, fallback: object) -> str:
    unit = str(value or fallback or "")
    if unit.endswith(".service"):
        unit = unit[:-8]
    return validate_identifier(unit, "journal unit")


def render(profile: dict, service: dict, loki_url: str) -> str:
    application = validate_identifier(profile.get("application_id") or profile.get("application"), "application")
    service_id = validate_identifier(service.get("service_id"), "service_id")
    environment = validate_identifier(profile.get("environment", "local"), "environment")
    target = validate_identifier(profile.get("target_id", "local"), "target_id")
    scope = validate_identifier(profile.get("scope_id", application), "scope_id")
    labels = {
        "application": application,
        "environment": environment,
        "target": target,
        "scope_id": scope,
        "service": service_id,
    }
    label_lines = ",\n".join(f"    {key} = {hcl(value)}" for key, value in labels.items()) + ","
    blocks = []
    sources = service.get("sources")
    if not isinstance(sources, list):
        raise ValueError("service sources must be a list")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("source entry must be an object")
        kind = source.get("kind")
        if kind == "journal":
            unit = journal_unit(source.get("unit"), service.get("systemd_unit"))
            blocks.append("\n".join([
                f'loki.source.journal "{block_label(service_id, f"journal_{index}")}" {{',
                f'  matches    = "_SYSTEMD_UNIT={unit}.service"',
                "  labels = {", label_lines, "  }",
                "  forward_to = [loki.write.autoops.receiver]", "}"]))
        elif kind == "file":
            path = validate_path(source.get("path"))
            blocks.append("\n".join([
                f'loki.source.file "{block_label(service_id, f"file_{index}")}" {{',
                "  targets = [{", f"    __path__ = {hcl(path)},", label_lines,
                "  }]", "  file_match {", "    enabled = true", "    sync_period = \"10s\"", "  }",
                "  forward_to = [loki.write.autoops.receiver]", "}"]))
        elif kind == "loki":
            # An existing Loki source is a query target, not a local Alloy
            # input. Do not turn it into a second collector.
            continue
        else:
            raise ValueError(f"unsupported source kind: {kind}")
    if not blocks:
        raise ValueError("profile has no journal or file source to render")
    return "\n".join([
        "// Managed by JiuwenSwarm AutoOps; generated from a ServiceProfile.",
        "// Credentials are supplied to Alloy through its deployment environment.",
        "",
        'loki.write "autoops" {',
        "  endpoint {", f"    url = {hcl(loki_url + '/loki/api/v1/push')}",
        "  }", "}", "", "\n\n".join(blocks), ""])


def atomic_write(path: Path, content: str) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o640)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Alloy Loki sources from a ServiceProfile.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--loki-url", required=True)
    parser.add_argument("--service")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        profile = read_profile(args.profile)
        service = select_service(profile, args.service)
        atomic_write(args.output, render(profile, service, validate_url(args.loki_url)))
        print(json.dumps({"status": "READY", "profile": str(args.profile),
                          "service": service.get("service_id"), "output": str(args.output),
                          "credentials_persisted": False}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
