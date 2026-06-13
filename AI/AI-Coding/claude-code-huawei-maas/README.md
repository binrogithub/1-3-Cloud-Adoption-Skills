# claude-code-huawei-maas

This skill documents Claude Code CLI usage patterns for connecting to Huawei Cloud MaaS through `claude-code-router`.

It is intended for operators who want either:

- side-by-side commands where `claude` continues using Anthropic Claude models and `claude-glm` uses Huawei MaaS `glm-5.1`
- Claude Code search prompts routed through CCR to a LiteLLM callback that injects Exa search results

## Scope

Side-by-side scope (the deployed production chain):

```text
claude CLI
  -> Anthropic Claude models

claude-glm CLI
  -> claude-code-router on http://127.0.0.1:3456 (custom router)
  -> LiteLLM Anthropic adapter on http://127.0.0.1:4010
  -> LiteLLM on http://127.0.0.1:4000 (docker)
  -> Huawei Cloud MaaS glm-5.1
```

`claude-glm` routes through the `claude-opus-4-6` alias; the CCR custom router
maps it to the LiteLLM Anthropic adapter, which converts Anthropic
messages/tools/streaming to OpenAI chat completions and carries streaming usage
(`stream_options.include_usage`) so Claude Code auto-compact works.

Optional LiteLLM-backed search scope:

```text
Claude Code search prompt
  -> claude-code-router on http://127.0.0.1:3456
  -> CCR bridge removes local WebSearch/WebFetch tools for search-intent prompts
  -> LiteLLM /v1/responses
  -> LiteLLM custom_callbacks.py calls Exa and injects source snippets
  -> Huawei Cloud MaaS glm-5.1 answers normally
```

Optional image scope:

```text
Claude Code image prompt
  -> claude-code-router image route
  -> LiteLLM /v1/chat/completions
  -> LiteLLM custom_callbacks.py detects image blocks
  -> LiteLLM rewrites model to vision-openrouter
  -> OpenRouter vision model answers
```

For Claude Agent SDK or custom proxy patterns, use the separate `Claude-Code-SDK-Agent-MaaS-Skill`.

## Quick Start

```bash
export HUAWEI_MAAS_API_KEY='replace-with-your-maas-api-key'
./scripts/configure-claude-glm.sh
```

Prerequisite: the LiteLLM stack (port 4000) must already be running; the script
provisions only the local side (CCR config, adapter, wrapper), not LiteLLM
itself (see the separate `LiteLLM-Huawei-MaaS-Proxy` project). It reads
`LITELLM_ANTHROPIC_KEY` / `LITELLM_CCR_KEY` from the environment or
`/root/LiteLLM/.env` when present.

The side-by-side script configures:

- `~/.claude-code-router/config.json` — the verified 3-provider config deployed
  from `assets/ccr/config.json` (`LiteLLM Anthropic Adapter` / `LiteLLM Provider`
  / `litellm-chat`, `CUSTOM_ROUTER_PATH`, `APIKEY`)
- `~/.claude-code-router/custom-router.js` — unknown-model rejection and the
  `claude-opus-4-6` → adapter mapping, from `assets/ccr/custom-router.js`
- `~/.claude-code-router/plugins/*.js` — `claude-thinking-filter`,
  `claude-websearch-to-responses`, `reasoning-effort-filter`, from `assets/ccr/plugins/`
- `~/litellm-anthropic-adapter/` — the local Anthropic adapter (port 4010) via
  `scripts/install-anthropic-adapter.sh`
