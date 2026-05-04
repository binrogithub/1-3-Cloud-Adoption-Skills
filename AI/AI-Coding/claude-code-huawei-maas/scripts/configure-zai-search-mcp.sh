#!/usr/bin/env bash
set -euo pipefail

ZAI_MCP_NAME="${ZAI_MCP_NAME:-web-search-prime}"
ZAI_MCP_URL="${ZAI_MCP_URL:-https://api.z.ai/api/mcp/web_search_prime/mcp}"
CLAUDE_USER_CONFIG="${CLAUDE_USER_CONFIG:-$HOME/.claude.json}"
VERIFY="${VERIFY:-1}"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

if [ -z "${Z_API_KEY:-}" ]; then
  die "Z_API_KEY is not set. Create a Z.ai API key and export Z_API_KEY before running this script."
fi

need_cmd node
need_cmd python3

mkdir -p "$(dirname "$CLAUDE_USER_CONFIG")"

CLAUDE_USER_CONFIG="$CLAUDE_USER_CONFIG" \
ZAI_MCP_NAME="$ZAI_MCP_NAME" \
ZAI_MCP_URL="$ZAI_MCP_URL" \
node <<'NODE'
const fs = require("fs");

const configPath = process.env.CLAUDE_USER_CONFIG;
const name = process.env.ZAI_MCP_NAME || "web-search-prime";
const url = process.env.ZAI_MCP_URL || "https://api.z.ai/api/mcp/web_search_prime/mcp";
const headersHelper = "python3 -c 'import json, os; print(json.dumps({\"Authorization\": \"Bearer \" + os.environ[\"Z_API_KEY\"]}))'";

let config = {};
if (fs.existsSync(configPath)) {
  const raw = fs.readFileSync(configPath, "utf8").trim();
  if (raw) {
    config = JSON.parse(raw);
  }
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  fs.copyFileSync(configPath, `${configPath}.backup.${stamp}`);
}

if (!config.mcpServers || typeof config.mcpServers !== "object" || Array.isArray(config.mcpServers)) {
  config.mcpServers = {};
}

config.mcpServers[name] = {
  type: "http",
  url,
  headersHelper,
};

fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
NODE

echo "configured: Claude Code MCP $ZAI_MCP_NAME -> $ZAI_MCP_URL"
echo "config: $CLAUDE_USER_CONFIG"

if [ "$VERIFY" = "1" ]; then
  need_cmd claude
  claude mcp get "$ZAI_MCP_NAME"
fi
