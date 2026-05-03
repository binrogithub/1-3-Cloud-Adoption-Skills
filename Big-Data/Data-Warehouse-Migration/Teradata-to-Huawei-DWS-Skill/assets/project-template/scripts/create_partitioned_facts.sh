#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

echo "Creating partitioned fact table copies in finance_dw_partitioned."
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/05_partitioned_fact_tables.sql"

echo "Partitioned fact row counts:"
dws_psql -P pager=off -v ON_ERROR_STOP=1 -c "
SELECT 'finance_dw_partitioned.fact_transaction' AS table_name, count(*) FROM finance_dw_partitioned.fact_transaction
UNION ALL SELECT 'finance_dw_partitioned.fact_daily_balance', count(*) FROM finance_dw_partitioned.fact_daily_balance
UNION ALL SELECT 'finance_dw_partitioned.fact_loan_snapshot', count(*) FROM finance_dw_partitioned.fact_loan_snapshot
ORDER BY table_name;"

