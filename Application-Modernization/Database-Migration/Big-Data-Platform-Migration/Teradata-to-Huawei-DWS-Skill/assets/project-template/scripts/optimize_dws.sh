#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

echo "Building optimized DWS reporting marts and refreshing statistics."
dws_psql -v ON_ERROR_STOP=1 < "${ROOT_DIR}/sql/dws/04_optimize_reporting_marts.sql"

echo "Optimization metadata:"
dws_psql -P pager=off -v ON_ERROR_STOP=1 -c "SELECT object_name, row_count, refreshed_at FROM reports.optimization_metadata ORDER BY object_name;"

