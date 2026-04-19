#!/bin/bash
# ============================================================
# example_full_pipeline.sh
# End-to-end pipeline: OBS → MRS → OBS → DWS
# This script orchestrates the complete financial risk control
# pipeline from data upload through report generation.
#
# Prerequisites:
#   - MRS cluster running with Spark, Hive, HBase
#   - DWS cluster running and accessible
#   - OBS buckets created
#   - Data files generated (example_generate_mexico_data.py)
#
# Usage:
#   chmod +x example_full_pipeline.sh
#   ./example_full_pipeline.sh
# ============================================================

set -euo pipefail

# --- Configuration (replace placeholders) ---
RAW_BUCKET="<raw_bucket>"
RESULTS_BUCKET="<results_bucket>"
CURATED_BUCKET="<curated_bucket>"
MRS_MASTER="<mrs_master_ip>"
DWS_ENDPOINT="<dws_endpoint>"
DWS_PORT=8000
DWS_DB="financedb"
DWS_USER="<db_user>"
DWS_PASSWORD="<db_password>"
DATA_DIR="mexico_data"

echo "============================================"
echo "Full Pipeline: OBS → MRS → OBS → DWS"
echo "============================================"

# ============================================================
# Phase 1: Data Ingestion (Local → OBS)
# ============================================================
echo ""
echo "=== Phase 1: Data Ingestion ==="
echo "Uploading data to OBS..."

# Upload to OBS raw bucket
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "customers/customers.csv" --file "${DATA_DIR}/customers.csv"
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "accounts/accounts.csv" --file "${DATA_DIR}/accounts.csv"
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "transactions/transactions.csv" --file "${DATA_DIR}/transactions.csv"

echo "Phase 1 complete: Data uploaded to OBS"

# ============================================================
# Phase 2: MRS Analysis (OBS → Spark → OBS)
# ============================================================
echo ""
echo "=== Phase 2: MRS Spark Analysis ==="

# Step 2a: Register Hive tables over OBS data
echo "2a. Registering Hive tables..."
ssh root@${MRS_MASTER} "hive -f /opt/scripts/register_hive_tables.sql"

# Step 2b: Run Spark risk analysis
echo "2b. Running Spark risk analysis..."
ssh root@${MRS_MASTER} "spark-submit \
    --master yarn \
    --deploy-mode cluster \
    --executor-memory 8g \
    --executor-cores 4 \
    --driver-memory 4g \
    --conf spark.hadoop.fs.obs.impl=com.huawei.cloud.obs.OBSFileSystem \
    /opt/scripts/spark_risk_analysis.py"

# Step 2c: Export results to OBS
echo "2c. Exporting results to OBS..."
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${RESULTS_BUCKET}/risk_scores/'
    STORED AS PARQUET
    SELECT * FROM openbank_risk.risk_scores;
\""

echo "Phase 2 complete: MRS analysis results in OBS"

# ============================================================
# Phase 3: DWS Data Warehouse (OBS → DWS)
# ============================================================
echo ""
echo "=== Phase 3: DWS Data Warehouse ==="

# Step 3a: Create DWS tables
echo "3a. Creating DWS tables..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/dws_create_tables.sql

# Step 3b: Load and transform data
echo "3b. Loading and transforming data (ODS → DW → DM)..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/dws_etl_load.sql

echo "Phase 3 complete: DWS data warehouse loaded"

# ============================================================
# Phase 4: Reporting and Compliance
# ============================================================
echo ""
echo "=== Phase 4: Reporting and Compliance ==="

# Step 4a: Generate risk reports
echo "4a. Generating risk reports..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/dws_generate_reports.sql

# Step 4b: Check CNBV compliance
echo "4b. Checking CNBV compliance..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/check_cnbv_compliance.sql

# Step 4c: Check AML/KYC compliance
echo "4c. Checking AML/KYC compliance..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/check_aml_kyc_compliance.sql

# Step 4d: Detect structuring patterns
echo "4d. Detecting structuring patterns..."
gsql -h ${DWS_ENDPOINT} -p ${DWS_PORT} -U ${DWS_USER} -W ${DWS_PASSWORD} \
    -d ${DWS_DB} -f scripts/check_structuring_detection.sql

echo "Phase 4 complete: Reports and compliance checks done"

# ============================================================
# Phase 5: Pipeline Validation
# ============================================================
echo ""
echo "=== Phase 5: Pipeline Validation ==="

python3 scripts/validate_pipeline_parity.py

echo ""
echo "============================================"
echo "Full Pipeline Complete!"
echo "============================================"
echo "Data flow: Local → OBS → MRS → OBS → DWS"
echo "Reports available in DWS rpt schema"
