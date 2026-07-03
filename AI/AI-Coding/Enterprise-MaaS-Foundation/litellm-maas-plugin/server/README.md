# LiteLLM Gateway Setup for Claude Code (Server Side)

Make a LiteLLM proxy serve **native Claude Code** clients over the Anthropic
`/v1/messages` protocol, backed by an OpenAI-compatible reasoning model
(GLM-5.2 on Huawei MaaS in this deployment). Supports many concurrent Claude
Code clients, each with its own virtual key, budget, and rate limits.

```
Claude Code #1 ─┐  each with its own LiteLLM virtual key
Claude Code #2 ─┼──Anthropic /v1/messages──►  LiteLLM :4000
Claude Code #N ─┘                             │  auth / budgets / tpm / rpm / Prometheus
                                              │  anthropic_stream_guard  (this plugin)
                                              │  claude-* wildcard route
                                              ▼
                                       GLM-5.2 (/chat/completions)
```

## Why a plugin is needed

Two defects break native Claude Code against LiteLLM + OpenAI-compatible
reasoning backends (verified on `litellm v1.83.14-stable.patch.3`):

1. **Request routing.** Anthropic `thinking`/`reasoning` params (sent by
   Claude Code at high/max effort) force LiteLLM to call the OpenAI
   **Responses API** (`/responses`), which MaaS-style backends do not serve →
   `404 APIG.0101`, and repeated failures trip the router cooldown
   (`429 No deployments available`).
2. **Stream protocol.** The messages→chat/completions adapter emits the whole
   response as **one `text` content block mixing `thinking_delta` and
   `text_delta`** — an Anthropic protocol violation. Claude Code tolerates it
   for short replies but fails under heavy thinking (`/effort max`).

`anthropic_stream_guard` (a LiteLLM custom callback — **no LiteLLM source
patched**) fixes both:

- `async_pre_call_hook` strips `thinking` / `reasoning` / `reasoning_effort`
  so requests stay on `/chat/completions`
  (disable via `ASG_STRIP_THINKING=false` if your claude-* aliases point at a
  real Anthropic upstream).
- `async_post_call_streaming_iterator_hook` re-sequences the outgoing SSE
  stream: retypes the first content block to match its deltas and synthesizes
  the missing `content_block_stop`/`content_block_start` pairs (with index
  remapping) when the delta family flips. Already-correct streams pass through
  byte-identical; failures are fail-open (pass-through). OpenAI-protocol
  streams (`/chat/completions` clients) are never touched.

It also diagnoses a separate endpoint-capability failure: if the model emits
raw `<tool_call>` markup as ordinary text, Claude Code will display that text
and no tool will execute. The guard reports this via
`asg_unparsed_tool_markup_total`, but it does not rewrite model-invented
markup. Enable structured function/tool calling on the backend endpoint.

Design details: [`../docs/PRD-anthropic-stream-guard.md`](../docs/PRD-anthropic-stream-guard.md)

## Install

```bash
./install-litellm-plugin.sh                # defaults: /root/LiteLLM, service litellm
./install-litellm-plugin.sh --dry-run      # preview changes
./install-litellm-plugin.sh --uninstall    # roll back mount + callback
```

The script is idempotent, backs up every file it touches (`.bak.<timestamp>`),
and performs:

| Step | File | Change |
|---|---|---|
| mount plugin | `docker-compose.yml` | `- <repo>/litellm_plugins/anthropic_stream_guard/callback.py:/app/anthropic_stream_guard.py:ro` |
| register callback | `litellm_config.yaml` | `litellm_settings.callbacks: - anthropic_stream_guard.proxy_handler_instance` |
| routing flag | `litellm_config.yaml` | `litellm_settings.use_chat_completions_url_for_anthropic_messages: true` |
| restart + verify | container | health wait + in-container import check |

> The plugin **must** be mounted as a single file at
> `/app/anthropic_stream_guard.py`: LiteLLM's `get_instance_fn` resolves
> callbacks as `<module>.py` next to the config file and does not support
> package directories.

## Required LiteLLM configuration (manual, deployment-specific)

**1. Model routes.** Claude Code sends several internal model names
(`claude-opus-4-6`, `claude-haiku-4-5-20251001`, …). Map them all with a
wildcard entry in `model_list`:

```yaml
  - model_name: "claude-*"
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    model_info:
      max_input_tokens: 192000
      max_output_tokens: 128000
```

**2. Router tuning (single-deployment models).** Defaults can turn a few
failures into a 30 s total outage:

```yaml
router_settings:
  allowed_fails: 1000   # effectively disable cooldown for a single deployment
  cooldown_time: 5
```

**3. Per-client virtual keys.** Issue one key per Claude Code client; the ACL
must cover the wildcard:

```bash
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "content-type: application/json" \
  -d '{"key_alias":"claude-code-alice","models":["claude-*"],
       "max_budget":100,"tpm_limit":500000,"rpm_limit":30}'
```

**4. Network.** For remote clients, expose port 4000 to their IPs only
(cloud security group). LiteLLM already binds `0.0.0.0:4000` in this compose.

## Verify

```bash
# stream protocol check: first block must be "thinking", no mixed deltas
curl -sN http://127.0.0.1:4000/v1/messages \
  -H "content-type: application/json" -H "x-api-key: <key>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-opus-4-6","max_tokens":256,"stream":true,
       "thinking":{"type":"enabled","budget_tokens":2048},
       "messages":[{"role":"user","content":"what is 2+2? think briefly"}]}' \
  | grep -oE "\"type\": \"(text|thinking|thinking_delta|text_delta)\"" | head

# tool-call capability check (issue #111):
python3 ../tests/live_smoke.py tools

# full regression (text / 185K context / image / search / tools):
python3 ../tests/live_smoke.py all
```

Expected: `content_block_start` types match their delta families
(`thinking` block first, then `text`), and an interactive Claude Code client
works at `/effort max`.

For the tool-call check, expected is `PASS - structured tool_use block`. If it
reports raw tool markup, fix the backend route: for Huawei MaaS, use an
endpoint with function calling enabled for OpenAI-compatible requests; for
self-hosted vLLM, start with `--enable-auto-tool-choice` and the matching
`--tool-call-parser`.

## Rollback

`./install-litellm-plugin.sh --uninstall` (removes mount + callback,
restarts), or restore the `.bak.<timestamp>` files and restart. The plugin is
stateless.

## Compatibility

- Tested on `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`.
- Idempotent with future LiteLLM fixes: if upstream emits correct streams,
  the guard rewrites nothing.
- Coexists with other callbacks (Prometheus, budgets, search/vision
  enrichment); it only inspects Anthropic-format SSE chunks.
