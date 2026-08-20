---
name: litellm-maas-auto-plugin
description: Deploy, configure, verify, upgrade, troubleshoot, or remove a LiteLLM bridge for native Claude Code and OpenCode backed by Huawei MaaS GLM-5.2 and OpenRouter. Use for Anthropic Messages compatibility, GLM reasoning filtering, structured tool calls, multilingual smart routing, context length-band policy, prefix-affinity hashing, vision routing, virtual keys, agent tool-call loop protection, or end-to-end gateway validation.
---

# LiteLLM MaaS Auto Plugin

Operate the production bridge without exposing provider keys to coding clients.
Preserve unrelated callbacks, mounts, budgets, metrics, and user configuration.

## Architecture

```text
Claude Code → /v1/messages
            → smart_router
            → anthropic_stream_guard
            → anthropic_reasoning_filter
            → GLM-5.2 or OpenRouter

OpenCode   → /v1/chat/completions
           → smart_router
           → GLM-5.2 or OpenRouter
```

Use three model roles:

- `glm-5.2`: the mainline. Code generation, fixes, tests, architecture,
  refactoring, and all ordinary engineering work. Keyword-based premium
  escalation was removed (it bare-token-matched `auth`/`payment`/`design` and
  routed ordinary coding to premium at full cold-prefill cost).
- `premium-openrouter`: cross-provider fallback target for the mainline, used
  only when an upstream 5xx replays a bounded conversation. No longer a routing
  destination; the capability-gap branch (phase 4) will use it for measured
  failures.
- `vision-openrouter`: screenshots, images, and visual/UI design.

Recognize routing intent in Chinese, English, Brazilian Portuguese, and
Spanish. Keep unmatched execution work on the requested GLM-backed alias.

## Required inputs

- LiteLLM deployment directory and Compose service/container names.
- Working `glm-5.2`, `premium-openrouter`, and `vision-openrouter` groups.
- MaaS and OpenRouter credentials in server-side environment files.
- LiteLLM master key for issuing scoped virtual keys.

Never print or commit MaaS, OpenRouter, master, or virtual keys. Keep
key-bearing files at mode `0600`.

## Preflight

Run read-only checks before editing:

```bash
docker compose ps
curl -fsS http://127.0.0.1:4000/health/liveliness
docker inspect litellm_proxy --format \
  '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Inspect the active LiteLLM config and generator. Persist every model or
callback change in both places when regeneration would otherwise erase it.

## Install callbacks

Preview and apply:

```bash
server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir> \
  --dry-run

server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir>
```

Register callbacks in this order:

```yaml
litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true
  callbacks:
    - anthropic_stream_guard.proxy_handler_instance
    - anthropic_reasoning_filter.proxy_handler_instance
    - smart_router.proxy_handler_instance
    - glm_loop_breaker.proxy_handler_instance
```

The deployment may combine `smart_router` with another operational callback.
Keep the stream guard before the reasoning filter because LiteLLM chains
stream iterators in callback order.

### Anthropic stream guard

Use `litellm_plugins/anthropic_stream_guard/callback.py` to:

- strip incompatible Claude-only request controls;
- repair mixed thinking/text block families and indexes;
- synthesize missing terminal events after early upstream termination;
- preserve structured tools and diagnose raw `<tool_call>` markup;
- re-surface queued user interjections;
- fail open without logging payloads.

### Reasoning filter

Keep GLM thinking enabled upstream:

```yaml
litellm_params:
  extra_body:
    thinking:
      type: enabled
