#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

psql_source -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/01_schema/finance_dw.sql"
psql_source -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/02_data/load_finance_sample.sql"
psql_source -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/03_reports/report_views.sql"

psql_source -P pager=off -c "
SELECT 'customers' AS table_name, count(*) FROM finance_dw.dim_customer
UNION ALL SELECT 'accounts', count(*) FROM finance_dw.dim_account
UNION ALL SELECT 'transactions', count(*) FROM finance_dw.fact_transaction
UNION ALL SELECT 'daily_balances', count(*) FROM finance_dw.fact_daily_balance
UNION ALL SELECT 'loan_snapshots', count(*) FROM finance_dw.fact_loan_snapshot
ORDER BY table_name;"
