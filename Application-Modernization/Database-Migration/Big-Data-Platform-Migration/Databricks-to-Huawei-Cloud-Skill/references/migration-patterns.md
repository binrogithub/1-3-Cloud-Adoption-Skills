# Migration Patterns

## Default Target

Use this target pattern unless the user explicitly asks for something else:

`Databricks -> open files -> OBS -> MRS Spark -> Hive Metastore -> curated Parquet`

For blocked environments:

`Databricks -> open files -> HDFS/local -> MRS Spark -> Hive Metastore -> curated Parquet`

## Pattern Mapping

### 1. Simple file-to-table flow

Databricks pattern:

- read CSV from `Volumes`
- create or replace managed table
- export to `Parquet`
- query over the exported result

MRS pattern:

- read `CSV` or `Parquet` from `obs://...` or `hdfs:///...`
- write managed Hive table with `saveAsTable`
- write curated `Parquet`
- optionally create an external Hive table over the curated location

### 2. SQL warehouse flow

Databricks SQL warehouse is usually a control plane for executing staged SQL statements. MRS does not need a warehouse-equivalent abstraction for migration work. Rebuild the same logic as:

- Spark SQL inside one `spark-submit` job
- or a small sequence of repeatable jobs

### 3. Notebook migration

Treat notebooks as structured logic, not as UI artifacts.

Map:

- notebook cells -> staged Spark transformations
- `display()` or `.show()` -> lightweight validation outputs
- Databricks tables/volumes -> Hive tables and `OBS` or `HDFS` paths
- notebook-managed outputs -> curated Parquet plus Hive metadata

### 4. Bronze/Silver/Gold migration

When the source is not explicitly layered, infer the layers:

- `raw/bronze`
  - landed source files and minimally typed data
- `standardized/silver`
  - cleaned joins, business keys, normalized facts and dimensions
- `analytical/gold`
  - KPI tables, dashboards, rule-hit results, exception outputs

This layered mapping helps agents rebuild intent quickly and compare outputs at multiple checkpoints.

## Preferred File Formats

- Prefer `Parquet` for interchange and curated outputs.
- Use `CSV` only for simple raw ingestion or synthetic test data.
- Avoid designing the migration around proprietary table semantics when the goal is portability.

## Recommended MRS Output Pattern

For each migrated flow, produce:

- Hive managed table for SQL access
- curated `Parquet` output for portability
- a small metric set for parity checks

## Minimal Migration Sequence

1. Inspect source tables, notebooks, and SQL statements.
2. Identify source paths, table dependencies, and key metrics.
3. Recreate source data in open files if needed.
4. Rebuild transformations in Spark on MRS.
5. Write Hive tables and curated `Parquet`.
6. Compare metric outputs.
7. Record operational gaps separately.

## What Usually Changes

- Databricks `Volumes` paths become `obs://...` or `hdfs:///...`
- SQL warehouse execution becomes `spark-submit` or Spark SQL on MRS
- managed storage semantics become Hive plus object storage
- notebook UX disappears, but analytical intent remains

## What Should Stay the Same

- business rules
- joins and feature logic
- aggregation logic
- row-count expectations
- analytical outputs
- validation metrics
