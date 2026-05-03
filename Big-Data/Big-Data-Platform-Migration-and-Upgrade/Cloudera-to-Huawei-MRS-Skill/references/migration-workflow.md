# Migration Workflow

## End-to-End Sequence

### Phase 1: Source Analysis

1. **Inventory the Cloudera source:**
   - List Hive databases and tables (`SHOW DATABASES; SHOW TABLES;`)
   - Extract DDL for each table (`SHOW CREATE TABLE <table>;`)
   - Identify partitioned tables and partition keys
   - Catalog Spark jobs (spark-submit scripts, JARs, arguments)
   - Catalog Impala queries (saved queries, report views)
   - Check for UDFs, Hive ACID tables, HBase integration, Kafka connectors

2. **Identify migration scope:**
   - Tables to migrate (dimensions, facts, staging)
   - Jobs to migrate (ETL, reporting, ad-hoc)
   - Views to migrate (report views, analytical views)
   - Data volume per table (row counts, file sizes)

3. **Separate business logic from platform behavior:**
   - Pure SQL logic -> direct migration
   - Cloudera-specific features -> rewrite or flag as gap
   - Kerberos/Sentry policies -> plan Ranger migration

### Phase 2: Source Data Export

1. **Choose export format:**
   - Parquet (preferred): preserves schema, compression, partitioning
   - CSV: only for simple raw data or when Parquet is unavailable
   - ORC: if source already uses ORC and target will too

2. **Export from Cloudera HDFS/Hive:**

```bash
# Using Spark to export Hive tables as Parquet
spark-submit --master yarn \
  --class com.example.HiveTableExporter \
  --output-format parquet \
  --table finance_dw.fact_transaction \
  --output-path /export/finance_dw/fact_transaction

# Or using hdfs dfs -get for existing Parquet data
hdfs dfs -get /user/hive/warehouse/finance_dw.db/fact_transaction /local/export/
```

3. **For local simulation (no real Cloudera):**
   - Use Spark Standalone (1 master + N workers) with Bitnami/legacy images
   - Generate synthetic data matching the source schema
   - Write Parquet files matching the source layout

### Phase 3: MRS Cluster Provisioning

1. **Query available MRS versions and specs:**

```python
from huaweicloudsdkmrs.v1.mrs_client import MrsClient
# Use list_versions_metadata or show_mrs_version_metadata
# to find available versions in the target region
```

2. **Create MRS cluster:**
   - Version: prefer LTS (e.g., MRS 3.5.0-LTS)
   - Type: ANALYSIS for Spark/Hive workloads
   - Components: Hadoop, Spark, Hive, Tez, ZooKeeper (minimum for analytics)
   - Nodes: 2 Master + 3 Core (service-enforced minimum)
   - Spec: `c6.4xlarge.4.linux.bigdata` or larger
   - Disk: 600 GB SAS minimum (region-dependent)
   - VPC: use existing or create default
   - Billing: pay-per-use for demo; reserved for production

3. **Wait for cluster to reach `running` state:**
   - Poll `list_clusters` API
   - Typical startup time: 10-20 minutes

4. **Bind EIP to Master1 for remote access** (see SKILL.md for details)

5. **Configure security group** for SSH (port 22 and/or 9022)

### Phase 4: OBS Data Landing

1. **Create OBS bucket:**

```bash
obsutil config -i=<ak> -k=<sk> -e=obs.<region>.myhuaweicloud.com
obsutil mb obs://<bucket> -location=<region>
```

2. **Upload Parquet data:**

```bash
# For each table
obsutil cp /local/path/<table> obs://<bucket>/<project>/finance_dw/<table> -flat -r -f -j=4 -p=4
```

3. **Verify upload:**

```bash
obsutil ls obs://<bucket>/<project>/finance_dw/ -limit=100 -s
```

### Phase 5: MRS Table Migration

1. **Create Hive database and external tables:**

```sql
CREATE DATABASE IF NOT EXISTS finance_dw;

CREATE EXTERNAL TABLE IF NOT EXISTS finance_dw.dim_branch (
  branch_id int,
  branch_code string,
  branch_name string,
  province string,
  city string
)
STORED AS PARQUET
LOCATION 'obs://<bucket>/<project>/finance_dw/dim_branch';
```

2. **Recover partitions for partitioned tables:**

```sql
MSCK REPAIR TABLE finance_dw.fact_transaction;
MSCK REPAIR TABLE finance_dw.fact_daily_balance;
MSCK REPAIR TABLE finance_dw.fact_loan_snapshot;
```

3. **Verify table creation:**

```bash
# Use beeline for DDL verification
beeline -u "jdbc:hive2://<master_ip>:10000" -e "USE finance_dw; SHOW TABLES;"

# Use spark-sql for data queries (Hive cannot read Spark-generated Parquet)
spark-sql --master yarn -e "SELECT count(*) FROM finance_dw.fact_transaction;"
```

### Phase 6: Job and View Migration

1. **Migrate Spark jobs:**
   - Update `--master` to `yarn`
   - Update HDFS paths to OBS paths
   - Update dependency JARs for MRS Spark version
   - Test with `spark-submit`

2. **Migrate report views:**
   - Convert Impala-specific syntax to Hive/Spark SQL
   - Create views in the `reports` database
   - Test with Spark SQL

### Phase 7: Parity Validation

1. **Run validation queries on both source and MRS**
2. **Compare results** (see references/result-parity.md)
3. **Document any discrepancies**

### Phase 8: Operational Hardening

1. Configure Ranger policies (replacing Sentry)
2. Set up OBS agency for MRS-to-OBS access
3. Configure Kerberos if required
4. Set up monitoring and alerting
5. Document runbooks for common operations

## Timing Estimates

| Phase | Typical Duration |
| --- | --- |
| Source analysis | 1-4 hours |
| Data export | 1-8 hours (depends on volume) |
| MRS provisioning | 15-30 minutes |
| OBS upload | 30 min - 4 hours (depends on volume and bandwidth) |
| Table creation | 15-30 minutes |
| Job migration | 2-8 hours |
| Parity validation | 1-2 hours |
| Operational hardening | 4-16 hours |
