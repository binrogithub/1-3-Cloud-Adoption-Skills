#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOTENV_PATH="${JIUWENSWARM_AUTOOPS_MODEL_ENV:-${JIUWENSWARM_AUTOOPS_DOTENV:-${HOME}/.jiuwenswarm/config/.env}}"

command -v jiuwenswarm >/dev/null 2>&1 || {
  printf 'missing required command: jiuwenswarm\n' >&2
  exit 1
}

[[ -r "${DOTENV_PATH}" ]] || {
  printf 'Shared model configuration is missing: %s\nRun sudo /opt/Jiuwenswarm_AutoOps/scripts/configure-model.py\n' "${DOTENV_PATH}" >&2
  exit 1
}

file_mode="$(stat -c '%a' "${DOTENV_PATH}")"
if [[ "${file_mode}" != 600 && "${file_mode}" != 400 ]]; then
  printf 'MaaS dotenv file must use mode 0600 or 0400: %s\n' "${DOTENV_PATH}" >&2
  exit 1
fi

chat_gateway_url="${JIUWENSWARM_AUTOOPS_CHAT_GATEWAY_URL:-ws://127.0.0.1:19001/acp}"

chat_mode="${JIUWENSWARM_AUTOOPS_MODE:-agent.fast}"
chat_timeout="${JIUWENSWARM_AUTOOPS_CHAT_TIMEOUT:-120}"

for variable in API_BASE API_KEY MODEL_NAME MODEL_PROVIDER; do
  if ! grep -Eq "^[[:space:]]*${variable}=[\"']?.+" "${DOTENV_PATH}"; then
    printf 'Shared model configuration is missing %s: %s\n' "${variable}" "${DOTENV_PATH}" >&2
    exit 1
  fi
done

exec jiuwenswarm chat \
  --dotenv "${DOTENV_PATH}" \
  --project-dir "${PROJECT_DIR}" \
  --trusted-dir "${PROJECT_DIR}" \
  --gateway-url "${chat_gateway_url}" \
  --mode "${chat_mode}" \
  --timeout "${chat_timeout}" \
  "$@"
