#!/usr/bin/env bash
# Idempotent client-side installer for a laptop joining an already-running
# LiteLLM + SearXNG gateway. Does NOT mint a virtual key; the operator
# provides one. For the operator-side wrapper that mints a new key see
# scripts/wire_claude_glm.sh instead.
#
# Required env (caller exports them, never hardcode):
#   ECS_PUBLIC_IP            public IPv4 of the gateway ECS
#   LITELLM_VIRTUAL_KEY      virtual key minted by the operator for this laptop
#   MCP_TOKEN                bearer token configured on searxng-mcp.service
#
# Optional:
#   ASSETS_DIR               where this skill's assets/ live (default: skill local)
#
# Usage:
#   ECS_PUBLIC_IP=... LITELLM_VIRTUAL_KEY=... MCP_TOKEN=... \
#     bash scripts/install_claude_glm_client.sh

set -euo pipefail

: "${ECS_PUBLIC_IP:?missing}"
: "${LITELLM_VIRTUAL_KEY:?missing}"
: "${MCP_TOKEN:?missing}"

SKILL_DIR=${SKILL_DIR:-"$(cd "$(dirname "$0")/.." && pwd)"}
ASSETS_DIR=${ASSETS_DIR:-"$SKILL_DIR/assets/config"}

for cmd in claude ccr curl install sed openssl; do
    command -v "$cmd" >/dev/null || { echo "missing tool: $cmd" >&2; exit 127; }
done

echo "[1/6] preflight"
LAPTOP_IP=$(curl -s -m 5 https://ifconfig.me || true)
echo "    laptop egress IP: ${LAPTOP_IP:-<unknown>}"
echo "    gateway: $ECS_PUBLIC_IP"

LIVE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" \
       "http://$ECS_PUBLIC_IP:4000/health/liveliness" || true)
if [ "$LIVE" != "200" ]; then
    echo "    LiteLLM /health/liveliness returned http=$LIVE." >&2
    echo "    Likely the SG does not trust ${LAPTOP_IP:-this laptop}'s /32 yet." >&2
    echo "    Ask the operator to whitelist tcp/22, tcp/4000, tcp/8788 for that IP." >&2
    exit 2
fi

NOAUTH=$(curl -s -m 10 -o /dev/null -w "%{http_code}" -X POST \
         "http://$ECS_PUBLIC_IP:8788/mcp" \
         -H 'Content-Type: application/json' \
         -H 'Accept: application/json,text/event-stream' \
         -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' || true)
if [ "$NOAUTH" != "401" ]; then
    echo "    MCP /mcp without auth returned http=$NOAUTH (expected 401)." >&2
    echo "    The MCP server may be down, or the SG is dropping you on tcp/8788." >&2
    exit 3
fi

echo "[2/6] write env file"
mkdir -p "$HOME/.config/claude-glm"
cat > "$HOME/.config/claude-glm/env" <<EOF
export LITELLM_VIRTUAL_KEY="$LITELLM_VIRTUAL_KEY"
export CLAUDE_GLM_ROUTER_KEY="claude-glm-local"
EOF
chmod 600 "$HOME/.config/claude-glm/env"

echo "[3/6] write ccr config"
mkdir -p "$HOME/.claude-code-router"
sed "s|@@ECS_PUBLIC_IP@@|$ECS_PUBLIC_IP|g" \
    "$ASSETS_DIR/claude-code-router.config.json.example" \
    > "$HOME/.claude-code-router/config.json"
chmod 600 "$HOME/.claude-code-router/config.json"

echo "[4/6] install wrapper"
mkdir -p "$HOME/.local/bin"
install -m 755 \
    "$ASSETS_DIR/claude-glm-wrapper.sh.example" \
    "$HOME/.local/bin/claude-glm"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "    note: \$HOME/.local/bin is not in PATH; add it to your shell rc";;
esac

echo "[5/6] (re)start ccr with env loaded"
ccr stop >/dev/null 2>&1 || true
sleep 1
# shellcheck disable=SC1090
source "$HOME/.config/claude-glm/env"
ccr start >/dev/null
sleep 2

echo "[6/6] register SearXNG MCP under isolated CLAUDE_CONFIG_DIR"
mkdir -p "$HOME/.claude-glm-config"
CLAUDE_CONFIG_DIR="$HOME/.claude-glm-config" \
    claude mcp remove searxng >/dev/null 2>&1 || true
CLAUDE_CONFIG_DIR="$HOME/.claude-glm-config" claude mcp add \
    --transport http --scope user searxng \
    "http://$ECS_PUBLIC_IP:8788/mcp" \
    --header "Authorization: Bearer $MCP_TOKEN"

echo
echo "done. verify with:"
echo "  claude mcp list                                   # should NOT show searxng"
echo "  CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp list   # should show searxng"
echo "  claude-glm -p '只回复两个字：你好'"
echo "  claude-glm --permission-mode bypassPermissions -p '用 mcp__searxng__web_search 查 Anthropic，返回前 3 条 title+url。'"
