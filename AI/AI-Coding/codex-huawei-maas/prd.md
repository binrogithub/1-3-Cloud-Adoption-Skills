# PRD: codex-huawei-maas / codex-glm

## 20 Design Questions And Best Answers

1. Should Codex connect directly to Huawei MaaS?
   No. Codex 0.139.0 only accepts `wire_api = "responses"`, while the tested Huawei MaaS endpoint returns 404 for `/responses`.

2. Where should the adapter live?
   In the CCR process. Install a small Node shim that adds `POST /v1/responses` to CCR and forwards to CCR's existing `/v1/messages` pipeline.

3. Should v1 support Codex tool calls?
   Yes, for the practical coding-agent subset: function calling, tool outputs, `local_shell`, and `apply_patch` item mapping.

4. Why not support tool calls in v1?
   The shim should map protocols only. Codex CLI remains responsible for sandboxing, approvals, command execution, and patch application.

5. How should Codex config be isolated?
   Use `~/.codex/glm.config.toml` and `codex --profile glm`; do not modify `~/.codex/config.toml`.

6. What is the command name?
   `codex-glm`, with a compatibility symlink `Codex-glm`.

7. How does `codex-glm` call Codex?
   It loads `~/.config/codex-glm/env`, health-checks CCR, then execs `codex --profile glm --model "$MAAS_MODEL" "$@"`.

8. Which port layout is used?
   `codex-glm` uses an isolated CCR home and listens on `127.0.0.1:3457`; this avoids overwriting or restarting any shared CCR process used by `claude-glm`.

9. Should systemd user service be installed?
   Yes by default, with `INSTALL_SYSTEMD_USER_SERVICE=0` to disable it.

10. What is the failure recovery policy?
    The wrapper restarts CCR once if unhealthy. The optional systemd health timer continuously checks and restarts CCR.

11. Where are secrets stored?
    `~/.config/codex-glm/env`, mode `0600`.

12. Is the CCR change reversible?
    Yes. The installer backs up `dist/cli.js`, injects one marked `require(...)` line, and supports `RESTORE_CCR=1`.

13. Is the installer idempotent?
    Yes. Re-running updates generated files and does not duplicate the CCR injection line.

14. What is the default model?
    `glm-5.1`.

15. What is the default MaaS base URL?
    `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`, with CCR provider URL `${MAAS_BASE_URL}/chat/completions`.

16. What is the default max output token limit?
    `8192`, via CCR `maxtoken`.

17. What is the default context window?
    `120000`, used in the Codex profile and CCR long-context threshold.

18. Are web search and image inputs supported?
    Yes, as experimental opt-in routes. `CODEX_GLM_ENABLE_SEARCH=1` routes through LiteLLM search injection; `CODEX_GLM_ENABLE_IMAGE=1` advertises image input and adds the LiteLLM vision route. `CODEX_GLM_IMAGE_MODEL` controls the LiteLLM vision model group and defaults to `vision-openrouter`.

19. What is the acceptance smoke test?
    `codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"` returns `OK`.

20. What files does the repository ship?
    `prd.md`, `README.md`, `SKILL.md`, `scripts/configure-codex-glm.sh`, `scripts/codex-glm-ccr-responses-shim.cjs`, and `scripts/test-codex-glm.sh`.

## Goal

Provide a side-by-side `codex-glm` command that keeps the original `codex` command on its existing OpenAI/ChatGPT behavior while routing only `codex-glm` through CCR to Huawei MaaS `glm-5.1`.

## Non-Goals

- Do not replace the original `codex`.
- Do not add a separate bridge service or port.
- Do not enable image or web search by default before the operator has configured LiteLLM callbacks and upstream keys.
- Do not support file search, remote MCP passthrough, or full Responses item streaming semantics in v1.
- Do not execute shell commands or apply patches in the shim.

## Architecture

```text
codex-glm
  -> codex --profile glm --model glm-5.1
  -> http://127.0.0.1:3457/v1/responses
  -> CCR Responses route shim
  -> CCR existing /v1/messages routing/provider pipeline
  -> Huawei MaaS /openai/v1/chat/completions
  -> glm-5.1
```

Experimental search route:

```text
codex-glm search-intent prompt
  -> CCR Responses route shim
  -> isolated CCR LiteLLM Provider
  -> LiteLLM /v1/responses
  -> custom_callbacks.py injects Exa results when EXA_API_KEY is configured
  -> glm-5.1 answers from injected results
```

Experimental image route:

```text
codex-glm image prompt
  -> CCR Responses route shim preserves image blocks
  -> isolated CCR Router.image
  -> LiteLLM /v1/chat/completions
  -> custom_callbacks.py rewrites model to vision-openrouter
  -> OpenRouter vision model answers
```

## Acceptance Criteria

- `codex-glm --version` passes through to Codex CLI.
- `codex --version` remains unaffected.
- `codex --profile glm --strict-config --help` parses the profile.
- `curl http://127.0.0.1:3457/v1/responses` no longer returns route missing after installation.
- `~/.claude-code-router/config.json` is not modified by `codex-glm` installation or wrapper startup.
- `codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"` returns `OK`.
- `RESTORE_CCR=1 ./scripts/configure-codex-glm.sh` restores the original CCR `dist/cli.js`.
- Function tools and tool outputs are converted between Codex Responses and CCR's Anthropic-style `/v1/messages` payload.
- Upstream `tool_use` blocks are converted back to Responses tool items.
- `CODEX_GLM_TRACE=1` writes redacted fixtures.
- Upstream calls retry HTTP 429 responses; optional serialization is controlled by `CODEX_GLM_UPSTREAM_RPS`.
- With `CODEX_GLM_ENABLE_SEARCH=1`, generated model catalog sets `supports_search_tool: true`, isolated CCR default route points to LiteLLM, and the local search transformer is installed.
- With `CODEX_GLM_ENABLE_IMAGE=1`, generated model catalog includes image modality and isolated CCR config includes `Router.image` pointing at `CODEX_GLM_IMAGE_MODEL`.
- `node tests/test-shim-transform.js` verifies search intent handling and image block preservation.
- `bash tests/test-configure-generation.sh` verifies search/image config generation without touching real `codex`, `ccr`, or `~/.claude-code-router`.
