---
name: claude-code-huawei-maas
description: Configure Claude Code to use Huawei Cloud MaaS or ModelArts MaaS through claude-code-router and a LiteLLM Anthropic adapter, optionally add a CCR bridge for LiteLLM-backed search or Z.ai web-search-prime MCP search, or add a claude-anou anonymous blind model-test command. Use when Codex needs to add a side-by-side claude-glm command that routes to Huawei MaaS glm-5.1 while preserving the original claude command on Anthropic, install or configure claude-code-router, deploy the production CCR config/custom-router/adapter, adjust context length, verify that Claude Code is actually backed by MaaS, route Claude Code WebSearch/current-news/latest prompts through a LiteLLM Exa search injection path, configure Z.ai MCP search with Z_API_KEY, or add an optional claude-anou command that runs Claude Code as "Anonymous-Model" and binds each project to a hidden anon-model-a/anon-model-b backend for blind A/B model comparison.
---

# Claude Code Huawei MaaS

## Overview

Use this skill to route Claude Code through `claude-code-router` (`ccr`) and a LiteLLM Anthropic adapter to Huawei Cloud MaaS. The setup is side-by-side: keep the original `claude` command on Anthropic and add `claude-glm`/`Claude-glm` for Huawei MaaS `glm-5.1`. The deployed chain is `claude-glm → ccr (3456, custom router) → LiteLLM Anthropic adapter (4010) → LiteLLM (4000, docker) → MaaS glm-5.1`, routed via the `claude-opus-4-6` alias. It can also install the CCR bridge used with LiteLLM-side Exa search injection or add the Z.ai `web-search-prime` MCP search tool for Claude Code.

## Quick Path

1. Confirm the user has a MaaS API key and that the LiteLLM stack (port 4000) is running (the script provisions only the local CCR/adapter/wrapper side, not LiteLLM itself — see the separate `LiteLLM-Huawei-MaaS-Proxy` project).
2. Confirm `claude --version` works. If it does not, install Claude Code first with `npm install -g @anthropic-ai/claude-code` (the script errors out with this hint when `claude` is missing).
3. Run `scripts/configure-claude-glm.sh` from this skill. It deploys the verified CCR config/custom-router/plugins from `assets/ccr/`, installs the local Anthropic adapter, and writes the `claude-glm` wrapper. Defaults match the tested setup:
   - backend model: `glm-5.1`
   - routing alias: `claude-opus-4-6`
   - auto-compact window: `180000`
   - LiteLLM keys read from the environment or `/root/LiteLLM/.env`
4. Verify both the router and Claude Code:
   - `ccr status`
   - `systemctl --user status claude-glm-ccr.service --no-pager` when systemd user services are available
   - `claude-glm --bare --print --output-format json 'Reply with OK only'`
   - `claude --version` still resolves to the original Claude Code install and is not wrapped by this path.
5. If the user has already hit MaaS context overflow or Claude Code resume failure, use the bundled recovery helper:
   - `claude-glm-recover <session-id>`
   - `claude-glm-recover <session-id> --launch`
   - then paste `/tmp/claude-glm-recovery-<session-id>.md` into the fresh session as the first prompt
6. If the user wants Claude Code search prompts such as `搜索今天的新闻` to avoid Claude Code local `WebFetch`, configure the CCR bridge and LiteLLM search callback:
   - route CCR to a LiteLLM provider that mounts `LiteLLM-Huawei-MaaS-Proxy/assets/config/custom_callbacks.py`
   - set `EXA_API_KEY` in the LiteLLM runtime environment when live search is desired
   - run `scripts/configure-ccr-search.py --dry-run`, then `--apply`
   - CCR removes local search/fetch tools for search-intent prompts; LiteLLM performs the actual Exa prefetch and injection
7. If the user also wants Z.ai search MCP, confirm they have a Z.ai account and API key, export it as `Z_API_KEY`, then run `scripts/configure-zai-search-mcp.sh`.
8. If the user wants to blind-test two models against each other inside Claude Code, run `scripts/configure-claude-anou.sh` (after claude-glm is configured) to add the optional `claude-anou` command. It launches Claude Code as `Anonymous-Model` and binds each project directory to a hidden `anon-model-a`/`anon-model-b` backend. Requires the LiteLLM stack to expose the `anon-model-a` and `anon-model-b` model groups.

