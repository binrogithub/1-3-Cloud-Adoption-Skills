# How Codex-OAuth-MaaS-Executor works

Codex CLI expects the OpenAI Responses API. Forky expects the Anthropic Messages API. The Codex-OAuth-MaaS-Executor bridge adapts protocol only for execution requests; other requests stay on Codex OAuth.

```text
Codex CLI
  -> POST /v1/responses on codex-forky bridge
  -> if tools and no image: POST /v1/messages on forky -> execution backend
  -> if no tools or image: POST /backend-api/codex/responses on chatgpt.com
```

## What The Bridge Converts

- Responses `input` messages to Anthropic `messages`.
- Responses `instructions` to Anthropic `system`.
- Responses function/local shell tool definitions to Anthropic `tools`.
- Responses tool-call outputs to Anthropic `tool_result` blocks.
- Anthropic streamed text/tool-use events back to Responses streamed events.

The bridge does not run tools. Codex receives tool calls from the model and decides whether to run shell commands, apply patches, or ask for approval.

## Model Names

`CODEX_FORKY_MODEL` defaults to `claude-sonnet-4-6` because forky treats tool-bearing Sonnet requests as normal execution turns. It is a route-facing model name, not the final execution model.

`CODEX_FORKY_OAUTH_MODEL` is the real Codex OAuth model used for non-execution requests. The installer defaults it to `gpt-5.5`; set the environment variable before running `configure-codex-forky.sh` to choose a different Codex OAuth model.

## Route Logs

The bridge writes one structured route event to stderr for every request:

```json
{"route":"forky-execution","reason":"tools_no_image"}
{"route":"codex-oauth","reason":"no_tools"}
{"route":"codex-oauth","reason":"image"}
```

These logs go to `/tmp/codex-forky-bridge.log` when the wrapper starts the bridge with `nohup`, or to the user service journal when systemd is available. Set `CODEX_FORKY_ROUTE_LOG=0` to disable them.

## Boundaries

Forky remains the source of truth for:

- execution backend URL and model
- prompt caching behavior

Codex-OAuth-MaaS-Executor owns only:

- Codex profile and model catalog
- local Responses endpoint on `127.0.0.1:3460`
- Responses to Messages protocol conversion
- Codex OAuth forwarding for non-tool or image requests
- side-by-side `codex-forky` wrapper
