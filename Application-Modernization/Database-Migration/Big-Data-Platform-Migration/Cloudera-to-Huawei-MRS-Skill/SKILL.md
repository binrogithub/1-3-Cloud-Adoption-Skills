---
name: cloudera-to-huawei-mrs
description: Use this skill when migrating Cloudera/CDH Hadoop, Hive, Spark, or Impala workloads to Huawei Cloud MRS. It covers source simulation, MRS cluster provisioning, OBS data landing, Hive external table creation, Spark SQL migration, report view migration, and end-to-end parity validation. Use when the user mentions Cloudera, CDH, HDP, or any Hadoop/Spark/Hive migration to Huawei Cloud MRS, OBS, or FusionInsight.
---

# Cloudera to Huawei Cloud MRS Migration Skill

## Overview

Use this skill for Cloudera Distribution including Apache Hadoop (CDH) or Hortonworks Data Platform (HDP) to Huawei Cloud MRS migration work. MRS (MapReduce Service) is Huawei Cloud's managed big-data platform built on FusionInsight, providing Hadoop, Hive, Spark, Tez, ZooKeeper, Ranger, and other components in a fully managed cluster.

This skill covers the complete migration lifecycle:

1. Source workload analysis and local simulation
2. MRS cluster provisioning on Huawei Cloud
3. OBS bucket creation and Parquet data landing
4. Hive external table DDL migration
5. Spark SQL / HiveQL job migration
6. Report view migration
7. End-to-end result parity validation
8. Operational hardening and production readiness

## Quick Start

Follow this sequence by default:

1. Analyze the Cloudera source: Hive tables, Spark jobs, Impala queries, HDFS layout.
2. Identify business logic vs. platform-specific behavior.
3. Export source data in Parquet format (preferred) or CSV.
4. Provision a target MRS cluster on Huawei Cloud.
5. Create an OBS bucket and upload Parquet data.
6. Create Hive external tables pointing to OBS locations.
7. Migrate Spark SQL / HiveQL jobs and report views.
8. Run parity validation comparing source and MRS metrics.
9. Document gaps: functional, operational, performance.

Read [references/migration-workflow.md](references/migration-workflow.md) for the detailed step-by-step procedure.

## Workflow Decision Tree

Start with the migration shape:

- **Full CDH cluster migration** (HDFS + Hive + Spark + Impala + Kafka + HBase):
  - This skill handles HDFS/Hive/Spark/Impala. For Kafka, use the `huawei-cloud-kafka` skill. For HBase, plan an OpenTSDB or CloudTable migration separately.
  - Read [references/migration-workflow.md](references/migration-workflow.md).

- **Hive warehouse migration only**:
  - Export Hive tables to Parquet, land in OBS, create MRS external tables.
  - Read [references/hive-migration.md](references/hive-migration.md).

- **Spark job migration only**:
  - Rewrite `spark-submit` commands for MRS YARN, adjust dependencies, test on MRS.
  - Read [references/spark-migration.md](references/spark-migration.md).

- **Impala query migration**:
  - Impala SQL -> Hive SQL or Spark SQL on MRS. Handle Impala-specific functions.
  - Read [references/impala-migration.md](references/impala-migration.md).

- **Parity validation**:
  - Compare row counts, aggregates, business metrics between source and MRS.
  - Read [references/result-parity.md](references/result-parity.md).

- **Blocked or failing migration**:
  - Check for path mismatches, Parquet compatibility, authorization, Kerberos, or CDH-specific assumptions.
  - Read [references/common-pitfalls.md](references/common-pitfalls.md).

## Core Rules

- **Preserve business semantics first.** UI parity and runtime behavior parity are not the goal.
- **Default target pattern:**
  `Cloudera HDFS/Hive -> Parquet export -> OBS landing -> MRS Hive external tables -> MRS Spark SQL -> curated results`
