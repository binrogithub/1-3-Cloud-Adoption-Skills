---
name: mrs-dws-finance-skill
description: Use this skill when setting up a financial risk control pipeline on Huawei Cloud. It helps configure OBS for raw and result data storage, MRS for Spark-based risk analysis and anomaly detection, and DWS for data warehousing and regulatory reporting. The skill covers risk scoring, AML/KYC compliance, cross-border monitoring, structuring detection, and automated report generation without relying on environment-specific details.
---

# MRS-DWS-Finance-Skill

## Overview

Use this skill for financial risk control scenarios on Huawei Cloud where `OBS` is the object storage layer, `MRS` is the big-data compute engine for Spark analysis, and `DWS` is the data warehouse for dimensional modeling and reporting. It is optimized for risk scoring, anomaly detection, regulatory compliance (CNBV, Banxico, AML/KYC), and automated report generation.

## Quick Start

Follow this sequence by default:

1. **Prepare OBS buckets** for raw data, analysis results, and curated datasets.
2. **Provision MRS cluster** with Spark, Hive, and HBase components.
3. **Provision DWS cluster** with column-store tables and hash distribution.
4. **Load raw data** into OBS and register Hive external tables on MRS.
5. **Run Spark risk analysis** to compute risk scores, detect anomalies, and cluster customers.
6. **Export analysis results** from MRS to OBS in Parquet format.
7. **Build DWS data warehouse** with ODS → DW → DM → RPT layered architecture.
8. **Load and transform data** from OBS into DWS using foreign tables and COPY.
9. **Generate regulatory reports** for CNBV, Banxico, and AML/KYC compliance.
10. **Validate pipeline parity** by comparing MRS and DWS metric outputs.

## Workflow Decision Tree

Start with the deployment shape:

- **Greenfield deployment** (no existing clusters):
  - Run `scripts/setup_obs_buckets.sh` to create OBS buckets.
  - Run `scripts/setup_mrs_cluster.py` to provision MRS.
  - Run `scripts/setup_dws_cluster.py` to provision DWS.
  - Read [references/architecture-patterns.md](references/architecture-patterns.md).

- **Data pipeline setup** (clusters exist, need pipeline):
  - Run `scripts/load_raw_data_to_obs.sh` to upload data.
  - Run `scripts/register_hive_tables.sql` to create MRS tables.
  - Run `scripts/spark_risk_analysis.py` to execute risk analysis.
  - Run `scripts/export_results_to_obs.sh` to save results.
  - Read [references/architecture-patterns.md](references/architecture-patterns.md).

- **DWS warehouse setup** (MRS analysis complete, need warehouse):
  - Run `scripts/dws_create_tables.sql` to create DWS schema.
  - Run `scripts/dws_etl_load.sql` to load and transform data.
  - Run `scripts/dws_generate_reports.sql` to generate reports.
  - Read [references/regulatory-compliance.md](references/regulatory-compliance.md).

- **Regulatory compliance check**:
  - Run `scripts/check_cnbv_compliance.sql` for CNBV limits.
  - Run `scripts/check_aml_kyc_compliance.sql` for AML/KYC levels.
  - Run `scripts/check_structuring_detection.sql` for smurfing patterns.
  - Read [references/regulatory-compliance.md](references/regulatory-compliance.md).

- **Pipeline validation or failure**:
  - Run `scripts/validate_pipeline_parity.py` to compare MRS vs DWS outputs.
  - Check for storage-path, authorization, or schema mismatch issues.
  - Read [references/common-pitfalls.md](references/common-pitfalls.md).

## Core Rules

- Preserve business semantics first. Platform-specific UI parity is not the goal.
- Default data flow pattern:
  - `Raw Data → OBS (raw/) → MRS Spark → OBS (results/) → DWS (ODS → DW → DM → RPT)`
- Default storage format:
  - Raw data: `CSV` in OBS
  - Analysis results: `Parquet` in OBS
  - DWS tables: `Column-store` with `MIDDLE` compression
- DWS table distribution:
  - Fact tables: `DISTRIBUTE BY HASH(transaction_id)` or `DISTRIBUTE BY HASH(customer_key)`
  - Dimension tables: Replicated (no distribution clause)
- If `OBS` access is blocked during setup or validation, continue with `HDFS` or local-node fallback to validate logic.
- Treat `OBS agency` or temporary-credential issues as operational blockers, not logic blockers.
- Keep all scripts and examples sanitized:
  - use placeholders such as `<bucket>`, `<region>`, `<mrs_master>`, `<dws_endpoint>`, `<dws_port>`, `<db_user>`, `<db_password>`
  - never copy hostnames, usernames, passwords, tokens, access keys, project IDs, or customer names

