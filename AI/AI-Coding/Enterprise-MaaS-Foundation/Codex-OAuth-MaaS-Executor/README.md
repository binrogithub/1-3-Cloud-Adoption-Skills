# Codex-OAuth-MaaS-Executor

Side-by-side `codex-forky` command for using Codex CLI with split routing:

- normal Codex tool/code execution turns -> forky execution backend, usually LiteLLM -> Huawei MaaS `glm-5.2`
- non-tool ordinary turns -> Codex ChatGPT/OAuth endpoint
- image turns -> Codex ChatGPT/OAuth endpoint
- plain `codex` remains unchanged

## Why A Bridge Is Needed

Codex CLI talks to model providers with the OpenAI Responses wire API. Forky exposes an Anthropic Messages-compatible API. This project adds a local bridge:

```text
codex-forky
  -> codex --profile forky
  -> http://127.0.0.1:3460/v1/responses
  -> codex-forky Responses bridge
  -> route by request shape
     -> tools/no image: forky http://127.0.0.1:3458/v1/messages -> glm-5.2
     -> no tools or image: https://chatgpt.com/backend-api/codex/responses -> Codex OAuth
```

The bridge does not execute shell commands or apply patches. Codex CLI keeps responsibility for sandboxing, approvals, command execution, and file edits.

## Prerequisites

- `codex` CLI installed.
- `node` and `curl` in PATH.
- Forky already installed and running, typically from `Opus-advisor-MaaS-executor`.
- Forky's execution backend already works, typically LiteLLM on `127.0.0.1:4000`.

## Quick Start

```bash
./scripts/configure-codex-forky.sh
codex-forky exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

Defaults:

```bash
FORKY_BASE_URL=http://127.0.0.1:3458
CODEX_FORKY_BRIDGE_URL=http://127.0.0.1:3460
CODEX_FORKY_ROUTER_KEY=codex-forky-local
CODEX_FORKY_MODEL=claude-sonnet-4-6       # forky route-facing model name
CODEX_FORKY_OAUTH_MODEL=gpt-5.5           # real Codex OAuth model for non-execution turns
CODEX_FORKY_CONTEXT_TOKENS=180000
CODEX_FORKY_MAX_OUTPUT_TOKENS=8192
```

## What The Installer Writes

- `~/.codex/forky.config.toml`
- `~/.codex-forky/model-catalog.json`
- `~/.codex-forky/codex-forky-responses-bridge.cjs`
- `~/.config/codex-forky/env`
- `~/.codex/skills/codex-oauth-maas-executor/`
- `~/.local/bin/codex-forky`
- `~/.local/bin/Codex-forky`
- `~/.local/bin/codex-forky-bridge-run`

When systemd user services are available, it also writes and starts:

- `~/.config/systemd/user/codex-forky-bridge.service`

Set `INSTALL_SYSTEMD_USER_SERVICE=0` to skip the service; the wrapper starts the bridge on demand.

## Routing Notes

Codex usually sends tool definitions during agentic execution. The bridge routes tool-bearing requests without image content to forky, and forky routes them to the configured execution backend.

For text-only prompts with no tools, the bridge bypasses forky and forwards the request to Codex's ChatGPT/OAuth Responses endpoint using `~/.codex/auth.json`.

Image input is advertised in the model catalog so Codex can pass screenshots or attached images through the bridge. Image requests bypass forky and go to Codex OAuth.

The bridge writes a route event to stderr for every request:

```json
{"route":"forky-execution","reason":"tools_no_image"}
{"route":"codex-oauth","reason":"no_tools"}
{"route":"codex-oauth","reason":"image"}
```

Set `CODEX_FORKY_ROUTE_LOG=0` to disable these route logs.

## Verification

```bash
./scripts/verify-codex-forky.sh
node tests/test-bridge-transform.js
node --check scripts/codex-forky-responses-bridge.cjs
node --check tests/test-bridge-transform.js
curl -fsS -H "Authorization: Bearer ${CODEX_FORKY_ROUTER_KEY:-codex-forky-local}" \
  http://127.0.0.1:3460/v1/responses
codex-forky exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

The verify script checks Codex OAuth tokens, forky health, forky `EXEC_MODEL=glm-5.2`, stale `gpt-5.5 high` runtime config, skill auto-discovery, bridge startup, no-tool OAuth routing to `gpt-5.5`, and tool routing into forky execution.

If `codex-forky` opens with `model: gpt-5.5 high` or repeatedly reads the wrong skill, the local runtime was configured before the lean profile was installed. Re-run:

```bash
env -u CODEX_FORKY_MODEL -u CODEX_FORKY_OAUTH_MODEL ./scripts/configure-codex-forky.sh
./scripts/verify-codex-forky.sh
```

Open a new `codex-forky` session after reconfiguration; existing sessions keep their old profile state.

## Rollback

```bash
systemctl --user disable --now codex-forky-bridge.service 2>/dev/null || true
rm -f ~/.local/bin/codex-forky ~/.local/bin/Codex-forky ~/.local/bin/codex-forky-bridge-run
rm -f ~/.codex/forky.config.toml
rm -rf ~/.codex-forky ~/.config/codex-forky
```

Rollback does not touch forky, Codex OAuth credentials, LiteLLM, or plain `codex`.
