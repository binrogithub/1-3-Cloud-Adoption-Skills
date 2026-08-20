# LiteLLM MaaS Claude Code Bridge

A LiteLLM plugin bridge that lets Claude Code use **GLM-5.2** (via Huawei MaaS)
as an explicit alternative backend — without modifying native Claude Code.

Native Claude Code stays native. GLM-5.2 is launched via a separate
`claude-litellm` command. Claude Code speaks the Anthropic `/v1/messages`
protocol directly to LiteLLM; no client-side router or adapter is required.

```text
claude            → native Claude Code (subscription/OAuth/API — unchanged)
claude-litellm    → Claude Code with GLM-5.2 through LiteLLM
                   └─ Anthropic /v1/messages
                        └─ LiteLLM :4000
                             ├─ virtual-key auth, budgets, spend logs, metrics
                             ├─ smart_router
                             ├─ anthropic_stream_guard
                             ├─ execution → Huawei MaaS GLM-5.2
                             ├─ visual / image → OpenRouter vision
                             └─ cross-provider fallback → OpenRouter Opus (token-capped)
```

`claude-glm-5.2` is the one public GLM model group. Native Claude model names
(`default`, `opus`, `sonnet`, `haiku`) are NOT remapped to GLM.

## Quick start

```bash
# 1. Install server plugin into your LiteLLM deployment
server/install-litellm-plugin.sh --litellm-dir <your-litellm-dir>

# 2. Issue a scoped virtual key (GLM group only)
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"claude-litellm-user","models":["claude-glm-5.2"],"tpm_limit":500000,"rpm_limit":30}'

# 3. Install the isolated GLM launcher on the client
echo "sk-virtual-key" | client/claude-litellm-setup.sh --base-url http://127.0.0.1:4000

# 4. Verify the installation
client/claude-litellm-setup.sh --verify

# 5. Start a GLM session
claude-litellm
```

## Included

| Path | Purpose |
| --- | --- |
| `client/claude-litellm-setup.sh` | Install the isolated GLM-5.2 launcher (`claude-litellm`) |
| `client/claude-litellm-migrate.sh` | Safe migration from the old global-remapping setup (`--dry-run` / `--apply`) |
| `client/configure-claude-code.sh` | Deprecated — dispatches to `claude-litellm-migrate.sh`; no longer writes global mappings |
| `client/claude-litellm` | GLM-5.2 launcher (installed to `~/.local/bin/`) |
| `client/claude-select` | Optional provider selector (`native` / `glm` / `status`) |
| `server/install-litellm-plugin.sh` | Idempotent install, verify, and uninstall |
| `server/deploy-and-verify.sh` | Deploy from a release artifact and run smoke tests |
| `litellm_plugins/anthropic_stream_guard/callback.py` | Request and Anthropic SSE compatibility callback |
| `litellm_plugins/anthropic_reasoning_filter/callback.py` | Hide thinking from Claude while preserving upstream reasoning |
| `litellm_plugins/smart_router/callback.py` | Four-language deterministic model router |
| `litellm_plugins/smart_router/smart_router_rules.json` | Versioned multilingual rules and observational score weights |
| `litellm_plugins/smart_router/smart_router_rules.schema.json` | Strict rules schema |
| `litellm_plugins/glm_loop_breaker/callback.py` | Agent tool-call loop circuit breaker |
| `litellm_plugins/tool_argument_guard/callback.py` | Schema-aware tool-argument validation and repair |
| `litellm_plugins/sidecar/callback.py` | Vision and premium bounded sidecar orchestration |
| `litellm_plugins/model_registry.json` | Model capability registry (routing, limits, sidecar flags) |
| `_litellm_adapter.py` | LiteLLM framework adapter helpers |
| `_request_context.py` | Request-scoped context and residency policy |
| `tests/` | Regression and live smoke tests (335 tests) |
| `SKILL.md` | Operator playbook (deploy, configure, troubleshoot) |
| `docs/BACKLOG.md` | Non-blocking carried items |

## What the callback fixes

