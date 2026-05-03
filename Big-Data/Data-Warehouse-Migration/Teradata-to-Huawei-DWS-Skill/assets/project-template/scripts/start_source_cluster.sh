#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

docker network inspect "${DEMO_NETWORK}" >/dev/null 2>&1 || docker network create "${DEMO_NETWORK}" >/dev/null

start_node() {
  local name="$1"
  shift

  if docker ps -a --format '{{.Names}}' | grep -qx "${name}"; then
    docker start "${name}" >/dev/null
    return
  fi

  docker run -d \
    --name "${name}" \
    --network "${DEMO_NETWORK}" \
    -e POSTGRES_DB="${DEMO_DB}" \
    -e POSTGRES_USER="${DEMO_USER}" \
    -e POSTGRES_PASSWORD="${DEMO_PASSWORD}" \
    "$@" \
    "${DEMO_IMAGE}" >/dev/null
}

start_node "${WORKER1}"
start_node "${WORKER2}"
start_node "${COORDINATOR}" -p "${DEMO_PORT}:5432"

wait_for_postgres "${WORKER1}"
wait_for_postgres "${WORKER2}"
wait_for_postgres "${COORDINATOR}"

docker exec -i -e PGPASSWORD="${DEMO_PASSWORD}" "${COORDINATOR}" \
  psql -U "${DEMO_USER}" -d "${DEMO_DB}" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS citus;
SELECT citus_set_coordinator_host('${COORDINATOR}', 5432);
SELECT citus_add_node('${WORKER1}', 5432)
WHERE NOT EXISTS (SELECT 1 FROM pg_dist_node WHERE nodename = '${WORKER1}');
SELECT citus_add_node('${WORKER2}', 5432)
WHERE NOT EXISTS (SELECT 1 FROM pg_dist_node WHERE nodename = '${WORKER2}');
SQL

echo "Source cluster is ready on 127.0.0.1:${DEMO_PORT}/${DEMO_DB}."
