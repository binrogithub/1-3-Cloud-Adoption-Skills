#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${PID_FILE:-/tmp/litellm-anthropic-adapter.pid}"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")"
  rm -f "$PID_FILE"
  echo "adapter stopped"
else
  echo "adapter is not running"
fi
