# SearXNG MCP HTTP Server

A minimal FastMCP 2.x HTTP server that wraps a local SearXNG instance and
exposes two tools: `web_search` and `fetch_url`. Bearer-token authenticated.

## Why local SearXNG + remote MCP

We deliberately put SearXNG on `127.0.0.1` and only expose the **MCP** layer
externally. Reasons:

- SearXNG has no auth and would otherwise need `nginx`/Caddy reverse-proxy
  with basic-auth or mTLS to be safe on the public internet.
- The MCP layer enforces a static bearer token and the SG ACL.
- The MCP layer normalizes outputs (truncated snippets, capped result count)
  and lets us add rate limiting or domain allow-lists later without changing
  SearXNG.
- A single SG rule (`8788/tcp` from operator `/32`) is the only outside-facing
  surface for search.

## SearXNG must enable JSON

In `searxng/settings.yml`:

```yaml
search:
  formats:
    - html
    - json
```

Without `json` in the formats list, SearXNG returns HTML and the MCP server
will fail to decode the response. The first time we deployed this, the MCP
returned an opaque parse error and it took 5 minutes to realize the cause.

## FastMCP 2.x server

The full file lives in `assets/config/searxng_mcp_server.py`. Key points:

- `from fastmcp import FastMCP`
- `mcp = FastMCP(name="searxng")`
- Decorate tools with `@mcp.tool` and an annotated signature; FastMCP derives
  the JSON schema from the type hints and docstring.
- `mcp.auth = StaticTokenVerifier(tokens={TOKEN: {"client_id": "..."}})` BEFORE
  `mcp.run(...)`.

The non-obvious import:

```python
# CORRECT in FastMCP 2.14+:
from fastmcp.server.auth import StaticTokenVerifier

# WRONG (older tutorials still show this; will ModuleNotFoundError):
from fastmcp.server.auth.providers.bearer import StaticTokenVerifier
```

Run with HTTP (streamable) transport:

```python
mcp.run(transport="http", host="0.0.0.0", port=8788)
```

This exposes `POST /mcp` accepting `application/json` requests and producing
SSE responses.

## HTTP transport handshake

```
POST /mcp        Authorization: Bearer <token>
                 Content-Type: application/json
                 Accept: application/json,text/event-stream
                 body = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{
                   "protocolVersion":"2024-11-05",
                   "capabilities":{},
                   "clientInfo":{"name":"<client>","version":"<v>"}}}

200 OK           mcp-session-id: <session>
                 Content-Type: text/event-stream
                 data: {"jsonrpc":"2.0","id":1,"result":{...}}

POST /mcp        + mcp-session-id header
                 body = {"jsonrpc":"2.0","method":"notifications/initialized"}
202 Accepted

POST /mcp        + mcp-session-id header
                 body = {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
data: {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}

POST /mcp        + mcp-session-id header
                 body = {"jsonrpc":"2.0","id":3,"method":"tools/call",
                         "params":{"name":"web_search","arguments":{"query":"..."}}}
data: {"jsonrpc":"2.0","id":3,"result":{"content":[...],"structuredContent":{...}}}
```

`Accept: application/json,text/event-stream` is required by FastMCP. Plain
`application/json` is rejected at this version.

## Tool surface

```python
@mcp.tool
async def web_search(query: str, num_results: int = 8,
                     language: str = "auto") -> list[dict]:
    """Returns [{title, url, snippet}, ...] up to num_results."""

@mcp.tool
async def fetch_url(url: str, max_chars: int = 6000) -> str:
    """Returns the textual body of url, truncated to max_chars."""
```

`web_search` returns a list of dicts; `structuredContent.result` in the JSON-RPC
response carries the parsed list, which Claude Code consumes natively.
`fetch_url` returns a string; the wrapper field is `structuredContent.result`
as well.

We deliberately do not return SearXNG's full result fields (engines list,
parsed_url, scores). They balloon token usage with no benefit to the agent.

## Securing the bearer token

The token lives in three places:

- `Environment=MCP_TOKEN=<token>` inside `/etc/systemd/system/searxng-mcp.service`.
- `Authorization: Bearer <token>` registered into Claude Code via
  `claude mcp add --header "Authorization: Bearer ..."` (stored in
  `~/.claude-glm-config/.claude.json`).
- A copy in your local secret store / `~/.config/claude-glm/env` if you script
  re-registration.

Rotation:

1. Generate a new token: `NEW=$(openssl rand -hex 16)`.
2. `sudo sed -i "s/^Environment=MCP_TOKEN=.*/Environment=MCP_TOKEN=$NEW/" \
       /etc/systemd/system/searxng-mcp.service`
3. `sudo systemctl daemon-reload && sudo systemctl restart searxng-mcp.service`.
4. On the laptop:
   `CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp remove searxng`
   then re-add with the new bearer.

## Operational concerns

- **Output budget**: snippet capped at 500 chars per result; result count
  capped at 20. Adjust in the server if needed.
- **Outbound**: the MCP makes outbound HTTP from the ECS to the public web
  via SearXNG. The ECS already needs an EIP for LiteLLM-to-MaaS, so this is
  free of additional networking cost.
- **Search engines**: SearXNG defaults are usually enough for an English/Chinese
  coding agent. To enable specific engines or disable noisy ones, edit
  `searxng/settings.yml > engines`.
- **Latency**: typical end-to-end (claude-glm → ccr → LiteLLM → MaaS plus
  parallel MCP search) is 3–8 seconds wall clock for short prompts. Most of
  that is GLM-5.1 reasoning tokens, not network.
- **Failures**: SearXNG returns 200 with `results: []` when all engines fail
  simultaneously (rate limit, captcha). The MCP returns an empty list; the
  agent then either retries or answers without search.

## Optional hardening

- Run SearXNG behind an internal Caddy with basic-auth and only let the MCP
  server reach it; useful if multiple MCPs share the host.
- Add IP allow-listing in the FastMCP server's middleware to refuse anything
  outside the laptop CIDR even before token check.
- Replace `StaticTokenVerifier` with `JWTVerifier` if multiple users will
  share the MCP and you want short-lived tokens.
