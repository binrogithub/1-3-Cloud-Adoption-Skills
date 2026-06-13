#!/usr/bin/env bash
# Wire claude-glm on the laptop:
#   - Mint a LiteLLM virtual key.
#   - Install ~/.local/bin/claude-glm, ~/.config/claude-glm/env,
#     ~/.claude-code-router/config.json.
#   - Register the SearXNG MCP under CLAUDE_CONFIG_DIR=~/.claude-glm-config so
#     the user's plain `claude` is unaffected.
#
# Required env:
#   ECS_PUBLIC_IP             public IP of the gateway ECS
#   LITELLM_MASTER_KEY        admin key on LiteLLM
#   MCP_TOKEN                 bearer token for searxng-mcp
#
# Optional:
#   ASSETS_DIR                where this skill's assets/ live (defaults to repo)

set -euo pipefail

: "${ECS_PUBLIC_IP:?missing}"
: "${LITELLM_MASTER_KEY:?missing}"
: "${MCP_TOKEN:?missing}"

ASSETS_DIR=${ASSETS_DIR:-"$(cd "$(dirname "$0")/../assets/config" && pwd)"}

echo "[1/5] mint virtual key on LiteLLM"
LITELLM_VIRTUAL_KEY=$(curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    -H 'Content-Type: application/json' \
    -X POST "http://$ECS_PUBLIC_IP:4000/key/generate" \
    -d '{"key_alias":"claude-glm-operator"}' \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")

echo "    LITELLM_VIRTUAL_KEY=$LITELLM_VIRTUAL_KEY"

echo "[2/5] write laptop env file"
mkdir -p "$HOME/.config/claude-glm" "$HOME/.claude-code-router" "$HOME/.claude-glm-config"
cat > "$HOME/.config/claude-glm/env" <<EOF
export LITELLM_VIRTUAL_KEY="$LITELLM_VIRTUAL_KEY"
export CLAUDE_GLM_ROUTER_KEY="claude-glm-local"
EOF
chmod 600 "$HOME/.config/claude-glm/env"

echo "[3/5] write ccr config"
sed "s|@@ECS_PUBLIC_IP@@|$ECS_PUBLIC_IP|g" \
    "$ASSETS_DIR/claude-code-router.config.json.example" \
    > "$HOME/.claude-code-router/config.json"
chmod 600 "$HOME/.claude-code-router/config.json"

echo "[4/5] install wrapper"
mkdir -p "$HOME/.local/bin"
install -m 755 "$ASSETS_DIR/claude-glm-wrapper.sh.example" "$HOME/.local/bin/claude-glm"

ccr stop >/dev/null 2>&1 || true
sleep 1
# Source the env so the variables exist for the ccr child process.
# shellcheck disable=SC1090
source "$HOME/.config/claude-glm/env"
ccr start >/dev/null

echo "[5/5] register MCP under isolated config dir"
CLAUDE_CONFIG_DIR="$HOME/.claude-glm-config" \
    claude mcp remove searxng >/dev/null 2>&1 || true
CLAUDE_CONFIG_DIR="$HOME/.claude-glm-config" claude mcp add \
    --transport http --scope user searxng \
    "http://$ECS_PUBLIC_IP:8788/mcp" \
    --header "Authorization: Bearer $MCP_TOKEN"

echo
echo "verify:"
echo "  claude mcp list                                  # should NOT show searxng"
echo "  CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp list   # should show searxng"
echo "  claude-glm -p '只回复两个字：你好'"
