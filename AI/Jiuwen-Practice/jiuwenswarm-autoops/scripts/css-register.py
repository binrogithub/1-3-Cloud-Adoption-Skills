#!/usr/bin/env python3
"""Register a Huawei Cloud CSS cluster without putting secrets in prompts or logs.

The command writes a cluster profile and a separate mode-0600 credential file.
Secret input is hidden when a terminal is available. Environment variables are
supported for non-interactive installation, but their values are never echoed.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
DEFAULT_DIR = Path(os.environ.get(
    "AUTOOPS_CSS_CONFIG_DIR",
    str(Path.home() / ".config" / "jiuwenswarm-autoops" / "css"),
)).expanduser()


def fail(message: str) -> int:
    print(json.dumps({"status": "INPUT_ERROR", "error": message}, ensure_ascii=False))
    return 2


def require_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise ValueError(f"{field} must match [A-Za-z0-9][A-Za-z0-9._-]{{0,62}}")
    return value


def require_nonempty(value: str | None, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field} is required and must be a single line")
    return value.strip()


def prompt_secret(label: str, env_name: str) -> str:
    value = os.environ.get(env_name)
    if value:
        return value
    if not os.isatty(0):
        raise ValueError(f"{env_name} is required in non-interactive mode")
    return getpass.getpass(f"{label}: ")


def atomic_json(path: Path, payload: dict[str, Any], mode: int) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"destination must be a regular file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, stat.S_IRWXU)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    profile_id = require_name(args.profile_id, "profile_id")
    credential_id = require_name(args.credential_id, "credential_id")
    cluster_id = require_nonempty(args.cluster_id, "cluster_id")
    if not UUID_RE.fullmatch(cluster_id):
        raise ValueError("cluster_id must be a Huawei Cloud CSS UUID")
    region = require_name(args.region, "region")
    project_id = require_nonempty(args.project_id, "project_id")
    domain_id = require_nonempty(args.domain_id, "domain_id") if args.domain_id else ""
    if args.api_adapter == "koo-cli":
        access_key = secret_key = ""
    else:
        access_key = require_nonempty(
            prompt_secret("Huawei Cloud AK", "HUAWEICLOUD_SDK_AK"),
            "access_key",
        )
        secret_key = require_nonempty(
            prompt_secret("Huawei Cloud SK", "HUAWEICLOUD_SDK_SK"),
            "secret_key",
        )
    endpoint = args.endpoint.rstrip("/") if args.endpoint else ""
    credential = {
        "schema_version": 1,
        "credential_id": credential_id,
        "provider": "huaweicloud",
        "project_id": project_id,
        "region": region,
    }
    if domain_id:
        credential["domain_id"] = domain_id
    if args.api_adapter == "koo-cli":
        credential["auth_source"] = "koo-cli-profile"
    else:
        credential.update({"access_key_id": access_key, "secret_access_key": secret_key})
    if endpoint:
        credential["css_endpoint"] = endpoint
    credential_ref = f"css/credentials/{credential_id}"
    profile = {
        "schema_version": 1,
        "profile_id": profile_id,
        "revision": args.revision,
        "provider": "huaweicloud",
        "resource_type": "css_cluster",
        "cluster_id": cluster_id,
        "cluster_name": args.cluster_name or profile_id,
        "region": region,
        "project_id": project_id,
        "domain_id": domain_id,
        "credential_ref": credential_ref,
        "engine": args.engine,
        "mode": args.mode,
        "api_adapter": args.api_adapter,
        "koo_cli_profile": args.koo_cli_profile,
        "koo_cli_mode": args.koo_cli_mode,
        "koo_cli_home": args.koo_cli_home,
        "enabled": True,
        "policy_ref": args.policy_ref,
        "capability_ref": "huaweicloud-css",
        "aliases": args.alias,
        "created_by": "css-register",
        "profile_fingerprint": hashlib.sha256(
            f"{profile_id}|{cluster_id}|{region}|{project_id}".encode()
        ).hexdigest()[:16],
    }
    return profile, credential


def default_policy(policy_id: str, mode: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": policy_id,
        "revision": 1,
        "mode": mode,
        "min_data_nodes": 2,
        "max_data_nodes": 10,
        "scale_out_step": 1,
        "scale_in_step": 1,
        "scale_out_cooldown_minutes": 30,
        "scale_in_cooldown_minutes": 120,
        "scale_in_delay_after_scale_out_minutes": 120,
        "scale_out_cpu_percent": 75,
        "scale_in_cpu_percent": 30,
        "scale_out_disk_percent": 75,
        "scale_in_disk_percent": 65,
        "scale_in_max_search_rate": 1000,
        "scale_in_max_indexing_rate": 1000,
        "scale_in_max_search_latency": 200,
        "scale_in_max_indexing_latency": 200,
        "scale_in_max_jvm_heap": 85,
        "scale_in_min_history_minutes": 1440,
        "sample_freshness_seconds": 180,
        "require_snapshot_for_scale_in": True,
        "allow_scale_out": mode == "auto",
        "allow_scale_in": False,
        "enforce_sustained_windows": mode == "auto",
        "scale_out_window_minutes": 5,
        "scale_out_required_samples": 3,
        "scale_in_stable_minutes": 30,
        "scale_in_required_samples": 10,
        "strict_scale_in_evidence": mode == "auto",
        "fresh_precheck_required": mode == "auto",
        "sample_freshness_seconds": 180,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a Huawei Cloud CSS cluster for AutoOps.")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--cluster-id", required=True, help="CSS cluster UUID")
    parser.add_argument("--region", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--domain-id", default="",
                        help="Huawei Cloud account/domain ID for AKSK context")
    parser.add_argument("--credential-id", default="default")
    parser.add_argument("--cluster-name", default="")
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--engine", choices=("opensearch", "elasticsearch", "unknown"), default="unknown")
    parser.add_argument("--mode", choices=("observe", "recommend", "auto"), default="observe")
    parser.add_argument("--policy-ref", default="css-default")
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--api-adapter", choices=("sdk", "koo-cli"), default="sdk")
    parser.add_argument("--koo-cli-profile", default="",
                        help="KooCLI profile name; omit to use its default profile")
    parser.add_argument("--koo-cli-home", default=os.environ.get("AUTOOPS_KOO_CLI_HOME", ""),
                        help="KooCLI HOME for role workers; credentials remain owned by KooCLI")
    parser.add_argument("--koo-cli-mode", choices=("AKSK", "ecsAgency"), default="AKSK",
                        help="KooCLI authentication mode; AKSK is the default")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    if args.revision < 1:
        return fail("revision must be positive")
    try:
        profile, credential = build(args)
        config_dir = args.config_dir.expanduser()
        profile_path = config_dir / "clusters" / f"{profile['profile_id']}.json"
        credential_path = config_dir / "credentials" / f"{credential['credential_id']}.json"
        policy_path = config_dir / "policies" / f"{profile['policy_ref']}.json"
        if profile_path.exists():
            current = json.loads(profile_path.read_text(encoding="utf-8"))
            if int(current.get("revision", 0)) >= profile["revision"]:
                raise ValueError("new profile revision must be greater than stored revision")
        if credential_path.exists():
            current = json.loads(credential_path.read_text(encoding="utf-8"))
            if current.get("credential_id") != credential["credential_id"]:
                raise ValueError("credential destination belongs to another credential")
        atomic_json(credential_path, credential, stat.S_IRUSR | stat.S_IWUSR)
        atomic_json(profile_path, profile, stat.S_IRUSR | stat.S_IWUSR)
        if not policy_path.exists():
            atomic_json(policy_path, default_policy(profile["policy_ref"], profile["mode"]),
                        stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))
    print(json.dumps({
        "status": "REGISTERED",
        "profile_id": profile["profile_id"],
        "cluster_id": profile["cluster_id"],
        "credential_ref": profile["credential_ref"],
        "mode": profile["mode"],
        "profile_path": str(profile_path),
        "credential_path": str(credential_path),
        "policy_path": str(policy_path),
        "secret_written": bool(credential.get("secret_access_key")),
        "api_adapter": profile["api_adapter"],
        "koo_cli_profile": profile["koo_cli_profile"],
        "koo_cli_mode": profile["koo_cli_mode"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
