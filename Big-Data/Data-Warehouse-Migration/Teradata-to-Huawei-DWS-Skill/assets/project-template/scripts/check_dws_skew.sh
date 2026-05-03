#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

echo "Checking hash distribution skew using a 32-bucket approximation."
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/06_distribution_skew_checks.sql"
dws_psql -P pager=off -v ON_ERROR_STOP=1 -c "SELECT * FROM reports.distribution_skew_report ORDER BY table_name;"

