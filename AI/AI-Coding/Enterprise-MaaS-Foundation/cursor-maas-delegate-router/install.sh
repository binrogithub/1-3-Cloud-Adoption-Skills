#!/usr/bin/env bash
# USER-GLOBAL install: copy skill to ~/.cursor/skills + runtime + policy + hooks.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DST="${HOME}/.cursor/skills"
NAME="cursor-maas-delegate-router"
DST="${SKILLS_DST}/${NAME}"

mkdir -p "${SKILLS_DST}"
rm -rf "${DST}"
cp -a "${ROOT}" "${DST}"
# drop caches if any
find "${DST}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

echo "Installed skill: ${DST}"

ARGS=()
if [[ -n "${DELEGATE_API_KEY:-}" ]]; then
  ARGS+=(--api-key "${DELEGATE_API_KEY}")
elif [[ -n "${HUAWEI_MAAS_API_KEY:-}" ]]; then
  ARGS+=(--api-key "${HUAWEI_MAAS_API_KEY}")
fi
if [[ -n "${DELEGATE_API_BASE:-}" ]]; then
  ARGS+=(--base-url "${DELEGATE_API_BASE}")
elif [[ -n "${HUAWEI_MAAS_API_BASE:-}" ]]; then
  ARGS+=(--base-url "${HUAWEI_MAAS_API_BASE}")
fi
if [[ -n "${DELEGATE_MODEL:-}" ]]; then
  ARGS+=(--model "${DELEGATE_MODEL}")
fi

python3 "${DST}/scripts/install.py" "${ARGS[@]}"
echo "INSTALL SKILL OK — scope=USER-GLOBAL"
echo "Reload Cursor / start a new Agent chat."
