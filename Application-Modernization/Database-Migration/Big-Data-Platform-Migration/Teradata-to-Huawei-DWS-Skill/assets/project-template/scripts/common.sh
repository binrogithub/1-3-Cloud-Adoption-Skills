#!/usr/bin/env bash
set -euo pipefail

DEMO_NETWORK="${DEMO_NETWORK:-tdsim-net}"
DEMO_IMAGE="${DEMO_IMAGE:-citusdata/citus:12.1}"
DEMO_DB="${DEMO_DB:-tdsim}"
DEMO_USER="${DEMO_USER:-tdadmin}"
DEMO_PASSWORD="${DEMO_PASSWORD:-tdadmin}"
DEMO_PORT="${DEMO_PORT:-15432}"

COORDINATOR="${COORDINATOR:-tdsim-coordinator}"
WORKER1="${WORKER1:-tdsim-worker1}"
WORKER2="${WORKER2:-tdsim-worker2}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

psql_source() {
  docker exec -i \
    -e PGPASSWORD="${DEMO_PASSWORD}" \
    "${COORDINATOR}" \
    psql \
    -U "${DEMO_USER}" \
    -d "${DEMO_DB}" \
    "$@"
}

wait_for_postgres() {
  local container="$1"
  local retries="${2:-60}"

  for _ in $(seq 1 "${retries}"); do
    if docker exec "${container}" pg_isready -U "${DEMO_USER}" -d "${DEMO_DB}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for ${container}." >&2
  return 1
}
