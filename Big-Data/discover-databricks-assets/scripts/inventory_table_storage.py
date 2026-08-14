#!/usr/bin/env python3
"""Build a table-focused map of data and Delta metadata locations."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIELDS = [
    "asset_type",
    "catalog",
    "schema",
    "table",
    "full_name",
    "table_type",
    "data_source_format",
    "owner",
    "comment",
    "storage_scheme",
    "table_root",
    "asset_location",
    "location_status",
    "access_notes",
    "ddl_status",
    "ddl",
]


def asset_row(source: dict[str, str], asset_type: str, asset_location: str) -> dict[str, str]:
    root = source.get("storage_location", "").rstrip("/")
    scheme = root.split(":", 1)[0] if ":" in root else ""
    if not root:
        status = "metadata_missing"
        notes = "The Unity Catalog API did not expose a physical storage location for this table."
    elif scheme == "uc-deltasharing":
        status = "delta_sharing_reference"
        notes = "Logical Delta Sharing location; copy through the sharing protocol, not direct object storage."
    elif scheme in {"s3", "abfss", "gs"}:
        status = "cloud_location_available"
        notes = "Direct listing/copy requires cloud storage credentials with access to this location."
    else:
        status = "location_available"
        notes = "Validate access to this source location before migration."
    return {
        "asset_type": asset_type,
        "catalog": source.get("catalog", ""),
        "schema": source.get("schema", ""),
        "table": source.get("name", ""),
        "full_name": source.get("full_name", ""),
        "table_type": source.get("table_type", ""),
        "data_source_format": source.get("data_source_format", ""),
        "owner": source.get("owner", ""),
        "comment": source.get("comment", ""),
        "storage_scheme": scheme,
        "table_root": root,
        "asset_location": asset_location,
        "location_status": status,
        "access_notes": notes,
        "ddl_status": source.get("ddl_status", ""),
        "ddl": source.get("ddl", ""),
    }


def build(input_path: Path, output_path: Path) -> tuple[int, int]:
    rows: list[dict[str, str]] = []
    table_count = 0
    with input_path.open(encoding="utf-8", newline="") as handle:
        for source in csv.DictReader(handle):
            if source.get("object_type") != "TABLE":
                continue
            table_count += 1
            root = source.get("storage_location", "").rstrip("/")
            rows.append(asset_row(source, "TABLE_ROOT", root))
            if not root:
                continue
            data_format = source.get("data_source_format", "").upper()
            data_pattern = f"{root}/**/*.parquet" if data_format == "DELTA" else f"{root}/**/*"
            rows.append(asset_row(source, "DATA_FILES", data_pattern))
            if data_format == "DELTA":
                rows.append(asset_row(source, "DELTA_METADATA", f"{root}/_delta_log/"))

    rows.sort(key=lambda row: (row["catalog"], row["schema"], row["table"], row["asset_type"]))
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return table_count, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("databricks_objects_ddl.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("databricks_table_storage_inventory.csv")
    )
    args = parser.parse_args()
    table_count, asset_count = build(args.input, args.output)
    print(f"Wrote {asset_count} asset rows for {table_count} tables to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
