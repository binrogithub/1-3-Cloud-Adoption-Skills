#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

OBS_ENV_FILE="${OBS_ENV_FILE:-${ROOT_DIR}/config/obs.env}"
if [[ -f "${OBS_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${OBS_ENV_FILE}"
  set +a
fi

OBS_REGION="${OBS_REGION:-la-south-2}"
OBS_BUCKET="${OBS_BUCKET:-}"
OBS_PREFIX="${OBS_PREFIX:-teradata-dws-demo/export}"
OBS_AK="${OBS_AK:-${CLOUD_SDK_AK:-${AK:-}}}"
OBS_SK="${OBS_SK:-${CLOUD_SDK_SK:-${SK:-}}}"

require_obs_config() {
  if [[ -z "${OBS_BUCKET}" || "${OBS_BUCKET}" == replace-with-* ]]; then
    cat >&2 <<EOF
Missing OBS settings.
Create ${OBS_ENV_FILE} from config/obs.env.example or export:
  OBS_BUCKET, optional OBS_REGION, OBS_PREFIX, OBS_AK, OBS_SK
EOF
    return 1
  fi
  if [[ -z "${OBS_AK}" || -z "${OBS_SK}" ]]; then
    echo "Missing OBS credentials. Export OBS_AK/OBS_SK, CLOUD_SDK_AK/CLOUD_SDK_SK, or AK/SK." >&2
    return 1
  fi
}