- **Prefer Parquet as the interchange format.** Use CSV only for raw/simple inputs or when Parquet is not available.
- **Use Spark SQL for queries on Spark-generated Parquet.** MRS Hive 3.1's Parquet reader does not support dictionary-encoded Parquet files produced by Spark 3.x. Always use `spark-sql --master yarn` instead of `beeline` for querying Spark-generated Parquet tables.
- **Never write AK/SK, passwords, tokens, or project IDs into tracked files.** Use environment variables, `.secrets/` directory, or MRS agency for authorization.
- **If OBS access is blocked**, continue with HDFS or local-node fallback to validate logic, and record the OBS issue as an operational hardening gap.
- **Sanitize all output:** use placeholders such as `<bucket>`, `<mrs-master>`, `<cluster_id>`, `<ak>`, `<sk>`, `<project_id>`, `<region>`.

## Migration Mapping

| Cloudera/CDH Source | Huawei Cloud MRS Target |
| --- | --- |
| HDFS files | OBS objects (`obs://<bucket>/<prefix>/`) |
| Hive managed tables | Hive external tables on OBS or HDFS |
| Hive Metastore | MRS Hive Metastore (managed by MRS) |
| Spark on YARN | Spark on YARN (MRS Spark 3.x) |
| Impala queries | Hive SQL or Spark SQL on MRS |
| Spark-submit jobs | spark-submit on MRS YARN |
| Kerberos + Sentry | Kerberos + Ranger (MRS) |
| Oozie workflows | MRS JobGateway or DolphinScheduler |
| Cloudera Manager | MRS Manager (FusionInsight Manager) |
| HDFS disk-based storage | OBS object storage (pay-per-use) |
| Parquet/ORC/Avro files | Parquet/ORC/Avro files (format preserved) |

## MRS Cluster Sizing Guide

When provisioning MRS, these are the minimum service-enforced constraints (as of MRS 3.5.0-LTS):

| Parameter | Minimum | Notes |
| --- | --- | --- |
| MRS version | 3.5.0-LTS | Prefer LTS versions; some versions are marked test-only and cannot be created |
| Master nodes | 2 | HA requirement; cannot be 1 |
| Core nodes | 3 | Service-enforced minimum for MRS 3.x |
| Node spec | `c6.4xlarge.4.linux.bigdata` | Must use `.linux.bigdata` suffix for MRS node specs |
| System disk | 600 GB SAS | Service-enforced minimum; varies by region |
| Data disk | 600 GB SAS | Service-enforced minimum; varies by region |
| Cluster type | ANALYSIS | For Spark/Hive workloads; use HYBRID for mixed workloads |

**Important:** MRS creation API constraints are region- and version-dependent. Always query available versions and specs for the target region before submitting a create request. The SDK may reject versions marked as test-only.

## OBS Data Landing Pattern

### Directory Layout

```
obs://<bucket>/<project>/
  finance_dw/
    dim_branch/
      part-00000-<uuid>.snappy.parquet
      _SUCCESS
    dim_product/
      ...
    fact_transaction/
      txn_date_key=20250401/
        part-00000-<uuid>.snappy.parquet
      txn_date_key=20250402/
        ...
      _SUCCESS
    fact_daily_balance/
      balance_date_key=20250401/
        ...
    fact_loan_snapshot/
      snapshot_date_key=20250401/
        ...
```

### Upload via obsutil

```bash
# Configure obsutil on MRS Master
obsutil config -i=<ak> -k=<sk> -e=obs.<region>.myhuaweicloud.com

# Create bucket
obsutil mb obs://<bucket> -location=<region>

# Upload table directory (use -f to force, -flat for flat structure)
obsutil cp /local/path/<table> obs://<bucket>/<project>/finance_dw/<table> -flat -r -f -j=4 -p=4
```

### Upload via MRS HDFS (alternative)

