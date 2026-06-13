---
name: codex-huawei-maas
description: Configure a side-by-side codex-glm command that routes Codex CLI to Huawei Cloud MaaS glm-5.1 through a CCR /v1/responses shim while preserving the original codex command.
---

# Codex Huawei MaaS

Use this skill when the user wants `codex-glm` to use Huawei MaaS `glm-5.1` without changing the original `codex` command.

## Quick Path

1. Confirm the user has a Huawei MaaS OpenAI-compatible API key.
2. Run:

```bash
export API_KEY='replace-with-your-maas-api-key'
./scripts/configure-codex-glm.sh
```

3. Verify:

```bash
./scripts/test-codex-glm.sh
codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

## Behavior

- Creates `~/.codex/glm.config.toml` and `~/.codex-glm/model-catalog.json` and launches Codex with `--profile glm`.
- Keeps the original `codex` command untouched.
- Configures CCR to route to Huawei MaaS `/chat/completions`.
- Injects a reversible CCR route shim for `POST /v1/responses`.
- Stores secrets in `~/.config/codex-glm/env` with `0600` permissions.
- Defaults to `glm-5.1`, context window `120000`, and max output tokens `8192`.
- Writes a model catalog JSON so Codex resolves `glm-5.1` metadata without the fallback warning.
- Search and image routing are experimental opt-in paths:
  - `CODEX_GLM_ENABLE_SEARCH=1` routes default traffic through LiteLLM `/v1/responses` and installs the local search transformer.
  - `CODEX_GLM_ENABLE_IMAGE=1` advertises image input and adds a CCR `image` route through LiteLLM `/v1/chat/completions`.
  - `CODEX_GLM_IMAGE_MODEL` selects the LiteLLM model group for image requests and defaults to `vision-openrouter`.
  - These paths require the same LiteLLM `custom_callbacks.py` search/image hooks used by `claude-glm`.

## Rollback

```bash
RESTORE_CCR=1 ./scripts/configure-codex-glm.sh
ccr restart
```

## Limits

The v1 route shim supports text and the practical Codex coding-agent tool subset. Image input and web search are disabled by default and require the LiteLLM opt-in routes above. File search, remote MCP passthrough, and full Responses item streaming are still out of scope.
