#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/obs_common.sh
source "${SCRIPT_DIR}/obs_common.sh"

require_obs_config

"${SCRIPT_DIR}/upload_export_to_obs.sh"

python3 "${SCRIPT_DIR}/generate_dws_obs_load_sql.py" \
  --bucket "${OBS_BUCKET}" \
  --prefix "${OBS_PREFIX}" \
  --output "${ROOT_DIR}/sql/dws/08_load_from_obs.generated.sql"

echo "Review sql/dws/08_load_from_obs.generated.sql before executing OBS-based DWS loading."

