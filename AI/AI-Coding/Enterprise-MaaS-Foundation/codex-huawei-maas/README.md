# codex-huawei-maas

Side-by-side `codex-glm` command for using Codex CLI with Huawei Cloud MaaS `glm-5.1` through `claude-code-router` (CCR).

## Why A CCR Shim Is Needed

Codex 0.139.0 only accepts model providers that use the OpenAI Responses wire API. Huawei MaaS exposes an OpenAI-compatible Chat Completions endpoint, but the tested MaaS base URL returns 404 for `/responses`.

This project extends CCR with a local `POST /v1/responses` route. Codex talks Responses to CCR, and CCR continues routing to Huawei MaaS `/chat/completions`.

```text
codex-glm
  -> codex --profile glm
  -> CCR http://127.0.0.1:3457/v1/responses
  -> CCR /v1/messages pipeline
  -> Huawei MaaS /openai/v1/chat/completions
  -> glm-5.1
```

## Quick Start

```bash
export API_KEY='replace-with-your-maas-api-key'
./scripts/configure-codex-glm.sh
codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

The installer accepts `HUAWEI_MAAS_API_KEY`, `MAAS_API_KEY`, or `API_KEY`.

## What The Installer Writes

- `~/.codex-glm/ccr-home/.claude-code-router/config.json`
- `~/.codex/glm.config.toml`
- `~/.codex-glm/model-catalog.json`
- `~/.config/codex-glm/env`
- `~/.local/bin/codex-glm`
- `~/.local/bin/Codex-glm`
- CCR `dist/codex-glm-ccr-responses-shim.cjs`
- one marked `require("./codex-glm-ccr-responses-shim.cjs")` line in CCR `dist/cli.js`

When systemd user services are available, it also installs:

- `~/.config/systemd/user/codex-glm-ccr.service`
- `~/.config/systemd/user/codex-glm-ccr-health.service`
- `~/.config/systemd/user/codex-glm-ccr-health.timer`

Set `INSTALL_SYSTEMD_USER_SERVICE=0` to skip systemd units and rely on wrapper startup.

## Defaults

```bash
MAAS_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
MAAS_MODEL=glm-5.1
MAAS_CONTEXT_TOKENS=120000
MAAS_MAX_OUTPUT_TOKENS=8192
CODEX_GLM_CCR_HOME=~/.codex-glm/ccr-home
CCR_BASE_URL=http://127.0.0.1:3457
CODEX_GLM_ROUTER_KEY=codex-glm-local
CODEX_GLM_UPSTREAM_RPS=0
CODEX_GLM_429_RETRIES=3
CODEX_GLM_ENABLE_SEARCH=0
CODEX_GLM_ENABLE_IMAGE=0
CODEX_GLM_IMAGE_MODEL=vision-openrouter
LITELLM_BASE_URL=http://127.0.0.1:4000
LITELLM_CCR_KEY=<defaults to LITELLM_API_KEY/MAAS_API_KEY/HUAWEI_MAAS_API_KEY>
```

## Tool Calling

The shim converts the practical Codex Responses subset used by coding agents:

- Responses `function` tools to Anthropic-style `tools` for CCR.
- Responses function call outputs to Anthropic `tool_result` messages.
- Upstream `tool_use` blocks back to Responses `function_call` items.
- `local_shell` and `apply_patch` tool names back to Codex response item types.

The shim does not execute shell commands or apply patches. Codex CLI remains responsible for sandboxing, approvals, command execution, and file edits.

## Search And Image Routing

Search and image support are experimental and disabled by default. Enable them only when LiteLLM is running with the `custom_callbacks.py` search/image hooks used by `claude-glm`.

```bash
CODEX_GLM_ENABLE_SEARCH=1 \
CODEX_GLM_ENABLE_IMAGE=1 \
CODEX_GLM_IMAGE_MODEL=vision-openrouter \
LITELLM_BASE_URL=http://127.0.0.1:4000 \
LITELLM_CCR_KEY="$LITELLM_CCR_KEY" \
./scripts/configure-codex-glm.sh
```

When search is enabled, the isolated CCR config routes default traffic through LiteLLM `/v1/responses` and installs a local `claude-websearch-to-responses` transformer. Search-intent prompts have tools stripped before the model call; LiteLLM injects Exa results when `EXA_API_KEY` is available.

When image is enabled, the model catalog advertises image input, and the isolated CCR config adds an `image` route through LiteLLM `/v1/chat/completions`. The image route defaults to `CODEX_GLM_IMAGE_MODEL=vision-openrouter`; set it to another LiteLLM vision-capable model group if needed.

## Trace And Rate Limits

Set `CODEX_GLM_TRACE=1` to write redacted request fixtures under `/tmp/codex-glm-traces`, or set `CODEX_GLM_TRACE_DIR` to another directory.

Huawei MaaS test quota has been observed at 1 request per second. Set `CODEX_GLM_UPSTREAM_RPS` to serialize upstream calls when needed; the default `0` disables local throttling. The shim retries HTTP 429 responses with jitter. Use `CODEX_GLM_429_RETRIES=0` to disable 429 retries.

## Verification

```bash
./scripts/test-codex-glm.sh
bash tests/test-configure-generation.sh
codex --version
codex-glm --version
codex --profile glm --strict-config --help
curl -fsS -H "Authorization: Bearer ${CODEX_GLM_ROUTER_KEY:-codex-glm-local}" \
  http://127.0.0.1:3457/
```

The end-to-end test is:

```bash
codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

## Rollback

Restore the original CCR `dist/cli.js`:

```bash
RESTORE_CCR=1 ./scripts/configure-codex-glm.sh
HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}" ccr restart
```

This removes the injected shim line. It does not delete your `~/.codex/glm.config.toml`, `~/.config/codex-glm/env`, or isolated CCR home under `~/.codex-glm/ccr-home`.

## v1 Limits

- Text and basic tool-calling requests.
- Function calling, function outputs, `local_shell`, and `apply_patch` are protocol-mapped.
- Image inputs and web search are experimental opt-in paths that require LiteLLM callbacks and upstream keys.
- File search, remote MCP passthrough, and full Responses item streaming are not supported.
- The original `codex` command is not replaced.
