#!/usr/bin/env python3
"""Register one explicit AutoOps ServiceProfile for later TUI reuse."""
from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path

from autoops_context import NAME_RE

DEFAULT_DIR = Path.home() / ".config" / "jiuwenswarm-autoops" / "service-profiles"


def fail(message: str) -> int:
    print(json.dumps({"status": "INPUT_ERROR", "error": message}, ensure_ascii=False))
    return 2


def validate_path(value: str) -> str | None:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        return "log paths must be absolute and cannot contain '..'."
    return None


def build_profile(args: argparse.Namespace) -> dict:
    for field in ("profile_id", "application_id", "service", "target", "scope_id"):
        value = getattr(args, field)
        if not NAME_RE.fullmatch(value):
            raise ValueError(f"{field} must match [A-Za-z0-9][A-Za-z0-9._-]{{0,62}}")
    for path in args.log_path:
        error = validate_path(path)
        if error:
            raise ValueError(error)
    source = [{"kind": "journal", "unit": args.journal_unit, "required": True}]
    source.extend({"kind": "file", "path": path, "required": False} for path in args.log_path)
    return {
        "schema_version": 1,
        "profile_id": args.profile_id,
        "revision": args.revision,
        "application_id": args.application_id,
        "application": args.application,
        "display_name": args.display_name or args.application,
        "aliases": args.application_alias,
        "visibility": args.visibility,
        "lifecycle": args.lifecycle,
        "canonical_object_id": args.canonical_object_id or args.application_id,
        "environment": args.environment,
        "target_kind": "host",
        "target_id": args.target,
        "scope_id": args.scope_id,
        "services": [{
            "service_id": args.service,
            "aliases": args.service_alias,
            "systemd_unit": args.journal_unit,
            "sources": source,
            "prometheus_profile": args.prometheus_profile,
            "opensearch_profile": args.opensearch_profile,
        }],
    }


def write_profile(profile: dict, destination_dir: Path) -> Path:
    if destination_dir.is_symlink():
        raise ValueError("profile directory must not be a symlink")
    destination_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(destination_dir, stat.S_IRWXU)
    destination = destination_dir / f"{profile['profile_id']}.json"
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError("profile destination must be a regular file")
    if destination.exists():
        current = json.loads(destination.read_text(encoding="utf-8"))
        if isinstance(current, dict) and int(current.get("revision", 0)) >= profile["revision"]:
            raise ValueError("new profile revision must be greater than the stored revision")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{profile['profile_id']}.", suffix=".tmp", dir=destination_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(profile, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fchmod(stream.fileno(), stat.S_IRUSR | stat.S_IWUSR)
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a published AutoOps ServiceProfile.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument("--application-alias", action="append", default=[])
    parser.add_argument("--service", required=True)
    parser.add_argument("--service-alias", action="append", default=[])
    parser.add_argument("--target", required=True)
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--environment", default="")
    parser.add_argument("--visibility", choices=("customer", "test", "internal"), default="customer")
    parser.add_argument("--lifecycle", choices=("active", "superseded"), default="active")
    parser.add_argument("--canonical-object-id", default="")
    parser.add_argument("--journal-unit", required=True)
    parser.add_argument("--log-path", action="append", default=[])
    parser.add_argument("--prometheus-profile", default="service_up")
    parser.add_argument("--opensearch-profile", default="")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--profile-dir", type=Path,
                        default=Path(os.environ.get("AUTOOPS_SERVICE_PROFILE_DIR", str(DEFAULT_DIR))).expanduser())
    args = parser.parse_args(argv)
    if args.revision < 1:
        return fail("revision must be positive")
    try:
        profile = build_profile(args)
        destination = write_profile(profile, args.profile_dir)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({"status": "REGISTERED", "profile_id": profile["profile_id"],
                      "revision": profile["revision"], "path": str(destination)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
