# PRD: Huawei MaaS Anthropic Compatibility Guard and Advisor Router

## Problem Statement

Meli observed that Huawei MaaS `glm-5.2` on `anthropic/v1/messages` does not
fully match the Anthropic Messages API. Streaming responses can use invalid
SSE framing, append an OpenAI-style `[DONE]` sentinel after `message_stop`, and
reject Anthropic-format forced `tool_choice`. The endpoint also rejects image
input and can produce non-strict structured output.

These defects make strict Anthropic clients fail even when the underlying GLM
model can answer text and code tasks. Meli needs a gateway policy that repairs
provider-specific protocol drift when it is safe, and routes unsupported or
high-judgment work to Anthropic or another premium provider.

## Solution

Extend `litellm-maas-auto-plugin` with two coordinated behaviors:

- `anthropic_stream_guard` repairs Huawei-specific Anthropic Messages protocol
  drift at the LiteLLM boundary.
- `smart_router` keeps low-risk execution on GLM while routing advisor,
  visual, strict-JSON, security, architecture, incident, and other capability
  gaps to premium or vision-capable models.

The outward contract remains strict Anthropic Messages. Huawei compatibility
logic is provider-bound, observable, and controlled by environment flags.

## User Stories

1. As a Meli Gateway user, I want Huawei GLM streams to parse as valid
   Anthropic Messages SSE, so that strict clients do not fail on provider
   formatting drift.
2. As an agent developer, I want Anthropic forced `tool_choice` requests to
   work against Huawei, so that tool workflows do not fail with schema 400.
3. As a platform operator, I want trailing `[DONE]` frames dropped after
   `message_stop`, so that OpenAI conventions do not leak into Anthropic
   clients.
4. As a product owner, I want image and visual workloads routed away from
   text-only Huawei endpoints, so that unsupported `image_url` calls do not
   fail.
5. As a code user, I want ordinary code, test, and refactor tasks to remain on
   GLM, so that cost and latency stay controlled.
6. As an advisor user, I want architecture, design, security, production
   incident, and complex debugging work routed to Anthropic or premium models,
   so that high-judgment tasks use a stronger provider.
7. As an SRE, I want metrics for every repair and route decision, so that
   provider fixes or regressions are visible.
8. As a compliance owner, I want cross-border fallback rules preserved, so that
   sensitive workloads do not silently move to another region.

## Implementation Decisions

- Add Huawei SSE normalization to `anthropic_stream_guard` without relaxing the
  global Anthropic parser.
- Parse bare `data:` followed by un-prefixed pretty JSON lines only when it
  forms a single valid Anthropic event.
- Re-emit repaired events as compact `data: {json}` Anthropic SSE using the
  existing serializer.
- Drop a standalone `data: [DONE]` event once a stream has reached
  `message_stop`.
- Keep Anthropic forced tool choice intact for LiteLLM `/v1/messages` ingress,
  because LiteLLM expects the Anthropic shape before downstream conversion.
- Provide opt-in translation of Anthropic forced tool choice
  `{"type":"tool","name":"<tool>"}` into Huawei's OpenAI-like validation shape
  for direct-provider adapter deployments.
- Keep `auto`, `any`, and `none` untouched unless a future provider-specific
  compatibility rule proves otherwise.
- Add a capability reason to smart-router metadata while preserving existing
  metadata keys.
- Route strict structured output requests to premium unless the prompt is
  clearly simple code/test/refactor work.
- Keep vision fallbacks vision-capable only.

## Testing Decisions

- Stream guard tests use raw byte fixtures that reproduce Huawei pretty JSON
  and `[DONE]` frames.
- Request tests assert `tool_choice` translation is opt-in and does not affect
  non-forced choices.
- Router tests assert ordinary code/test prompts stay on GLM, while advisor,
  visual, and strict structured-output prompts route to the correct capable
  pool.
- Tests verify behavior at the plugin boundary, not private helper details,
  except where a helper already represents the public compatibility contract of
  this single-file LiteLLM callback.

## Out of Scope

- Fixing Huawei MaaS serving itself.
- Adding true image understanding to a text-only GLM endpoint.
- Converting arbitrary raw model-authored tool markup into executable tool
  calls.
- Guaranteeing model-level JSON quality without validation and retry policy.

## Further Notes

The compatibility guard is a temporary provider shim. The target state remains
Huawei serving compliance with Anthropic Messages SSE and request schemas. Once
Huawei emits correct streams and accepts Anthropic `tool_choice`, the related
repair metrics should fall to zero and the shim can be disabled.
