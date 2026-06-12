#!/usr/bin/env bash
# Restore the verified claude-glm production CCR state from the repo archive:
# full 3-provider config (LiteLLM Anthropic Adapter / LiteLLM Provider /
# litellm-chat), the custom router with unknown-model rejection, and a ccr
# restart with the env vars the config placeholders need.
#
# Use this after anything rewrites ~/.claude-code-router/config.json to the
# legacy single-provider layout (symptoms: usage.input_tokens back to 0,
# unknown model names answered normally instead of rejected).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CCR_DIR="${CCR_DIR:-$HOME/.claude-code-router}"
GLM_ENV="${GLM_ENV:-$HOME/.config/claude-glm/env}"
LITELLM_ENV="${LITELLM_ENV:-/root/LiteLLM/.env}"
ROUTER_KEY_DEFAULT="claude-glm-local"

die() {
  echo "error: $*" >&2
  exit 1
}

[ -f "$REPO_DIR/assets/ccr/config.json" ] || die "archived config not found in repo"
[ -f "$REPO_DIR/assets/ccr/custom-router.js" ] || die "archived custom-router not found in repo"
[ -f "$GLM_ENV" ] || die "$GLM_ENV missing (HUAWEI_MAAS_API_KEY / CLAUDE_GLM_ROUTER_KEY)"
command -v ccr >/dev/null 2>&1 || die "ccr is not in PATH"

mkdir -p "$CCR_DIR"
for f in config.json custom-router.js; do
  if [ -f "$CCR_DIR/$f" ] && ! cmp -s "$REPO_DIR/assets/ccr/$f" "$CCR_DIR/$f"; then
    cp "$CCR_DIR/$f" "$CCR_DIR/$f.bak.$(date +%Y%m%d%H%M%S)"
  fi
  cp "$REPO_DIR/assets/ccr/$f" "$CCR_DIR/$f"
done
chmod 600 "$CCR_DIR/config.json"

# The adapter must be running for the default route; install script is idempotent.
"$REPO_DIR/scripts/install-anthropic-adapter.sh"

ccr stop >/dev/null 2>&1 || true
sleep 2
set -a
# shellcheck disable=SC1090
source "$GLM_ENV"
[ -f "$LITELLM_ENV" ] && source "$LITELLM_ENV"
set +a
if command -v setsid >/dev/null 2>&1; then
  setsid ccr start > /tmp/claude-glm-ccr.log 2>&1 < /dev/null &
else
  nohup ccr start > /tmp/claude-glm-ccr.log 2>&1 < /dev/null &
fi

ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-$ROUTER_KEY_DEFAULT}"
for _ in $(seq 1 30); do
  sleep 2
  # -m 30: a 200 needs one real 1-token inference round-trip (6-10s typical)
  status="$(curl -sS -m 30 -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $ROUTER_KEY" \
    -H 'content-type: application/json' \
    -d '{"model":"claude-opus-4-6","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}' \
    "http://127.0.0.1:3456/v1/messages" 2>/dev/null)" || status="000"
  case "$status" in
    200|400|404|5??) echo "restored: ccr healthy, authenticated POST -> HTTP $status"; exit 0 ;;
    401|403) die "router rejected $ROUTER_KEY (HTTP $status); check APIKEY expansion" ;;
  esac
done
die "ccr did not become healthy; see /tmp/claude-glm-ccr.log"
