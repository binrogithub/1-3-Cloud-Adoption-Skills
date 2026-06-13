#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-}}"
API_KEY="${2:-${API_KEY:-}}"
MODEL="${3:-${MODEL:-}}"

if [[ -z "${BASE_URL}" || -z "${API_KEY}" || -z "${MODEL}" ]]; then
  cat <<'EOF' >&2
Usage:
  verify_maas_openai_compatible.sh <base_url> <api_key> <model>

Or set:
  BASE_URL
  API_KEY
  MODEL
EOF
  exit 2
fi

TMP_BODY="$(mktemp)"
TMP_HEADERS="$(mktemp)"
cleanup() {
  rm -f "${TMP_BODY}" "${TMP_HEADERS}"
}
trap cleanup EXIT

HTTP_CODE="$(
  curl -sS \
    -D "${TMP_HEADERS}" \
    -o "${TMP_BODY}" \
    -w '%{http_code}' \
    -H "Authorization: Bearer ${API_KEY}" \
    -H 'Content-Type: application/json' \
    "${BASE_URL%/}/chat/completions" \
    -d @- <<EOF
{
  "model": "${MODEL}",
  "messages": [
    {
      "role": "user",
      "content": "Reply with exactly: ok"
    }
  ],
  "temperature": 0
}
EOF
)"

printf 'HTTP %s\n' "${HTTP_CODE}"

if [[ "${HTTP_CODE}" == "200" ]]; then
  if command -v jq >/dev/null 2>&1; then
    CONTENT="$(jq -r '.choices[0].message.content // empty' "${TMP_BODY}" 2>/dev/null || true)"
    MODEL_ECHO="$(jq -r '.model // empty' "${TMP_BODY}" 2>/dev/null || true)"
    printf 'Model: %s\n' "${MODEL_ECHO:-<unknown>}"
    printf 'Reply: %s\n' "${CONTENT:-<empty>}"
  else
    printf 'Response body saved in memory; install jq for parsed output.\n'
    sed -n '1,40p' "${TMP_BODY}"
  fi
  exit 0
fi

printf 'Request failed.\n'
printf 'Response headers:\n'
sed -n '1,40p' "${TMP_HEADERS}"
printf 'Response body:\n'
sed -n '1,80p' "${TMP_BODY}"
exit 1
