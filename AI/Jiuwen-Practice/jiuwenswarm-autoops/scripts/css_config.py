"""Load CSS cluster profiles and policies without exposing credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
def _default_dir() -> Path:
    configured = os.environ.get("AUTOOPS_CSS_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    try:
        from autoops_runtime_config import resolve_runtime
        return Path(resolve_runtime()["config_root"]) / "css"
    except (ImportError, KeyError, OSError, ValueError, json.JSONDecodeError):
        return Path.home() / ".config" / "jiuwenswarm-autoops" / "css"


DEFAULT_DIR = _default_dir().expanduser()


def _regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"CSS config must be a regular file: {path}")


def _read(path: Path) -> dict[str, Any]:
    _regular(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"CSS config must be an object: {path}")
    return value


def config_dir(value: str | Path | None = None) -> Path:
    return Path(value).expanduser() if value else DEFAULT_DIR


def load_profile(profile_id: str, directory: str | Path | None = None) -> dict[str, Any]:
    path = config_dir(directory) / "clusters" / f"{profile_id}.json"
    profile = _read(path)
    if profile.get("resource_type") != "css_cluster":
        raise ValueError("profile resource_type must be css_cluster")
    for field in ("profile_id", "cluster_id", "region", "project_id", "credential_ref"):
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            raise ValueError(f"CSS profile field is required: {field}")
    adapter = str(profile.get("api_adapter", "sdk")).strip().casefold()
    if adapter not in {"sdk", "koo-cli", "koocli", "hcloud"}:
        raise ValueError("CSS api_adapter must be sdk or koo-cli")
    if adapter in {"koo-cli", "koocli", "hcloud"}:
        auth_mode = str(profile.get("koo_cli_mode", "AKSK")).strip()
        if auth_mode not in {"AKSK", "ecsAgency"}:
            raise ValueError("CSS koo_cli_mode must be AKSK or ecsAgency")
    return profile


def load_credentials(profile: dict[str, Any], directory: str | Path | None = None) -> dict[str, Any]:
    if str(profile.get("api_adapter", "sdk")).strip().casefold() in {"koo-cli", "koocli", "hcloud"}:
        # KooCLI owns authentication in its configured profile. Do not make
        # JiuwenSwarm read or duplicate AK/SK for this adapter.
        return {
            "project_id": profile["project_id"], "region": profile["region"],
            "domain_id": profile.get("domain_id", ""),
        }
    ref = str(profile["credential_ref"])
    prefix = "css/credentials/"
    if not ref.startswith(prefix):
        raise ValueError("unsupported CSS credential reference")
    credential_id = ref[len(prefix):]
    if not credential_id or "/" in credential_id or "\\" in credential_id:
        raise ValueError("invalid CSS credential reference")
    path = config_dir(directory) / "credentials" / f"{credential_id}.json"
    credentials = _read(path)
    for field in ("access_key_id", "secret_access_key", "project_id", "region"):
        if not isinstance(credentials.get(field), str) or not credentials[field]:
            raise ValueError(f"CSS credential field is required: {field}")
    if credentials["secret_access_key"] in {"replace-with-sk", "replace-with-secret"}:
        raise ValueError("CSS secret key is still a placeholder")
    return credentials


def load_policy(policy_id: str, directory: str | Path | None = None) -> dict[str, Any]:
    path = config_dir(directory) / "policies" / f"{policy_id}.json"
    if not path.exists():
        path = config_dir(directory) / "policy.json"
    policy = _read(path)
    if policy.get("schema_version") not in {1, 2, 3}:
        raise ValueError("unsupported CSS policy schema_version")
    if policy.get("policy_id", policy_id) != policy_id:
        raise ValueError("CSS policy_id does not match requested policy")
    if not isinstance(policy.get("min_data_nodes"), int) or not isinstance(policy.get("max_data_nodes"), int):
        raise ValueError("CSS policy node bounds are required")
    if policy["min_data_nodes"] > policy["max_data_nodes"]:
        raise ValueError("CSS policy min_data_nodes exceeds max_data_nodes")
    return policy


def load_capability(profile: dict[str, Any], directory: str | Path | None = None) -> dict[str, Any]:
    capability_id = str(profile.get("capability_ref", "huaweicloud-css"))
    path = config_dir(directory) / "capabilities" / f"{capability_id}.json"
    if not path.exists():
        return {}
    capability = _read(path)
    if capability.get("schema_version") != 1:
        raise ValueError("unsupported CSS capability schema_version")
    return capability


def effective_policy(profile: dict[str, Any], directory: str | Path | None = None) -> dict[str, Any]:
    policy = dict(load_policy(profile.get("policy_ref", "css-default"), directory))
    capability = load_capability(profile, directory)
    provider_constraints = dict(policy.get("provider_constraints") or {})
    provider_constraints.update(capability.get("provider_constraints") or {})
    if provider_constraints:
        policy["provider_constraints"] = provider_constraints
    if capability.get("revision") is not None:
        policy["capability_revision"] = capability["revision"]
    return policy


def safe_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile["profile_id"],
        "resource_type": profile["resource_type"],
        "cluster_id": profile["cluster_id"],
        "cluster_name": profile.get("cluster_name", profile["profile_id"]),
        "region": profile["region"],
        "project_id": profile["project_id"],
        "domain_id": profile.get("domain_id", ""),
        "credential_ref": profile["credential_ref"],
        "mode": profile.get("mode", "observe"),
        "api_adapter": profile.get("api_adapter", "sdk"),
        "koo_cli_profile": profile.get("koo_cli_profile", ""),
        "koo_cli_mode": profile.get("koo_cli_mode", "AKSK"),
        "policy_ref": profile.get("policy_ref", "css-default"),
        "aliases": profile.get("aliases", []),
    }