Example:

```bash
export HUAWEI_MAAS_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-claude-glm.sh
```

The side-by-side script accepts `HUAWEI_MAAS_API_KEY`, `MAAS_API_KEY`, or `API_KEY` and stores it in `~/.config/claude-glm/env` with `0600` permissions so only `claude-glm` uses it, alongside the LiteLLM virtual keys.

Add Z.ai search MCP:

```bash
export Z_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-zai-search-mcp.sh
```

Add the CCR bridge for LiteLLM-backed search:

```bash
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-ccr-search.py --dry-run
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-ccr-search.py --apply
```

## Side-By-Side Claude-GLM

`scripts/configure-claude-glm.sh` keeps `claude` on Anthropic Claude models and adds `claude-glm` for Huawei MaaS through the deployed LiteLLM-adapter chain. It requires the LiteLLM stack (port 4000) to be running already; it provisions only the local side.

- Installs `@musistudio/claude-code-router` globally with npm if `ccr` is missing.
- Deploys `~/.claude-code-router/config.json` from `assets/ccr/config.json` — the verified 3-provider config (`LiteLLM Anthropic Adapter` on 4010, `LiteLLM Provider` on 4000 `/v1/responses`, `litellm-chat` on 4000 `/v1/chat/completions` for the image route), with `CUSTOM_ROUTER_PATH`, `APIKEY`, and `$LITELLM_*` placeholders expanded by `ccr` at runtime. Hardcoded `/root/.claude-code-router` paths are rewritten to the actual config dir.
- Deploys `~/.claude-code-router/custom-router.js` from `assets/ccr/custom-router.js` (maps `claude-opus-4-6`/`opus`/`claude-opus-*` to the adapter, rejects unknown models with a readable 404, allowlists `claude-*` and known models).
- Deploys `~/.claude-code-router/plugins/*.js` from `assets/ccr/plugins/` (`claude-thinking-filter`, `claude-websearch-to-responses`, `reasoning-effort-filter`) referenced by `config.json` `transformers[]`.
- Installs the local Anthropic adapter into `~/litellm-anthropic-adapter/` via `scripts/install-anthropic-adapter.sh`; the wrapper starts it on demand (`ensure_anthropic_adapter`).
- Stores `HUAWEI_MAAS_API_KEY`, `CLAUDE_GLM_ROUTER_KEY`, and the LiteLLM virtual keys (`LITELLM_ANTHROPIC_KEY`, `LITELLM_CCR_KEY`) in `~/.config/claude-glm/env` with `0600` permissions.
- Creates `~/.local/bin/claude-glm` and a compatibility symlink `~/.local/bin/Claude-glm`.
- Makes `claude-glm` discoverable by creating `/usr/local/bin` symlinks when writable, or by appending a guarded `~/.local/bin` PATH block to shell startup files; warns with a `hash -r` hint if the current shell still cannot find it.
- Installs `~/.local/bin/claude-glm-recover` for post-overflow recovery into a fresh session.
- Writes `~/.config/claude-glm/settings.json` denying `WebSearch`/`WebFetch` and injects it with `--settings`, because glm-5.1 has no native Anthropic server-side search/fetch. This keeps the plain `claude` command and `~/.claude` untouched. Users can re-enable by passing their own `--settings`.
- Creates `~/.local/bin/claude-glm-ccr-run` and `~/.local/bin/claude-glm-ccr-health` when systemd user services are available; the run unit also sources the LiteLLM env so the resident router can expand `$LITELLM_*`.
- Installs `~/.config/systemd/user/claude-glm-ccr.service`, `claude-glm-ccr-health.service`, and `claude-glm-ccr-health.timer` by default when `systemctl --user` works.
- Leaves the existing `claude` command untouched.
- Exports these defaults only inside the `claude-glm` wrapper:
  - `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`
  - `ANTHROPIC_AUTH_TOKEN=claude-glm-local`
  - `ANTHROPIC_MODEL=claude-opus-4-6` (routing alias)
  - `ANTHROPIC_CUSTOM_MODEL_OPTION=claude-opus-4-6`
  - `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` (auto-compact trigger window; `CLAUDE_CODE_MAX_CONTEXT_TOKENS` is ignored by Claude Code unless `DISABLE_COMPACT` is set)
