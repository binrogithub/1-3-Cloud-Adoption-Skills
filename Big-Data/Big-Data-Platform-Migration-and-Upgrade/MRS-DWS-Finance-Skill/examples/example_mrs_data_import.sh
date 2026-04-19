#!/bin/bash
# ============================================================
# example_mrs_data_import.sh
# Import data into MRS HDFS and run Hive table registration.
# Based on proven deployment workflow from /mnt/MRS.
#
# Usage:
#   chmod +x example_mrs_data_import.sh
#   ./example_mrs_data_import.sh
# ============================================================

set -euo pipefail

# --- Configuration (replace placeholders) ---
MRS_MASTER="<mrs_master_ip>"
HDFS_ROOT="/user/openbank"
DATA_DIR="mexico_data"       # Local directory with CSV files

echo "============================================"
echo "MRS Data Import and Hive Setup"
echo "============================================"

# ============================================================
# 1. Validate data files
# ============================================================
echo ""
echo "1. Validating data files..."

for file in customers.csv accounts.csv transactions.csv; do
    if [ ! -f "${DATA_DIR}/${file}" ]; then
        echo "ERROR: Missing ${DATA_DIR}/${file}"
        exit 1
    fi
    lines=$(wc -l < "${DATA_DIR}/${file}")
    echo "   ${file}: ${lines} lines"
done

echo "Data files validated"

# ============================================================
# 2. Create HDFS directories
# ============================================================
echo ""
echo "2. Creating HDFS directories..."

ssh root@${MRS_MASTER} "
    hdfs dfs -mkdir -p ${HDFS_ROOT}/customers
    hdfs dfs -mkdir -p ${HDFS_ROOT}/accounts
    hdfs dfs -mkdir -p ${HDFS_ROOT}/transactions
    hdfs dfs -mkdir -p ${HDFS_ROOT}/results
"

echo "HDFS directories created"

# ============================================================
# 3. Upload data to HDFS
# ============================================================
echo ""
echo "3. Uploading data to HDFS..."

# Copy data files to MRS master first
scp ${DATA_DIR}/customers.csv root@${MRS_MASTER}:/tmp/customers.csv
scp ${DATA_DIR}/accounts.csv root@${MRS_MASTER}:/tmp/accounts.csv
scp ${DATA_DIR}/transactions.csv root@${MRS_MASTER}:/tmp/transactions.csv

# Upload from MRS master to HDFS
ssh root@${MRS_MASTER} "
    hdfs dfs -put -f /tmp/customers.csv ${HDFS_ROOT}/customers/
    hdfs dfs -put -f /tmp/accounts.csv ${HDFS_ROOT}/accounts/
    hdfs dfs -put -f /tmp/transactions.csv ${HDFS_ROOT}/transactions/
"

echo "Data uploaded to HDFS"

# ============================================================
# 4. Verify upload
# ============================================================
echo ""
echo "4. Verifying upload..."

ssh root@${MRS_MASTER} "
    echo 'Customers:' && hdfs dfs -cat ${HDFS_ROOT}/customers/customers.csv | head -3
    echo 'Accounts:' && hdfs dfs -cat ${HDFS_ROOT}/accounts/accounts.csv | head -3
    echo 'Transactions:' && hdfs dfs -cat ${HDFS_ROOT}/transactions/transactions.csv | head -3
"

# ============================================================
# 5. Register Hive tables
# ============================================================
echo ""
echo "5. Registering Hive external tables..."

ssh root@${MRS_MASTER} "hive -f /opt/scripts/register_hive_tables.sql"

echo "Hive tables registered"

# ============================================================
# 6. Run Spark analysis
# ============================================================
echo ""
echo "6. Submitting Spark risk analysis job..."

ssh root@${MRS_MASTER} "
    spark-submit \
        --master yarn \
        --deploy-mode cluster \
        --name FinanceRiskAnalysis \
        --executor-memory 8g \
        --executor-cores 4 \
        --driver-memory 4g \
        --num-executors 3 \
        --conf spark.sql.shuffle.partitions=200 \
        /opt/scripts/spark_risk_analysis.py
"

echo "Spark analysis submitted"

# ============================================================
# 7. Export results
# ============================================================
echo ""
echo "7. Exporting analysis results..."

ssh root@${MRS_MASTER} "
    hdfs dfs -get ${HDFS_ROOT}/results/high_risk_customers /tmp/high_risk_customers
    hdfs dfs -get ${HDFS_ROOT}/results/customer_clusters /tmp/customer_clusters
"

echo "Results exported"

echo ""
echo "============================================"
echo "MRS Data Import Complete"
echo "============================================"
echo "Next: Run export_results_to_obs.sh to stage for DWS"
