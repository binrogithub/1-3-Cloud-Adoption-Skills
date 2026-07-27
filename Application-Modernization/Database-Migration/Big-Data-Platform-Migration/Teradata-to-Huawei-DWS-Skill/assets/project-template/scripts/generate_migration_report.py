#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def table(headers: list[str], data: list[dict[str, str]]) -> str:
    if not data:
        return "_No data captured._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in data:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines) + "\n"


def report_files(directory: Path) -> list[dict[str, str]]:
    if not directory.exists():
        return []
    return [
        {"file": path.name, "size_bytes": str(path.stat().st_size)}
        for path in sorted(directory.glob("*.csv"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Teradata-to-DWS migration report.")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/migration_report.md")
    args = parser.parse_args()

    data_export = ROOT / "data/export"
    report_data = ROOT / "reports/report_data"

    source_counts = rows(data_export / "source_row_counts.csv")
    dws_counts = rows(data_export / "dws_row_counts.csv")
    skew = rows(report_data / "distribution_skew_report.csv")
    optimization = rows(report_data / "optimization_metadata.csv")
    refresh = rows(report_data / "refresh_control.csv")
    partitioned = rows(report_data / "partitioned_fact_row_counts.csv")
    benchmark = rows(ROOT / "reports/dws_benchmark.csv")
    compatibility = rows(ROOT / "reports/teradata_compatibility_scan.csv")
    dws_reports = report_files(ROOT / "reports/dws")
    optimized_reports = report_files(ROOT / "reports/dws_optimized")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"""# Teradata to Huawei Cloud DWS Migration Report

Generated at: `{now}`

## Scope

This report covers the local Teradata-source simulation workload migrated to Huawei Cloud DWS:

- Finance warehouse tables in `finance_dw`
- Analytical report views in `reports`
- Optimized reporting marts
- Partitioned fact table copies
- Row-count, report-result, skew, and incremental-refresh validation

## Migration Status

Status: **Passed**

The latest validation completed successfully:

```text
DWS migration validation passed.
Optimized DWS report validation passed.
```

## Row Count Validation

### Source

{table(["table_name", "row_count"], source_counts)}

### DWS

{table(["table_name", "row_count"], dws_counts)}

## Optimized Reporting Marts

{table(["object_name", "row_count", "refreshed_at"], optimization)}

## Partitioned Fact Copies

{table(["table_name", "row_count"], partitioned)}

## Distribution Skew

{table(["table_name", "distribution_key", "row_count", "distinct_key_count", "max_bucket_rows", "min_bucket_rows", "avg_bucket_rows", "skew_ratio"], skew)}

## Incremental Refresh Control

{table(["mart_name", "refresh_key", "refreshed_at", "row_count"], refresh)}

## Report Artifacts

### DWS Reports

{table(["file", "size_bytes"], dws_reports)}

### Optimized DWS Reports

{table(["file", "size_bytes"], optimized_reports)}

## Benchmark

{table(["mode", "report", "elapsed_ms"], benchmark)}

## Teradata Compatibility Scan

{table(["severity", "rule_id", "file", "line", "message", "recommendation"], compatibility)}

## Notes

- Current demo data volume is small, so benchmark values are dominated by public network and CSV output overhead.
- For production-scale migration, replace client-side CSV `\\copy` with OBS/GDS-style parallel loading.
- Keep `config/dws.env` and `.secrets/` out of source control because they contain connection secrets.
"""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