- `~/.config/claude-glm/env` — `HUAWEI_MAAS_API_KEY`, `CLAUDE_GLM_ROUTER_KEY`, and the LiteLLM virtual keys
- `~/.config/claude-glm/settings.json` (denies native `WebSearch`/`WebFetch`, injected via `--settings`)
- `~/.local/bin/claude-glm`, `Claude-glm`, `claude-glm-recover`
- `~/.local/bin/claude-glm-ccr-run`, `claude-glm-ccr-health`
- `~/.config/systemd/user/claude-glm-ccr.service`, `claude-glm-ccr-health.service`, `claude-glm-ccr-health.timer`
- `ANTHROPIC_MODEL=claude-opus-4-6` (routing alias) only inside the `claude-glm` wrapper
- `ANTHROPIC_CUSTOM_MODEL_OPTION=claude-opus-4-6` only inside the `claude-glm` wrapper
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` only inside the `claude-glm` wrapper (auto-compact trigger window; `CLAUDE_CODE_MAX_CONTEXT_TOKENS` is ignored unless `DISABLE_COMPACT` is set)
- `claude --model claude-opus-4-6` only from the `claude-glm` wrapper, so the interactive header also selects the routed alias
- starts the local Anthropic adapter on demand (`ensure_anthropic_adapter`) before launching Claude Code
- background startup and readiness checks for `ccr` when the router is not already running
- real router health checks against `http://127.0.0.1:3456/`, so stale pid/status files do not cause `FailedToOpenSocket` or `ConnectionRefused` retries
- a fast `GET /v1/models` token preflight that fails immediately on 401/403 instead of letting Claude Code retry for 60s+
- stop/start race handling: if `ccr` is unhealthy, the wrapper stops it, waits for the old process to release, then waits up to 30 seconds for the restarted router to become healthy
- persistent `ccr` startup through a systemd user service when systemd is available
- a systemd health timer that checks the local router every 60 seconds and restarts the service when status or socket health fails
- `loginctl enable-linger` on best effort, so the user service can start with the user manager instead of waiting for an interactive shell

It also runs a smoke test and expects the result to report non-zero `modelUsage`.

Set `INSTALL_SYSTEMD_USER_SERVICE=0` before running the script to skip systemd service installation and keep wrapper-only startup.

To prepare CCR for LiteLLM-backed search, route `claude-glm` through a LiteLLM provider that uses `custom_callbacks.py`, set `EXA_API_KEY` in the LiteLLM runtime environment, then run:

```bash
./scripts/configure-ccr-search.py --dry-run
./scripts/configure-ccr-search.py --apply
```

The CCR bridge does not call Exa itself. It converts the request path for LiteLLM Responses compatibility and removes Claude Code local search/fetch tools for search-intent prompts, so GLM is not asked to emit fragile tool-call JSON. Live search is performed by the LiteLLM callback when `EXA_API_KEY` is configured. Normal `claude-glm` requests still route through the configured provider.

For image inputs, configure the LiteLLM proxy with `OpenRouter_API_KEY` and the `vision-openrouter` model group from `LiteLLM-Huawei-MaaS-Proxy`. The LiteLLM callback automatically rewrites image requests to that model group.

## Persistent CCR Service

On Linux or WSL environments with a running systemd user manager, `./scripts/configure-claude-glm.sh` installs and enables:

```text
claude-glm-ccr.service
claude-glm-ccr-health.timer
```

Check the persistent router state:

```bash
systemctl --user status claude-glm-ccr.service --no-pager
systemctl --user list-timers claude-glm-ccr-health.timer --no-pager
loginctl show-user "$USER" -p Linger
```

The service runs `ccr start` with the same private `~/.config/claude-glm/env` values used by `claude-glm`. The timer runs a real health probe against `http://127.0.0.1:3456/` every 60 seconds and restarts the service if the router is stale, stopped, or no longer accepting local requests.

## Local Router Recovery

When Claude Code reports errors such as:

```text
Unable to connect to API (FailedToOpenSocket)
ConnectionRefused: http://127.0.0.1:3456/v1/messages?beta=true
ccr failed to start; see /tmp/claude-glm-ccr.log
```

Check the local router before changing MaaS credentials:

```bash
ccr status
ss -ltnp | grep ':3456'
curl -fsS -H "Authorization: Bearer ${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}" http://127.0.0.1:3456/
```

