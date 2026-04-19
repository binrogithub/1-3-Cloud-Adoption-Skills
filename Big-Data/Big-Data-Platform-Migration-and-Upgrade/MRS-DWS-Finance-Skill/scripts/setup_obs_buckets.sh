#!/bin/bash
# ============================================================
# setup_obs_buckets.sh
# Create OBS buckets for financial risk control pipeline
# ============================================================

set -euo pipefail

# --- Placeholders (replace before running) ---
REGION="<region>"           # e.g. la-north-2
PROJECT_ID="<project_id>"

# --- Bucket naming convention ---
RAW_BUCKET="openbank-raw-${PROJECT_ID:0:8}"
RESULTS_BUCKET="openbank-results-${PROJECT_ID:0:8}"
CURATED_BUCKET="openbank-curated-${PROJECT_ID:0:8}"

echo "============================================"
echo "OBS Bucket Setup for Finance Risk Control"
echo "============================================"

# --- Create buckets ---
echo ""
echo "1. Creating raw data bucket: ${RAW_BUCKET}"
hcloud OBS CreateBucket --bucket "${RAW_BUCKET}" --region "${REGION}" --location "${REGION}"

echo ""
echo "2. Creating analysis results bucket: ${RESULTS_BUCKET}"
hcloud OBS CreateBucket --bucket "${RESULTS_BUCKET}" --region "${REGION}" --location "${REGION}"

echo ""
echo "3. Creating curated data bucket: ${CURATED_BUCKET}"
hcloud OBS CreateBucket --bucket "${CURATED_BUCKET}" --region "${REGION}" --location "${REGION}"

# --- Create folder structure ---
echo ""
echo "4. Creating folder structure in raw bucket..."
# Raw data folders
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "customers/" --body ""
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "accounts/" --body ""
hcloud OBS PutObject --bucket "${RAW_BUCKET}" --key "transactions/" --body ""

echo ""
echo "5. Creating folder structure in results bucket..."
# Analysis result folders
hcloud OBS PutObject --bucket "${RESULTS_BUCKET}" --key "risk_scores/" --body ""
hcloud OBS PutObject --bucket "${RESULTS_BUCKET}" --key "customer_clusters/" --body ""
hcloud OBS PutObject --bucket "${RESULTS_BUCKET}" --key "high_risk_customers/" --body ""
hcloud OBS PutObject --bucket "${RESULTS_BUCKET}" --key "anomaly_transactions/" --body ""
hcloud OBS PutObject --bucket "${RESULTS_BUCKET}" --key "daily_risk_stats/" --body ""

echo ""
echo "6. Creating folder structure in curated bucket..."
# Curated data folders (for DWS import)
hcloud OBS PutObject --bucket "${CURATED_BUCKET}" --key "dim/" --body ""
hcloud OBS PutObject --bucket "${CURATED_BUCKET}" --key "fact/" --body ""
hcloud OBS PutObject --bucket "${CURATED_BUCKET}" --key "agg/" --body ""

echo ""
echo "============================================"
echo "OBS Bucket Setup Complete"
echo "============================================"
echo "Raw data:      obs://${RAW_BUCKET}"
echo "Analysis:      obs://${RESULTS_BUCKET}"
echo "Curated:       obs://${CURATED_BUCKET}"
