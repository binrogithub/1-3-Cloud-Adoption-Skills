# Common Pitfalls

## OBS-Related Issues

### 1. OBS Access Denied

**Symptom**: MRS Spark or DWS cannot read/write to OBS bucket.

**Root Causes**:
- IAM agency not configured for MRS/DWS to access OBS
- Bucket policy does not grant cross-service access
- Temporary credentials expired

**Resolution**:
- Configure IAM agency for MRS cluster with OBS access
- Use permanent AK/SK for DWS foreign server (not temporary credentials)
- Verify bucket policy allows read/write from MRS and DWS service accounts

**Fallback**: Use HDFS as temporary storage to validate logic, then resolve OBS access separately.

### 2. OBS Path Format

**Symptom**: Hive external table or DWS foreign table returns 0 rows.

**Root Causes**:
- OBS path missing trailing slash for directory-based tables
- Wrong bucket name in LOCATION clause
- CSV delimiter mismatch

**Resolution**:
- Ensure OBS paths end with `/` for directory-based external tables
- Verify bucket name matches actual OBS bucket
- Match CSV delimiter with FIELDS TERMINATED BY clause

### 3. OBS File Encoding

**Symptom**: Special characters (RFC, CURP with ñ/á) corrupted in data.

**Root Causes**:
- File uploaded without UTF-8 encoding
- BOM (Byte Order Mark) in CSV file

**Resolution**:
- Upload files with explicit UTF-8 encoding
- Remove BOM from CSV files before upload
- Specify `encoding 'utf8'` in DWS foreign table OPTIONS

---

## MRS-Related Issues

### 4. Spark Out of Memory

**Symptom**: Spark job fails with OOM error during risk analysis.

**Root Causes**:
- Default executor memory too low for large transaction dataset
- Kryo serializer buffer too small
- Too many shuffle partitions

**Resolution**:
```properties
spark.executor.memory         8g
spark.driver.memory           4g
spark.kryoserializer.buffer.max 512m
spark.sql.shuffle.partitions  200
```

### 5. Hive Metastore Connection

**Symptom**: Spark SQL fails to find Hive tables.

**Root Causes**:
- `enableHiveSupport()` not called in SparkSession
- Metastore database not accessible
- Warehouse directory not configured

**Resolution**:
- Ensure `enableHiveSupport()` is called when creating SparkSession
- Configure `spark.sql.warehouse.dir` to point to OBS or HDFS warehouse
- Verify MySQL/metastore database connectivity

### 6. K-Means Clustering Failure

**Symptom**: K-Means model fails to converge or produces single-cluster output.

**Root Causes**:
- Features contain NULL values (stddev can be NULL)
- Features not standardized before clustering
- k value too large for dataset size

**Resolution**:
- Fill NULL values with 0 using `na.fill(0)` before VectorAssembler
- Always apply StandardScaler before K-Means
- Reduce k if customer count is small (< 5k)

---

## DWS-Related Issues

### 7. DWS Cluster Creation Failure

**Symptom**: `DWS.0001 - The resource does not exist or is illegal`

**Root Causes**:
- Invalid flavor name (e.g., `dws.m1.xlarge` instead of `dwsx2.xlarge`)
- Missing `datastore_version` parameter
- Missing `volume` configuration

**Resolution**:
- Use `ListNodeTypesRequest` to discover valid flavor names
- Include `datastore_version` (e.g., `"9.1.0.223"`)
- Add `Volume(volume="SSD", capacity=100)` to cluster request

### 8. DWS Foreign Table Import Slow

**Symptom**: INSERT from OBS foreign table takes very long time.

**Root Causes**:
- OBS bucket in different region than DWS cluster
- Large CSV files without compression
- No OBS import optimization settings

**Resolution**:
- Place OBS bucket in same region as DWS cluster
- Use Parquet format for curated data (smaller, faster)
- Set `obs_import_mode = 'bulk'` for large imports

### 9. DWS Distribution Key Mismatch

**Symptom**: Slow query performance on fact-dimension joins.

**Root Causes**:
- Fact table distributed on different key than join column
- Small dimension tables distributed instead of replicated

**Resolution**:
- Distribute fact tables on the most common join key
- Replicate small dimension tables (< 1M rows)
- Use `DISTRIBUTE BY REPLICATION` for date and lookup tables

### 10. DWS Column Store Compression

**Symptom**: INSERT fails with "invalid compression" error.

**Root Causes**:
- Using `COMPRESSION = HIGH` with string-heavy tables
- Compression level incompatible with data types

**Resolution**:
- Use `COMPRESSION = MIDDLE` as default (good balance)
- Use `COMPRESSION = LOW` for string-heavy dimension tables
- Use `COMPRESSION = HIGH` only for numeric-heavy fact tables

---

## Data Pipeline Issues

### 11. MRS-DWS Data Mismatch

**Symptom**: Risk scores differ between MRS Spark output and DWS report.

**Root Causes**:
- Different NULL handling in Spark vs DWS (NULL vs 0)
- Floating-point precision differences
- Data loaded at different times (not synchronized)

**Resolution**:
- Standardize NULL handling: fill NULLs with 0 in both systems
- Use NUMERIC(18,2) in DWS to match Spark Double precision
- Run pipeline validation after each ETL cycle

### 12. Time Zone Mismatch

**Symptom**: Transaction timestamps shifted by several hours between MRS and DWS.

**Root Causes**:
- MRS using UTC, DWS using local time (CST/CDT for Mexico)
- TIMESTAMP without time zone in DWS

**Resolution**:
- Use `TIMESTAMP WITH TIME ZONE` in DWS for all time columns
- Standardize on UTC in MRS Spark, convert to Mexico time in DWS
- Or standardize both systems on the same time zone

### 13. Schema Evolution

**Symptom**: New column added to source data, DWS ETL fails.

**Root Causes**:
- ODS table schema does not match new source schema
- DW transformation references missing columns

**Resolution**:
- Add new columns to ODS table first (with DEFAULT NULL)
- Update DW transformation to handle new columns
- Use `IF NULL` guards in transformation SQL

---

## Regulatory Compliance Issues

### 14. False Positive Structuring Alerts

**Symptom**: Too many structuring alerts for legitimate business transactions.

**Root Causes**:
- Threshold too low (10,000-15,000 MXN catches normal payments)
- No business context considered (payroll, supplier payments)
- No time window filtering

**Resolution**:
- Add business context: exclude payroll and known supplier payments
- Increase minimum transaction count threshold (≥ 5 per day)
- Add time window: only flag if transactions within 4-hour window

### 15. KYC Level Migration

**Symptom**: Customer KYC level changes, but historical transactions not re-evaluated.

**Root Causes**:
- KYC level stored as current state, not historical
- No SCD Type 2 on customer dimension

**Resolution**:
- Implement SCD Type 2 on `dim_customer` with `effective_date` and `expiry_date`
- Re-evaluate compliance when KYC level changes
- Keep historical KYC level in fact table for audit trail
