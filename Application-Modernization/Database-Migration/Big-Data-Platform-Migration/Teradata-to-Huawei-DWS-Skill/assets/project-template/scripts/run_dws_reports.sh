#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

OUT_DIR="${ROOT_DIR}/reports/dws"
mkdir -p "${OUT_DIR}"

run_report() {
  local view_name="$1"
  local file_name="$2"
  local order_clause="$3"
  local limit_clause="${4:-}"

  echo "Exporting DWS report ${view_name} -> reports/dws/${file_name}"
  dws_psql -v ON_ERROR_STOP=1 \
    -c "COPY (SELECT * FROM reports.${view_name} ${order_clause} ${limit_clause}) TO STDOUT WITH CSV HEADER" \
    > "${OUT_DIR}/${file_name}"
}

run_report branch_kpi branch_kpi.csv "ORDER BY year_num, month_num, branch_code"
run_report customer_profitability customer_profitability.csv "ORDER BY contribution_margin DESC, transaction_count DESC, customer_number, year_num, month_num" "LIMIT 500"
run_report liquidity_gap liquidity_gap.csv "ORDER BY balance_date, product_type, product_name, currency_code"
run_report loan_risk_snapshot loan_risk_snapshot.csv "ORDER BY snapshot_date, expected_credit_loss DESC"
run_report suspicious_activity suspicious_activity.csv "ORDER BY suspicious_count DESC, total_amount DESC, customer_number" "LIMIT 300"

ls -lh "${OUT_DIR}"/*.csv
