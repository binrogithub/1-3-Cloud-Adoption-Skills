#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/obs_common.sh
source "${SCRIPT_DIR}/obs_common.sh"

require_obs_config

python3 "${SCRIPT_DIR}/upload_export_to_obs.py" \
  --region "${OBS_REGION}" \
  --bucket "${OBS_BUCKET}" \
  --prefix "${OBS_PREFIX}" \
  "$@"

