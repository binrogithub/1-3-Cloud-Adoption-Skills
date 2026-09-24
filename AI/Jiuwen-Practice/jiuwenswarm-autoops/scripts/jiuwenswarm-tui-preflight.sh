#!/usr/bin/env bash
set -Eeuo pipefail

for command_name in jiuwenswarm jiuwenswarm-start; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "${command_name}" >&2
    exit 1
  }
done

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/load-model-env.sh"

if [[ "${API_BASE%/}" != https://* ]]; then
  printf 'API_BASE must use https\n' >&2
  exit 1
fi

case "${MODEL_PROVIDER}" in
  OpenAI|openai|openai_compatible) ;;
  *)
    printf 'MODEL_PROVIDER must be an OpenAI-compatible provider value\n' >&2
    exit 1
    ;;
esac

printf 'JiuwenSwarm preflight ready: command=%s, model=%s, endpoint=%s\n' \
  "$(command -v jiuwenswarm)" "${MODEL_NAME}" "${API_BASE%/}"
