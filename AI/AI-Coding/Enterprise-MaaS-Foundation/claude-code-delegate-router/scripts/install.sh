#!/usr/bin/env bash
# install.sh — thin entry point for the MaaS launcher installer.
#
# Delegates to client/claude-maas-setup.sh, which performs the actual
# credential storage and configuration. This wrapper exists so the public
# install interface matches docs/PRD.md §13.1:
#
#   printf '%s\n' "$HUAWEI_MAAS_API_KEY" | ./scripts/install.sh \
#     --base-url https://api-ap-southeast-1.modelarts-maas.com/anthropic \
#     --model glm-5.2
#
# The MaaS key is read from stdin and forwarded; it never appears in argv.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
setup="${script_dir}/../client/claude-maas-setup.sh"

if [[ ! -x "$setup" ]]; then
    echo "install: cannot find executable installer at $setup" >&2
    exit 1
fi

exec "$setup" "$@"