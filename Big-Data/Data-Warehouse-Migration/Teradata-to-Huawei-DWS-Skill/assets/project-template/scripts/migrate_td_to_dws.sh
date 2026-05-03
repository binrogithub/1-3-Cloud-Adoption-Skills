#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/export_td_data.sh"
"${SCRIPT_DIR}/load_dws_data.sh"
"${SCRIPT_DIR}/run_dws_reports.sh"
"${SCRIPT_DIR}/validate_dws_migration.sh"

echo "Teradata-source demo workload migrated to DWS successfully."

