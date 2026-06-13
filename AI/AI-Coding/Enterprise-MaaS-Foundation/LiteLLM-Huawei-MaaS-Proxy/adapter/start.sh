#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_FILE="${PID_FILE:-/tmp/litellm-anthropic-adapter.pid}"
LOG_FILE="${LOG_FILE:-/tmp/litellm-anthropic-adapter.log}"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "adapter already running: pid $(cat "$PID_FILE")"
  exit 0
fi

if command -v setsid >/dev/null 2>&1; then
  setsid node server.js > "$LOG_FILE" 2>&1 < /dev/null &
else
  nohup node server.js > "$LOG_FILE" 2>&1 < /dev/null &
fi
echo "$!" > "$PID_FILE"

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:4010/health >/dev/null 2>&1; then
    echo "adapter started: http://127.0.0.1:4010"
    exit 0
  fi
  sleep 0.2
done

echo "adapter failed to start; see $LOG_FILE" >&2
exit 1