If `ccr status` says running but the curl check fails, the router state is stale. Re-run `./scripts/configure-claude-glm.sh` or use the generated `claude-glm` wrapper; it now stops stale `ccr`, waits for shutdown, starts it in the background, and verifies the local socket before launching Claude Code.

## Session Recovery After Context Overflow

Claude Code and `claude-glm` can fail hard after a long tool-heavy session:

```text
Inference failed: the prompt length 197218 must less than the maximum input length 196608
Context low · Run /compact to compact & continue
```

For Huawei MaaS `glm-5.1`, this skill now includes `claude-glm-recover`, a recovery helper for overflowed or unrecoverable sessions.

What it does:

- reads the saved session JSONL under `~/.claude-glm-config/projects/`
- extracts the last user request, recent high-signal context, and the overflow error
- writes a compact recovery pack to `/tmp/claude-glm-recovery-<session-id>.md`
- starts a fresh `claude-glm` session without using `--resume`

Basic usage:

```bash
claude-glm-recover <session-id>
```

Launch a fresh session immediately after generating the recovery pack:

```bash
claude-glm-recover <session-id> --launch
```

Example:

```bash
claude-glm-recover 8b635e4f-95d8-4ef3-9672-97d2a1dab344 --launch
```

The helper intentionally does not call `--resume`. Current Claude Code resume paths are not reliable after context-limit failure, and on some root/sudo environments interactive prompt injection is blocked. The stable path is:

1. generate the recovery pack
2. open a fresh `claude-glm` session
3. paste the recovery markdown as the first prompt

You can also inspect the recovery prompt manually:

```bash
cat /tmp/claude-glm-recovery-<session-id>.md
```

Recommended operating pattern:

- keep MaaS prompt input below the model hard limit
- prefer narrow reads and summaries over full file dumps
- avoid piping large tool outputs straight back into the conversation
- recover into a fresh session instead of relying on `--resume` after overflow

## Files

```text
claude-code-huawei-maas/
├── README.md
├── SKILL.md
├── adapter/                  # LiteLLM Anthropic adapter (port 4010): usage passthrough lives here
│   ├── README.md
│   ├── server.js
│   ├── start.sh
│   └── stop.sh
├── agents/
│   └── openai.yaml
├── assets/
│   └── ccr/                  # verified production CCR config + custom router + transformer plugins
│       ├── config.json
│       ├── custom-router.js
│       └── plugins/
│           ├── claude-thinking-filter.js
│           ├── claude-websearch-to-responses.js
│           └── reasoning-effort-filter.js
├── scripts/
│   ├── claude-glm-recover.sh
│   ├── configure-ccr-search.py
│   ├── configure-claude-glm.sh
│   ├── configure-zai-search-mcp.sh
│   ├── install-anthropic-adapter.sh
│   └── restore-ccr-config.sh
└── tests/                    # production test plan, concurrent runner, reports
```

## Config Ownership Warning

`~/.claude-code-router/config.json` is rewritten by multiple tools on a shared host
(other coding agents, manual edits). The legacy single-provider layout silently degrades
claude-glm: `usage` drops back to 0 (auto-compact stops working) and unknown-model
rejection is bypassed because `CUSTOM_ROUTER_PATH` is absent and the adapter is bypassed.
If those symptoms appear, run `scripts/restore-ccr-config.sh` to reinstall the verified
3-provider config, custom router, plugins, and adapter, then find out what rewrote the
config before assuming a regression.

## Security

Do not commit a real MaaS API key. The side-by-side script writes `api_key: "$HUAWEI_MAAS_API_KEY"` into the router config and stores the local secret in `~/.config/claude-glm/env` with `0600` permissions, alongside the LiteLLM virtual keys (`LITELLM_ANTHROPIC_KEY`, `LITELLM_CCR_KEY`) that the config references as `$LITELLM_*` placeholders. The CCR search script edits config and transformer files but does not print environment values or API keys. Keep `EXA_API_KEY`, `OpenRouter_API_KEY`, and LiteLLM virtual keys only in the LiteLLM or CCR runtime environment.
