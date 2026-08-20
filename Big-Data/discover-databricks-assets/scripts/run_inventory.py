#!/usr/bin/env python3
"""Run the complete Databricks discovery inventory and emit a manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def run(script: Path, *args: str) -> None:
    subprocess.run([sys.executable, str(script), *args], check=True)


def count_csv(path: Path, field: str) -> dict[str, int]:
    with path.open(encoding="utf-8", newline="") as handle:
        return dict(Counter(row.get(field, "UNKNOWN") or "UNKNOWN" for row in csv.DictReader(handle)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, default=Path("f_credentials.env"))
    parser.add_argument("--output-dir", type=Path, default=Path("databricks_inventory"))
    parser.add_argument("--max-workspace-objects", type=int, default=100000)
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    credentials = str(args.credentials.resolve())

    objects = output / "objects_ddl.csv"
    storage = output / "table_storage.csv"
    workloads_csv = output / "jobs_pipelines.csv"
    workloads_json = output / "jobs_pipelines.json"
    platform = output / "platform_assets.csv"
    warnings = output / "warnings.json"
    object_warnings = output / ".objects_warnings.json"
    platform_warnings = output / ".platform_warnings.json"
    dependencies = output / "dependencies.csv"

    run(
        scripts / "inventory_objects.py",
        "--credentials", credentials,
        "--output", str(objects),
        "--warnings", str(object_warnings),
    )
    run(scripts / "inventory_table_storage.py", "--input", str(objects), "--output", str(storage))
    run(
        scripts / "inventory_workloads.py",
        "--credentials", credentials,
        "--csv-output", str(workloads_csv),
        "--json-output", str(workloads_json),
    )
    run(
        scripts / "inventory_platform.py",
        "--credentials", credentials,
        "--output", str(platform),
        "--warnings", str(platform_warnings),
        "--max-workspace-objects", str(args.max_workspace_objects),
    )
    run(
        scripts / "build_dependencies.py",
        "--objects", str(objects),
        "--workloads", str(workloads_json),
        "--output", str(dependencies),
    )

    warning_items = []
    for warning_file in (object_warnings, platform_warnings):
        warning_items.extend(json.loads(warning_file.read_text(encoding="utf-8")))
        warning_file.unlink()
    warnings.write_text(json.dumps(warning_items, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = [objects, storage, workloads_csv, workloads_json, platform, warnings, dependencies]
    manifest = {
        "inventory_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "objects": count_csv(objects, "object_type"),
            "storage_assets": count_csv(storage, "asset_type"),
            "workloads": count_csv(workloads_csv, "record_type"),
            "platform_assets": count_csv(platform, "asset_type"),
            "dependencies": count_csv(dependencies, "relation"),
        },
        "warnings_count": len(warning_items),
        "artifacts": [
            {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in artifacts
        ],
        "limitations": [
            "DDL is canonical metadata-derived SQL; browse-only objects may lack columns or definitions.",
            "View dependencies are heuristic unless explicit workload references expose them.",
            "Table file rows are location patterns, not recursive cloud-object listings.",
            "Secret values are never requested; sensitive workload configuration keys are redacted.",
            "Permissions and lineage require additional APIs/system tables and may depend on token privileges.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inventory complete: {output}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