- Starts the local Anthropic adapter, then `ccr` in the background when needed, validates the router with a real `http://127.0.0.1:3456/` health check instead of trusting only the pid/status file, runs a fast `GET /v1/models` token preflight that fails immediately on 401/403, and runs the real `claude` command with `--model claude-opus-4-6` unless the user already passed `--model` or invoked a Claude Code management subcommand.
- If `ccr status` is stale or the router socket is closed, stops `ccr`, waits briefly for the old process/port to release, then waits up to 30 seconds for the restarted router to become healthy.
- Keeps `ccr` resident through a systemd user service when supported, enables a 60-second health timer that restarts the service on failed status/socket checks, and best-effort enables user lingering with `loginctl enable-linger`.
- Restarts `ccr` and validates a small request through `claude-glm` (expects non-zero `modelUsage`).

Set `INSTALL_SYSTEMD_USER_SERVICE=0` before running `scripts/configure-claude-glm.sh` if the user wants wrapper-only startup and no systemd user units.

To reinstall just the CCR side after something rewrites the config (without re-running the full installer), use `scripts/restore-ccr-config.sh`.

## Recovery Workflow

Use this when the user reports one of these patterns:

- `prompt length ... must less than the maximum input length ...`
- repeated `/compact` failure
- `--resume` or `/resume` no longer restores usable context
- a long `claude-glm` session has become too large to continue safely

Preferred recovery flow:

1. Find the failed session id from the terminal history or `~/.claude-glm-config/history.jsonl`.
2. Run:

```bash
claude-glm-recover <session-id>
```

3. Open a fresh `claude-glm` session:

```bash
cd <original-project-dir>
claude-glm
```

4. Paste the generated recovery file:

```bash
cat /tmp/claude-glm-recovery-<session-id>.md
```

Or let the helper open the fresh session for you:

```bash
claude-glm-recover <session-id> --launch
```

Important limits:

- The helper does not repair the old session in place.
- The helper does not use `--resume`.
- On root/sudo environments, Claude Code often blocks interactive first-prompt injection, so the reliable recovery path is still a fresh session plus a pasted recovery pack.

## Manual Configuration

Use this if the script cannot be run or if the user wants to review each step.

1. Install CCR:

```bash
npm install -g @musistudio/claude-code-router
```

2. Install the verified CCR state. Copy the archived files rather than hand-writing them — the layout (3 providers, `CUSTOM_ROUTER_PATH`, transformer plugins) is load-bearing:

```bash
install -m 600 assets/ccr/config.json       ~/.claude-code-router/config.json
install -m 644 assets/ccr/custom-router.js  ~/.claude-code-router/custom-router.js
mkdir -p ~/.claude-code-router/plugins
install -m 644 assets/ccr/plugins/*.js      ~/.claude-code-router/plugins/
```

`config.json` defines three providers:
- `LiteLLM Anthropic Adapter` (`http://127.0.0.1:4010/v1/messages`, `Anthropic` transformer) — the default/background/longContext route via the `claude-opus-4-6` alias.
- `LiteLLM Provider` (`http://127.0.0.1:4000/v1/responses`) — the responses/search path.
- `litellm-chat` (`http://127.0.0.1:4000/v1/chat/completions`) — the `image` route.

The `APIKEY` and provider `api_key` fields are `$CLAUDE_GLM_ROUTER_KEY` / `$LITELLM_ANTHROPIC_KEY` / `$LITELLM_CCR_KEY` placeholders that `ccr` expands from its environment at start. Install the local Anthropic adapter and start it before `ccr`:

```bash
scripts/install-anthropic-adapter.sh   # -> ~/litellm-anthropic-adapter/ (port 4010)
```

3. Start or restart CCR (with the key env vars exported so the placeholders expand):

```bash
ccr restart
```

For persistent `ccr` startup on systemd user environments, install units equivalent to the script-generated service:

```bash
systemctl --user enable --now claude-glm-ccr.service claude-glm-ccr-health.timer
loginctl enable-linger "$USER"
```

Verify the resident router:

```bash
systemctl --user status claude-glm-ccr.service --no-pager
systemctl --user list-timers claude-glm-ccr-health.timer --no-pager
curl -fsS -H "Authorization: Bearer ${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}" http://127.0.0.1:3456/
```

