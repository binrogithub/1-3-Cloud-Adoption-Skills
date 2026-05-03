#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

DATA_DIR="${ROOT_DIR}/reports/report_data"
mkdir -p "${DATA_DIR}"

export_query() {
  local file_name="$1"
  local query="$2"

  dws_psql -v ON_ERROR_STOP=1 \
    -c "COPY (${query}) TO STDOUT WITH CSV HEADER" \
    > "${DATA_DIR}/${file_name}"
}

echo "Collecting DWS diagnostics for migration report."
export_query optimization_metadata.csv "SELECT object_name, row_count, refreshed_at FROM reports.optimization_metadata ORDER BY object_name"
export_query distribution_skew_report.csv "SELECT table_name, distribution_key, row_count, distinct_key_count, max_bucket_rows, min_bucket_rows, avg_bucket_rows, skew_ratio FROM reports.distribution_skew_report ORDER BY table_name"
export_query refresh_control.csv "SELECT mart_name, refresh_key, refreshed_at, row_count FROM reports.refresh_control ORDER BY refreshed_at DESC, mart_name"
export_query partitioned_fact_row_counts.csv "SELECT 'finance_dw_partitioned.fact_daily_balance' AS table_name, count(*)::bigint AS row_count FROM finance_dw_partitioned.fact_daily_balance UNION ALL SELECT 'finance_dw_partitioned.fact_loan_snapshot', count(*)::bigint FROM finance_dw_partitioned.fact_loan_snapshot UNION ALL SELECT 'finance_dw_partitioned.fact_transaction', count(*)::bigint FROM finance_dw_partitioned.fact_transaction ORDER BY table_name"

python3 "${SCRIPT_DIR}/generate_migration_report.py" \
  --output "${ROOT_DIR}/reports/migration_report.md"

echo "Generated reports/migration_report.md"

