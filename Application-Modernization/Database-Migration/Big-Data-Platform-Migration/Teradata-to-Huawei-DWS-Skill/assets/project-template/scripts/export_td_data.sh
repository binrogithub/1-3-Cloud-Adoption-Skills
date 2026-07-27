#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="${ROOT_DIR}/data/export"
TABLE_LIST="${ROOT_DIR}/data/control/table_order.txt"
mkdir -p "${OUT_DIR}"

export_table() {
  local table_name="$1"
  local file_name="${table_name//./__}.csv"
  echo "Exporting ${table_name} -> data/export/${file_name}"
  docker exec -e PGPASSWORD="${DEMO_PASSWORD}" "${COORDINATOR}" \
    psql -U "${DEMO_USER}" -d "${DEMO_DB}" \
      -v ON_ERROR_STOP=1 \
      -c "COPY (SELECT * FROM ${table_name}) TO STDOUT WITH CSV HEADER" \
    > "${OUT_DIR}/${file_name}"
}

while IFS= read -r table_name; do
  [[ -z "${table_name}" || "${table_name}" =~ ^# ]] && continue
  export_table "${table_name}"
done < "${TABLE_LIST}"

docker exec -i -e PGPASSWORD="${DEMO_PASSWORD}" "${COORDINATOR}" \
  psql -U "${DEMO_USER}" -d "${DEMO_DB}" -v ON_ERROR_STOP=1 <<'SQL' \
  > "${OUT_DIR}/source_row_counts.csv"
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

ls -lh "${OUT_DIR}"/*.csv
