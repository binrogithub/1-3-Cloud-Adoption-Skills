# claude-glm Client + SearXNG Search Onboarding

This is an **optional** add-on layer for the LiteLLM Huawei MaaS Proxy. The core
skill (README/SKILL) deploys the Docker Compose proxy with Prometheus/Grafana.
This document covers two extra capabilities folded in from the former
single-ECS gateway skill:

1. **Self-hosted SearXNG search MCP** — a private meta-search exposed over a
   bearer-authenticated remote MCP (`web_search`, `fetch_url`), as a
   self-hosted alternative to the Exa search injection in `custom_callbacks.py`.
2. **`claude-glm` client wiring** — route Claude Code through
   `claude-code-router` (ccr) to this proxy, with `CLAUDE_CONFIG_DIR` isolation
   so the user's plain `claude` is untouched, and register the SearXNG MCP into
   that isolated client only.

Both are opt-in. Skip this file entirely if you only need the OpenAI-compatible
proxy + observability.

## Topology

```
Proxy host (Docker Compose)
├── litellm        :4000   master + virtual keys, FinOps, multi-key LB
├── db             :5432   keys, teams, spend                 (internal)
├── prometheus     :9090   metrics
├── grafana        :3000   dashboards
├── searxng        :8080   meta-search, JSON enabled          (internal, profile: search)
└── searxng-mcp    :8788   FastMCP HTTP, bearer-auth          (profile: search)

Client laptop
├── claude         → Anthropic (untouched)
└── claude-glm     → ccr :3456 → LiteLLM :4000 → MaaS glm-5.1
                    + remote MCP searxng :8788 (web_search, fetch_url)
                    CLAUDE_CONFIG_DIR=~/.claude-glm-config (isolation)
```

For a single-host setup the client and proxy can be the same machine
(`@@LITELLM_HOST@@` = `127.0.0.1`). For a remote proxy (e.g. a Huawei Cloud
ECS), set `@@LITELLM_HOST@@` to its address and CIDR-lock ports `4000` and
`8788` to the client's `/32` — never widen to `0.0.0.0/0`.

## 1. Enable the SearXNG search MCP

Render the SearXNG settings (the generated file is gitignored), set
`MCP_TOKEN` in `.env`, then start the optional profile:

```bash
# From the proxy directory:
sed "s/@@SEARXNG_SECRET@@/$(openssl rand -hex 32)/" \
  assets/config/searxng/settings.yml.example > assets/config/searxng/settings.yml

# Add a bearer token for the MCP to .env:
echo "MCP_TOKEN=$(openssl rand -hex 16)" >> .env

docker compose --profile search up -d
docker compose ps   # litellm_searxng + litellm_searxng_mcp should be running
```

`searxng-settings.yml` must keep `search.formats: [html, json]`. Without `json`
the MCP receives HTML and tool calls fail with an opaque parse error. SearXNG is
bound internally only (`expose: 8080`); the MCP on `:8788` is the public face.

Smoke-test the MCP (expect `401` without the token, `200` with it):

```bash
source .env
curl -s -o /dev/null -w "no_auth=%{http_code}\n" -X POST \
  http://@@LITELLM_HOST@@:8788/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
# expect: no_auth=401
```

> FastMCP note: in FastMCP 2.14+, `StaticTokenVerifier` is imported from
> `fastmcp.server.auth` (not `...auth.providers.bearer`), and `mcp.auth` must be
> set before `mcp.run(...)`. The bundled `searxng_mcp_server.py` already does this.

## 2. Mint a per-client virtual key

Give each client its own LiteLLM virtual key for clean spend attribution and
revocation. Use the bundled FinOps helper:

```bash
python3 scripts/bootstrap_finops_team.py \
  --proxy-base-url http://@@LITELLM_HOST@@:4000 \
  --master-key "$LITELLM_MASTER_KEY" \
  --team-alias laptop-alice \
  --model huawei/glm-5.1 \
  --max-budget 20 --budget-duration 30d --tpm-limit 500000 --rpm-limit 30
# prints {"team_id", "issued_key", ...} — hand the key to the client out-of-band
```

Or mint directly with `POST /key/generate` (see SKILL "Virtual key management").

## 3. Wire `claude-glm` on the client

Prerequisites on the client laptop:

```bash
curl -fsSL https://claude.com/install.sh | bash    # or: npm i -g @anthropic-ai/claude-code
npm i -g @musistudio/claude-code-router             # the ccr binary
claude --version && ccr --version
```

### 3a. Local env file

```bash
mkdir -p ~/.config/claude-glm
cat > ~/.config/claude-glm/env <<'EOF'
export LITELLM_VIRTUAL_KEY="<the-issued-virtual-key>"
export CLAUDE_GLM_ROUTER_KEY="claude-glm-local"
EOF
chmod 600 ~/.config/claude-glm/env
```