4. Make `claude-glm` use the router while preserving `claude`:

```bash
mkdir -p ~/.config/claude-glm ~/.local/bin
chmod 700 ~/.config/claude-glm ~/.local/bin
cat > ~/.config/claude-glm/env <<'EOF'
export HUAWEI_MAAS_API_KEY='replace-with-your-maas-api-key'
export CLAUDE_GLM_ROUTER_KEY='claude-glm-local'
export LITELLM_ANTHROPIC_KEY='replace-with-your-litellm-key'
export LITELLM_CCR_KEY='replace-with-your-litellm-key'
EOF
chmod 600 ~/.config/claude-glm/env
```

Then create `~/.local/bin/claude-glm`. The wrapper routes through the
`claude-opus-4-6` alias, starts the local Anthropic adapter, validates the
router with an unauthenticated `GET /` health check, runs a fast `GET /v1/models`
token preflight (fail fast on 401/403), and injects `--model`/`--settings`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/.config/claude-glm/env"
export ANTHROPIC_AUTH_TOKEN="$CLAUDE_GLM_ROUTER_KEY"
export ANTHROPIC_BASE_URL=http://127.0.0.1:3456
case ",${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;;
esac
export ANTHROPIC_MODEL=claude-opus-4-6
export ANTHROPIC_CUSTOM_MODEL_OPTION=claude-opus-4-6
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME=claude-opus-4-6
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION='Claude Opus compatibility route to Huawei Cloud MaaS glm-5.1'
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000
unset CLAUDE_CODE_USE_BEDROCK

# Start the LiteLLM Anthropic adapter the default route depends on.
[ -x "$HOME/litellm-anthropic-adapter/start.sh" ] && "$HOME/litellm-anthropic-adapter/start.sh" >/dev/null 2>&1

ccr_healthy() { curl -fsS -m 2 "$ANTHROPIC_BASE_URL/" >/dev/null 2>&1; }

if ! ccr_healthy; then
  ccr stop >/dev/null 2>&1 || true
  ccr_log="${CLAUDE_GLM_CCR_LOG:-/tmp/claude-glm-ccr.log}"
  setsid ccr start > "$ccr_log" 2>&1 < /dev/null &
  for _ in {1..60}; do ccr_healthy && break; sleep 0.5; done
  ccr_healthy || { echo "ccr failed to start; see $ccr_log" >&2; exit 1; }
fi

# /v1/models returns 401/403 on bad auth, 404 on good auth (~6ms); fail fast.
status="$(curl -sS -m 2 -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $ANTHROPIC_AUTH_TOKEN" "$ANTHROPIC_BASE_URL/v1/models")" || status=000
case "$status" in 401|403) echo "router rejected the auth token (HTTP $status)" >&2; exit 1 ;; esac

