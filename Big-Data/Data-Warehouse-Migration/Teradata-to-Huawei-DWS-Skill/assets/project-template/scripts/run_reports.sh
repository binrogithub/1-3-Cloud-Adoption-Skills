#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="${ROOT_DIR}/reports/output"
mkdir -p "${OUT_DIR}"

run_report() {
  local view_name="$1"
  local file_name="$2"

  docker exec -i -e PGPASSWORD="${DEMO_PASSWORD}" "${COORDINATOR}" \
    psql -U "${DEMO_USER}" -d "${DEMO_DB}" \
      -v ON_ERROR_STOP=1 \
      -c "COPY (SELECT * FROM reports.${view_name}) TO STDOUT WITH CSV HEADER" \
    > "${OUT_DIR}/${file_name}"
}

run_report branch_kpi branch_kpi.csv
run_report customer_profitability customer_profitability.csv
run_report liquidity_gap liquidity_gap.csv
run_report loan_risk_snapshot loan_risk_snapshot.csv
run_report suspicious_activity suspicious_activity.csv

ls -lh "${OUT_DIR}"
