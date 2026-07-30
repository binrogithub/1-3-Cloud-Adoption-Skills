# PRD: LiteLLM MaaS Claude Code Bridge

## 1. Status

- Product: `litellm-maas-auto-plugin`
- Target release: lean GLM-5.1 edition
- Runtime: LiteLLM `v1.83.14-stable.patch.3`
- Upstream: Huawei ModelArts MaaS, `glm-5.1`
- Client: native Claude Code over Anthropic `/v1/messages`

## 2. Problem

Native Claude Code sends Anthropic Messages requests, including thinking
parameters, streaming content blocks, queued user interjections, and tool
definitions. Huawei MaaS exposes GLM-5.1 through an OpenAI-compatible
`/chat/completions` endpoint.

Without a compatibility layer:

1. Thinking parameters can make LiteLLM select the unsupported Responses API.
2. Mixed thinking/text stream events can violate the Anthropic SSE contract.
3. An incomplete upstream stream can end before terminal events are emitted.
4. Queued user interjections may be ignored by a non-Anthropic model.
5. Raw tool-call markup can be mistaken for a valid structured tool call.

The repository previously mixed this production bridge with unrelated
customer-specific virtual aliases, obsolete model versions, semantic-routing
experiments, and commercial pilot logic. Those components were not installed
by the server installer and were not available in the target environment.

## 3. Goal

Provide the smallest maintainable plugin that lets native Claude Code use a
LiteLLM virtual key and communicate reliably with GLM-5.1 through LiteLLM.

The supported request paths are:

```text
Claude Code
  -> Anthropic /v1/messages
  -> LiteLLM
  -> smart_router
     |-- execution and input <= 198K -> Huawei MaaS GLM-5.1
     |-- visual/UI/image             -> OpenRouter vision model
     `-- premium reasoning or >198K  -> OpenRouter Opus
  -> anthropic_stream_guard
```

## 4. Non-goals

This release does not provide:

- Customer-specific virtual model aliases or commercial telemetry.
- Embedding-based semantic prompt classification.
- Search-provider injection.
- Client-side routers, adapters, or wrappers.

These capabilities require separate credentials, models, policies, and
operational ownership. They must be delivered as independent optional
packages if reintroduced.

The deterministic smart router does provide:

- GLM-5.1 for code generation, fixes, tests, documentation, and refactoring.
- Premium/Opus for architecture, complex debugging, security review,
  production incidents, infrastructure changes, and input above 198K tokens.
- `vision-openrouter` for screenshots, UI, and image input.
- Intent matching in Chinese, English, Brazilian Portuguese, and Spanish.
- A strict context boundary: `<= 198000` stays on GLM and `> 198000` routes
  to Premium/Opus, unless an earlier image or premium-intent rule applies.

## 5. Users

- Platform operator: installs, upgrades, verifies, and rolls back the plugin.
- Claude Code user: receives a model-scoped LiteLLM virtual key.
- Security/FinOps operator: controls budgets and audits requests in LiteLLM.

## 6. Functional requirements

### FR-1: Server installation

The installer must:

- Mount the stream guard, reasoning filter, and smart router as single files.
- Register their callbacks in stream-guard, reasoning-filter, router order.
- Set `use_chat_completions_url_for_anthropic_messages: true`.
- Back up every modified file.
- Be idempotent.
- Support dry-run and uninstall.
- Restart LiteLLM and verify import and health.

### FR-2: Claude model compatibility

LiteLLM must expose a `claude-*` route backed by `openai/glm-5.1`.
Virtual client keys must be restricted to `claude-*`.

The Claude-compatible name is an alias only; interfaces and documentation
must clearly state that the upstream model is GLM-5.1.

### FR-3: Request normalization

For Anthropic Messages calls to an OpenAI-compatible backend, the callback
must safely strip unsupported thinking/reasoning parameters and incompatible
server-side search tools.

The GLM-5.1 model route must keep `thinking.type=enabled`. The response
pipeline must register `anthropic_reasoning_filter` after
`anthropic_stream_guard`. It removes thinking blocks only from Anthropic
responses, compacts content indexes, and preserves final content, tool calls,
usage, stop reasons, and terminal events. OpenAI-compatible clients may still
consume the original `reasoning_content`.

### FR-4: Stream normalization

The callback must:

- Preserve already-valid Anthropic streams.
- Keep content-block indices ordered.
- Separate thinking and text delta families into matching blocks.
- Synthesize missing terminal events when safe.
- Fail open if normalization itself raises an exception.

### FR-5: User interjections

The callback must re-surface the newest queued user interjection so GLM-5.1
sees it as a high-salience final instruction. The transformation must be
idempotent.

### FR-6: Tool-call diagnostics

The plugin must detect raw `<tool_call>`-style text when tools were declared,
increment an observable metric, and leave content unchanged. It must not
attempt to parse unstable model-authored markup into executable tools.

### FR-7: Client configuration

The client script must:

- Write gateway settings to `~/.claude/settings.json`.
- Use `ANTHROPIC_BASE_URL` and a LiteLLM virtual key.
- Configure primary and fast-model aliases consistently.
- Pre-approve the custom API key when possible.
- Preserve unrelated Claude settings.
- Back up modified files.
- Support restoring Anthropic defaults.
- Verify both a normal message and a structured tool call.

### FR-8: Secret handling

- No real key may be committed or printed in full.
- Key-bearing files must use mode `0600`.
- Documentation and tests must use placeholders or environment variables.
- Runtime logs must not contain MaaS or LiteLLM keys.

### FR-9: Observability

Expose Prometheus counters for request normalization, stream repair,
interjection amplification, raw tool markup, upstream errors, and synthesized
terminations.

The smart router must record `estimated_tokens`, `matched_rule`,
`complexity_score`, `router_version`, and the request-scoped fallback chain.
The score is diagnostic only and must not override deterministic routing.

### FR-10: Configurable routing and safe fallback

- Store Chinese, English, Brazilian Portuguese, and Spanish intent rules in a
  versioned JSON file with a strict JSON Schema and import-time validation.
- Route GLM failures to Premium only when cross-border policy permits.
- Downgrade Premium to GLM only for explicitly permitted rules at or below
  198000 tokens.
- Route Vision failures only to another vision-capable model.
- Use request-scoped LiteLLM fallbacks; do not install a global,
  capability-blind fallback chain.

## 7. Repository scope

Production source:

```text
client/
server/
litellm_plugins/anthropic_stream_guard/
litellm_plugins/smart_router/
  smart_router_rules.json
  smart_router_rules.schema.json
