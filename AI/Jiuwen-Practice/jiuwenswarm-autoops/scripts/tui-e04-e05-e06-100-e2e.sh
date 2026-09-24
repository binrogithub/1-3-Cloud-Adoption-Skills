#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

RUN_PREFIX=e040506-100a bash "$SCRIPT_DIR/tui-e04-e05-e06-50-e2e.sh"
RUN_PREFIX=e040506-100b START_AT=51 bash "$SCRIPT_DIR/tui-e04-e05-e06-100b-e2e.sh"

printf 'TUI_100_E2E_RESULT=PASS total=100\n'