exec claude --model "$ANTHROPIC_MODEL" --settings "$HOME/.config/claude-glm/settings.json" "$@"
```

The generated wrapper (`scripts/configure-claude-glm.sh`) additionally skips the
`--model`/`--settings` injection for Claude Code management subcommands and when
the user passes their own.

## Native WebSearch/WebFetch Disabled By Default

`claude-glm` denies Claude Code's native `WebSearch` and `WebFetch` tools by default,
because glm-5.1 cannot invoke Anthropic's server-side search/fetch — left enabled, the
model either emits unreliable tool calls or gets silently bridged elsewhere, misleading
the user into thinking native search ran. The wrapper enforces this with a
claude-glm-only settings file (`~/.config/claude-glm/settings.json`,
`permissions.deny: ["WebSearch", "WebFetch"]`) injected via `--settings`, so the plain
`claude` command on Anthropic is unaffected.

Verify: `web_search_requests` stays 0 and the model reports it cannot search.

```bash
claude-glm --print --output-format json '搜索今天的新闻。如果无法联网搜索，只回复 NO-WEB。'
```

To re-enable native search for a single run, pass your own `--settings` file without the
deny entries. The two opt-in alternatives below (LiteLLM Exa bridge, Z.ai MCP) provide
real search through explicit, separately configured paths rather than the native tools.

## CCR Bridge For LiteLLM Search

Use this when the user wants Claude Code search tasks to avoid Claude Code local `WebFetch`/`Fetch`, especially for prompts like:

- `搜索今天的新闻`
- `search latest release notes`
- `find current pricing`
- any request that depends on current web information

This path is different from Z.ai MCP search and from LiteLLM `websearch_interception`. Z.ai MCP exposes a search tool directly to Claude Code. The claude-glm path uses CCR only as a bridge: `Claude Code -> ccr transformer -> LiteLLM /v1/responses -> LiteLLM custom callback -> Exa snippets -> MaaS model`.

Expected search API configuration:

- Set `EXA_API_KEY` in the LiteLLM process environment when live search is desired.
- Mount `LiteLLM-Huawei-MaaS-Proxy/assets/config/custom_callbacks.py` into LiteLLM.
- Do not configure LiteLLM `search_tools` or `websearch_interception` for this path.
- If no search API key is present, LiteLLM logs that Exa is not configured and the model answers without injected live results. Normal `claude-glm` prompts continue to use the configured provider.

Expected CCR behavior:

- Use CCR transformer order:

```json
[
  ["maxtoken", {"max_tokens": 8192}],
  "cleancache",
  "claude-websearch-to-responses",
  "openai-responses",
  "claude-websearch-to-responses"
]
```

- Detect search intent from the latest user message, not from `<system-reminder>` context.
- Set `use_chat_completions_api = true` for Responses payloads so LiteLLM can bridge to OpenAI-compatible chat models.
- Remove local Claude Code search/fetch tools for search-intent prompts so GLM does not emit unreliable tool calls.
- Leave live search fetching to the LiteLLM callback.

Preferred setup script:

```bash
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-ccr-search.py --dry-run
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-ccr-search.py --apply
```

Validate CCR search routing:

```bash
curl -sS -N 'http://127.0.0.1:3456/v1/messages?beta=true' \
  -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"claude-opus-4-6",
    "max_tokens":512,
    "stream":true,
    "tools":[
      {"name":"WebFetch","description":"Fetch URL","input_schema":{"type":"object","properties":{"url":{"type":"string"},"prompt":{"type":"string"}},"required":["url","prompt"]}},
      {"name":"WebSearch","description":"Search the web","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}
    ],
    "messages":[{"role":"user","content":[{"type":"text","text":"搜索今天的新闻，只列1条。"}]}]
  }'
