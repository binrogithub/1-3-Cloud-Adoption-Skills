#!/usr/bin/env python3
"""Check a published CSS AutoOps layout without changing the host."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _installer_module(source_root: Path):
    path = source_root / "scripts" / "install-autoops-runtime.py"
    spec = importlib.util.spec_from_file_location("autoops_install_runtime_for_css_check", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"installer is not importable: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_layout(source_root: Path, install_root: Path, config_root: Path,
                 systemd_root: Path) -> dict[str, Any]:
    installer = _installer_module(source_root)
    reasons: list[str] = []
    runtime_files = list(installer.RUNTIME_ASSET_FILES)
    swarmflow_files = list(installer.SWARMFLOW_FILES)
    source_files = runtime_files + [f"swarmflow/{item}" for item in swarmflow_files]
    missing_source = [item for item in runtime_files if not (source_root / item).is_file()]
    missing_source += [item for item in swarmflow_files if not (source_root / "swarmflow" / item).is_file()]
    missing_install = [item for item in runtime_files if not (install_root / item).is_file()]
    missing_install += [f"swarmflow/{item}" for item in swarmflow_files
                        if not (install_root / "swarmflow" / item).is_file()]
    missing_units = [item for item in installer.SYSTEMD_FILES if not (systemd_root / item).is_file()]
    if missing_source:
        reasons.append("source_assets_missing")
    if missing_install:
        reasons.append("installed_assets_missing")
    if missing_units:
        reasons.append("systemd_units_missing")
    parsed_json: list[str] = []
    json_roots = (install_root / "config/css", install_root / "config/acceptance")
    for directory in json_roots:
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                    parsed_json.append(str(path))
                except (OSError, ValueError, json.JSONDecodeError):
                    reasons.append(f"invalid_json:{path.name}")
    manifest_path = install_root / "autoops-install-manifest.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.is_file():
        reasons.append("install_manifest_missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != 2:
                reasons.append("install_manifest_schema")
        except (OSError, ValueError, json.JSONDecodeError):
            reasons.append("install_manifest_invalid")
    css_unit = systemd_root / "jiuwenswarm-autoops-css-watch.service"
    if css_unit.is_file():
        unit_text = css_unit.read_text(encoding="utf-8")
        if "AUTOOPS_CSS_ACTION_DB=" not in unit_text:
            reasons.append("css_action_db_not_persisted")
        if "ProtectSystem=strict" not in unit_text:
            reasons.append("css_service_hardening_missing")
    if config_root.exists() and config_root.is_symlink():
        reasons.append("config_root_symlink")
    result = {
        "schema_version": 1, "status": "PASS" if not reasons else "NOT_READY",
        "source_root": str(source_root), "install_root": str(install_root),
        "config_root": str(config_root), "systemd_root": str(systemd_root),
        "source_asset_count": len(source_files) - len(missing_source),
        "installed_asset_count": len(source_files) - len(missing_install),
        "parsed_json_count": len(parsed_json), "manifest_schema": manifest.get("schema_version"),
        "missing_source": missing_source, "missing_install": missing_install,
        "missing_units": missing_units, "reasons": sorted(set(reasons)),
        "customer_secret_validation": "external_credential_files_not_read",
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the installed CSS AutoOps layout.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--systemd-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = check_layout(args.source_root, args.install_root, args.config_root, args.systemd_root)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 1, "status": "NOT_READY", "reasons": ["self_check_error"], "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
