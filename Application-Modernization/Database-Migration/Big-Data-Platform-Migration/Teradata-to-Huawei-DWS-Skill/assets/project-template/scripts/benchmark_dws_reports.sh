#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

mode="${1:-base}"
case "${mode}" in
  base)
    queries=(
      "branch_kpi|SELECT * FROM reports.branch_kpi ORDER BY year_num, month_num, branch_code"
      "customer_profitability|SELECT * FROM reports.customer_profitability ORDER BY contribution_margin DESC, transaction_count DESC, customer_number, year_num, month_num LIMIT 500"
      "liquidity_gap|SELECT * FROM reports.liquidity_gap ORDER BY balance_date, product_type, product_name, currency_code"
      "loan_risk_snapshot|SELECT * FROM reports.loan_risk_snapshot ORDER BY snapshot_date, expected_credit_loss DESC"
      "suspicious_activity|SELECT * FROM reports.suspicious_activity ORDER BY suspicious_count DESC, total_amount DESC, customer_number LIMIT 300"
    )
    ;;
  optimized)
    queries=(
      "branch_kpi|SELECT * FROM reports.branch_kpi_mart ORDER BY year_num, month_num, branch_code"
      "customer_profitability|SELECT * FROM reports.customer_profitability_mart ORDER BY contribution_margin DESC, transaction_count DESC, customer_number, year_num, month_num LIMIT 500"
      "liquidity_gap|SELECT * FROM reports.liquidity_gap_mart ORDER BY balance_date, product_type, product_name, currency_code"
      "loan_risk_snapshot|SELECT * FROM reports.loan_risk_snapshot_mart ORDER BY snapshot_date, expected_credit_loss DESC"
      "suspicious_activity|SELECT * FROM reports.suspicious_activity_mart ORDER BY suspicious_count DESC, total_amount DESC, customer_number LIMIT 300"
    )
    ;;
  *)
    echo "Usage: $0 [base|optimized]" >&2
    exit 2
    ;;
esac

for entry in "${queries[@]}"; do
  name="${entry%%|*}"
  query="${entry#*|}"
  start_ns="$(date +%s%N)"
  dws_psql -v ON_ERROR_STOP=1 -q -c "COPY (${query}) TO STDOUT WITH CSV HEADER" >/dev/null
  end_ns="$(date +%s%N)"
  elapsed_ms="$(( (end_ns - start_ns) / 1000000 ))"
  printf '%s,%s,%s\n' "${mode}" "${name}" "${elapsed_ms}"
done

