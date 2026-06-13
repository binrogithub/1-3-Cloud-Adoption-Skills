#!/usr/bin/env bash
# Idempotent installer for the LiteLLM Anthropic adapter.
#
# Copies adapter/{server.js,start.sh,stop.sh} from this repo into
# ~/litellm-anthropic-adapter/ (the path the claude-glm wrapper's
# ensure_anthropic_adapter expects), backing up differing files as
# .bak.<timestamp>, then starts the adapter and verifies /health on 4010.
set -euo pipefail

ADAPTER_DEST="${ADAPTER_DEST:-$HOME/litellm-anthropic-adapter}"
ADAPTER_HEALTH_URL="${ADAPTER_HEALTH_URL:-http://127.0.0.1:4010/health}"
VERIFY="${VERIFY:-1}"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

need_cmd node
need_cmd curl

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTER_SRC="$SCRIPT_DIR/../adapter"
[ -d "$ADAPTER_SRC" ] || die "adapter source directory not found: $ADAPTER_SRC"

for f in server.js start.sh stop.sh; do
  [ -f "$ADAPTER_SRC/$f" ] || die "missing source file: $ADAPTER_SRC/$f"
done

mkdir -p "$ADAPTER_DEST"

timestamp="$(date +%Y%m%d%H%M%S)"
for f in server.js start.sh stop.sh; do
  src="$ADAPTER_SRC/$f"
  dest="$ADAPTER_DEST/$f"
  if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
    echo "unchanged: $dest (skip)"
    continue
  fi
  if [ -f "$dest" ]; then
    cp -p "$dest" "$dest.bak.$timestamp"
    echo "backup: $dest.bak.$timestamp"
  fi
  cp "$src" "$dest"
  echo "installed: $dest"
done

chmod +x "$ADAPTER_DEST/start.sh" "$ADAPTER_DEST/stop.sh"

if [ "$VERIFY" = "1" ]; then
  "$ADAPTER_DEST/start.sh"
  curl -fsS -m 5 "$ADAPTER_HEALTH_URL" >/dev/null ||
    die "adapter health check failed: $ADAPTER_HEALTH_URL"
  echo "verified: $ADAPTER_HEALTH_URL"
fi

echo "installed: litellm-anthropic-adapter -> $ADAPTER_DEST"
