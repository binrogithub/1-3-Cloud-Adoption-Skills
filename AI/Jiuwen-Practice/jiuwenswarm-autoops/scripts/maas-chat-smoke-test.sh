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
request_file="${work_dir}/request.json"
response_file="${work_dir}/response.json"

MODEL_NAME="${MODEL_NAME}" python3 - > "${request_file}" <<'PY'
import json
import os

print(json.dumps({
    "model": os.environ["MODEL_NAME"],
    "messages": [{"role": "user", "content": "Respond with exactly: READY"}],
    "temperature": 0,
    "max_tokens": 8,
    "stream": False,
}))
PY

curl --silent --show-error --fail \
  --connect-timeout 10 \
  --max-time 45 \
  --header "Authorization: Bearer ${API_KEY}" \
  --header 'Content-Type: application/json' \
  --data-binary "@${request_file}" \
  --output "${response_file}" \
  "${MAAS_BASE_URL}/chat/completions"

MAAS_RESPONSE_FILE="${response_file}" MODEL_NAME="${MODEL_NAME}" python3 - <<'PY'
import json
import os

with open(os.environ["MAAS_RESPONSE_FILE"], encoding="utf-8") as response:
    payload = json.load(response)

choices = payload.get("choices")
if not isinstance(choices, list) or not choices:
    raise SystemExit("MaaS returned an unexpected chat completion response")

message = choices[0].get("message") if isinstance(choices[0], dict) else None
content = message.get("content") if isinstance(message, dict) else None
if not isinstance(content, str) or not content.strip():
    raise SystemExit("MaaS returned an empty chat completion")

print(f"MaaS chat ready: model={os.environ['MODEL_NAME']}")
print(f"response={content.strip()[:80]}")
PY
