#!/usr/bin/env bash
set -Eeuo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/load-model-env.sh"
MAAS_BASE_URL="${API_BASE%/}"

for command_name in curl python3; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "${command_name}" >&2
    exit 1
  }
done

work_dir="$(mktemp -d)"
trap 'rm -rf -- "${work_dir}"' EXIT
response_file="${work_dir}/models.json"

curl --silent --show-error --fail \
  --connect-timeout 10 \
  --max-time 30 \
  --header "Authorization: Bearer ${API_KEY}" \
  --header 'Accept: application/json' \
  --output "${response_file}" \
  "${MAAS_BASE_URL}/models"

MAAS_RESPONSE_FILE="${response_file}" MAAS_BASE_URL="${MAAS_BASE_URL}" python3 - <<'PY'
import json
import os
from urllib.parse import urlparse

with open(os.environ["MAAS_RESPONSE_FILE"], encoding="utf-8") as response:
    payload = json.load(response)

models = payload.get("data")
if not isinstance(models, list):
    raise SystemExit("MaaS returned an unexpected /models response")

model_ids = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
host = urlparse(os.environ["MAAS_BASE_URL"]).netloc
print(f"MaaS connection ready: endpoint={host}, models={len(model_ids)}")
for model_id in model_ids[:10]:
    print(f"model={model_id}")
if not model_ids:
    raise SystemExit("MaaS authentication succeeded but no models are available to this account")
PY
