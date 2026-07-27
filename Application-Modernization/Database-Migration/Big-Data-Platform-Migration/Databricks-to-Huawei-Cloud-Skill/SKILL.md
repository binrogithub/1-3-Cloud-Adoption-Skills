---
name: databricks-to-huawei-cloud-skill
description: Use this skill when migrating Databricks tables, notebooks, SQL warehouse flows, or Spark pipelines to Huawei Cloud. It helps analyze the source workload, map Databricks patterns to OBS plus MRS Spark and Hive, generate sanitized migration scripts, validate result parity, and compare execution behavior without relying on environment-specific details.
---

# Databricks to Huawei Cloud Skill

## Overview

Use this skill for Databricks-to-Huawei Cloud migration work where `MRS` is the default compute target for Spark workloads and `OBS` is the preferred object storage target. It is optimized for notebook migration, open-format export, functional parity testing, and repeatable migration execution.

## Quick Start

Follow this sequence by default:

1. Inspect the Databricks source workflow.
2. Separate business logic from Databricks-specific platform behavior.
3. Prefer `Parquet` as the interchange format and `CSV` only for raw/simple inputs.
4. Map the source into `raw/bronze -> standardized/silver -> analytical/gold`.
5. Rebuild the execution path on `MRS Spark + Hive`.
6. Compare row counts, aggregates, business metrics, and run time.
7. Document operational gaps such as object-store authorization separately from logic migration.

## Workflow Decision Tree

Start with the migration shape:

- Simple file-to-table flow:
  - Read source files from Databricks `Volumes` or tables.
  - Export to `Parquet`.
  - Recreate the managed or external table pattern on MRS.
  - Read [references/migration-patterns.md](references/migration-patterns.md).
- Multi-step notebook with joins, features, or rules:
  - Treat notebook cells as staged Spark transformations.
  - Preserve analytical intent, not notebook UX.
  - Rebuild as one Spark job or a small job chain on MRS.
  - Read [references/migration-patterns.md](references/migration-patterns.md).
- Result validation or performance comparison:
  - Compare metric outputs across platforms before discussing tuning.
  - Read [references/result-parity.md](references/result-parity.md).
- Migration failure or mismatch:
  - Check for storage-path, metadata, authorization, or Databricks-only assumptions.
  - Read [references/common-pitfalls.md](references/common-pitfalls.md).

## Core Rules

- Preserve business semantics first. UI parity is not the goal.
- Default target pattern:
  - `Databricks source -> open files -> OBS -> MRS Spark -> Hive tables -> curated Parquet`
- If `OBS` access is blocked during migration or validation, continue with an `HDFS` or local-node fallback to validate logic.
- Treat `OBS agency` or temporary-credential issues as operational blockers, not logic blockers.
- Keep all scripts and examples sanitized:
  - use placeholders such as `<bucket>`, `<catalog>`, `<schema>`, `<warehouse_http_path>`, `<mrs-master>`
  - never copy hostnames, usernames, passwords, tokens, access keys, project IDs, or customer names

## Default Deliverables

When using this skill, prefer producing:

- a migration mapping from Databricks patterns to MRS patterns
- a minimal Databricks-side export or reconstruction script
- a minimal MRS-side Spark job template
- a parity-check metric table
- a short gap list:
  - functional gaps
  - operational gaps
  - performance caveats

## Script Use

Use the bundled templates when you need a starting point:

- `scripts/databricks_sql_warehouse_pattern.py`
  - generic SQL warehouse execution and metric collection pattern
- `scripts/mrs_spark_submit_pattern.py`
  - generic MRS Spark job pattern with Hive output and metric emission
- `scripts/compare_metrics_template.py`
  - generic exact-match and delta comparison for Databricks vs MRS metrics

## Reference Use

- Read [references/migration-patterns.md](references/migration-patterns.md) for mapping rules and target design.
- Read [references/result-parity.md](references/result-parity.md) when validating migrated workloads.
- Read [references/common-pitfalls.md](references/common-pitfalls.md) when a migration is blocked or producing mismatched results.