- Keeps Anthropic Messages requests on the OpenAI-compatible Chat
  Completions path.
- Strips unsupported thinking/reasoning parameters.
- Keep GLM-5.2 upstream thinking enabled and register
  `anthropic_reasoning_filter.proxy_handler_instance` after the stream guard.
  It hides provider reasoning only from Anthropic/Claude responses while
  preserving final text and structured tool calls.
- Removes incompatible server-side search tool declarations.
- Translates Anthropic forced `tool_choice` into the OpenAI-compatible
  function-choice shape required by some Huawei MaaS endpoints.
- Separates mixed thinking and text delta families into valid Anthropic
  content blocks.
- Repairs Huawei raw Anthropic SSE frames that use bare `data:` plus
  un-prefixed pretty JSON, and drops trailing OpenAI-style `data: [DONE]`
  after `message_stop`.
- Synthesizes missing terminal events when an upstream stream ends early.
- Re-surfaces the newest queued user interjection.
- Detects raw model-authored `<tool_call>` markup and exposes a metric without
  attempting unsafe reparsing.

Already-correct streams pass through unchanged. Callback failures are
fail-open.

## Prerequisites

- A healthy Docker Compose LiteLLM deployment.
- A `claude-glm-5.2` model route backed by `openai/glm-5.2`.
- A LiteLLM virtual key allowed to use `claude-glm-5.2` only (internal
  Sidecar models are server-owned, not client-accessible).
- Native Claude Code installed.

## Install the server plugin

```bash
server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir>
```

The installer:

1. mounts the callbacks plus the smart-router rules and model registry;
2. registers their callbacks in the required order;
3. enables Chat Completions routing for Anthropic Messages;
4. restarts LiteLLM;
5. waits for health and verifies all imports and deployment invariants.

Preview or roll back:

```bash
server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir> \
  --dry-run

server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir> \
  --uninstall
```

## Required model route

```yaml
model_list:
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

Issue one virtual key per client (GLM group only — internal sidecars are NOT included):

```bash
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"claude-litellm-user",
       "models":["claude-glm-5.2"],
       "tpm_limit":500000,"rpm_limit":30}'
```

The public client key can call ONLY `claude-glm-5.2`. Internal Sidecar models
(`vision-openrouter`, `vision-openrouter-secondary`, `premium-openrouter`)
are server-owned and accessed only through the plugin's internal orchestration.
Native Claude traffic bypasses LiteLLM entirely.

## Configure Claude Code for GLM

```bash
# Key read from stdin (never passed as argv):
echo "sk-virtual-key" | client/claude-litellm-setup.sh --base-url http://127.0.0.1:4000

# Or via environment variable:
CLAUDE_LITELLM_KEY=sk-virtual-key client/claude-litellm-setup.sh --base-url http://127.0.0.1:4000

# Verify installation (authenticates with the key, checks ACL):
client/claude-litellm-setup.sh --verify
```

This installs the `claude-litellm` launcher and an isolated GLM profile in
`~/.config/claude-litellm/`. It does NOT modify `~/.claude/settings.json`,
`~/.claude.json`, or shell profiles. Native `claude` remains unchanged.

Start a GLM session:

```bash
claude-litellm [normal Claude Code arguments]
```

Start a native Claude session (unchanged):

```bash
claude [normal Claude Code arguments]
```

Optional selector:

```bash
client/claude-select native [args]   # native Claude
client/claude-select glm [args]      # GLM-5.2 through LiteLLM
client/claude-select status          # show config + endpoint
```

Migrate from the old global-remapping setup:

```bash
# Preview what would be removed (model mappings are auto-removed; legacy
# URL/credentials require exact ownership evidence).
client/claude-litellm-migrate.sh --dry-run

# Compute the full 64-char SHA-256 of the old gateway key, then apply.
FP=$(printf '%s' "$OLD_GATEWAY_KEY" | sha256sum | cut -d' ' -f1)
client/claude-litellm-migrate.sh --apply \
  --old-base-url http://127.0.0.1:4000 \
  --old-key-fingerprint "$FP"
