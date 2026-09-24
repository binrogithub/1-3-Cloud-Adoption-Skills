#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
config_dir="${JIUWENSWARM_AUTOOPS_CONFIG_DIR:-${PROJECT_DIR}/config/local}"
if [[ -f "${PROJECT_DIR}/components.env" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT_DIR}/components.env"
fi
loki_url="${LOKI_LOCAL_BASE_URL:-}"

usage() {
  cat <<'EOF'
Usage: configure-local-loki.sh [--url URL] [--config-dir DIRECTORY]

Verify a Loki /ready endpoint and write a 0600 AutoOps Loki env file.
The file contains no credentials. Existing files are replaced atomically.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) loki_url="${2:-}"; shift 2 ;;
    --config-dir) config_dir="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$loki_url" ]]; then
  [[ -n "${LOKI_HTTP_HOST:-}" && -n "${LOKI_HTTP_PORT:-}" ]] || {
    printf 'Loki URL is not configured; set LOKI_LOCAL_BASE_URL or LOKI_HTTP_HOST/LOKI_HTTP_PORT in components.env\n' >&2
    exit 2
  }
  loki_url="http://${LOKI_HTTP_HOST}:${LOKI_HTTP_PORT}"
fi

[[ "$loki_url" =~ ^https?://[^[:space:]]+$ ]] || {
  printf 'Loki URL must be an HTTP(S) URL\n' >&2
  exit 2
}
command -v curl >/dev/null 2>&1 || {
  printf 'missing required command: curl\n' >&2
  exit 1
}

ready_body="$(curl --silent --show-error --fail --max-time 5 "${loki_url%/}/ready")" || {
  printf 'Loki readiness probe failed: %s\n' "$loki_url" >&2
  exit 1
}
[[ "$ready_body" == "ready" ]] || {
  printf 'Loki readiness probe returned unexpected response\n' >&2
  exit 1
}

mkdir -p -- "$config_dir"
chmod 700 -- "$config_dir"
temp_file="$(mktemp "${config_dir}/.loki.env.XXXXXX")"
trap 'rm -f -- "$temp_file"' EXIT
cat > "$temp_file" <<EOF
# Managed by JiuwenSwarm AutoOps local Loki configuration.
# Credentials are intentionally absent; add tenant/token only when required.
LOKI_BASE_URL="${loki_url}"
LOKI_TENANT_ID=""
LOKI_BEARER_TOKEN=""
LOKI_SERVICE_LABEL="service"
LOKI_TIMEOUT_SECONDS="15"
AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES="1440"
AUTOOPS_LOCAL_JOURNAL_FALLBACK="1"
EOF
chmod 600 -- "$temp_file"
mv -f -- "$temp_file" "${config_dir}/loki.env"
trap - EXIT
printf '{"status":"READY","loki_base_url":"%s","config":"%s"}\n' \
  "$loki_url" "${config_dir}/loki.env"
