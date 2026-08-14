# Inventory output contract

Read this file when interpreting, validating, joining, or extending inventory outputs.

## Artifact set

| File | Grain | Primary identifier | Purpose |
|---|---|---|---|
| `manifest.json` | One run | `created_at_utc` | Counts, checksums, warnings, limitations |
| `objects_ddl.csv` | Table, view, or function | `object_type + full_name` | Unity Catalog objects and canonical DDL |
| `table_storage.csv` | Storage asset per table | `full_name + asset_type` | Table roots, data patterns, Delta metadata paths |
| `jobs_pipelines.csv` | Job, task, job cluster, or pipeline | `record_type + object_id` | Flattened workload inventory |
| `jobs_pipelines.json` | One document | API identifiers | Redacted full workload definitions |
| `platform_assets.csv` | Platform asset | `asset_type + asset_id/path/full_name` | Catalogs, schemas, volumes, compute, repos, workspace code, and governance metadata |
| `dependencies.csv` | Directed edge | Source + relation + target | Workload, storage, and heuristic view dependencies |
| `warnings.json` | Warning | Array position | Permission gaps, scan limits, and endpoint failures |

## Completeness rules

- Treat `ddl_status=complete` as metadata-complete canonical DDL, not guaranteed byte-for-byte output from `SHOW CREATE`.
- Treat `ddl_status=metadata_missing` as a blocker requiring SQL compute, elevated metadata access, or manual recovery.
- Treat `confidence=exact` dependency edges as directly represented by source configuration.
- Treat `confidence=heuristic` edges as candidates requiring validation with lineage APIs, SQL parsing, or system tables.
- Treat `uc-deltasharing://` as a protocol reference, not a directly copyable object-store path.
- Treat `DATA_FILES` paths as location patterns. The inventory does not recursively list S3, OBS, ADLS, or GCS objects.
- Review `warnings.json` before claiming workspace completeness.

## Stable join keys

- Join table assets to objects with `table_storage.full_name = objects_ddl.full_name`.
- Join job tasks to jobs with `JOB_TASK.parent_id = JOB.object_id`.
- Join dependency sources and targets to the matching type-specific identifiers.
- Prefer immutable Databricks IDs from workload and platform outputs. Use names only when APIs do not expose IDs.

## Security contract

- Never request secret values.
- Never print tokens, passwords, private keys, or cloud access keys.
- Redact sensitive configuration keys before writing full workload definitions.
- Store inventory outputs as sensitive architecture metadata and restrict filesystem permissions.
- Record permission failures as warnings; do not silently claim an inaccessible asset class is empty.

## Version 1 boundaries

Version 1 does not guarantee full permissions, row/column policies, account-level identities, query history,
runtime lineage, cloud-object listings, dashboards outside job references, model registry objects, vector search,
serving endpoints, or marketplace assets. Add these as explicit modules in later versions rather than broadening
the meaning of existing files.
