# Laptop Client Onboarding

Audience: a developer joining a gateway that is **already running**. The
operator has finished `SKILL.md` Steps 1–13 and now wants to plug a second
laptop (or onboard a teammate) into the same gateway without redeploying
anything on the ECS.

If you are the operator who just deployed the gateway, follow `SKILL.md`
Steps 14–16 instead. They cover wiring the laptop you deployed *from*. This
document picks up from there for *additional* laptops.

## What the operator must hand over

The new client cannot derive these from anywhere; the operator shares them
out-of-band (1Password, encrypted message, internal vault). Never paste them
into chat or commit them.

| Value | Source on the gateway side | Notes |
|---|---|---|
| `<ECS_PUBLIC_IP>` | Huawei Cloud Console → ECS → EIP | Stable per ECS, public IPv4. |
| `<LITELLM_VIRTUAL_KEY>` | Mint via `POST /key/generate` with the master key, see `references/aicoding-agent-integration.md` | One key per laptop is best for spend attribution and clean revocation. |
| `<MCP_BEARER_TOKEN>` | `Environment=MCP_TOKEN=...` in `/etc/systemd/system/searxng-mcp.service` on the ECS | Same token for all clients today; rotate by editing the unit. |

The operator should also confirm:

- The exposed model name to use: `huawei-glm-5.1` (no slash; matches the
  ccr config template).
- Optional ports the new laptop is allowed to talk to (default `tcp/22`,
  `tcp/4000`, `tcp/8788`).

## What the operator must do on the gateway side

Add the new laptop's outbound public IP `/32` to the existing security
group on the three ports the client needs.

The client runs `curl -s https://ifconfig.me` on the new laptop and sends
the value to the operator. The operator opens the SG and adds three
ingress rules (`tcp/22`, `tcp/4000`, `tcp/8788`) for that `/32`.

If the client is behind a CGNAT or VPN whose egress IP changes, plan for
re-whitelisting. The skill's troubleshooting doc covers the symptom.

## Laptop prerequisites

```bash
# Claude Code CLI
curl -fsSL https://claude.com/install.sh | bash
# or: npm i -g @anthropic-ai/claude-code

# claude-code-router (the ccr binary)
npm i -g @musistudio/claude-code-router

claude --version
ccr --version
curl --version | head -1
```

## Connectivity smoke-tests

Run these *before* writing config. Each one isolates a different
ingredient.

```bash
# 1. Confirm the SG sees the same egress IP the operator whitelisted.
curl -s -m 5 https://ifconfig.me; echo

# 2. LiteLLM liveliness (does not require auth).
curl -s -m 10 -w "\n[http=%{http_code}]\n" \
  http://<ECS_PUBLIC_IP>:4000/health/liveliness
# expect: "I'm alive!"  http=200

# 3. MCP rejects unauthenticated callers.
curl -s -m 10 -o /dev/null -w "mcp_no_auth=%{http_code}\n" \
  -X POST http://<ECS_PUBLIC_IP>:8788/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json,text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
# expect: mcp_no_auth=401
```

If `(2)` times out or `(3)` is `000`, your laptop's egress IP is not in the
SG. Re-confirm `ifconfig.me` with the operator and have them update the
whitelist before continuing.

## One-shot install (recommended)

Use the bundled client installer. It takes the three values as env vars,
writes everything, restarts ccr, and registers the SearXNG MCP under an
isolated `CLAUDE_CONFIG_DIR` so plain `claude` is unaffected.

```bash
ECS_PUBLIC_IP='<ECS_PUBLIC_IP>' \
LITELLM_VIRTUAL_KEY='<LITELLM_VIRTUAL_KEY>' \
MCP_TOKEN='<MCP_BEARER_TOKEN>' \
bash scripts/install_claude_glm_client.sh
```

Skip to **Verify** below.

## Manual install (step by step)

If you prefer to lay each file down yourself, or you want to understand
what the installer does.

### 1. Local env file

```bash
mkdir -p ~/.config/claude-glm
cat > ~/.config/claude-glm/env <<'EOF'
export LITELLM_VIRTUAL_KEY="<LITELLM_VIRTUAL_KEY>"
export CLAUDE_GLM_ROUTER_KEY="claude-glm-local"
EOF
chmod 600 ~/.config/claude-glm/env
```

`CLAUDE_GLM_ROUTER_KEY` is a local-only token between the wrapper and ccr.
Any non-empty string works; use the literal `claude-glm-local` to match
the ccr config example.

### 2. ccr config

Copy `assets/config/claude-code-router.config.json.example` to
`~/.claude-code-router/config.json`, replacing the `<ECS_PUBLIC_IP>`
placeholder.

```bash
mkdir -p ~/.claude-code-router
sed "s|@@ECS_PUBLIC_IP@@|<ECS_PUBLIC_IP>|g" \
  AI/AI-Coding/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/assets/config/claude-code-router.config.json.example \
  > ~/.claude-code-router/config.json
chmod 600 ~/.claude-code-router/config.json
```

