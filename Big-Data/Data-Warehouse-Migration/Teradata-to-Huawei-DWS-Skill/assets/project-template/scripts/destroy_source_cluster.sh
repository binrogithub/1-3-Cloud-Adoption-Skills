#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

for name in "${COORDINATOR}" "${WORKER1}" "${WORKER2}"; do
  if docker ps -a --format '{{.Names}}' | grep -qx "${name}"; then
    docker rm -f -v "${name}" >/dev/null
  fi
done

if docker network inspect "${DEMO_NETWORK}" >/dev/null 2>&1; then
  docker network rm "${DEMO_NETWORK}" >/dev/null
fi

echo "Source cluster destroyed."

