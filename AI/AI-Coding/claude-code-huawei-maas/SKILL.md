---
name: claude-code-huawei-maas
description: Configure Claude Code to use Huawei Cloud MaaS or ModelArts MaaS through an OpenAI-compatible endpoint, and optionally add Z.ai web-search-prime MCP search. Use when Codex needs to migrate Claude Code from Anthropic/Sonnet/Opus to Huawei MaaS models such as glm-5.1, install or configure claude-code-router, set API_KEY-based authentication, create a claude wrapper, adjust context length, verify that interactive Claude Code is actually backed by MaaS, or configure Z.ai MCP search with Z_API_KEY.
---

# Claude Code Huawei MaaS

## Overview

Use this skill to make `claude` route through `claude-code-router` (`ccr`) to Huawei Cloud MaaS OpenAI-compatible chat completions. It can also add the Z.ai `web-search-prime` MCP search tool for Claude Code. Prefer bundled scripts for repeatability, then inspect or patch only if the host has unusual paths or package managers.

## Quick Path

1. Confirm the user has a MaaS OpenAI-compatible base URL, model name, and API key environment variable. Do not write the raw key to files; reference `$API_KEY`.
2. Run `scripts/configure.sh` from this skill. Defaults match the tested setup:
   - base URL: `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
   - model: `glm-5.1`
   - context tokens: `190000`
   - max output tokens: `32768`
3. Verify both the router and Claude Code:
   - `ccr status`
   - `claude --bare --print --output-format json 'Reply with OK only'`
   - In interactive mode, the header should show `glm-5.1`, not Sonnet/Opus.
4. If the user also wants Z.ai search MCP, confirm they have a Z.ai account and API key, export it as `Z_API_KEY`, then run `scripts/configure-zai-search-mcp.sh`.

Example:

```bash
export API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure.sh
```

Override defaults when needed:

```bash
MAAS_BASE_URL='https://api-ap-southeast-1.modelarts-maas.com/openai/v1' \
MAAS_MODEL='glm-5.1' \
MAAS_CONTEXT_TOKENS=190000 \
MAAS_MAX_OUTPUT_TOKENS=32768 \
/root/.codex/skills/claude-code-huawei-maas/scripts/configure.sh
```

Add Z.ai search MCP:

```bash
export Z_API_KEY='...'
/root/.codex/skills/claude-code-huawei-maas/scripts/configure-zai-search-mcp.sh
```

## What The Script Does

- Installs `@musistudio/claude-code-router` globally with npm if `ccr` is missing.
- Writes `~/.claude-code-router/config.json` with a provider named `huawei-maas`.
- Uses `api_key: "$API_KEY"` in config so secrets remain in the environment.
- Sets the provider URL to `${MAAS_BASE_URL}/chat/completions`.
- Routes `default`, `background`, `think`, and `longContext` to `huawei-maas,<model>`.
- Wraps the current `claude` command and preserves the original binary as `<claude-path>.real`.
- Exports these defaults in the wrapper:
  - `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`
  - `ANTHROPIC_AUTH_TOKEN=test`
  - `ANTHROPIC_MODEL=<model>`
  - `ANTHROPIC_CUSTOM_MODEL_OPTION=<model>`
  - `CLAUDE_CODE_MAX_CONTEXT_TOKENS=<context>`
- Restarts `ccr` and validates a small request through `claude`.

## Manual Configuration

Use this if the script cannot be run or if the user wants to review each step.

1. Install CCR:

```bash
npm install -g @musistudio/claude-code-router
```

2. Write `~/.claude-code-router/config.json`:

```json
{
  "LOG": true,
  "LOG_LEVEL": "info",
  "API_TIMEOUT_MS": 600000,
  "NON_INTERACTIVE_MODE": false,
  "Providers": [
    {
      "name": "huawei-maas",
      "api_base_url": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions",
      "api_key": "$API_KEY",
      "models": ["glm-5.1"],
      "transformer": {
        "use": [
          ["maxtoken", { "max_tokens": 32768 }],
          "cleancache",
          "enhancetool"
        ]
      }
    }
  ],
  "Router": {
    "default": "huawei-maas,glm-5.1",
    "background": "huawei-maas,glm-5.1",
    "think": "huawei-maas,glm-5.1",
    "longContext": "huawei-maas,glm-5.1",
    "longContextThreshold": 190000
  }
}
```

3. Start or restart CCR:

```bash
ccr restart
```

4. Make `claude` use the router. Either run with `ccr code`, or wrap/export these variables before launching Claude Code:

```bash
export ANTHROPIC_AUTH_TOKEN=test
export ANTHROPIC_BASE_URL=http://127.0.0.1:3456
export ANTHROPIC_MODEL=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME=glm-5.1
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION='Huawei Cloud MaaS glm-5.1'
export CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000
unset CLAUDE_CODE_USE_BEDROCK
```

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

## Verification

Prefer a non-interactive JSON check because it reports actual `modelUsage`:

```bash
claude --bare --print --output-format json 'Reply with OK only'
```

Successful output should include:

```json
"modelUsage": {
  "glm-5.1": {
    "contextWindow": 200000
  }
}
```

If the interactive header still says Sonnet/Opus, check whether the user launched an old shell or old session. The wrapper must export `ANTHROPIC_MODEL` and `ANTHROPIC_CUSTOM_MODEL_OPTION`; then restart the interactive `claude` process.

For Z.ai MCP search, verify the MCP connection:

```bash
claude mcp get web-search-prime
```

Successful output should show `Status: ✓ Connected`. If it is connected, Claude Code can call `mcp__web-search-prime__web_search_prime`.

## Troubleshooting

- **`Not logged in`**: Claude was started without router environment variables. Use the wrapper, `ccr code`, or export `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`.
- **Interactive mode shows Sonnet but JSON shows `glm-5.1`**: Add `ANTHROPIC_MODEL` and `ANTHROPIC_CUSTOM_MODEL_OPTION` to the wrapper and restart `claude`.
- **`API_KEY is not set`**: Export `API_KEY` before `ccr start` or before launching `claude`; the config intentionally references `$API_KEY`.
- **`Z_API_KEY is not set`**: Export `Z_API_KEY` before starting Claude Code or before running `claude mcp get web-search-prime`.
- **Z.ai MCP fails with auth errors**: Confirm the user has a Z.ai account, the API key is active, and the environment variable name is exactly `Z_API_KEY`.
- **Z.ai MCP was added with a literal `${Z_API_KEY}` header**: Replace the static `headers` entry with `headersHelper` so Claude Code reads the current environment at runtime.
- **`curl` fails with shared library errors**: Use Node `fetch` or `claude --print` for verification instead of curl.
- **Long context mismatch**: Treat `190k` as context length, not output length. Keep `maxtoken.max_tokens` as a generation cap such as `32768`; set `CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000`.
- **Existing `claude` wrapper**: Preserve user changes. Inspect the wrapper before replacing it, and keep the original binary or script as `.real`.

## Resources

- `scripts/configure.sh`: end-to-end installer/configurator and smoke test.
- `scripts/configure-zai-search-mcp.sh`: add and verify Z.ai `web-search-prime` MCP search using `Z_API_KEY`.
