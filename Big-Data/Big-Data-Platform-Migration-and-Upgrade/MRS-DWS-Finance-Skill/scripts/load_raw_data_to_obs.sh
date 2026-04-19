#!/bin/bash
# ============================================================
# load_raw_data_to_obs.sh
# Upload financial data files to OBS raw bucket
# ============================================================

set -euo pipefail

# --- Placeholders (replace before running) ---
RAW_BUCKET="<raw_bucket>"    # e.g. openbank-raw-xxxxxxxx
REGION="<region>"

# --- Data file paths (local) ---
CUSTOMERS_FILE="data/customers.csv"
ACCOUNTS_FILE="data/accounts.csv"
TRANSACTIONS_FILE="data/transactions.csv"

echo "============================================"
echo "Load Raw Data to OBS"
echo "============================================"

# --- Upload customer data ---
echo ""
echo "1. Uploading customer data..."
hcloud OBS PutObject \
    --bucket "${RAW_BUCKET}" \
    --key "customers/customers.csv" \
    --file "${CUSTOMERS_FILE}" \
    --region "${REGION}"

# --- Upload account data ---
echo ""
echo "2. Uploading account data..."
hcloud OBS PutObject \
    --bucket "${RAW_BUCKET}" \
    --key "accounts/accounts.csv" \
    --file "${ACCOUNTS_FILE}" \
    --region "${REGION}"

# --- Upload transaction data ---
echo ""
echo "3. Uploading transaction data..."
hcloud OBS PutObject \
    --bucket "${RAW_BUCKET}" \
    --key "transactions/transactions.csv" \
    --file "${TRANSACTIONS_FILE}" \
    --region "${REGION}"

echo ""
echo "============================================"
echo "Data Upload Complete"
echo "============================================"
echo "Customers:     obs://${RAW_BUCKET}/customers/"
echo "Accounts:      obs://${RAW_BUCKET}/accounts/"
echo "Transactions:  obs://${RAW_BUCKET}/transactions/"
