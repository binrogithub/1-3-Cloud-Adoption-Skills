#!/usr/bin/env bash
# Load the same restricted dotenv used by `jiuwenswarm chat --dotenv`.
JIUWENSWARM_AUTOOPS_MODEL_ENV="${JIUWENSWARM_AUTOOPS_MODEL_ENV:-${HOME}/.jiuwenswarm/config/.env}"
if [[ ! -r "$JIUWENSWARM_AUTOOPS_MODEL_ENV" ]]; then
  printf 'Shared model configuration is not readable: %s\n' "$JIUWENSWARM_AUTOOPS_MODEL_ENV" >&2
  return 1 2>/dev/null || exit 1
fi
model_env_mode="$(stat -c '%a' "$JIUWENSWARM_AUTOOPS_MODEL_ENV")"
if [[ "$model_env_mode" != 600 && "$model_env_mode" != 400 ]]; then
  printf 'Shared model configuration must use mode 0600 or 0400: %s\n' "$JIUWENSWARM_AUTOOPS_MODEL_ENV" >&2
  return 1 2>/dev/null || exit 1
fi
mapfile -t model_values < <(python3 - "$JIUWENSWARM_AUTOOPS_MODEL_ENV" <<'PY'
import json
import re
import sys
from pathlib import Path

names = ("API_BASE", "API_KEY", "MODEL_NAME", "MODEL_PROVIDER")
values = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    match = re.fullmatch(r"\s*([A-Z_]+)\s*=\s*(.*?)\s*", line)
    if not match or match.group(1) not in names:
        continue
    raw = match.group(2)
    try:
        value = json.loads(raw) if raw.startswith('"') else raw.strip("'\"")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {match.group(1)} value in model.env: {exc}")
    values[match.group(1)] = value
for name in names:
    value = values.get(name, "")
    if not isinstance(value, str) or not value or "\n" in value or "\t" in value:
        raise SystemExit(f"Shared model configuration is missing or invalid {name}")
    print(value)
PY
)
if [[ ${#model_values[@]} -ne 4 ]]; then
  printf 'Could not parse shared model configuration: %s\n' "$JIUWENSWARM_AUTOOPS_MODEL_ENV" >&2
  return 1 2>/dev/null || exit 1
fi
API_BASE="${model_values[0]}"
API_KEY="${model_values[1]}"
MODEL_NAME="${model_values[2]}"
MODEL_PROVIDER="${model_values[3]}"
export API_BASE API_KEY MODEL_NAME MODEL_PROVIDER