```

## Verify

```bash
# Run the test suite (335 tests)
make test

# Run live smoke probes against your gateway
LITELLM_KEY=sk-virtual-key python3 tests/live_smoke.py all

# Quick end-to-end check
claude-litellm -p "Reply with OK only." --max-turns 1
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

GLM-5.2 owns every final response. The deterministic router never routes a
whole turn to Vision or Premium — those are bounded Sidecars that inject
structured context into the same GLM request.

**Vision Sidecar**: if a request carries image content, the sidecar extracts
images, sends each to Luna (`vision-openrouter`) for a structured description,
injects the caption text in-place, and GLM-5.2 produces the sole user-facing
answer. Exactly one Luna attempt; on failure, exactly one Luna Pro
(`vision-openrouter-secondary`) attempt — inherited retries/fallbacks disabled.
If both fail, an explicit `VISION_SIDECAR_UNAVAILABLE` error is returned; GLM
never guesses image content. Successful descriptions are cached by image
SHA-256; a repeated image makes zero new Vision calls.

**Premium Sidecar**: on a tool-call failure or loop, the sidecar makes at most
one bounded Premium (`premium-openrouter`) advisory call, injects the advice,
and returns control to GLM-5.2 for the final response.

Length is never a routing trigger. Estimated input is classified into bands
(normal/advisory/oversize), tagged in metadata and counted in a metric, but
the request stays on GLM. Never escalate to another model on length alone.

Routing metadata includes the token estimate, matched rule, router version,
length band, and request-scoped fallback chain. Same-provider fallback
(GLM → `glm-5.1-fallback`) is token-capped at `SMART_ROUTER_FALLBACK_TOKEN_CAP`.
Cross-border fallback is gated on a `data_residency` tag read from the
virtual key/team context or the server-side `SMART_ROUTER_DEFAULT_DATA_RESIDENCY`
env — not from client request metadata.

When `SMART_ROUTER_DEPLOYMENT_COUNT` is greater than `1`, mainline traffic is
pinned to a stable `SMART_ROUTER_MAINLINE_PREFIX-<idx>` alias via a stateless
SHA-256 consistent hash over `metadata.session_id` (preferred) or the system
prompt plus first user text. The hash is stable across restarts.

Monitor `smart_router_requests_total`, `smart_router_fallbacks_total`,
`smart_router_cross_border_blocks_total`, `smart_router_length_band_total`, and
`mainline_deployment_selected_total`.

For automated work, use separate virtual keys for interactive clients, CI,
and recurring loops. Limit each work item to two attempts, enforce rolling
budgets/RPM/TPM, honor `Retry-After` with bounded exponential backoff and
jitter, and stop after exhaustion instead of creating a 429 retry storm.

## Configuration reference

All configuration is via environment variables (see `.env.example` for defaults):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ASG_STRIP_THINKING` | `true` | Strip Anthropic thinking/reasoning params |
| `ASG_AMPLIFY_INTERJECTIONS` | `true` | Re-surface queued user messages |
| `SMART_ROUTER_ADVISORY_THRESHOLD` | `200000` | Tag advisory band, stay on mainline |
| `SMART_ROUTER_OVERSIZE_THRESHOLD` | `500000` | Record oversize band, stay on mainline |
| `SMART_ROUTER_FALLBACK_TOKEN_CAP` | `200000` | Suppress cross-provider fallback above this |
| `SMART_ROUTER_MAINLINE_PREFIX` | `glm` | Pinned deployment alias prefix |
| `SMART_ROUTER_DEPLOYMENT_COUNT` | `1` | `>1` enables prefix-affinity hashing |
| `SMART_ROUTER_MAINLINE_GROUP` | `claude-*` | Same-provider fallback group for affinity |
| `SMART_ROUTER_DEFAULT_DATA_RESIDENCY` | *(empty)* | `china-only` blocks cross-provider fallback by default |
| `TOOL_ARG_GUARD_MODE` | `enforce` | Tool argument validation mode (`off`/`observe`/`enforce`) |

## License

MIT — see [LICENSE](LICENSE).
