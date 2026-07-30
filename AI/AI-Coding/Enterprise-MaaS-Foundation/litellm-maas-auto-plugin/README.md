# LiteLLM MaaS Claude Code Bridge

Connect native Claude Code clients to a LiteLLM gateway backed by Huawei
ModelArts MaaS GLM-5.1. Claude Code speaks the Anthropic `/v1/messages`
protocol directly to LiteLLM; no client-side router or adapter is required.

```text
Claude Code
  └─ Anthropic /v1/messages
       └─ LiteLLM :4000
            ├─ virtual-key auth, budgets, spend logs, metrics
            ├─ smart_router
            ├─ anthropic_stream_guard
            ├─ execution / <=198K → Huawei MaaS GLM-5.1
            ├─ visual / image → OpenRouter vision
            └─ premium reasoning / >198K → OpenRouter Opus
```

`claude-*` names are compatibility aliases. They do not imply that the
upstream model is an Anthropic Claude model.

## Included

| Path | Purpose |
| --- | --- |
| `client/configure-claude-code.sh` | Configure or restore a native Claude Code client |
| `server/install-litellm-plugin.sh` | Idempotent install, verify, and uninstall |
| `litellm_plugins/anthropic_stream_guard/callback.py` | Request and Anthropic SSE compatibility callback |
| `litellm_plugins/anthropic_reasoning_filter/callback.py` | Hide thinking from Claude while preserving upstream reasoning |
| `litellm_plugins/smart_router/callback.py` | Four-language deterministic model router |
| `litellm_plugins/smart_router/smart_router_rules.json` | Versioned multilingual rules and observational score weights |
| `litellm_plugins/smart_router/smart_router_rules.schema.json` | Strict rules schema |
| `tests/test_anthropic_stream_guard.py` | Callback regression tests |
| `tests/test_smart_router.py` | Language, intent, and 198K boundary tests |
| `tests/live_smoke.py` | Live message, stream, and tool-call probes |
| `docs/PRD-lean-glm51.md` | Current product requirements and acceptance criteria |

## What the callback fixes

- Keeps Anthropic Messages requests on the OpenAI-compatible Chat
  Completions path.
- Strips unsupported thinking/reasoning parameters.
- Keep GLM-5.1 upstream thinking enabled and register
  `anthropic_reasoning_filter.proxy_handler_instance` after the stream guard.
  It hides provider reasoning only from Anthropic/Claude responses while
  preserving final text and structured tool calls.
- Removes incompatible server-side search tool declarations.
- Separates mixed thinking and text delta families into valid Anthropic
  content blocks.
- Synthesizes missing terminal events when an upstream stream ends early.
- Re-surfaces the newest queued user interjection.
- Detects raw model-authored `<tool_call>` markup and exposes a metric without
  attempting unsafe reparsing.

Already-correct streams pass through unchanged. Callback failures are
fail-open.

## Prerequisites

- A healthy Docker Compose LiteLLM deployment.
- A working `glm-5.1` model route.
- A `claude-*` model route backed by `openai/glm-5.1`.
- A LiteLLM virtual key allowed to use `claude-*`, `vision-openrouter`,
  `vision-openrouter-secondary`, and `premium-openrouter`.
- Native Claude Code installed.

## Install the server plugin

```bash
server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy
```

The installer:

1. mounts the three callbacks plus the smart-router rules;
2. registers their callbacks in the required order;
3. enables Chat Completions routing for Anthropic Messages;
4. restarts LiteLLM;
5. waits for health and verifies all three imports.

Preview or roll back:

```bash
server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy \
  --dry-run

server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy \
  --uninstall
```

## Required model route

```yaml
model_list:
  - model_name: "claude-*"
    litellm_params:
      model: openai/glm-5.1
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    model_info:
      max_input_tokens: 198000
      max_output_tokens: 128000
```

Issue one virtual key per client:

```bash
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"claude-code-user",
       "models":["claude-*","vision-openrouter",
                 "vision-openrouter-secondary","premium-openrouter"],
       "tpm_limit":500000,"rpm_limit":30}'
```

## Configure Claude Code

```bash
client/configure-claude-code.sh sk-virtual-key \
  --base-url http://127.0.0.1:4000 \
  --model claude-opus-4-6 \
  --verify
```

The requested name `claude-opus-4-6` matches the `claude-*` compatibility
route and is served by GLM-5.1.

Restore direct Anthropic defaults:

```bash
client/configure-claude-code.sh --restore
```

## Verify

```bash
LITELLM_KEY=sk-virtual-key \
python3 tests/live_smoke.py all
python3 tests/test_smart_router.py

claude -p "Reply with OK only." --max-turns 1
```

Expected:

- message probe: HTTP 200;
- stream probe: valid SSE ending in `message_stop`;
- tool probe: structured `tool_use`;
- Claude CLI: successful response through LiteLLM.

## Security

- Never use the MaaS key or LiteLLM master key on a client.
- Keep client keys and Claude settings at mode `0600`.
- Expose port 4000 only to approved source addresses.
- Put TLS in front of LiteLLM for remote production clients.
- Monitor LiteLLM spend logs and `asg_*` Prometheus metrics.

## Smart routing

The deterministic router recognizes Chinese, English, Brazilian Portuguese,
and Spanish. Images and visual/UI requests use `vision-openrouter`;
architecture, database design, complex debugging, security review, production
incidents, infrastructure changes, and input above 198000 tokens use
`premium-openrouter`. Other execution work stays on GLM.

Routing metadata includes the token estimate, matched rule, observational
complexity score, router version, and request-scoped fallback chain. GLM can
fall back to Premium only when cross-border policy permits it; Premium can
downgrade only for explicitly permitted rules below the context limit; Vision
falls back only to `vision-openrouter-secondary`.

Payment/authentication/PCI changes, race conditions, repeated failed fixes,
protected paths, and production/infrastructure migrations are
non-downgradable Premium work. Monitor `smart_router_requests_total`,
`smart_router_fallbacks_total`, `smart_router_cross_border_blocks_total`, and
`smart_router_complexity_score`.

For automated work, use separate virtual keys for interactive clients, CI,
and recurring loops. Limit each work item to two attempts, enforce rolling
budgets/RPM/TPM, honor `Retry-After` with bounded exponential backoff and
jitter, and stop after exhaustion instead of creating a 429 retry storm.