If OBS is temporarily unavailable, land data in HDFS first:

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && hdfs dfs -mkdir -p /user/hive/warehouse/finance_dw.db/<table>'
su - omm -c 'source /opt/Bigdata/client/bigdata_env && hdfs dfs -put /local/path/<table>/* /user/hive/warehouse/finance_dw.db/<table>/'
```

## Hive External Table Migration

### DDL Template

```sql
-- Non-partitioned dimension table
CREATE EXTERNAL TABLE IF NOT EXISTS finance_dw.dim_branch (
  branch_id int,
  branch_code string,
  branch_name string,
  province string,
  city string
)
STORED AS PARQUET
LOCATION 'obs://<bucket>/<project>/finance_dw/dim_branch';

-- Partitioned fact table
CREATE EXTERNAL TABLE IF NOT EXISTS finance_dw.fact_transaction (
  transaction_id bigint,
  account_id int,
  customer_id int,
  branch_id int,
  product_id int,
  transaction_ts timestamp,
  txn_type string,
  channel string,
  amount decimal(18,2),
  balance_after decimal(18,2),
  counterparty_region string,
  is_suspicious boolean,
  risk_score decimal(6,2)
)
PARTITIONED BY (txn_date_key int)
STORED AS PARQUET
LOCATION 'obs://<bucket>/<project>/finance_dw/fact_transaction';

-- Recover partitions after creation
MSCK REPAIR TABLE finance_dw.fact_transaction;
```

### Critical: Hive vs. Spark SQL for Parquet

**MRS Hive 3.1's built-in Parquet reader does not support dictionary-encoded Parquet files generated by Spark 3.x.** You will see errors like:

```
UnsupportedOperationException: org.apache.parquet.column.values.dictionary.PlainValuesDictionary$PlainIntegerDictionary
```

**Solution:** Always use Spark SQL for querying Spark-generated Parquet tables:

```bash
# WRONG - will fail on Spark-generated Parquet
beeline -u "jdbc:hive2://<host>:10000" -e "SELECT count(*) FROM finance_dw.fact_transaction;"

# CORRECT - use Spark SQL
spark-sql --master yarn --executor-memory 4g --executor-cores 2 --num-executors 3 -e "SELECT count(*) FROM finance_dw.fact_transaction;"
```

If you need Hive-based access, re-write the Parquet files without dictionary encoding using Spark:

```sql
-- Re-write Parquet without dictionary encoding for Hive compatibility
INSERT OVERWRITE DIRECTORY '/tmp/hive_compatible/fact_transaction'
USING PARQUET
OPTIONS ('parquet.enable.dictionary' = 'false')
SELECT * FROM finance_dw.fact_transaction;
```

## Spark SQL / HiveQL Migration

### beeline Connection on MRS

```bash
# Source the client environment
source /opt/Bigdata/client/bigdata_env

# Connect to HiveServer2 (use the Master node's internal IP, not localhost)
beeline -u "jdbc:hive2://<master_internal_ip>:10000"

# Or use ZooKeeper-based discovery
beeline -u "jdbc:hive2://<zookeeper_host>:2181/default;serviceDiscoveryMode=zooKeeper;zooKeeperNamespace=hiveserver2"
```

### spark-sql on MRS

```bash
source /opt/Bigdata/client/bigdata_env

# Interactive
spark-sql --master yarn --executor-memory 4g --executor-cores 2 --num-executors 3

# Batch from file
spark-sql --master yarn --executor-memory 4g --executor-cores 2 --num-executors 3 -f /path/to/script.sql
```

### Impala to Spark SQL Conversion

| Impala Feature | MRS Spark SQL Equivalent |
| --- | --- |
| `COMPUTE STATS` | `ANALYZE TABLE ... COMPUTE STATISTICS` |
| `SHOW TABLE STATS` | `DESCRIBE EXTENDED ...` |
| `INVALIDATE METADATA` | `MSCK REPAIR TABLE ...` or `REFRESH TABLE ...` |
| `REFRESH <table>` | `REFRESH TABLE <table>` |
| Impala `LIMIT` without `ORDER BY` | Same syntax works in Spark SQL |
| `NDV()` | `APPROX_COUNT_DISTINCT()` |
| `GROUP_CONCAT` | `COLLECT_LIST` + `ARRAY_JOIN` |

## Report View Migration

Migrate Impala or Hive report views to Spark SQL views:

```sql
CREATE DATABASE IF NOT EXISTS reports;

