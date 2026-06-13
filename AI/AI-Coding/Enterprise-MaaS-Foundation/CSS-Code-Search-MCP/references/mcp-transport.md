# MCP Transport and nginx Proxy

## FastMCP HTTP/SSE Transport

The CSS Code Search MCP server uses FastMCP's HTTP transport (Streamable HTTP), which:

- Listens on a configurable port (default 8789).
- Exposes a single `/mcp` endpoint.
- Requires `Accept: application/json, text/event-stream` for the SSE handshake.
- Uses session IDs for stateful communication.
- Supports bearer-token authentication via `StaticTokenVerifier`.

Direct curl testing will fail because curl doesn't implement the MCP SSE protocol. Use the MCP SDK client instead:

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async with streamablehttp_client(url="http://host:8789/mcp", headers={...}) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

## nginx Reverse Proxy

When an existing MCP server (e.g. SearXNG) already uses port 8788, nginx co-hosts both:

```
nginx :8788
  ├── /mcp      → 127.0.0.1:18788  (SearXNG MCP, moved from 8788)
  └── /css/mcp  → 127.0.0.1:8789   (CSS Code Search MCP)
```

### nginx Configuration

```nginx
server {
    listen 8788;

    location /mcp {
        proxy_pass http://127.0.0.1:18788;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Authorization $http_authorization;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    location /css/mcp {
        proxy_pass http://127.0.0.1:8789/mcp;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Authorization $http_authorization;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

Key settings:

- `proxy_http_version 1.1` + `proxy_set_header Connection ""`: required for SSE keep-alive.
- `proxy_buffering off`: prevents nginx from buffering SSE events.
- `proxy_read_timeout 300s`: allows long-running MCP sessions.
- `proxy_set_header Authorization`: passes bearer token through to the backend.

## Claude Code MCP Registration

In `~/.claude-glm-config/.claude.json`:

```json
{
  "mcpServers": {
    "searxng": {
      "type": "http",
      "url": "http://<ECS_IP>:8788/mcp",
      "headers": {"Authorization": "Bearer <SEARXNG_TOKEN>"}
    },
    "css-search": {
      "type": "http",
      "url": "http://<ECS_IP>:8788/css/mcp",
      "headers": {"Authorization": "Bearer <CSS_TOKEN>"}
    }
  }
}
```

Claude Code's MCP client handles the SSE transport, session management, and tool invocation natively. No additional bridge or tunnel software is needed on the laptop.

## Security

- Bearer tokens are generated with `openssl rand -hex 16` (128-bit entropy).
- Tokens are stored in `/opt/css_mcp_token` (root-only, 0600).
- Security group rules restrict port 8788 to the operator's `/32` CIDR.
- CSS port 9200 is private (no EIP, only reachable from ECS subnet).
