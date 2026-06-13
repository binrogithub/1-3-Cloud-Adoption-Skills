#!/usr/bin/env bash
# Install SearXNG (Docker) + SearXNG MCP HTTP server (FastMCP) on the same ECS.
# Idempotent.
#
# Required env:
#   MCP_TOKEN              the bearer token clients must send
#
# Usage:
#   ssh root@$ECS MCP_TOKEN=... bash /root/install_searxng_and_mcp.sh

set -euo pipefail

: "${MCP_TOKEN:?missing}"

echo "[1/6] docker"
if ! command -v docker >/dev/null; then
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose-v2
    systemctl enable --now docker
fi

echo "[2/6] searxng compose + settings"
mkdir -p /opt/searxng/searxng
SECRET=$(openssl rand -hex 32)
cat > /opt/searxng/docker-compose.yml <<'YAML'
services:
  searxng:
    image: docker.io/searxng/searxng:latest
    container_name: searxng
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://127.0.0.1:8080/
      - INSTANCE_NAME=ecs-searxng
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
YAML
cat > /opt/searxng/searxng/settings.yml <<EOF
use_default_settings: true
server:
  secret_key: "$SECRET"
  bind_address: "0.0.0.0"
  port: 8080
  limiter: false
  image_proxy: false
search:
  formats:
    - html
    - json
ui:
  static_use_hash: true
EOF

echo "[3/6] docker compose up"
cd /opt/searxng
docker compose pull >/dev/null
docker compose up -d
sleep 8
curl -s -G 'http://127.0.0.1:8080/search' \
    --data-urlencode 'q=hello' --data-urlencode 'format=json' \
    -H 'Accept: application/json' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('searxng results:', len(d.get('results',[])))"

echo "[4/6] searxng-mcp user and venv"
id searxmcp 2>/dev/null \
  || useradd --system --home /opt/searxng-mcp --shell /usr/sbin/nologin searxmcp
mkdir -p /opt/searxng-mcp
if [ ! -x /opt/searxng-mcp/venv/bin/python ]; then
    python3 -m venv /opt/searxng-mcp/venv
fi
/opt/searxng-mcp/venv/bin/pip install -q --upgrade pip
/opt/searxng-mcp/venv/bin/pip install -q "fastmcp>=2,<3" httpx

cat > /opt/searxng-mcp/server.py <<'PY'
"""SearXNG MCP HTTP server. Wraps a local SearXNG as an MCP web_search tool."""
import os
import httpx
from fastmcp import FastMCP

SEARXNG = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8080")
TOKEN = os.environ.get("MCP_TOKEN", "")
PORT = int(os.environ.get("MCP_PORT", "8788"))

mcp = FastMCP(name="searxng")


@mcp.tool
async def web_search(query: str, num_results: int = 8, language: str = "auto") -> list[dict]:
    """Search the web via SearXNG. Returns list of {title, url, snippet}."""
    num_results = max(1, min(20, num_results))
    params = {"q": query, "format": "json", "language": language, "safesearch": "1"}
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{SEARXNG}/search", params=params,
                        headers={"Accept": "application/json"})
        r.raise_for_status()
        data = r.json()
    out = []
    for it in (data.get("results") or [])[:num_results]:
        out.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "snippet": (it.get("content") or "")[:500],
        })
    return out


@mcp.tool
async def fetch_url(url: str, max_chars: int = 6000) -> str:
    """Fetch a URL and return its text content (truncated)."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "ecs-searxng-mcp/1.0"})
        r.raise_for_status()
    return r.text[:max_chars]


if __name__ == "__main__":
    if TOKEN:
        from fastmcp.server.auth import StaticTokenVerifier
        mcp.auth = StaticTokenVerifier(tokens={TOKEN: {"client_id": "claude-glm"}})
    mcp.run(transport="http", host="0.0.0.0", port=PORT)
PY
chown -R searxmcp:searxmcp /opt/searxng-mcp

echo "[5/6] systemd unit"
cat > /etc/systemd/system/searxng-mcp.service <<EOF
[Unit]
Description=SearXNG MCP HTTP server
After=docker.service
Wants=docker.service

[Service]
Type=simple
User=searxmcp
Group=searxmcp
WorkingDirectory=/opt/searxng-mcp
Environment=SEARXNG_URL=http://127.0.0.1:8080
Environment=MCP_PORT=8788
Environment=MCP_TOKEN=$MCP_TOKEN
ExecStart=/opt/searxng-mcp/venv/bin/python /opt/searxng-mcp/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now searxng-mcp.service

echo "[6/6] wait for listener"
for i in $(seq 1 15); do
    if ss -tlnp | grep -q ':8788'; then
        echo "searxng-mcp listening on :8788"
        break
    fi
    sleep 2
done
journalctl -u searxng-mcp.service -n 15 --no-pager | tail -15