## Financial Risk Control Rules

### Anomaly Detection Rules

| Rule | Threshold | Action |
|------|-----------|--------|
| Large Amount | > 50,000 MXN (individual) / > 500,000 MXN (business) | Alert + SAR filing |
| Frequent Transactions | > 20 per hour per account | Temporary hold |
| Unusual Location | High-risk cities (CNBV flagged) | Secondary verification |
| Unusual Time | 2:00 AM - 5:00 AM large transactions | Manual review |
| Round Amount | Exact round numbers (50k, 100k, 150k MXN) | Flag for review |
| Cross-Border | US-Mexico border city transactions | Enhanced monitoring |
| Structuring | Multiple transactions below reporting threshold | SAR filing |
| Suspicious Pattern | Transactions just below 15,000 MXN threshold | Pattern analysis |

### Regulatory Compliance (Mexico)

| Regulation | Key Requirement | Implementation |
|------------|----------------|----------------|
| CNBV Circular 15/2020 | Daily/monthly transaction limits | DWS constraint checks |
| Banxico SPEI | Instantáneo ≤ 8,000 MXN, Regular ≤ 500,000 MXN | Payment routing logic |
| Ley Fintech (AML/KYC) | Level 1 ≤ 7,500, Level 2 ≤ 30,000, Level 3 unlimited | KYC level enforcement |
| FATF | Suspicious activity reporting | Automated SAR generation |

## Default Deliverables

When using this skill, prefer producing:

- an OBS bucket layout for raw data, analysis results, and curated datasets
- an MRS cluster configuration with Spark, Hive, and HBase
- a DWS cluster configuration with layered schema (ODS/DW/DM/RPT)
- a Spark risk analysis job template
- a DWS ETL and reporting script set
- a regulatory compliance check script set
- a pipeline parity validation report
- a short gap list:
  - functional gaps (missing risk rules, incomplete coverage)
  - operational gaps (OBS access, cluster sizing, backup)
  - regulatory gaps (unmet CNBV/Banxico/AML requirements)

## Script Use

Use the bundled templates when you need a starting point:

- `scripts/setup_obs_buckets.sh`
  - create OBS buckets for raw, results, and curated data
- `scripts/setup_mrs_cluster.py`
  - provision MRS cluster with Spark, Hive, HBase
- `scripts/setup_dws_cluster.py`
  - provision DWS cluster with minimal flavor
- `scripts/load_raw_data_to_obs.sh`
  - upload CSV data files to OBS
- `scripts/register_hive_tables.sql`
  - create Hive external tables over OBS data
- `scripts/spark_risk_analysis.py`
  - run Spark risk scoring, anomaly detection, and customer clustering
- `scripts/export_results_to_obs.sh`
  - save MRS analysis results to OBS in Parquet format
- `scripts/dws_create_tables.sql`
  - create DWS database, schemas, and all tables (ODS/DW/DM/RPT)
- `scripts/dws_etl_load.sql`
  - load data from OBS to ODS, transform to DW, aggregate to DM
- `scripts/dws_generate_reports.sql`
  - generate risk overview, customer risk, city risk, and compliance reports
- `scripts/check_cnbv_compliance.sql`
  - validate CNBV transaction limit compliance
- `scripts/check_aml_kyc_compliance.sql`
  - validate AML/KYC level compliance
- `scripts/check_structuring_detection.sql`
  - detect structuring (smurfing) patterns
- `scripts/validate_pipeline_parity.py`
  - compare MRS and DWS metric outputs for consistency

## Example Use

Use the bundled examples for quick-start deployment with proven patterns:

- `examples/example_discover_resources.py`
  - discover VPC, Subnet, Security Group, DWS node types, and AZs
- `examples/example_create_dws_cluster.py`
  - create a minimal DWS cluster with all required V2 API parameters
- `examples/example_generate_mexico_data.py`
  - generate Mexico-specific test data with regulatory-compliant anomalies
- `examples/example_mrs_data_import.sh`
  - import data to MRS HDFS, register Hive tables, and run Spark analysis
- `

- Read [references/architecture-patterns.md](references/architecture-patterns.md) for end-to-end pipeline design and layering strategy.
- Read [references/regulatory-compliance.md](references/regulatory-compliance.md) for CNBV, Banxico, and AML/KYC compliance rules and implementation.
- Read [references/common-pitfalls.md](references/common-pitfalls.md) when a setup or pipeline is blocked or producing mismatched results.