```

Pass criteria:

- With `EXA_API_KEY` visible to LiteLLM, output contains current-information text and source URLs.
- Without `EXA_API_KEY`, `claude-glm` still answers normally but has no injected live search results.
- Claude Code does not show local `Fetch(...)` or `WebFetch(...)` tool calls for search-intent prompts.

## Z.ai Web Search MCP

Use this when the user wants Claude Code to have the Z.ai `web-search-prime` MCP search tool, exposed as `mcp__web-search-prime__web_search_prime`.

Prerequisites:

- The user has a Z.ai account.
- The user has created a Z.ai API key.
- The key is available in the shell as `Z_API_KEY`.

Do not write the raw Z.ai API key into Claude config. Store it in the environment and configure Claude Code to build the MCP `Authorization` header at runtime.

Preferred setup:

```bash
export Z_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-zai-search-mcp.sh
```

Manual user-scope config in `~/.claude.json`:

```json
{
  "mcpServers": {
    "web-search-prime": {
      "type": "http",
      "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
      "headersHelper": "python3 -c 'import json, os; print(json.dumps({\"Authorization\": \"Bearer \" + os.environ[\"Z_API_KEY\"]}))'"
    }
  }
}
```

The helper produces this HTTP header when Claude Code starts the MCP connection:

```text
Authorization: Bearer <Z_API_KEY>
```

## Anonymous Blind Model Test (claude-anou)

Use this optional command when the user wants to evaluate two models against each
other inside Claude Code **without knowing which model is answering** — a blind
A/B comparison. `claude-anou` launches Claude Code displaying only the model name
`Anonymous-Model` and routes each project directory consistently to one of two
hidden backends, `anon-model-a` or `anon-model-b`.

It is purely additive and opt-in: it leaves the plain `claude`, the `claude-glm`
command, and `~/.claude` untouched. It reuses the claude-glm router env, the CCR
custom router (`assets/ccr/custom-router.js`, which already contains the
`Anonymous-Model` branch), and the `anon-model-a`/`anon-model-b` providers in
`assets/ccr/config.json`.

How the routing works:

- `claude-anou` exports `ANTHROPIC_MODEL=Anonymous-Model` (and the matching
  `ANTHROPIC_CUSTOM_MODEL_OPTION*`) so the Claude Code header and `--model` never
  reveal the real model.
- The first time it runs in a project directory it writes a random assignment to
  `<project>/.mt` (`a` or `b`) and keeps it stable for that project on later runs.
- On every run it copies `<project>/.mt` to
  `~/.claude-code-router/.session-model`, the live signal the CCR custom router
  reads. The router maps `Anonymous-Model` to `LiteLLM Provider,anon-model-a`
  when the assignment is `a`, otherwise `LiteLLM Provider,anon-model-b` (and
  falls back to `anon-model-b` if the file is unreadable).
- It runs the same `ccr` health-check / restart bootstrap as `claude-glm`, and
  injects `--model Anonymous-Model` unless the user passed their own `--model` or
  invoked a Claude Code management subcommand.

Prerequisites:

- `claude-glm` is already configured (`scripts/configure-claude-glm.sh`), so
  `~/.config/claude-glm/env`, `ccr`, the archived CCR config, and the custom
  router are in place.
- The LiteLLM stack (port 4000) exposes the `anon-model-a` and `anon-model-b`
  model groups. This skill does not provision LiteLLM or decide which real models
  map to a/b — define that in your LiteLLM config (see the separate
  `LiteLLM-Huawei-MaaS-Proxy` project).

Install:

```bash
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-claude-anou.sh
```

Use (always run from inside the project directory you want to test):

```bash
cd <project-dir>
claude-anou
```

Reveal the mapping only after the blind test is finished: inspect
`<project-dir>/.mt` (`a`/`b`) and the `anon-model-a`/`anon-model-b` → real-model
mapping in your LiteLLM config. To re-roll a project's assignment, delete its
`.mt` file before the next run.

Run only one `claude-anou` session at a time. `~/.claude-code-router/.session-model`
is a single global signal that each run overwrites from the current project's
`.mt`; two concurrent `claude-anou` sessions in different projects would
cross-route each other's in-flight requests and invalidate the blind test. The
per-project `.mt` assignment is still stable across non-overlapping runs.

Verify the routing without revealing the model in the answer:

```bash
cat <project-dir>/.mt                       # a or b
cat ~/.claude-code-router/.session-model    # matches .mt after a run
claude-anou --print --output-format json 'Reply with OK only'
```

The JSON `modelUsage` reports the real backend model id, so run that check only
when you intentionally want to break blindness (for example, to confirm the
wiring). For a genuine blind test, judge the answers, not the usage metadata.

## Verification

Prefer a non-interactive JSON check because it reports actual `modelUsage`:

```bash
claude-glm --bare --print --output-format json 'Reply with OK only'
```

Successful output should report the routed model under `modelUsage` with non-zero
`usage.input_tokens`/`usage.output_tokens`. Note that `contextWindow` always shows
Claude Code's built-in table value (200000 for unknown or aliased models) and cannot
be overridden; the effective context limit is enforced by
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` instead. Zero token usage means the LiteLLM-side
streaming path is not returning usage (`stream_options.include_usage`) and
auto-compact will not work.

If `claude-glm` still says Sonnet/Opus, check whether the user launched an old shell or old session. The wrapper must export `ANTHROPIC_MODEL` and `ANTHROPIC_CUSTOM_MODEL_OPTION` and pass `--model "$ANTHROPIC_MODEL"` to `claude`; then restart the interactive `claude-glm` process. If plain `claude` says Sonnet/Opus, that is expected in side-by-side mode.

For Z.ai MCP search, verify the MCP connection:

```bash
claude mcp get web-search-prime
```

Successful output should show `Status: ✓ Connected`. If it is connected, Claude Code can call `mcp__web-search-prime__web_search_prime`.

For LiteLLM-backed search, verify that the model is not choosing Claude Code local fetch:

```bash
claude-glm -p '搜索今天的新闻，只列1条。'
```

