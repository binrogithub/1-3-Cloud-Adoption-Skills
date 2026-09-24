#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--install-only" ]]; then
  shift
  python3 "${SCRIPT_DIR}/install-jiuwenswarm-autoops-skills.py" "$@"
  exec python3 "${SCRIPT_DIR}/install-autoops-runtime.py"
fi

exec "${SCRIPT_DIR}/Jiuwen_autoops_tui" "$@"
