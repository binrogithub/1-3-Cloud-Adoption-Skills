#!/usr/bin/env bash
# deploy_css_mcp.sh — One-shot deploy: index repo + start MCP server + configure nginx
#
# Usage:
#   deploy_css_mcp.sh <state_json_path> [repo_url_override]
#
# Example:
#   deploy_css_mcp.sh css-search-20260508123456-state.json
#   deploy_css_mcp.sh css-search-20260508123456-state.json https://github.com/org/other-repo

set -euo pipefail

STATE_PATH="${1:?Usage: deploy_css_mcp.sh <state.json> [repo_url_override]}"
REPO_URL_OVERRIDE="${2:-}"

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required. Install with: apt-get install jq / brew install jq"
    exit 1
fi

STATE=$(cat "$STATE_PATH")

# Extract values from state JSON
REPO_URL="${REPO_URL_OVERRIDE:-$(echo "$STATE" | jq -r '.repo_url')}"
CSS_ENDPOINT=$(echo "$STATE" | jq -r '.css_endpoint')
CSS_IP=$(echo "$CSS_ENDPOINT" | sed 's|http://||;s|:9200||')
ECS_IP=$(echo "$STATE" | jq -r '.ecs_public_ip')
SSH_KEY=$(echo "$STATE" | jq -r '.ssh_key_path')
SSH_USER=$(echo "$STATE" | jq -r '.ssh_user // "root"')
CIDR=$(echo "$STATE" | jq -r '.allowed_cidr')
INDEX_NAME=$(basename "$REPO_URL" .git | tr '[:upper:]' '[:lower:]')
CSS_URL="http://${CSS_IP}:9200"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o BatchMode=yes $SSH_USER@$ECS_IP"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

echo "=== CSS Code Search MCP Deploy ==="
echo "State:     $STATE_PATH"
echo "Repo:      $REPO_URL"
echo "CSS:       $CSS_URL"
echo "ECS:       $SSH_USER@$ECS_IP"
echo "SSH key:   $SSH_KEY"
echo "Index:     $INDEX_NAME"
echo ""

# --- Step 1: Verify CSS ---
echo "--- Step 1: Verify CSS connectivity ---"
CSS_RESP=$($SSH "curl -s --connect-timeout 5 $CSS_URL" 2>/dev/null || "")
if echo "$CSS_RESP" | grep -q "You Know, for Search"; then
    echo "CSS is reachable at $CSS_URL"
else
    echo "ERROR: CSS not reachable at $CSS_URL. Scanning subnet..."
    $SSH "for ip in ${CSS_IP%.*}.{1..254}; do
      code=\$(curl -s --connect-timeout 1 -o /dev/null -w '%{http_code}' http://\$ip:9200 2>/dev/null)
      [ \"\$code\" != \"000\" ] && echo \"  Found: \$ip:9200 (HTTP \$code)\"
    done"
    echo "Update css_endpoint in state JSON and re-run."
    exit 1
fi

# --- Step 2: Clone and index repo ---
echo "--- Step 2: Clone and index repo ---"
REPO_NAME=$(basename "$REPO_URL" .git)
$SSH "cd /tmp && rm -rf $REPO_NAME && git clone --depth 1 $REPO_URL" 2>/dev/null
$SCP scripts/index_repo_to_css.py $SSH_USER@$ECS_IP:/opt/index_repo_to_css.py 2>/dev/null
$SSH "pip3 install -q requests 2>/dev/null; python3 /opt/index_repo_to_css.py /tmp/$REPO_NAME $CSS_URL $INDEX_NAME"

# --- Step 3: Deploy MCP server ---
echo "--- Step 3: Deploy MCP server ---"
$SCP assets/config/css_mcp_server.py $SSH_USER@$ECS_IP:/opt/css_mcp_server.py 2>/dev/null
$SSH "pip3 install -q fastmcp httpx 2>/dev/null"

MCP_TOKEN=$($SSH "openssl rand -hex 16")
$SSH "echo $MCP_TOKEN > /opt/css_mcp_token"
$SSH "pkill -f css_mcp_server.py 2>/dev/null; sleep 1"
$SSH "nohup env CSS_INDEX=$INDEX_NAME MCP_TOKEN=$MCP_TOKEN python3 /opt/css_mcp_server.py > /var/log/css_mcp_server.log 2>&1 &"
sleep 3
$SSH "ss -tlnp | grep 8789" && echo "MCP server running on :8789" || { echo "ERROR: MCP server not running"; exit 1; }

# --- Step 4: Configure nginx ---
echo "--- Step 4: Configure nginx reverse proxy ---"
$SSH "
  if ! command -v nginx &>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
  fi

  # Move existing SearXNG MCP behind nginx if it binds 8788 directly
  if ss -tlnp | grep -q ':8788' && ! ss -tlnp | grep -q 'nginx'; then
    echo 'Moving existing MCP from :8788 to :18788'
    if [ -f /etc/systemd/system/searxng-mcp.service ]; then
      sed -i 's/MCP_PORT=8788/MCP_PORT=18788/' /etc/systemd/system/searxng-mcp.service
      systemctl daemon-reload && systemctl restart searxng-mcp
    fi
  fi

  cat > /etc/nginx/sites-available/mcp-proxy << 'NGINX'
server {
    listen 8788;
    location /mcp {
        proxy_pass http://127.0.0.1:18788;
        proxy_http_version 1.1;
        proxy_set_header Connection \"\";
        proxy_set_header Authorization \$http_authorization;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
    location /css/mcp {
        proxy_pass http://127.0.0.1:8789/mcp;
        proxy_http_version 1.1;
        proxy_set_header Connection \"\";
        proxy_set_header Authorization \$http_authorization;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
NGINX
  ln -sf /etc/nginx/sites-available/mcp-proxy /etc/nginx/sites-enabled/mcp-proxy
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl enable nginx && systemctl restart nginx
"

# --- Step 5: Update state and print config ---
# Write MCP token back to state JSON
STATE_UPDATED=$(echo "$STATE" | jq --arg token "$MCP_TOKEN" '. + {mcp_token: $token}')
echo "$STATE_UPDATED" > "$STATE_PATH"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Add this to ~/.claude-glm-config/.claude.json -> mcpServers:"
echo ""
cat << JSON
"css-search": {
  "type": "http",
  "url": "http://$ECS_IP:8788/css/mcp",
  "headers": {
    "Authorization": "Bearer $MCP_TOKEN"
  }
}
JSON
echo ""
echo "Then restart claude-glm."
