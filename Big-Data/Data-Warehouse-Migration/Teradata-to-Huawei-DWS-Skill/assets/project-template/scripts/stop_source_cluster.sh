#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${SCRIPT_DIR}/common.sh"

for name in "${COORDINATOR}" "${WORKER1}" "${WORKER2}"; do
  if docker ps --format '{{.Names}}' | grep -qx "${name}"; then
    docker stop "${name}" >/dev/null
  fi
done

echo "Source cluster stopped."

