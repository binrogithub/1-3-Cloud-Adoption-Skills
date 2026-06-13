#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-https://api-<region>.modelarts-maas.com/openai/v1}}"
MODEL="${2:-${MODEL:-<model_id>}}"
API_KEY_PLACEHOLDER="${3:-${API_KEY_PLACEHOLDER:-<MaaS_API_Key>}}"

cat <<EOF
Provider: OpenAI Compatible
Base URL: ${BASE_URL}
Model: ${MODEL}
API Key: ${API_KEY_PLACEHOLDER}

Recommended first-pass test:
Reply with exactly: ok

Example model:
glm-5.1
EOF
