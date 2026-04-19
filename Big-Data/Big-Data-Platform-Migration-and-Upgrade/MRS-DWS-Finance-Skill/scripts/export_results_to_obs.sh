#!/bin/bash
# ============================================================
# export_results_to_obs.sh
# Export MRS analysis results to OBS in Parquet format
# ============================================================

set -euo pipefail

# --- Placeholders (replace before running) ---
MRS_MASTER="<mrs_master>"          # MRS master node IP
RESULTS_BUCKET="<results_bucket>"   # e.g. openbank-results-xxxxxxxx
CURATED_BUCKET="<curated_bucket>"   # e.g. openbank-curated-xxxxxxxx

echo "============================================"
echo "Export MRS Results to OBS"
echo "============================================"

# --- Export risk scores ---
echo ""
echo "1. Exporting risk scores to OBS..."
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${RESULTS_BUCKET}/risk_scores/'
    STORED AS PARQUET
    SELECT
        customer_id, total_transactions, total_amount,
        avg_amount, max_amount, fraud_count,
        risk_score, risk_level
    FROM openbank_risk.risk_scores
\""

# --- Export customer clusters ---
echo ""
echo "2. Exporting customer clusters to OBS..."
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${RESULTS_BUCKET}/customer_clusters/'
    STORED AS PARQUET
    SELECT
        customer_id, total_transactions, total_amount, cluster
    FROM openbank_risk.customer_clusters
\""

# --- Export high risk customers ---
echo ""
echo "3. Exporting high risk customers to OBS..."
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${RESULTS_BUCKET}/high_risk_customers/'
    STORED AS PARQUET
    SELECT
        customer_id, total_transactions, total_amount,
        fraud_count, risk_score, risk_level
    FROM openbank_risk.high_risk_customers
    ORDER BY risk_score DESC
\""

# --- Copy curated data for DWS import ---
echo ""
echo "4. Preparing curated data for DWS import..."
# Dimension data
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${CURATED_BUCKET}/dim/dim_customer/'
    STORED AS PARQUET
    SELECT * FROM openbank_risk.customers
\""

ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${CURATED_BUCKET}/dim/dim_account/'
    STORED AS PARQUET
    SELECT * FROM openbank_risk.accounts
\""

# Fact data
ssh root@${MRS_MASTER} "spark-sql -e \"
    INSERT OVERWRITE DIRECTORY 'obs://${CURATED_BUCKET}/fact/fact_transaction/'
    STORED AS PARQUET
    SELECT * FROM openbank_risk.transactions
\""

echo ""
echo "============================================"
echo "Export Complete"
echo "============================================"
echo "Risk scores:       obs://${RESULTS_BUCKET}/risk_scores/"
echo "Customer clusters: obs://${RESULTS_BUCKET}/customer_clusters/"
echo "High risk:         obs://${RESULTS_BUCKET}/high_risk_customers/"
echo "Curated dim:       obs://${CURATED_BUCKET}/dim/"
echo "Curated fact:      obs://${CURATED_BUCKET}/fact/"
