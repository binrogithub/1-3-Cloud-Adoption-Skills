#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${MODULE_DIR}/config/vm_migrate.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[VM-MIGRATE][ERROR] Env file not found: ${ENV_FILE}" >&2
  echo "Copy ${MODULE_DIR}/config/vm_migrate.env.example to ${MODULE_DIR}/config/vm_migrate.env and edit it." >&2
  exit 1
fi

mkdir -p "${MODULE_DIR}/out"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

: "${RESULT_PATH:=${MODULE_DIR}/out/migration_result.json}"
export RESULT_PATH

python3 "${SCRIPT_DIR}/mgc_migrate.py"
