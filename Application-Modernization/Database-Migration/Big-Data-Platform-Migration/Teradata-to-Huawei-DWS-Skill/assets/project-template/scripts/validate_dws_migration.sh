#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

OUT_DIR="${ROOT_DIR}/data/export"
mkdir -p "${OUT_DIR}"

echo "Collecting DWS row counts."
dws_psql -v ON_ERROR_STOP=1 <<'SQL' > "${OUT_DIR}/dws_row_counts.csv"
COPY (
  SELECT 'finance_dw.dim_branch' AS table_name, count(*)::bigint AS row_count FROM finance_dw.dim_branch
  UNION ALL SELECT 'finance_dw.dim_product', count(*)::bigint FROM finance_dw.dim_product
  UNION ALL SELECT 'finance_dw.dim_customer', count(*)::bigint FROM finance_dw.dim_customer
  UNION ALL SELECT 'finance_dw.dim_account', count(*)::bigint FROM finance_dw.dim_account
  UNION ALL SELECT 'finance_dw.dim_date', count(*)::bigint FROM finance_dw.dim_date
  UNION ALL SELECT 'finance_dw.fact_transaction', count(*)::bigint FROM finance_dw.fact_transaction
  UNION ALL SELECT 'finance_dw.fact_daily_balance', count(*)::bigint FROM finance_dw.fact_daily_balance
  UNION ALL SELECT 'finance_dw.fact_loan_snapshot', count(*)::bigint FROM finance_dw.fact_loan_snapshot
) TO STDOUT WITH CSV HEADER;
SQL

python3 "${SCRIPT_DIR}/compare_csv.py" \
  "${OUT_DIR}/source_row_counts.csv" \
  "${OUT_DIR}/dws_row_counts.csv" \
  --key table_name \
  --numeric row_count

if [[ -d "${ROOT_DIR}/reports/output" && -d "${ROOT_DIR}/reports/dws" ]]; then
  python3 "${SCRIPT_DIR}/compare_csv.py" \
    "${ROOT_DIR}/reports/output/branch_kpi.csv" \
    "${ROOT_DIR}/reports/dws/branch_kpi.csv" \
    --key province --key city --key branch_code --key year_num --key month_num
  python3 "${SCRIPT_DIR}/compare_csv.py" \
    "${ROOT_DIR}/reports/output/customer_profitability.csv" \
    "${ROOT_DIR}/reports/dws/customer_profitability.csv" \
    --key customer_number --key year_num --key month_num
  python3 "${SCRIPT_DIR}/compare_csv.py" \
    "${ROOT_DIR}/reports/output/liquidity_gap.csv" \
    "${ROOT_DIR}/reports/dws/liquidity_gap.csv" \
    --key balance_date --key product_type --key product_name --key currency_code
  python3 "${SCRIPT_DIR}/compare_csv.py" \
    "${ROOT_DIR}/reports/output/loan_risk_snapshot.csv" \
    "${ROOT_DIR}/reports/dws/loan_risk_snapshot.csv" \
    --key snapshot_date --key province --key city --key product_name --key risk_stage
  python3 "${SCRIPT_DIR}/compare_csv.py" \
    "${ROOT_DIR}/reports/output/suspicious_activity.csv" \
    "${ROOT_DIR}/reports/dws/suspicious_activity.csv" \
    --key customer_number
fi

echo "DWS migration validation passed."
