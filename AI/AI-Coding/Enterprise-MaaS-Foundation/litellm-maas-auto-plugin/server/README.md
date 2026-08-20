# LiteLLM Gateway Setup for Claude Code (Server Side)

Make a LiteLLM proxy serve **native Claude Code** clients over the Anthropic
`/v1/messages` protocol, backed by an OpenAI-compatible reasoning model
(GLM-5.1 on Huawei MaaS in this deployment). Supports many concurrent Claude
Code clients, each with its own virtual key, budget, and rate limits.

```
Claude Code #1 ─┐  each with its own LiteLLM virtual key (claude-glm-5.2 only)
Claude Code #2 ─┼──Anthropic /v1/messages──►  LiteLLM :4000
Claude Code #N ─┘                             │  auth / budgets / tpm / rpm / Prometheus
                                              │  anthropic_stream_guard  (this plugin)
                                              │  claude-glm-5.2 route
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
  (disable via `ASG_STRIP_THINKING=false` if your GLM model points at a
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

Design details: see `litellm_plugins/anthropic_stream_guard/README.md`

## Install

```bash
./install-litellm-plugin.sh --litellm-dir <your-litellm-dir>
./install-litellm-plugin.sh --litellm-dir <your-litellm-dir> --dry-run      # preview changes
./install-litellm-plugin.sh --litellm-dir <your-litellm-dir> --uninstall    # roll back mount + callback
```

The script is idempotent, backs up every file it touches (`.bak.<timestamp>`),
and performs:

| Step | File | Change |
|---|---|---|
| mount plugins | `docker-compose.yml` | mount four callbacks + `/app/sidecar.py` + `/app/model_registry.json` + `/app/smart_router_rules.json` + a read-write `/app/cache` volume |
| register callbacks | `litellm_config.yaml` | stream guard, reasoning filter, smart router, loop breaker (sidecar is imported by smart_router, not registered) |
| routing flag | `litellm_config.yaml` | `litellm_settings.use_chat_completions_url_for_anthropic_messages: true` |
| restart + verify | container | health wait + in-container import check (incl. sidecar + cache writable) |

> Each plugin **must** be mounted as a single `/app/<module>.py` file:
> LiteLLM's `get_instance_fn` resolves callbacks next to the config file and
> does not support package directories.

## Required LiteLLM configuration (manual, deployment-specific)

**1. Model routes.** Five honest routes (PRD-glm-consolidation §10):

```yaml
model_list:
  - model_name: claude-glm-5.2
    litellm_params:
      model: openai/glm-5.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    model_info: { max_input_tokens: 1000000, max_output_tokens: 128000 }

  - model_name: glm-5.1-fallback
    litellm_params:
      model: openai/glm-5.1
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY_0
    model_info: { max_input_tokens: 196608, max_output_tokens: 128000 }

  - model_name: vision-openrouter
    litellm_params: { model: openrouter/openai/gpt-5.6-luna, api_key: os.environ/OPENROUTER_API_KEY }
    model_info: { max_input_tokens: 1050000, max_output_tokens: 128000 }

  - model_name: vision-openrouter-secondary
    litellm_params: { model: openrouter/openai/gpt-5.6-luna-pro, api_key: os.environ/OPENROUTER_API_KEY }
    model_info: { max_input_tokens: 1050000, max_output_tokens: 128000 }

  - model_name: premium-openrouter
    litellm_params: { model: openrouter/anthropic/claude-opus-5, api_key: os.environ/OPENROUTER_API_KEY }
    model_info: { max_input_tokens: 1000000, max_output_tokens: 128000 }
```

The public client key is restricted to `claude-glm-5.2` only. Native Claude
model names (`default`, `opus`, `sonnet`, `haiku`) are NOT remapped — native
Claude bypasses LiteLLM entirely. GLM-5.2 is selected explicitly via the
`claude-litellm` launcher (see `client/README.md`).

**1b. Sidecar internal key + cache (PRD-glm52-mainline-sidecars).** GLM-5.2
owns every final answer. Vision (Luna/Luna-Pro) and Premium (Opus 5) are
**bounded sidecars**: they receive one image + a fixed instruction (vision) or
a ≤8K-token failure summary (premium), return structured JSON, and that text is
injected into the GLM request. Sidecars call the same loopback gateway with a
dedicated internal virtual key so auth/budgets/spend logs are preserved. Set in
the compose environment:

```bash
SIDECAR_BASE_URL=http://127.0.0.1:4000
SIDECAR_API_KEY=<dedicated internal virtual key>
SIDECAR_CACHE_DIR=/app/cache
```

Issue the internal key with an ACL of exactly the sidecar models (client keys
must NOT include these):

```bash
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "content-type: application/json" \
  -d '{"key_alias":"sidecar-internal",
       "models":["vision-openrouter","vision-openrouter-secondary","premium-openrouter"],
       "max_budget":200,"tpm_limit":500000,"rpm_limit":60}'