```

Use `litellm_plugins/anthropic_reasoning_filter/callback.py` to hide
`thinking`, `redacted_thinking`, `thinking_delta`, and `signature_delta` only
from Anthropic responses. Compact remaining block indexes to `0..n`. Preserve
text, `tool_use`, usage, stop reasons, and `message_stop`.

Do not disable GLM thinking merely to hide it in Claude Code. OpenAI-compatible
clients such as OpenCode must still be able to receive `reasoning_content`.

Disabling thinking also costs the model its ability to escape agent tool-call
loops. Measured on one glm-5.2 route from a context seeded with three loop
iterations: 12 of 12 runs looped with thinking disabled, 1 of 6 with it enabled.
Verify thinking is actually live by reading `reasoning_tokens` and the length of
`reasoning_content` in a response — a model-level `extra_body` overrides a
request-level `thinking` parameter, so the request is not evidence. See
`docs/archive/PRD-glm-loop-breaker.md`.

### Loop breaker

Use `litellm_plugins/glm_loop_breaker/callback.py` as the second line of defence
behind thinking. It fingerprints assistant tool calls already in the request,
detects repeating cycles of period 1-3 at the tail of the history, then raises
`temperature` to a floor and finally appends an instruction to stop retrying.

Register it last so it sees the request after routing has chosen a model.

Its default model pattern covers `glm` and `claude-glm-5.2` (the public GLM
model group). Check `GLM_LOOP_MODEL_PATTERN` against the deployment's own
`model_list`.

### Smart router

Use `litellm_plugins/smart_router/callback.py`. GLM-5.2 owns every final
response. The router never routes a whole turn to Vision or Premium — those
are bounded Sidecars that inject structured context into the same GLM request.

**Sidecar flow (PRD product contract):**

1. **GLM mainline**: every request stays on `claude-glm-5.2`.
2. **Vision Sidecar**: if the request carries image content, the sidecar
   extracts images, sends each to Luna (`vision-openrouter`) for a structured
   description, injects the caption text in-place, and GLM-5.2 produces the
   sole user-facing answer. Exactly one Luna attempt; on failure, exactly one
   Luna Pro (`vision-openrouter-secondary`) attempt — inherited LiteLLM
   retries/fallbacks are disabled for these internal calls. If both fail, the
   request returns an explicit `VISION_SIDECAR_UNAVAILABLE` error; GLM never
   guesses image content. Successful descriptions are cached by image SHA-256
   in the LiteLLM-mounted local volume; a repeated image makes zero new Vision
   calls.
3. **Premium Sidecar**: on a tool-call failure or loop, the sidecar makes at
   most one bounded Premium (`premium-openrouter`) advisory call, injects the
   advice, and returns control to GLM-5.2 for the final response.

Length is never a routing trigger. Estimated input is classified into bands
(normal/advisory/oversize), tagged in metadata and counted in a metric, but
the request stays on GLM. Never escalate to another model on length alone.

Load multilingual intent rules from
`litellm_plugins/smart_router/smart_router_rules.json`. Validate edits against
`smart_router_rules.schema.json`; the callback also rejects unknown keys,
invalid regexes, and duplicate rule IDs.

Record `estimated_tokens`, `matched_rule`, `router_version`, `length_band`,
and the selected request-scoped fallback chain under `metadata.smart_router`.

Same-provider fallback (GLM → `glm-5.1-fallback`) is token-capped at
`SMART_ROUTER_FALLBACK_TOKEN_CAP`. Cross-border fallback is gated on a
`data_residency` tag read from the virtual key/team context
(`user_api_key_dict.metadata.data_residency == "china-only"`) or the server-side
`SMART_ROUTER_DEFAULT_DATA_RESIDENCY` env — not from client request metadata.

When `SMART_ROUTER_DEPLOYMENT_COUNT` is greater than `1`, mainline traffic is
pinned to a stable `SMART_ROUTER_MAINLINE_PREFIX-<idx>` alias via a stateless
SHA-256 consistent hash over `metadata.session_id` (preferred) or the system
prompt plus first user text. The hash is plain SHA-256, so it is stable across
restarts. The pinned alias falls back to the `SMART_ROUTER_MAINLINE_GROUP`
same-provider group.

A normal client virtual key may access ONLY `claude-glm-5.2`. The internal
Sidecar key (server-admin operation only) accesses the Sidecar and fallback
groups (`vision-openrouter`, `vision-openrouter-secondary`,
`premium-openrouter`, `glm-5.1-fallback`) — never grant these to a client
key. Do not reuse the LiteLLM master key or MaaS key on clients.

Expose and monitor:

- `smart_router_requests_total{route,matched_rule,router_version}`
- `smart_router_fallbacks_total{source,target,reason}`
- `smart_router_cross_border_blocks_total{matched_rule}` (residency blocks via key/env tag)
- `smart_router_length_band_total{band}`
- `mainline_deployment_selected_total{deployment}`

### Retry and budget controls

- Limit an execution item to two model attempts. Include concise failure
  evidence in the second attempt; after that, return `needs_escalation` and do
  not route the same item back to GLM.
- Give interactive clients, CI, and recurring loops separate virtual keys.
- Set per-key rolling budgets plus RPM and TPM limits as circuit breakers.
- Treat 429 as capacity/budget backpressure: use bounded exponential backoff
  with jitter, honor `Retry-After`, and stop rather than creating a retry
  storm.
- Bound workflow concurrency to the virtual key's RPM/TPM capacity and set a
  hard wall-clock timeout.

## Model routes

The public GLM model group (the only model a client key may access):

```yaml
- model_name: "claude-glm-5.2"
  litellm_params:
    model: openai/glm-5.2
    api_base: os.environ/HUAWEI_MAAS_API_BASE
    api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    extra_body:
      thinking:
        type: enabled
  model_info:
    max_input_tokens: 1000000
    max_output_tokens: 128000
```

Internal Sidecar groups (server-only, accessed by a dedicated internal key —
never by a client key). Vision (Luna/Luna-Pro) and Premium (Opus 5) are
bounded sidecars that never produce the final user-facing response:

```yaml
- model_name: vision-openrouter
  litellm_params:
    model: openrouter/openai/gpt-5.6-luna

- model_name: vision-openrouter-secondary
  litellm_params:
    model: openrouter/openai/gpt-5.6-luna-pro

- model_name: premium-openrouter
  litellm_params:
    model: openrouter/anthropic/claude-opus-5
