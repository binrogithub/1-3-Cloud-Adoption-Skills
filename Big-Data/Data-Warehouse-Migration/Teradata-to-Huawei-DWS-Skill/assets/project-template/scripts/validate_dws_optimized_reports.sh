#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${ROOT_DIR}/reports/output/branch_kpi.csv" \
  "${ROOT_DIR}/reports/dws_optimized/branch_kpi.csv" \
  --key province --key city --key branch_code --key year_num --key month_num
python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${ROOT_DIR}/reports/output/customer_profitability.csv" \
  "${ROOT_DIR}/reports/dws_optimized/customer_profitability.csv" \
  --key customer_number --key year_num --key month_num
python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${ROOT_DIR}/reports/output/liquidity_gap.csv" \
  "${ROOT_DIR}/reports/dws_optimized/liquidity_gap.csv" \
  --key balance_date --key product_type --key product_name --key currency_code
python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${ROOT_DIR}/reports/output/loan_risk_snapshot.csv" \
  "${ROOT_DIR}/reports/dws_optimized/loan_risk_snapshot.csv" \
  --key snapshot_date --key province --key city --key product_name --key risk_stage
python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${ROOT_DIR}/reports/output/suspicious_activity.csv" \
  "${ROOT_DIR}/reports/dws_optimized/suspicious_activity.csv" \
  --key customer_number

echo "Optimized DWS report validation passed."