```

Verification source:

```text
tests/test_anthropic_stream_guard.py
tests/test_smart_router.py
tests/live_smoke.py
```

Documentation:

```text
README.md
SKILL.md
client/README.md
server/README.md
docs/PRD-lean-glm51.md
docs/PRD-anthropic-stream-guard.md
```

The production repository must not contain customer-specific aliases,
unavailable model routes, or test suites for plugins that are not shipped.

## 8. Acceptance criteria

1. Runtime source contains no obsolete customer-specific aliases or obsolete
   model-version names.
2. Chinese, English, Brazilian Portuguese, and Spanish routing tests pass.
3. An estimated 198000-token execution request stays on GLM; 198001 routes
   to Premium/Opus.
2. LiteLLM container imports `anthropic_stream_guard`.
3. LiteLLM does not import `cc_glm52_guard` or `context_window_guard`.
4. `/health/liveliness` returns HTTP 200.
5. `/v1/messages` returns an Anthropic message response.
6. Streaming produces a valid terminal sequence.
7. Tool probe returns a structured `tool_use` block.
8. `claude -p` completes successfully through the gateway.
9. Installer dry-run is a no-op after installation.
10. Uninstall remains available and documented.
11. All retained unit tests pass.
12. Secret scan of tracked/product files and runtime logs is clean.
13. Invalid rule files fail closed during callback import.
14. Complexity scoring never changes the selected hard-rule route.
15. Vision fallback never selects a text-only model.

## 9. Risks

- GLM-5.1 behavior can differ from Anthropic models even with protocol
  compatibility.
- Function calling depends on the selected MaaS endpoint capability.
- HTTP transport on a remote network does not provide TLS; production remote
  access should terminate TLS in front of LiteLLM.
- The `claude-*` wildcard may expose more client aliases than expected; key
  ACLs and budgets remain mandatory.

## 10. Rollback

Run:

```bash
server/install-litellm-plugin.sh \
  --litellm-dir /root/LiteLLM-Huawei-MaaS-Proxy \
  --uninstall
```

The installer removes the mount and callback, restarts LiteLLM, and leaves
backups for manual restoration.
