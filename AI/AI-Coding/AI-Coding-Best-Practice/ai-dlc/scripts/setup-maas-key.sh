#!/usr/bin/env bash
# setup-maas-key.sh — interactive MaaS credential entry for openjiuwen gateway.
#
# Reads the Huawei Cloud MaaS API key from a terminal prompt (hidden, read -rs)
# or from stdin (non-interactive/CI, IFS= read -r), and writes it into the
# openjiuwen gateway .env file.  Only replaces API_KEY=/API_BASE=/
# MODEL_PROVIDER=/MODEL_NAME= lines — every other variable in the .env file
# is preserved untouched.
#
# The key is read as DATA, never appears in argv, stdout, stderr, or logs.
# Atomic write via mktemp same-dir + chmod 600 + mv.
#
# Usage:
#   ./scripts/setup-maas-key.sh [--env-file <path>] [--force]
#   printf '%s\n' "$KEY" | ./scripts/setup-maas-key.sh   # non-interactive
set -euo pipefail

PY="$(command -v python3.12 || command -v python3 || echo ${HOME}/.local/bin/python3.12)"

DEFAULT_ENV_FILE="$HOME/.jiuwenswarm/config/.env"
DEFAULT_BASE_URL="https://api-ap-southeast-1.modelarts-maas.com/v1"
DEFAULT_MODEL_NAME="glm-5.2"

ENV_FILE="${DEFAULT_ENV_FILE}"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)    ENV_FILE="$2"; shift 2 ;;
    --env-file=*)  ENV_FILE="${1#--env-file=}"; shift ;;
    --force)       FORCE=1; shift ;;
    --help|-h)
      cat <<'USAGE'
setup-maas-key.sh — interactive MaaS credential entry for openjiuwen gateway

Options:
  --env-file <path>  target .env file (default: ~/.jiuwenswarm/config/.env)
  --force            suppress the "existing value" warning
USAGE
      exit 0 ;;
    *) shift ;;
  esac
done

# ── Read credentials ──────────────────────────────────────────
base_url=""
model_name=""
api_key=""

if [[ -t 0 ]]; then
  # Interactive terminal: prompt for each value
  read -r -p "Huawei Cloud MaaS API base URL [${DEFAULT_BASE_URL}]: " base_url
  base_url="${base_url:-${DEFAULT_BASE_URL}}"
  read -r -p "Model name [${DEFAULT_MODEL_NAME}]: " model_name
  model_name="${model_name:-${DEFAULT_MODEL_NAME}}"
  read -rs -p "Huawei Cloud MaaS API key (input hidden): " api_key
  echo
else
  # Non-interactive (pipe/CI): read one line from stdin as the key
  IFS= read -r api_key || true
  api_key="${api_key%$'\r'}"
  base_url="${DEFAULT_BASE_URL}"
  model_name="${DEFAULT_MODEL_NAME}"
fi

# Reject empty / whitespace-only key
if [[ ! "${api_key}" =~ [^[:space:]] ]]; then
  echo "setup-maas-key: api key must not be empty or whitespace-only" >&2
  exit 1
fi

# ── Warn on existing non-empty API_KEY (but still write) ───────
if [[ -f "${ENV_FILE}" ]] && [[ "${FORCE}" == "0" ]]; then
  existing_key=""
  if grep -q '^API_KEY=' "${ENV_FILE}" 2>/dev/null; then
    existing_key="$(grep '^API_KEY=' "${ENV_FILE}" | head -1 | cut -d= -f2-)"
  fi
  if [[ -n "${existing_key}" ]]; then
    echo "setup-maas-key: WARNING — ${ENV_FILE} already has an API_KEY value." >&2
    echo "setup-maas-key: Use --force to suppress this warning. Writing anyway." >&2
  fi
fi

# ── Write to .env file ────────────────────────────────────────
# Replace or append API_KEY=/API_BASE=/MODEL_PROVIDER=/MODEL_NAME= lines.
# All other lines preserved untouched.  The key is passed via a temp file
# (chmod 600), never via argv or env.
mkdir -p "$(dirname "${ENV_FILE}")"

KEY_TMP="$(mktemp)"
chmod 600 "${KEY_TMP}"
printf '%s\n' "${api_key}" > "${KEY_TMP}"
trap 'rm -f "${KEY_TMP}"' EXIT

"${PY}" - "${ENV_FILE}" "${base_url}" "${model_name}" "${KEY_TMP}" <<'PYEOF'
import os, sys, tempfile

env_file   = sys.argv[1]
base_url   = sys.argv[2]
model_name = sys.argv[3]
key_file   = sys.argv[4]

with open(key_file, "r", encoding="utf-8") as f:
    api_key = f.readline().rstrip("\n")

# Read existing content (if any)
try:
    lines = open(env_file, encoding="utf-8").read().splitlines()
except FileNotFoundError:
    lines = []

replacements = {
    "API_KEY":         api_key,
    "API_BASE":        base_url,
    "MODEL_NAME":      model_name,
    "MODEL_PROVIDER":  "OpenAI",
}

seen = set()
out = []
for ln in lines:
    replaced = False
    for var in replacements:
        if ln.startswith(var + "="):
            out.append(f"{var}={replacements[var]}")
            seen.add(var)
            replaced = True
            break
    if not replaced:
        out.append(ln)

# Append any variables that weren't already present
for var, val in replacements.items():
    if var not in seen:
        out.append(f"{var}={val}")

result = "\n".join(out) + "\n"

# Atomic write: mktemp in same dir + mv
d = os.path.dirname(env_file) or "."
fd, tmp = tempfile.mkstemp(dir=d)
os.write(fd, result.encode("utf-8"))
os.close(fd)
os.chmod(tmp, 0o600)
os.rename(tmp, env_file)
PYEOF

rm -f "${KEY_TMP}"
trap - EXIT

echo "setup-maas-key: MaaS credentials written to ${ENV_FILE}"
echo "setup-maas-key: base_url=${base_url} model_name=${model_name}"

# ── Offer to restart the gateway ──────────────────────────────
echo "Restart jiuwenswarm-gateway to apply? [y/N]"
if [[ -t 0 ]]; then
  read -r -p "> " answer
else
  IFS= read -r answer || true
fi
if [[ "${answer}" == "y" || "${answer}" == "Y" ]]; then
  systemctl restart jiuwenswarm-gateway && echo "setup-maas-key: gateway restarted" \
    || echo "setup-maas-key: gateway restart failed — run: systemctl restart jiuwenswarm-gateway" >&2
else
  echo "setup-maas-key: skip restart — run 'systemctl restart jiuwenswarm-gateway' when ready"
fi
