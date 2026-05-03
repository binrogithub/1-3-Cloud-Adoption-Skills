#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dws_common.sh
source "${SCRIPT_DIR}/dws_common.sh"

refresh_month="${1:-202506}"
snapshot_date="${2:-2025-06-30}"

if [[ ! "${refresh_month}" =~ ^[0-9]{6}$ ]]; then
  echo "refresh_month must be YYYYMM, got ${refresh_month}" >&2
  exit 2
fi

year_num="${refresh_month:0:4}"
month_num="$((10#${refresh_month:4:2}))"

echo "Incrementally refreshing marts for month=${refresh_month}, snapshot_date=${snapshot_date}."
dws_psql \
  -v ON_ERROR_STOP=1 \
  -v year_num="${year_num}" \
  -v month_num="${month_num}" \
  -v refresh_month="${refresh_month}" \
  -v snapshot_date="${snapshot_date}" \
  < "${ROOT_DIR}/sql/dws/07_incremental_mart_refresh.sql"

dws_psql -P pager=off -v ON_ERROR_STOP=1 -c "SELECT * FROM reports.refresh_control ORDER BY refreshed_at DESC, mart_name;"