The example uses `$LITELLM_VIRTUAL_KEY` indirection; the variable comes
from the env file when ccr starts. Do not paste the literal key into
`config.json`.

### 3. Wrapper

```bash
mkdir -p ~/.local/bin
install -m 755 \
  AI/AI-Coding/LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/assets/config/claude-glm-wrapper.sh.example \
  ~/.local/bin/claude-glm

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
     export PATH="$HOME/.local/bin:$PATH" ;;
esac
```

The shipped wrapper already sets `DISABLE_COMPACT=false` and
`CLAUDE_CODE_MAX_CONTEXT_TOKENS=180000`, leaving ~8% headroom under
GLM-5.1's 196608-token input ceiling. Do not lower the headroom; see
`references/troubleshooting.md` for what happens otherwise.

### 4. Start ccr in a shell that has the env loaded

```bash
source ~/.config/claude-glm/env
ccr stop 2>/dev/null || true
ccr start
sleep 2
ss -tlnp 2>/dev/null | grep 3456 || \
  curl -s -o /dev/null -w "ccr=%{http_code}\n" http://127.0.0.1:3456/
```

If ccr starts before `LITELLM_VIRTUAL_KEY` is in its environment, every
request returns `401` from upstream. The wrapper guards against this on
auto-start; manual `ccr start` does not, so always source the env file
first.

### 5. Register the SearXNG MCP under an isolated config dir

```bash
mkdir -p ~/.claude-glm-config

CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp add \
  --transport http --scope user searxng \
  http://<ECS_PUBLIC_IP>:8788/mcp \
  --header "Authorization: Bearer <MCP_BEARER_TOKEN>"

# Verify isolation
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp list   # has searxng ✓
claude mcp list                                          # does NOT have searxng
```

The isolation is the whole point of `CLAUDE_CONFIG_DIR`. Without it,
your regular `claude` would also see (and possibly trigger) the SearXNG
tool. See `references/aicoding-agent-integration.md` for the design
detail.

## Verify

```bash
# Round-trip through ccr → LiteLLM → MaaS
claude-glm -p '只回复两个字：你好'
# expect: 你好

# Round-trip through ccr → LiteLLM and MCP → SearXNG → public web
claude-glm --permission-mode bypassPermissions -p \
  '用 mcp__searxng__web_search 查 Anthropic Claude，返回前 3 条 title+url。'
# expect: three real search results, formatted as the agent decides
```

If the second prompt returns "MCP 搜索工具需要你授权" instead of results,
the permission gate has not been bypassed; either re-run with
`--permission-mode bypassPermissions`, or in an interactive session,
approve the tool once when the prompt appears.

## Day-2 operations

### Egress IP changed

Symptom: `claude-glm` stalls and prints
`Retrying ... attempt N/10 · API_TIMEOUT_MS=...`. ccr cannot reach
LiteLLM because the SG no longer trusts your `/32`.

```bash
curl -s https://ifconfig.me; echo
```

Send the new IP to the operator and ask them to add the new `/32` and
remove the stale rule. Do not change anything on your laptop; the gateway
URL has not moved.

### Removing yourself

```bash
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp remove searxng
ccr stop 2>/dev/null || true
rm -f ~/.local/bin/claude-glm
rm -rf ~/.config/claude-glm ~/.claude-code-router ~/.claude-glm-config
```

Then ask the operator to remove your `/32` from the SG and revoke your
LiteLLM virtual key (`POST /key/delete`). The MCP bearer token is shared,
so do not ask for it to be rotated unless you suspect leakage.

### Suspected leak of your virtual key

Tell the operator. They revoke the key on LiteLLM and mint a new one. You
update `~/.config/claude-glm/env` and `ccr stop && source ~/.config/
claude-glm/env && ccr start`.

### Suspected leak of the MCP bearer token

Tell the operator. They edit `Environment=MCP_TOKEN=...` in
`/etc/systemd/system/searxng-mcp.service`, `systemctl daemon-reload`,
`systemctl restart searxng-mcp.service`, and re-share the new token. Each
client then runs:

```bash
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp remove searxng
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp add \
  --transport http --scope user searxng \
  http://<ECS_PUBLIC_IP>:8788/mcp \
  --header "Authorization: Bearer <NEW_MCP_BEARER_TOKEN>"
```

## Hygiene rules for the new client

- Never paste any of the three handed-over values into the repo, into
  chat, into screenshots, or into shell history that gets backed up
  unencrypted. They go straight into `~/.config/claude-glm/env`,
  `~/.claude-code-router/config.json` (indirected), and the local
  `~/.claude-glm-config/.claude.json` (written by `claude mcp add`).
- Set `chmod 600` on `~/.config/claude-glm/env` and
  `~/.claude-code-router/config.json`.
- If you commit dotfiles to a personal repo, add the four locations above
  to `.gitignore`.
- The MCP bearer token is shared across clients. If your laptop is
  compromised, the operator must rotate the token for everyone, not just
  for you.
