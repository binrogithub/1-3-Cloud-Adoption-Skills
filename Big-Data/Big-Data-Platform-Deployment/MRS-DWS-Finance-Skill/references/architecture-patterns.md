# Architecture Patterns

## End-to-End Pipeline Design

### Data Flow Overview

```
Raw Data → OBS (raw/) → MRS Spark → OBS (results/) → DWS (ODS → DW → DM → RPT)
```

### Layer Descriptions

| Layer | Purpose | Storage | Format | Retention |
|-------|---------|---------|--------|-----------|
| **OBS Raw** | Source data landing zone | OBS | CSV | 90 days |
| **MRS Spark** | Risk analysis, anomaly detection, clustering | HDFS/OBS | Parquet | 30 days |
| **OBS Results** | Analysis output staging | OBS | Parquet | 90 days |
| **DWS ODS** | Operational Data Store (1:1 with source) | DWS Column | Row | 1 year |
| **DWS DW** | Data Warehouse (cleaned, conformed) | DWS Column | Column | 2 years |
| **DWS DM** | Data Mart (aggregated by subject) | DWS Column | Column | 3 years |
| **DWS RPT** | Report (final output for dashboards) | DWS Column | Column | 5 years |

---

## OBS Bucket Layout

```
openbank-raw-<id>/
├── customers/          # Customer master data (CSV)
├── accounts/           # Account master data (CSV)
└── transactions/       # Transaction data (CSV)

openbank-results-<id>/
├── risk_scores/        # Customer risk scores (Parquet)
├── customer_clusters/  # K-Means cluster assignments (Parquet)
├── high_risk_customers/ # High-risk customer list (Parquet)
├── anomaly_transactions/ # Flagged transactions (Parquet)
└── daily_risk_stats/   # Daily risk statistics (Parquet)

openbank-curated-<id>/
├── dim/                # Dimension data for DWS
│   ├── dim_customer/
│   └── dim_account/
├── fact/               # Fact data for DWS
│   └── fact_transaction/
└── agg/                # Pre-aggregated data for DWS
```

---

## MRS Cluster Architecture

### Component Selection

| Component | Purpose | Version |
|-----------|---------|---------|
| **Spark** | Risk analysis, anomaly detection, ML | 3.x (MRS 3.1.5) |
| **Hive** | SQL interface, external tables over OBS | 3.x |
| **HBase** | Real-time risk score lookups | 2.x |
| **ZooKeeper** | Coordination service | 3.x |

### Node Sizing

| Node Type | Count | Flavor | Storage | Purpose |
|-----------|-------|--------|---------|---------|
| Master | 3 | c6.4xlarge.4 | 200GB SSD | HA, ResourceManager |
| Core | 3+ | c6.4xlarge.4 | 200GB SSD | DataNode, Spark Executor |

### Spark Configuration

```properties
# Memory configuration
spark.executor.memory         8g
spark.executor.cores          4
spark.driver.memory           4g

# OBS integration
spark.hadoop.fs.obs.impl     com.huawei.cloud.obs.OBSFileSystem
spark.hadoop.fs.obs.endpoint obs.<region>.myhuaweicloud.com

# Serialization
spark.serializer             org.apache.spark.serializer.KryoSerializer
spark.kryoserializer.buffer.max 512m
```

---

## DWS Cluster Architecture

### Schema Design

```
financedb/
├── ods/          # Operational Data Store
│   ├── ods_transaction
│   ├── ods_customer
│   └── ods_account
├── dw/           # Data Warehouse
│   ├── dim_customer     (SCD Type 2)
│   ├── dim_account      (SCD Type 2)
│   ├── dim_date
│   ├── dim_city
│   ├── dim_payment_method
│   └── fact_transaction
├── dm/           # Data Mart
│   ├── dm_customer_risk
│   ├── dm_city_risk
│   ├── dm_daily_transaction
│   └── dm_payment_method_risk
└── rpt/          # Report
    ├── risk_overview
    ├── customer_risk_report
    └── compliance_report
```

### Distribution Strategy

| Table Type | Distribution | Rationale |
|------------|-------------|-----------|
| Fact tables | `DISTRIBUTE BY HASH(transaction_key)` | Even data distribution |
| Large dimension | `DISTRIBUTE BY HASH(customer_key)` | Co-locate with facts |
| Small dimension | `DISTRIBUTE BY REPLICATION` | Broadcast join optimization |
| Report tables | `DISTRIBUTE BY REPLICATION` | Small result sets |

### Compression and Storage

| Setting | Value | Rationale |
|---------|-------|-----------|
| Orientation | COLUMN | Analytical query optimization |
| Compression | MIDDLE | Balance between speed and size |
| Partition | By date on fact tables | Prune irrelevant data |

---

## Data Pipeline Sequence

### Phase 1: Data Ingestion

```
1. Source systems generate CSV data
2. Upload to OBS raw bucket (load_raw_data_to_obs.sh)
3. Register Hive external tables (register_hive_tables.sql)
```

### Phase 2: MRS Analysis

```
4. Run Spark risk analysis (spark_risk_analysis.py)
   - Feature engineering (time, customer stats)
   - Rule-based anomaly detection
   - K-Means customer clustering
   - Risk score calculation
   - Regulatory compliance checks
5. Export results to OBS (export_results_to_obs.sh)
```

### Phase 3: DWS Warehouse

```
6. Create DWS schema (dws_create_tables.sql)
7. Load ODS from OBS via foreign tables (dws_etl_load.sql)
8. Transform ODS → DW (dimension and fact loading)
9. Aggregate DW → DM (data mart creation)
10. Generate DM → RPT (report tables)
```

### Phase 4: Reporting and Compliance

```
11. Generate risk reports (dws_generate_reports.sql)
12. Check CNBV compliance (check_cnbv_compliance.sql)
13. Check AML/KYC compliance (check_aml_kyc_compliance.sql)
14. Detect structuring patterns (check_structuring_detection.sql)
15. Validate pipeline parity (validate_pipeline_parity.py)
```

---

## Scheduling

| Job | Schedule | Engine | Dependency |
|-----|----------|--------|------------|
| Data Upload | Every 15 min | OBS SDK | Source system |
| Spark Risk Analysis | Hourly | MRS Spark | Data Upload |
| DWS ETL Load | Hourly +5 min | DWS gsql | Spark Analysis |
| Compliance Checks | Daily 00:00 | DWS gsql | DWS ETL |
| Report Generation | Daily 01:00 | DWS gsql | Compliance Checks |
| Pipeline Validation | Daily 02:00 | Python | Report Generation |
