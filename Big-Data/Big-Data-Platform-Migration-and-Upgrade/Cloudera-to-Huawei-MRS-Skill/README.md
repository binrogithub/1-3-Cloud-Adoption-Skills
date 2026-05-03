# Cloudera to Huawei Cloud MRS Migration Skill

Migrate Cloudera Distribution including Apache Hadoop (CDH) or Hortonworks Data Platform (HDP) workloads to Huawei Cloud MRS (MapReduce Service). This skill covers the complete migration lifecycle from source analysis through parity validation.

## What It Does

- **Source analysis**: Discover Hive tables, Spark jobs, Impala queries, and HDFS layout on the Cloudera cluster
- **MRS provisioning**: Create a target MRS 3.5.0-LTS cluster on Huawei Cloud with correct sizing and EIP access
- **OBS data landing**: Export Parquet data from Cloudera and upload to Huawei Cloud OBS buckets
- **Hive external table migration**: Create MRS Hive external tables pointing to OBS locations with partition recovery
- **Spark SQL / HiveQL migration**: Convert Impala queries and HiveQL jobs to Spark SQL on MRS YARN
- **Report view migration**: Migrate Impala or Hive report views to Spark SQL views
- **Parity validation**: Compare row counts, aggregates, and business metrics between source and MRS

## Key Technical Notes

- **Hive 3.1 Parquet reader incompatibility**: MRS Hive 3.1 cannot read dictionary-encoded Parquet files produced by Spark 3.x. Always use `spark-sql --master yarn` instead of `beeline` for querying Spark-generated Parquet tables.
- **EIP binding**: Use EIP V3 SDK (not V2) with `associate_instance_type="PORT"` for binding public IPs to MRS Master nodes.
- **MRS minimums**: MRS 3.5.0-LTS requires 2 Master nodes, 3 Core nodes, 600 GB disks, and `.linux.bigdata` node spec suffix.

## Skill Assets

| File | Purpose |
| --- | --- |
| `SKILL.md` | Agent-facing workflow, trigger rules, and decision tree |
| `references/migration-workflow.md` | 8-phase end-to-end migration workflow |
| `references/hive-migration.md` | Hive Metastore, DDL, partition, and ACID migration |
| `references/spark-migration.md` | Spark version mapping, spark-submit, PySpark migration |
| `references/impala-migration.md` | Impala SQL function and DDL conversion to Spark SQL |
| `references/result-parity.md` | Validation strategy, query patterns, and acceptance criteria |
| `references/common-pitfalls.md` | 10+ known pitfalls with solutions |
| `references/mrs-operations.md` | MRS cluster access, paths, service users, obsutil |
| `scripts/source_simulation.sh` | Local Spark Standalone cluster for source simulation |
| `scripts/mrs_provision.py` | MRS cluster provisioning via Huawei Cloud SDK |
| `scripts/obs_upload.sh` | Parquet upload to OBS via obsutil |
| `scripts/validate_parity.py` | Source vs. MRS metric comparison script |

## Validated Migration

This skill was validated against a real MRS 3.5.0-LTS cluster with a finance data warehouse migration. All 12 parity metrics passed:

| Metric | Source | MRS | Status |
| --- | --- | --- | --- |
| dim_branch | 10 | 10 | PASS |
| dim_product | 6 | 6 | PASS |
| dim_customer | 2,000 | 2,000 | PASS |
| dim_account | 8,000 | 8,000 | PASS |
| dim_date | 181 | 181 | PASS |
| fact_transaction | 120,000 | 120,000 | PASS |
| fact_daily_balance | 728,000 | 728,000 | PASS |
| fact_loan_snapshot | 1,500 | 1,500 | PASS |
| amount_sum | 1,205,934,000.00 | 1,205,934,000.00 | PASS |
| suspicious_count | 262 | 262 | PASS |
| ending_balance_sum | 11,288,418,400.00 | 11,288,418,400.00 | PASS |
| ecl_sum | 7,499,313.97 | 7,499,313.97 | PASS |

## When to Use

- Migrating CDH or HDP Hadoop/Spark/Hive workloads to Huawei Cloud MRS
- Converting Impala queries to Spark SQL on MRS
- Landing Cloudera data in OBS and creating Hive external tables
- Validating migration parity between source and MRS
- Troubleshooting Cloudera-to-MRS migration issues
