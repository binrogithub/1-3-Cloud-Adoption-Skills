#!/usr/bin/env bash
# Source Simulation: Local Spark Standalone Cluster
#
# Simulates a minimal Cloudera/CDH source environment using Spark Standalone.
# Uses bitnamilegacy/spark:3.5.1 (compatible with Docker 18.09+).
#
# Usage:
#   ./source_simulation.sh start    # Start 1 master + 2 workers
#   ./source_simulation.sh stop     # Stop all containers
#   ./source_simulation.sh destroy  # Remove containers, network, volumes

set -euo pipefail

NETWORK="${DEMO_NETWORK:-cloudera-mrs-sim-net}"
IMAGE="${DEMO_IMAGE:-bitnamilegacy/spark:3.5.1}"
MASTER="${MASTER:-cloudera-sim-master}"
WORKER1="${WORKER1:-cloudera-sim-worker1}"
WORKER2="${WORKER2:-cloudera-sim-worker2}"

start_cluster() {
  docker network inspect "${NETWORK}" >/dev/null 2>&1 || docker network create "${NETWORK}" >/dev/null

  # Master
  if ! docker ps -a --format '{{.Names}}' | grep -qx "${MASTER}"; then
    docker run -d --name "${MASTER}" --network "${NETWORK}" \
      -e SPARK_MODE=master -p 17077:7077 -p 18080:8080 \
      -v "$(pwd)":/workspace "${IMAGE}" >/dev/null
  else
    docker start "${MASTER}" >/dev/null
  fi

  # Workers
  for w in "${WORKER1}" "${WORKER2}"; do
    if ! docker ps -a --format '{{.Names}}' | grep -qx "${w}"; then
      docker run -d --name "${w}" --network "${NETWORK}" \
        -e SPARK_MODE=worker -e SPARK_MASTER_URL=spark://"${MASTER}":7077 \
        -v "$(pwd)":/workspace "${IMAGE}" >/dev/null
    else
      docker start "${w}" >/dev/null
    fi
  done

  echo "Cluster started: ${MASTER} + ${WORKER1} + ${WORKER2}"
  echo "Spark UI: http://127.0.0.1:18080"
}

stop_cluster() {
  for c in "${WORKER2}" "${WORKER1}" "${MASTER}"; do
    docker stop "${c}" 2>/dev/null || true
  done
  echo "Cluster stopped."
}

destroy_cluster() {
  for c in "${WORKER2}" "${WORKER1}" "${MASTER}"; do
    docker rm -f "${c}" 2>/dev/null || true
  done
  docker network rm "${NETWORK}" 2>/dev/null || true
  echo "Cluster destroyed."
}

case "${1:-}" in
  start)   start_cluster ;;
  stop)    stop_cluster ;;
  destroy) destroy_cluster ;;
  *)       echo "Usage: $0 {start|stop|destroy}"; exit 1 ;;
esac