With `EXA_API_KEY` available to LiteLLM, successful output should return current-news text and source URLs. Without a search key, the request should still complete, but it will not have injected live search results. Interactive Claude Code should not show `Fetch(https://...)` for search-intent prompts after the CCR transformer filters local fetch tools.

## Troubleshooting

- **`Not logged in` from `claude-glm`**: Claude was started without router environment variables. Use the wrapper, `ccr code`, or export `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`.
- **Plain `claude` still uses Claude/Sonnet/Opus**: Expected in side-by-side mode. Use `claude-glm` for Huawei MaaS.
- **`claude-glm` interactive mode shows Sonnet/Opus but JSON shows `glm-5.1`**: Ensure the wrapper invokes `claude --model "$ANTHROPIC_MODEL"` instead of only `ccr code`.
- **`HUAWEI_MAAS_API_KEY, MAAS_API_KEY, or API_KEY is not set`**: Export one of those variables before running `configure-claude-glm.sh`.
- **`claude-glm` hangs before Claude Code starts**: Check the generated wrapper. It must not run foreground `ccr start >/dev/null`; it should background `ccr start`, then wait until `ccr status` includes `Status: Running`.
- **`Unable to connect to API (FailedToOpenSocket)` or `ConnectionRefused` against `http://127.0.0.1:3456/v1/messages?beta=true`**: Treat this as a local router/socket problem first, not a MaaS key problem. Check `ccr status`, `ss -ltnp | grep ':3456'`, and `curl -fsS -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" http://127.0.0.1:3456/`. If status says running but curl fails, stop and restart `ccr`; the side-by-side wrapper should do this automatically.
- **`ccr failed to start; see /tmp/claude-glm-ccr.log` after an automatic restart**: This can be a stop/start race where the old router process or port has not fully released. Use the current wrapper logic that waits for `ccr stop`, then waits up to 30 seconds for a real router health check. Inspect `/tmp/claude-glm-ccr.log` and `ccr status` if it still fails.
- **Persistent `ccr` did not start after reboot/login**: Check `systemctl --user is-enabled claude-glm-ccr.service claude-glm-ccr-health.timer`, `systemctl --user status claude-glm-ccr.service --no-pager`, and `loginctl show-user "$USER" -p Linger`. On systems without a running user systemd manager, run with `INSTALL_SYSTEMD_USER_SERVICE=0` and rely on wrapper startup instead.
- **Health timer keeps restarting `ccr`**: Check `journalctl --user -u claude-glm-ccr.service -u claude-glm-ccr-health.service --no-pager -n 100`, then verify `~/.config/claude-glm/env`, the router key, and `curl -fsS -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" http://127.0.0.1:3456/`.
- **`claude` hangs 60s+ with a wrong router token instead of failing fast**: CCR returns 401 in milliseconds, but the Claude Code CLI retries 401 responses for over a minute with no readable error. The generated wrapper sends one authenticated `GET /v1/models` preflight (~6ms; 404 on good auth, 401/403 on bad) and exits immediately with a readable message on 401/403; if you see that message, fix `ANTHROPIC_AUTH_TOKEN` / `CLAUDE_GLM_ROUTER_KEY` vs the CCR `APIKEY`, then `ccr restart`.
- **Misspelled model name still answers normally**: CCR silently falls back to the default route for unknown model names. The archived `assets/ccr/custom-router.js` rejects unknown models with a readable per-request 404 (throwing from a custom router does NOT work — CCR catches it and falls back silently; route to a non-existent provider instead). The rejection only works when `config.json` sets `CUSTOM_ROUTER_PATH`; `claude-*` names and the known model list always pass through so Claude Code background models are never blocked.
- **Prompts larger than ~128KB fail with `Argument list too long`**: Linux caps a single argv argument (MAX_ARG_STRLEN). Pipe large prompts via stdin instead of passing them as a CLI argument.
- **`usage.input_tokens` back to 0 / unknown models answered normally again**: something rewrote `~/.claude-code-router/config.json` to the legacy single-provider layout, bypassing the LiteLLM Anthropic adapter and the custom router. Run `scripts/restore-ccr-config.sh` to reinstall the archived 3-provider config, custom router, transformer plugins, and adapter, then restart ccr with the right env. Check for other agents or tooling on the host that regenerate CCR config before assuming the fix did not stick.
- **`Z_API_KEY is not set`**: Export `Z_API_KEY` before starting Claude Code or before running `claude mcp get web-search-prime`.
- **Z.ai MCP fails with auth errors**: Confirm the user has a Z.ai account, the API key is active, and the environment variable name is exactly `Z_API_KEY`.
- **Z.ai MCP was added with a literal `${Z_API_KEY}` header**: Replace the static `headers` entry with `headersHelper` so Claude Code reads the current environment at runtime.
- **Search prompt calls Claude Code `Fetch`/`WebFetch`**: Configure the CCR bridge with `configure-ccr-search.py`. The transformer should detect search intent and filter local search/fetch tools from the downstream request.
- **Search prompt has no live results**: Confirm `EXA_API_KEY` is visible to the LiteLLM process and inspect `litellm_proxy` logs for `[ExaSearch]`.
- **Search results are stale or missing URLs**: Inspect the LiteLLM callback and Exa provider response first. The model should answer only from injected LiteLLM search snippets when search succeeds.
- **`curl` fails with shared library errors**: Use Node `fetch` or `claude --print` for verification instead of curl.
- **Long context mismatch**: Set `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` so auto-compact fires before the MaaS hard input limit (196608 tokens for glm-5.1), leaving room for one full turn. Keep `maxtoken.max_tokens` as a generation cap such as `8192`. Do not rely on `CLAUDE_CODE_MAX_CONTEXT_TOKENS`: Claude Code only reads it when `DISABLE_COMPACT` is set. (`config.json` `longContextThreshold` of 120000 is the CCR routing threshold, separate from the auto-compact window.)
- **Session overflows at ~196k tokens even though usage looks fine**: Check that the LiteLLM-side streaming responses carry usage. The adapter must send `stream_options: {"include_usage": true}` upstream; without it Claude Code sees zero token usage, never triggers auto-compact, and runs into the MaaS hard input limit (196608 tokens for glm-5.1).
- **Existing `claude-glm` wrapper**: Preserve user changes. Inspect the wrapper before replacing it.

