---
name: litellm-maas-auto-plugin
description: Deploy, configure, verify, upgrade, troubleshoot, or remove a LiteLLM bridge for native Claude Code and OpenCode backed by Huawei MaaS GLM-5.1 and OpenRouter. Use for Anthropic Messages compatibility, GLM reasoning filtering, structured tool calls, multilingual smart routing, 198K context escalation, vision routing, virtual keys, agent tool-call loop protection, or end-to-end gateway validation.
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
            → GLM-5.1 or OpenRouter

OpenCode   → /v1/chat/completions
           → smart_router
           → GLM-5.1 or OpenRouter
```

Use three model roles:

- `glm-5.1`: code generation, fixes, tests, documentation, and refactoring.
- `premium-openrouter`: architecture, database design, complex debugging,
  security review, production incidents, infrastructure changes, and input
  above 198000 tokens.
- `vision-openrouter`: screenshots, images, and visual/UI design.

Recognize routing intent in Chinese, English, Brazilian Portuguese, and
Spanish. Keep unmatched execution work on the requested GLM-backed alias.

## Required inputs

- LiteLLM deployment directory and Compose service/container names.
- Working `glm-5.1`, `premium-openrouter`, and `vision-openrouter` groups.
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
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy \
  --dry-run

server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy
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
`docs/PRD-glm-loop-breaker.md`.

### Loop breaker

Use `litellm_plugins/glm_loop_breaker/callback.py` as the second line of defence
behind thinking. It fingerprints assistant tool calls already in the request,
detects repeating cycles of period 1-3 at the tail of the history, then raises
`temperature` to a floor and finally appends an instruction to stop retrying.

Register it last so it sees the request after routing has chosen a model.

Its default model pattern covers `glm` and `*-coding-*` aliases such as
`coding-auto`, which resolve to a GLM upstream under a name containing no "glm".
Check `GLM_LOOP_MODEL_PATTERN` against the deployment's own `model_list`.

### Smart router

Use `litellm_plugins/smart_router/callback.py`. Apply hard rules in order:

1. Image content → `vision-openrouter`.
2. Estimated input `> 198000` → `premium-openrouter`.
3. Visual/UI intent → `vision-openrouter`.
4. Premium reasoning intent → `premium-openrouter`.
5. Everything else remains on GLM.

At the exact boundary, 198000 stays on GLM and 198001 routes to Premium.
Treat payment/authentication/PCI, race conditions, repeated failed fixes,
CODEOWNERS-protected paths, and production or infrastructure migrations as
non-downgradable Premium work.

Load multilingual intent rules from
`litellm_plugins/smart_router/smart_router_rules.json`. Validate edits against
`smart_router_rules.schema.json`; the callback also rejects unknown keys,
invalid regexes, duplicate rule IDs, and scoring weights that do not sum to
one. Keep `complexity_score` observational: never let it override the hard
routing order.

Record `estimated_tokens`, `matched_rule`, `complexity_score`, `router_version`,
and the selected request-scoped fallback chain under `metadata.smart_router`.

Use capability- and residency-safe request fallbacks:

- GLM execution → Premium unless a sensitive/data-residency rule blocks the
  China-to-US fallback.
- Premium → GLM only at `<= 198000` and only for a matched rule marked
  `allow_downgrade`.
- Vision → `vision-openrouter-secondary`; never fall back to a text-only model.

Allow virtual keys to access every configured fallback model.

Expose and monitor:

- `smart_router_requests_total{route,matched_rule,router_version}`
- `smart_router_fallbacks_total{source,target,reason}`
- `smart_router_cross_border_blocks_total{matched_rule}`
- `smart_router_complexity_score{route}`

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

Configure the GLM-backed Claude alias:

```yaml
- model_name: "claude-*"
  litellm_params:
    model: openai/glm-5.1
    api_base: os.environ/HUAWEI_MAAS_API_BASE
    api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    extra_body:
      thinking:
        type: enabled
  model_info:
    max_tokens: 198000
    max_input_tokens: 198000
    max_output_tokens: 128000
```

Use separate OpenRouter groups so premium reasoning does not randomly share a
vision deployment:

```yaml
- model_name: vision-openrouter
  litellm_params:
    model: openrouter/openai/gpt-4o

- model_name: vision-openrouter-secondary
  litellm_params:
    model: openrouter/google/gemini-2.5-pro

- model_name: premium-openrouter
  litellm_params:
    model: openrouter/anthropic/claude-opus-4
```

Supply credentials, limits, and pricing through the deployment configuration.

## Virtual keys

Issue one scoped key per client or host.

Claude Code key models:

```json
["claude-*", "vision-openrouter", "vision-openrouter-secondary",
 "premium-openrouter"]
```

OpenCode key models:

```json
["glm-5.1", "vision-openrouter", "vision-openrouter-secondary",
 "premium-openrouter"]
```

Store key responses in separate `0600` files. Do not reuse the LiteLLM master
key or MaaS key on clients.

## Configure clients

### Claude Code

```bash
client/configure-claude-code.sh sk-virtual-key \
  --base-url http://127.0.0.1:4000 \
  --model claude-opus-4-6 \
  --verify
```

The `claude-*` name is a compatibility alias; do not describe it as an actual
Anthropic model.

### OpenCode

Use `@ai-sdk/openai-compatible` and `/v1/chat/completions`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "enterprise-maas/glm-5.1",
  "provider": {
    "enterprise-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:4000/v1",
        "apiKey": "{env:LITELLM_OPENCODE_KEY}"
      },
      "models": {
        "glm-5.1": {
          "name": "GLM 5.1 Thinking",
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
- 198000/198001 routing tests pass;
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
2. Is `glm_loop_breaker` registered, and does `GLM_LOOP_MODEL_PATTERN` match the
   alias the client requested?
3. Does the looping tool report success on failure? A `sleep` that returns
   `done` tells the model the step worked and gives it no reason to change.

Dropped `reasoning_content` in the request history is not the cause; echoing it
back does not break the loop.

## Roll back

```bash
server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy \
  --uninstall
```

Verify remaining callbacks and mounts after rollback. Restore client settings
separately when required.