```

The installer mounts a persistent read-write `/app/cache` volume
(`<litellm-dir>/assets/cache`) for the SHA-256 caption cache (30-day TTL) and
the premium intervention ledger (24h retention). Recursion is blocked by key
identity: a sidecar's loopback call re-enters the gateway, but smart_router
detects the internal key and skips sidecar orchestration (invariant I5). A
client key forging `metadata.sidecar_kind` is blocked, not trusted.

**2. Router tuning (single-deployment models).** Defaults can turn a few
failures into a 30 s total outage:

```yaml
router_settings:
  allowed_fails: 1000   # effectively disable cooldown for a single deployment
  cooldown_time: 5
```

**3. Per-client virtual keys.** Issue one key per Claude Code client. A normal
client key may access ONLY `claude-glm-5.2` — never the wildcard, never the
internal Sidecar groups:

```bash
curl -sS -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "content-type: application/json" \
  -d '{"key_alias":"claude-code-alice",
       "models":["claude-glm-5.2"],
       "max_budget":100,"tpm_limit":500000,"rpm_limit":30}'
```

Internal Sidecar groups (`vision-openrouter`, `vision-openrouter-secondary`,
`premium-openrouter`, `glm-5.1-fallback`) are server-only — they are accessed
by a dedicated internal key with an ACL of exactly those models, never by a
client key. Native Claude (`default`, `opus`, `sonnet`, `haiku`) bypasses
LiteLLM entirely and is never remapped.

**4. Network.** For remote clients, expose port 4000 to their IPs only
(cloud security group). LiteLLM already binds `0.0.0.0:4000` in this compose.

**5. Automation circuit breakers.** Use separate virtual keys for interactive
clients, CI, and recurring loops. Set rolling budgets, RPM, and TPM on each
key. Limit an execution item to two attempts, honor `Retry-After`, use bounded
exponential backoff with jitter, and stop after exhaustion. Size workflow
concurrency below the key's RPM/TPM capacity.

## Verify

```bash
# stream protocol check: first block must be "thinking", no mixed deltas
curl -sN http://127.0.0.1:4000/v1/messages \
  -H "content-type: application/json" -H "x-api-key: <key>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-glm-5.2","max_tokens":256,"stream":true,
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

To return the gateway to a previous release, install the previous artifact
with `--artifact` (which verifies `SHA256SUMS` and installs from the
extraction, not the working tree), restart, and confirm the container hash
matches the previous artifact — not merely that health is green.

```bash
# 1. Install the previous-good artifact (kept in releases/).
SIDECAR_API_KEY=… bash server/install-litellm-plugin.sh \
  --litellm-dir <your-litellm-dir> \
  --artifact releases/litellm-auto-plugin-<previous-sha>.tar.gz

# 2. Restart the proxy.
cd <your-litellm-dir> && docker compose up -d litellm

# 3. Confirm the container hash equals the PREVIOUS artifact's hash.
docker exec litellm python3 -c "import hashlib; print(hashlib.sha256(open('/app/smart_router.py','rb').read()).hexdigest())"
# Compare against: tar xzf releases/<previous>.tar.gz -O | … | sha256sum

# 4. Confirm health and a GLM 200.
curl -s http://127.0.0.1:4000/health/readiness | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"
```

`./install-litellm-plugin.sh --uninstall` removes the mount + callback and
restarts; restore the `.bak.<timestamp>` files for a config-only revert. The
plugin is stateless.

## Compatibility

- Tested on `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`.
- Idempotent with future LiteLLM fixes: if upstream emits correct streams,
  the guard rewrites nothing.
- Coexists with other callbacks (Prometheus, budgets, search/vision
  enrichment); it only inspects Anthropic-format SSE chunks.
