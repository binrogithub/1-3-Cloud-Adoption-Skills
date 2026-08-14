---
name: discover-databricks-assets
description: Inventory Databricks workspaces for migration discovery, including Unity Catalog catalogs, schemas, tables, views, functions, volumes, canonical DDL, table data and Delta metadata locations, jobs, tasks, pipelines, compute, repositories, workspace objects, secret-scope names, and dependency edges. Use when Codex needs to audit Databricks assets, assess migration scope or readiness, produce repeatable CSV/JSON inventories, identify metadata gaps, or prepare a future migration to Huawei Cloud DataArts Studio, MRS, DLI, GaussDB(DWS), and OBS.
---

# Discover Databricks Assets

Create a read-only, reproducible source inventory before designing or automating migration. Preserve raw-enough
metadata for later transformation while emitting flattened CSV files for analysis.

## Run the inventory

1. Confirm the user authorized read-only access to the workspace in scope.
2. Locate credentials without printing values. Prefer `DATABRICKS_HOST` and `DATABRICKS_TOKEN`; otherwise pass a
   credential file containing an HTTPS workspace URL and a `dapi` token on separate lines.
3. Run from this skill directory or use absolute paths:

```bash
python3 scripts/run_inventory.py \
  --credentials /absolute/path/to/f_credentials.env \
  --output-dir /absolute/path/to/databricks_inventory
```

4. Allow outbound access only to the configured workspace. The scripts use GET requests and do not start SQL
   warehouses, run jobs, read secret values, or download table/file contents.
5. Inspect `manifest.json` and `warnings.json` before reporting completeness.
6. Summarize counts by asset type, incomplete DDL, permission gaps, dependency confidence, and storage scheme.

If the workspace object tree is exceptionally large, set `--max-workspace-objects`. Report the cap as a scope
limit; never describe a capped scan as complete.

## Interpret the artifacts

Read [references/output-contract.md](references/output-contract.md) whenever validating files, joining outputs,
or evaluating completeness. Preserve all generated artifacts together because `manifest.json` records their
checksums and counts.

Use these primary outputs:

- `objects_ddl.csv` for tables, views, functions, and canonical metadata-derived DDL.
- `table_storage.csv` for table roots, data patterns, Delta log paths, and transfer-access status.
- `jobs_pipelines.csv` and `jobs_pipelines.json` for flattened and redacted workload definitions.
- `platform_assets.csv` for catalogs, schemas, volumes, compute, repos, workspace code, and governance metadata.
- `dependencies.csv` for exact configuration edges and explicitly labeled heuristic SQL edges.

Do not recursively enumerate a whole volume when the request concerns table data. Use table storage locations.
Do not claim that `uc-deltasharing://` references are direct cloud paths. Do not infer that an empty API result is
complete when the matching endpoint appears in `warnings.json`.

## Handle DDL limitations

Generate canonical DDL from Unity Catalog metadata without starting compute. Mark unavailable columns or view
definitions as `metadata_missing`. Ask before starting a stopped or billable SQL warehouse to obtain
`SHOW CREATE` output. Keep source DDL separate from future Huawei-target SQL.

## Assess Huawei migration

Only enter migration assessment or transformation when the user requests it. Then read
[references/huawei-assessment.md](references/huawei-assessment.md), verify current Huawei service capabilities
from official documentation, and build an evidence-backed compatibility matrix. Treat DataArts Studio, MRS,
DLI, GaussDB(DWS), and OBS as candidate components rather than one-to-one replacements.

Do not create target resources, transfer data, rewrite production code, or modify Databricks assets during the
discovery phase. Require explicit authorization for those later phases.

## Extend the skill

Add new asset classes as separate scripts or explicit output columns. Update the output contract, manifest
limitations, and dependency semantics together. Redact sensitive values before serialization, add an offline
fixture test, run the relevant script against an authorized workspace, and validate the skill after each update.
