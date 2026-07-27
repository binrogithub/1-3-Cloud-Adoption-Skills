#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DWS_ENV_FILE="${DWS_ENV_FILE:-${ROOT_DIR}/config/dws.env}"
if [[ -f "${DWS_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${DWS_ENV_FILE}"
  set +a
fi

DWS_HOST="${DWS_HOST:-}"
DWS_PORT="${DWS_PORT:-8000}"
DWS_DATABASE="${DWS_DATABASE:-postgres}"
DWS_USER="${DWS_USER:-dbadmin}"
DWS_PASSWORD="${DWS_PASSWORD:-}"
DWS_SSLMODE="${DWS_SSLMODE:-prefer}"
DWS_SQL_CLIENT="${DWS_SQL_CLIENT:-docker}"
DWS_SQL_CLIENT_IMAGE="${DWS_SQL_CLIENT_IMAGE:-citusdata/citus:12.1}"

require_dws_config() {
  if [[ -z "${DWS_HOST}" || -z "${DWS_PASSWORD}" \
     || "${DWS_HOST}" == replace-with-* \
     || "${DWS_PASSWORD}" == replace-with-* ]]; then
    cat >&2 <<EOF
Missing DWS connection settings.
Create ${DWS_ENV_FILE} from config/dws.env.example or export:
  DWS_HOST, DWS_PASSWORD, optional DWS_PORT, DWS_DATABASE, DWS_USER
EOF
    return 1
  fi
}

dws_psql() {
  require_dws_config

  if [[ "${DWS_SQL_CLIENT}" == "docker" ]]; then
    docker run --rm -i --network host \
      -e PGPASSWORD="${DWS_PASSWORD}" \
      -e PGSSLMODE="${DWS_SSLMODE}" \
      -v "${ROOT_DIR}:/work" \
      -w /work \
      --entrypoint psql \
      "${DWS_SQL_CLIENT_IMAGE}" \
      -h "${DWS_HOST}" \
      -p "${DWS_PORT}" \
      -U "${DWS_USER}" \
      -d "${DWS_DATABASE}" \
      "$@"
    return
  fi

  PGPASSWORD="${DWS_PASSWORD}" PGSSLMODE="${DWS_SSLMODE}" psql \
    -h "${DWS_HOST}" \
    -p "${DWS_PORT}" \
    -U "${DWS_USER}" \
    -d "${DWS_DATABASE}" \
    "$@"
}