## Resources

- `scripts/configure-claude-glm.sh`: side-by-side installer that preserves `claude` and adds `claude-glm`/`Claude-glm`, deploying the production CCR config/custom-router/plugins and the local Anthropic adapter.
- `scripts/configure-ccr-search.py`: install the CCR bridge that strips local search/fetch tools and routes search-intent prompts toward LiteLLM-side Exa injection.
- `scripts/configure-zai-search-mcp.sh`: add and verify Z.ai `web-search-prime` MCP search using `Z_API_KEY`.
- `scripts/configure-claude-anou.sh`: opt-in installer for the `claude-anou` anonymous blind model-test command; writes the `assets/claude-anou` wrapper, seeds `~/.claude-code-router/.session-model`, and reuses the claude-glm env and CCR custom router. Requires claude-glm configured and LiteLLM `anon-model-a`/`anon-model-b` model groups.
- `assets/claude-anou`: archived `claude-anou` wrapper — shows `Anonymous-Model`, binds each project (`.mt`) to `anon-model-a`/`anon-model-b` via `~/.claude-code-router/.session-model`, and runs the same ccr bootstrap as claude-glm.
- `scripts/install-anthropic-adapter.sh`: idempotently install the LiteLLM Anthropic adapter (`adapter/`) that bridges CCR to LiteLLM `/v1/chat/completions` on port 4010 and carries streaming usage (`stream_options.include_usage`).
- `scripts/restore-ccr-config.sh`: restore the verified 3-provider CCR config, custom router, and transformer plugins from `assets/ccr/`, reinstall the adapter, and restart ccr with the env vars its placeholders need.
- `adapter/`: archived LiteLLM Anthropic adapter (server.js/start.sh/stop.sh) used by the deployed claude-glm chain; without it, usage reporting and auto-compact degrade.
- `assets/ccr/`: archived production CCR `config.json` (3 providers, `CUSTOM_ROUTER_PATH`, `APIKEY`), `custom-router.js` (unknown-model rejection, provider-existence guard), and `plugins/` (the transformer plugins `config.json` loads).
- `tests/`: production test plan matrix, concurrent Top-30 runner, fix plan, and test reports.
