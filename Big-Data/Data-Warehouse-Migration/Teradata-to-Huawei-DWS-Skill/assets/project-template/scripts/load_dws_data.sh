#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

echo "Creating DWS schemas, tables, and report views."
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/01_create_finance_dw.sql"
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/02_report_views.sql"

echo "Loading exported CSV files into DWS."
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/03_load_data.sql"

echo "Refreshing DWS statistics."
dws_psql -v ON_ERROR_STOP=1 -c "ANALYZE finance_dw.dim_branch; ANALYZE finance_dw.dim_product; ANALYZE finance_dw.dim_customer; ANALYZE finance_dw.dim_account; ANALYZE finance_dw.dim_date; ANALYZE finance_dw.fact_transaction; ANALYZE finance_dw.fact_daily_balance; ANALYZE finance_dw.fact_loan_snapshot;"