`CLAUDE_GLM_ROUTER_KEY` is a local-only token between the wrapper and ccr; any
non-empty value works. Use the literal `claude-glm-local` to match the example.

### 3b. ccr config

```bash
mkdir -p ~/.claude-code-router
sed "s|@@LITELLM_HOST@@|127.0.0.1|g" \
  assets/config/claude-code-router.config.json.example \
  > ~/.claude-code-router/config.json
chmod 600 ~/.claude-code-router/config.json
```

Replace `127.0.0.1` with the proxy host if remote. The config uses
`$LITELLM_VIRTUAL_KEY` indirection — never paste the literal key into
`config.json`.

### 3c. Wrapper

```bash
mkdir -p ~/.local/bin
install -m 755 assets/config/claude-glm-wrapper.sh.example ~/.local/bin/claude-glm
# ensure ~/.local/bin is on PATH
```

The shipped wrapper sets `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`,
`CLAUDE_CONFIG_DIR=~/.claude-glm-config` (isolation), keeps auto-compact on, and
leaves ~8% headroom under GLM-5.1's 196608-token input ceiling
(`CLAUDE_CODE_MAX_CONTEXT_TOKENS=180000`). Do not lower the headroom.

### 3d. Start ccr with the env loaded

```bash
source ~/.config/claude-glm/env
ccr stop 2>/dev/null || true
ccr start
```

If ccr starts before `LITELLM_VIRTUAL_KEY` is in its environment, every request
returns `401` upstream. The wrapper guards auto-start; a manual `ccr start` does
not, so always source the env file first. ccr has no SIGHUP — restart to pick up
config changes.

## 4. Register the SearXNG MCP into `claude-glm` only

```bash
mkdir -p ~/.claude-glm-config
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp add \
  --transport http --scope user searxng \
  http://@@LITELLM_HOST@@:8788/mcp \
  --header "Authorization: Bearer <MCP_TOKEN>"

CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp list   # shows searxng ✓
claude mcp list                                          # does NOT show searxng
```

The isolation is the point of `CLAUDE_CONFIG_DIR`: the user's plain `claude`
never sees or triggers the SearXNG tool.

## 5. Verify end-to-end

```bash
# ccr → LiteLLM → MaaS
claude-glm -p '只回复两个字：你好'         # expect: 你好

# ccr → LiteLLM and MCP → SearXNG → public web
claude-glm --permission-mode bypassPermissions -p \
  '用 mcp__searxng__web_search 查 Huawei Cloud MaaS GLM 价格，列出前 3 条 title+url。'
```

The first MCP call triggers a one-time permission prompt; approve it, or use
`--permission-mode bypassPermissions` for non-interactive runs.

## Day-2 and troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `claude-glm` stalls, retries `API_TIMEOUT_MS` | client `/32` not allowed on the proxy SG (remote host) | re-check `curl ifconfig.me`, update the SG rule for `:4000` and `:8788` |
| model id in chunks is `glm-5.1` (no `huawei-` prefix) | ccr bypassing LiteLLM, going straight to MaaS | fix the provider `api_base_url` in `config.json` |
| ccr returns 401/403 | `LITELLM_VIRTUAL_KEY` empty in ccr env | `source ~/.config/claude-glm/env` then `ccr stop && ccr start` |
| `mcp list` shows `searxng: ! Failed` but curl to `:8788/mcp` works | header mismatch | header must be exactly `Authorization: Bearer <token>`, no trailing space |
| MCP returns 200 but `tools/list` empty | FastMCP import failure that didn't crash | `docker compose logs searxng-mcp` |
| MCP `web_search` returns parse error | SearXNG JSON format disabled | ensure `search.formats` includes `json` in `settings.yml`, restart searxng |
| interactive Anthropic model picker after wrapper edit | wrapper didn't set `ANTHROPIC_MODEL` before `claude` | use `claude --model "$ANTHROPIC_MODEL"` (quoted) |

### Offboarding a client

```bash
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp remove searxng
ccr stop 2>/dev/null || true
rm -f ~/.local/bin/claude-glm
rm -rf ~/.config/claude-glm ~/.claude-code-router ~/.claude-glm-config
```

Then revoke the client's virtual key on the proxy (`POST /key/delete`). The MCP
bearer token is shared across clients — rotate it (edit `MCP_TOKEN` in `.env`,
`docker compose --profile search up -d`) only on suspected leakage, and have every
client re-`add` the MCP with the new token.

## Hygiene

- Never paste the virtual key or MCP token into the repo, chat, screenshots, or
  unencrypted shell history. They belong in `~/.config/claude-glm/env`,
  `~/.claude-code-router/config.json` (indirected), and the isolated
  `~/.claude-glm-config/.claude.json`.
- `chmod 600` the env file and ccr config.
- For a remote proxy, keep `searxng` internal (`expose`, not `ports`) and only
  publish the bearer-auth MCP on `:8788`, CIDR-locked to client `/32`s.
