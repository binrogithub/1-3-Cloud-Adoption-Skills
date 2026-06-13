# AI Coding Agent Integration

This file documents how Claude Code (CLI) is wired into the LiteLLM gateway via
`claude-code-router` (`ccr`), what the request path looks like, and how
`CLAUDE_CONFIG_DIR` keeps the user's regular `claude` clean.

## Why the indirection

Claude Code speaks the **Anthropic Messages API**. Huawei MaaS speaks the
**OpenAI Chat Completions API**. LiteLLM also speaks OpenAI. So we need a
translator in front of LiteLLM.

`claude-code-router` is the smallest dependable translator. It listens on
`127.0.0.1:3456` for Anthropic-format requests and rewrites them into
OpenAI-format upstream calls. We point that upstream at LiteLLM, not at MaaS,
so:

- Spend, RPM/TPM caps, and audit live in one place (LiteLLM).
- The MaaS API key never ships to laptops (only the LiteLLM virtual key does).
- Adding more models (e.g. a second MaaS region, a self-hosted model) only
  needs an entry in LiteLLM `config.yaml`; the laptop wrapper does not change.

## Request path

```
claude-glm CLI
  └── exec claude --model huawei-glm-5.1
        ANTHROPIC_BASE_URL=http://127.0.0.1:3456
        ANTHROPIC_AUTH_TOKEN=$CLAUDE_GLM_ROUTER_KEY
        CLAUDE_CONFIG_DIR=~/.claude-glm-config
        └── HTTPS (Anthropic format)
              └── claude-code-router (ccr) :3456
                    APIKEY=$CLAUDE_GLM_ROUTER_KEY
                    Provider "litellm"
                    api_base_url=http://<ECS_PUBLIC_IP>:4000/v1/chat/completions
                    api_key=$LITELLM_VIRTUAL_KEY
                    └── HTTP (OpenAI format)
                          └── LiteLLM Proxy :4000
                                model_name "huawei-glm-5.1"
                                upstream openai/glm-5.1
                                api_base $HUAWEI_MAAS_API_BASE
                                api_key $HUAWEI_MAAS_API_KEY
                                └── HTTPS (OpenAI format)
                                      └── Huawei Cloud MaaS
                                            model glm-5.1
```

The ccr access log (`~/.claude-code-router/logs/ccr-*.log`) shows the
`response.model` field on each chunk; if it reads `huawei-glm-5.1` you are on
the LiteLLM path. If it reads `glm-5.1` you regressed to direct MaaS.

## Why `CLAUDE_CONFIG_DIR`

Claude Code stores user-scope MCP servers, settings, and history in
`~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`). The default is the
HOME directory.

If we registered the SearXNG MCP at the default scope, both `claude` and
`claude-glm` would see it. We do not want that: SearXNG is configured for the
GLM coding agent, not necessarily for the user's regular Claude flows.

Setting `CLAUDE_CONFIG_DIR=~/.claude-glm-config` in the wrapper means
`claude-glm` reads and writes a separate `.claude.json`. Plain `claude`
continues to use `~/.claude.json` and remains unaware of the SearXNG MCP.

Verify the isolation after registration:

```
CLAUDE_CONFIG_DIR=~/.claude-glm-config claude mcp list   # has searxng
claude mcp list                                           # does not
```

## `ccr` config patterns

```jsonc
{
  "HOST": "127.0.0.1",
  "PORT": 3456,
  "APIKEY": "$CLAUDE_GLM_ROUTER_KEY",
  "LOG": true,
  "API_TIMEOUT_MS": 600000,
  "Providers": [
    {
      "name": "litellm",
      "api_base_url": "http://<ECS_PUBLIC_IP>:4000/v1/chat/completions",
      "api_key": "$LITELLM_VIRTUAL_KEY",
      "models": ["huawei-glm-5.1"],
      "transformer": { "use": ["enhancetool"] }
    }
  ],
  "Router": {
    "default":      "litellm,huawei-glm-5.1",
    "background":   "litellm,huawei-glm-5.1",
    "think":        "litellm,huawei-glm-5.1",
    "longContext":  "litellm,huawei-glm-5.1",
    "longContextThreshold": 190000
  }
}
```

Notes:

- The `$VAR` substitution happens in the `ccr` process at startup. After any
  edit to `~/.config/claude-glm/env`, you must restart `ccr`.
- Use the **alias without slash** (`huawei-glm-5.1`). The Router string is
  parsed by comma; slashes are tolerated but make scripting harder.
- Keep `enhancetool` enabled so tool calls survive the Anthropic-to-OpenAI
  translation.

## Wrapper script behavior

The wrapper at `~/.local/bin/claude-glm` does these things, in order:

1. Source the env file (`~/.config/claude-glm/env`).
2. Export `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` so Claude Code talks to ccr.
3. Export `ANTHROPIC_AUTH_TOKEN=$CLAUDE_GLM_ROUTER_KEY` so ccr accepts the call.
4. Export `CLAUDE_CONFIG_DIR=$HOME/.claude-glm-config` for isolation.
5. If `ccr` is not running, start it. Refuse to start if the LiteLLM virtual
   key is empty.
6. If the user's command does not contain `--model`, inject
   `--model huawei-glm-5.1`. Subcommands like `agents`, `auth`, `doctor`,
   `mcp`, `update` skip injection.

The wrapper is the single point that decides "this invocation is GLM-routed".

## Switching the upstream model later

Two changes only:

1. Add a new `model_list` entry in LiteLLM `/etc/litellm/config.yaml` and
   reload `litellm.service`.
2. Update `Providers[0].models` in `ccr` config and (optionally) the `Router`
   strings; restart `ccr`.

The wrapper, the MCP, the SG rules, and the laptop credentials do not change.

## Spend and budget

Mint per-purpose virtual keys with the LiteLLM admin API:

```
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
     -H 'Content-Type: application/json' \
     -X POST http://$ECS_PUBLIC_IP:4000/key/generate \
     -d '{"key_alias":"team-platform","models":["huawei-glm-5.1"],
          "max_budget":50.0,"budget_duration":"30d","tpm_limit":40000,"rpm_limit":120}'
```

For a personal GLM coding agent we usually mint **one unrestricted key** for
the operator and let LiteLLM track spend without gating it. For shared use,
always set `max_budget` and `budget_duration` so the key self-disables.

## Failure modes specific to this stack

- **ccr returns 200 but Claude Code shows a model picker** — the wrapper
  failed to inject `--model`. Check that `$ANTHROPIC_MODEL` is exported before
  `exec claude`.
- **ccr returns 401 from upstream** — the LiteLLM virtual key in the ccr
  config did not interpolate; `$LITELLM_VIRTUAL_KEY` is empty in ccr's
  process environment. `ccr stop && ccr start` after `source` of the env file.
- **Tool calls fail under streaming** — usually means ccr's transformer
  dropped a tool block. The `enhancetool` transformer is the workaround.
- **`mcp list` says searxng is `! Failed`** — the bearer token in
  `~/.claude-glm-config/.claude.json` is wrong, or the SG was tightened to
  exclude the laptop's current IP.
- **Plain `claude` starts seeing the SearXNG MCP** — `CLAUDE_CONFIG_DIR` was
  not exported in the wrapper, or someone registered the MCP without
  `CLAUDE_CONFIG_DIR` set. Run `claude mcp remove searxng` to clean up.
