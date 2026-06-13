# LiteLLM Anthropic Adapter

Minimal Node.js (no dependencies) protocol bridge that exposes an Anthropic
`/v1/messages` endpoint and forwards to a LiteLLM OpenAI-compatible
`/v1/chat/completions` endpoint.

## Position in the chain

```
claude-glm wrapper -> ccr (127.0.0.1:3456) -> litellm-anthropic-adapter (127.0.0.1:4010)
                   -> LiteLLM (127.0.0.1:4000, docker) -> Huawei MaaS glm-5.1
```

ccr routes Anthropic-format requests for adapter-backed models (see
`assets/ccr/custom-router.js`) to this adapter; the adapter converts
Anthropic messages/tools/streaming SSE to and from the OpenAI chat
completions format.

## Files

- `server.js` — the adapter. Listens on `ADAPTER_HOST:ADAPTER_PORT`
  (default `127.0.0.1:4010`), forwards to `LITELLM_CHAT_URL`
  (default `http://127.0.0.1:4000/v1/chat/completions`). Includes the
  `stream_options.include_usage` fix (so usage tokens arrive in streaming
  responses) and tool-call argument guardrails for Bash/Read/Write/Edit.
- `start.sh` — idempotent background start (PID file
  `/tmp/litellm-anthropic-adapter.pid`, log
  `/tmp/litellm-anthropic-adapter.log`), waits for `/health`.
- `stop.sh` — stops the PID-file process.

## Environment

`server.js` loads `ENV_FILE` (default `/root/LiteLLM/.env`) at startup and
needs one of:

- `LITELLM_ANTHROPIC_KEY` (preferred), or
- `LITELLM_CCR_KEY`

as the default Bearer key for LiteLLM when the incoming request carries no
usable key (CCR forwards unexpanded `$VAR` placeholders, which the adapter
ignores on purpose).

## Relation to the claude-glm wrapper

The deployed `claude-glm` wrapper (`~/.local/bin/claude-glm`) calls
`ensure_anthropic_adapter`, which runs `~/litellm-anthropic-adapter/start.sh`
if it exists and is executable — so the adapter is started on demand before
ccr is health-checked. Install these files to that location with
`scripts/install-anthropic-adapter.sh`.