CREATE OR REPLACE VIEW reports.branch_kpi AS
SELECT b.province, b.city, b.branch_code, b.branch_name,
       d.year_num, d.month_num,
       count(*) AS transaction_count,
       round(sum(t.amount), 2) AS transaction_amount,
       count(DISTINCT t.customer_id) AS active_customers,
       round(avg(t.risk_score), 2) AS avg_risk_score,
       sum(CASE WHEN t.is_suspicious THEN 1 ELSE 0 END) AS suspicious_transaction_count
FROM finance_dw.fact_transaction t
JOIN finance_dw.dim_branch b ON b.branch_id = t.branch_id
JOIN finance_dw.dim_date d ON d.date_key = t.txn_date_key
GROUP BY b.province, b.city, b.branch_code, b.branch_name, d.year_num, d.month_num;
```

## Parity Validation

### Minimum Validation Checks

Always compare at least these metrics between source and MRS:

1. **Row counts** for all dimension and fact tables
2. **Distinct business-key counts** (e.g., distinct customer_id, account_id)
3. **Aggregate sums** for key financial fields (amount, balance, principal)
4. **Category-level totals** (by product type, branch, risk level)
5. **Exception counts** (suspicious transactions, overdue loans)
6. **Derived metric parity** (expected credit loss, contribution margin, liquidity gap)

### Validation Query Pattern

Run a single UNION ALL query in Spark SQL and save results to HDFS for clean parsing:

```sql
USE finance_dw;