```

Native Claude (`default`, `opus`, `sonnet`, `haiku`) bypasses LiteLLM entirely
and is never remapped. Supply credentials, limits, and pricing through the
deployment configuration.

## Virtual keys

Issue one scoped key per client or host. A normal client key may access ONLY
`claude-glm-5.2`:

```json
["claude-glm-5.2"]
```

The internal Sidecar key (server-admin operation only) may access exactly the
Sidecar groups:

```json
["vision-openrouter", "vision-openrouter-secondary", "premium-openrouter"]
```

Store key responses in separate `0600` files. Do not reuse the LiteLLM master
key or MaaS key on clients.

## Configure clients

### Claude Code

Install the isolated GLM-5.2 launcher (native `claude` is never modified):

```bash
echo "sk-virtual-key" | client/claude-litellm-setup.sh \
  --base-url http://127.0.0.1:4000
client/claude-litellm-setup.sh --verify
claude-litellm   # start a GLM session
```

The gateway key is read from stdin or `CLAUDE_LITELLM_KEY` — never from argv.
`claude-glm-5.2` is the one public GLM model group; native Claude model names
are not remapped. To migrate from the old global-remapping setup, first preview
with `client/claude-litellm-migrate.sh --dry-run`. Model mappings are removed
automatically; legacy URL and credential fields require exact ownership
evidence, so apply with the full 64-char SHA-256 fingerprint of the old
gateway key:

```bash
FP=$(printf '%s' "$OLD_GATEWAY_KEY" | sha256sum | cut -d' ' -f1)
client/claude-litellm-migrate.sh --apply \
  --old-base-url http://127.0.0.1:4000 \
  --old-key-fingerprint "$FP"
```

A plain `--apply` without these flags only removes model mappings; it does
NOT complete migration if legacy URL/credentials remain.

### OpenCode

Use `@ai-sdk/openai-compatible` and `/v1/chat/completions`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "enterprise-maas/glm-5.2",
  "provider": {
    "enterprise-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:4000/v1",
        "apiKey": "{env:LITELLM_OPENCODE_KEY}"
      },
      "models": {
        "glm-5.2": {
          "name": "GLM 5.2 Thinking",
          "limit": {"context": 198000, "output": 128000}
        }
      }
    }
  }
}
```

Use `opencode run --thinking` to verify a distinct reasoning event. Without
that display flag, GLM thinking remains enabled even when the CLI hides it.

## Validate

Run static and unit checks in the pinned LiteLLM image when host Python is
older than 3.7:

```bash
docker run --rm \
  --entrypoint /app/.venv/bin/python \
  -v "$PWD:/workspace:ro" -w /workspace \
  ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 \
  tests/test_anthropic_stream_guard.py

docker run --rm \
  --entrypoint /app/.venv/bin/python \
  -v "$PWD:/workspace:ro" -w /workspace \
  ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 \
  tests/test_anthropic_reasoning_filter.py

python3 tests/test_smart_router.py
```

Run live validation with a scoped virtual key:

```bash
LITELLM_KEY=sk-virtual-key python3 tests/live_smoke.py all
```

Confirm:

- normal Messages, ordered SSE, and structured `tool_use` pass;
- OpenAI chat responses retain `reasoning_content`;
- Claude Messages contain no thinking blocks and start visible content at
  index 0;
- length-band tagging and fallback-cap tests pass;
- spend logs show the actual provider model, not only the requested alias;
- all core services remain healthy;
- logs contain no credentials.

## Troubleshoot

### Claude Code displays reasoning garbage

Confirm GLM thinking remains enabled and the reasoning filter is mounted after
the stream guard. Test both streaming and non-streaming Messages responses.
Do not solve this by disabling upstream thinking.

### Claude Code waits forever

Check for missing `message_stop` and early upstream termination. The stream
guard must synthesize `content_block_stop`, `message_delta`, and
`message_stop` when safe.

### Tool calls appear as text

Run `tests/live_smoke.py tools`. If raw `<tool_call>` markup appears, repair
provider function-calling capability. Do not parse model-authored markup into
executable tools.

### OpenCode has no reasoning event

Call `/v1/chat/completions` directly and verify `reasoning_content` exists.
Then run OpenCode with `--thinking`. The Anthropic reasoning filter must pass
OpenAI chunks through unchanged.

### Agent repeats the same tool call forever

The client is looping on an unchanging environment: a page stuck loading, a
command whose output never varies. Check in this order.

1. Is provider thinking actually live on the route? Read `reasoning_tokens` and
   `len(reasoning_content)` from a response, not the request parameters. Zero
   reasoning tokens means thinking is off regardless of what the request said.
2. Is `glm_loop_breaker` registered, and does `GLM_LOOP_MODEL_PATTERN` match
   the model the client requested? The default `glm|coding-|claude-` covers
   `claude-glm-5.2` (the public GLM model group).
3. Does the looping tool report success on failure? A `sleep` that returns
   `done` tells the model the step worked and gives it no reason to change.

Dropped `reasoning_content` in the request history is not the cause; echoing it
back does not break the loop.

## Roll back

```bash
server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir> \
  --uninstall
```

Verify remaining callbacks and mounts after rollback. Restore client settings
separately when required.