SELECT 'dim_branch' AS metric, cast(count(*) as string) AS value FROM dim_branch
UNION ALL SELECT 'dim_product', cast(count(*) as string) FROM dim_product
UNION ALL SELECT 'fact_transaction', cast(count(*) as string) FROM fact_transaction
UNION ALL SELECT 'amount_sum', cast(round(sum(amount),2) as string) FROM fact_transaction
UNION ALL SELECT 'suspicious_count', cast(sum(CASE WHEN is_suspicious THEN 1 ELSE 0 END) as string) FROM fact_transaction
UNION ALL SELECT 'ending_balance_sum', cast(round(sum(ending_balance),2) as string) FROM fact_daily_balance
UNION ALL SELECT 'ecl_sum', cast(round(sum(pd_score*lgd*ead),2) as string) FROM fact_loan_snapshot;
```

Save to HDFS for clean retrieval:

```sql
INSERT OVERWRITE DIRECTORY '/tmp/mrs_validation'
USING csv OPTIONS ('delimiter'='\t')
SELECT * FROM validation_results;
```

Read from HDFS:

```bash
hdfs dfs -cat /tmp/mrs_validation/*
```

Read [references/result-parity.md](references/result-parity.md) for the complete validation methodology.

## MRS Cluster Provisioning

### Via Huawei Cloud Python SDK

```python
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkmrs.v1.region.mrs_region import MrsRegion
from huaweicloudsdkmrs.v1.mrs_client import MrsClient
from huaweicloudsdkmrs.v1.model.create_cluster_request import CreateClusterRequest

creds = BasicCredentials(<ak>, <sk>, <project_id>)
client = MrsClient.new_builder() \
    .with_credentials(creds) \
    .with_region(MrsRegion.value_of(<region>)) \
    .build()

# Query available versions and specs first
# Then create cluster with service-validated minimums
```

### EIP Binding for Remote Access

MRS Master nodes are on internal VPC by default. To access remotely:

1. Allocate an EIP using the EIP V3 SDK:

```python
from huaweicloudsdkeip.v3.region.eip_region import EipRegion
from huaweicloudsdkeip.v3.eip_client import EipClient
from huaweicloudsdkeip.v3.model.create_publicip_request import CreatePublicipRequest
from huaweicloudsdkeip.v3.model.create_publicips_request_body import CreatePublicipsRequestBody
from huaweicloudsdkeip.v3.model.create_publicip_option import CreatePublicipOption

body = CreatePublicipOption(type="5_bgp", ip_version=4)
bandwidth = CreatePublicipBandwidthOption(name="mrs-eip-bw", size=5, share_type="PER")
req = CreatePublicipRequest(body=CreatePublicipsRequestBody(publicip=body, bandwidth=bandwidth))
```

2. Find the Master1 ECS port ID:

```python
# List ECS instances, find the MRS Master1 node
# Extract os_ext_ip_sport_id from the address
```

3. Bind EIP to port using V3 API:

```python
from huaweicloudsdkeip.v3.model.update_publicip_request import UpdatePublicipRequest
from huaweicloudsdkeip.v3.model.update_publicips_request_body import UpdatePublicipsRequestBody
from huaweicloudsdkeip.v3.model.update_publicip_option import UpdatePublicipOption

body = UpdatePublicipOption(
    associate_instance_type="PORT",
    associate_instance_id=<port_id>
)
req = UpdatePublicipRequest(publicip_id=<eip_id>, body=UpdatePublicipsRequestBody(publicip=body))
```

4. SSH access:

```bash
ssh -p 22 root@<eip_address>    # standard SSH
ssh -p 9022 root@<eip_address>   # MRS default SSH port
```

### Security Group Rules

MRS creates a dedicated security group. You may need to add ingress rules for SSH access:

- Port 22 (SSH) from your IP or 0.0.0.0/0
- Port 9022 (MRS SSH) from your IP or 0.0.0.0/0

Use the VPC V3 SDK `batch_create_security_group_rules` or the MRS Manager UI.

## MRS Manager Access

- MRS Manager UI: `https://<master_floating_ip>:28860`
- Default admin credentials are set during cluster creation
- The `omm` user owns Hadoop services; always run Hadoop/Hive/Spark commands as `omm`:

```bash
su - omm -c 'source /opt/Bigdata/client/bigdata_env && <command>'
```

## Default Deliverables

When using this skill, produce:

1. **Migration mapping** from Cloudera patterns to MRS patterns
2. **Source export script** (Parquet extraction from HDFS/Hive)
3. **OBS landing layout** (bucket structure and upload commands)
4. **MRS DDL scripts** (external table creation + MSCK REPAIR)
5. **MRS view scripts** (report view migration)
6. **Parity validation results** (metric comparison table)
7. **Gap list:**
   - Functional gaps (UDFs, Impala-specific SQL, Hive ACID)
   - Operational gaps (Kerberos, Ranger, OBS agency, EIP)
   - Performance caveats (Parquet encoding, partition strategy)

## Script Use

Use the bundled templates when you need a starting point:

- `scripts/source_simulation.sh` - local Spark Standalone cluster for source simulation
- `scripts/mrs_provision.py` - MRS cluster creation with version/spec discovery
- `scripts/obs_upload.sh` - Parquet upload to OBS via obsutil
- `scripts/validate_parity.py` - source vs. MRS metric comparison

## Reference Use

- Read [references/migration-workflow.md](references/migration-workflow.md) for the complete end-to-end workflow.
- Read [references/hive-migration.md](references/hive-migration.md) for Hive table and Metastore migration details.
- Read [references/spark-migration.md](references/spark-migration.md) for Spark job migration details.
- Read [references/impala-migration.md](references/impala-migration.md) for Impala query conversion.
- Read [references/result-parity.md](references/result-parity.md) for validation methodology.
- Read [references/common-pitfalls.md](references/common-pitfalls.md) for troubleshooting.
- Read [references/mrs-operations.md](references/mrs-operations.md) for MRS cluster operations and access patterns.
