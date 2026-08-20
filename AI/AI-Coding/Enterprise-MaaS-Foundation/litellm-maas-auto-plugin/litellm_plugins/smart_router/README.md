# Smart Router

Deterministic LiteLLM pre-call router. GLM-5.2 is the mainline and owns every
final answer (PRD-glm52-mainline-sidecars, invariant I1).

## Routing + sidecar flow

`async_pre_call_hook` runs two phases:

1. **Sidecar orchestration** (`orchestrate_sidecars`): imports the `sidecar`
   module and runs vision + premium sidecars. Images are extracted recursively
   (including nested `tool_result.content[]`), captioned by Luna/Luna-Pro, and
   the caption text is injected in-place — so the request never carries image
   bytes and never leaves the mainline. Tool-failure/loop signals trigger a
   bounded Premium recovery call (one per failure fingerprint) or a hard-stop.
   After sidecar processing the model is forced to `claude-glm-5.2`.
   Recursion bypass: an internal sidecar key re-entering the gateway is detected
   and skips orchestration (I5). A client key forging `metadata.sidecar_kind` is
   blocked (I10).
2. **Routing policy** (`route_request`): length bands, context cliff, prefix
   affinity, same-provider fallback (`glm-5.1-fallback`, 196608-token cap),
   data-residency gate. Images are NO LONGER routed here — every successful turn
   is `glm_execution`. Keyword/regex image routing and the `image_reference`
   branch were deleted (they misrouted text-only turns and sent full
   conversations to the visual model).

Length is never a routing trigger. Estimated input is classified into three
bands and recorded, but the request stays on its route regardless of length.

Length is never a routing trigger. Estimated input is classified into three
bands and recorded, but the request stays on its chosen route regardless of
length:

| Band | Tokens | Action |
| --- | --- | --- |
| normal | `< 200000` | None. |
| advisory | `200000` – `500000` | Tag `length_band` in metadata, increment metric, stay on mainline. |
| oversize | `> 500000` | Tag `length_band` in metadata, increment metric, stay on mainline. |

Never escalate to another model on length alone.

Each request records `estimated_tokens`, `matched_rule`, `router_version`,
`fallback_chain`, `length_band`, and, when applicable,
`provider_capability_reason` under `metadata.smart_router`. Ordinary code
generation, test generation, and simple refactors remain on GLM unless a
higher-priority hard rule matches.

Rules live in `smart_router_rules.json` and are described by
`smart_router_rules.schema.json`. The callback validates the configuration at
import time and fails fast on unknown keys, invalid regexes, or duplicate IDs.

Fallbacks are request-scoped:

- GLM execution can fall back to Premium only when the estimated token count is
  at or below `SMART_ROUTER_FALLBACK_TOKEN_CAP`. Above the cap the upstream error
  is allowed to propagate rather than replaying a large conversation against
  premium.
- Vision can fall back only to `vision-openrouter-secondary`.

Same-provider fallback (vision -> vision-secondary, or the mainline affinity
group) is exempt from the token cap. Cross-border fallback is gated on a
`data_residency` tag read from the virtual key/team context
(`user_api_key_dict.metadata.data_residency == "china-only"`) or the server-side
`SMART_ROUTER_DEFAULT_DATA_RESIDENCY` env — not from client request metadata,
which is client-controlled and defaults off. The legacy `cross_border_block_rules`
and `premium_rules` have been deleted.

Prometheus metrics:

```text
smart_router_requests_total{route,matched_rule,router_version}
smart_router_fallbacks_total{source,target,reason}
smart_router_cross_border_blocks_total{matched_rule}
smart_router_length_band_total{band}
mainline_deployment_selected_total{deployment}
```

Environment overrides:

```bash
SMART_ROUTER_GLM_MODEL=claude-*
SMART_ROUTER_VISION_MODEL=vision-openrouter
SMART_ROUTER_VISION_FALLBACK_MODEL=vision-openrouter-secondary
SMART_ROUTER_PREMIUM_MODEL=premium-openrouter
SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD=198000
SMART_ROUTER_ADVISORY_THRESHOLD=200000
SMART_ROUTER_OVERSIZE_THRESHOLD=500000
SMART_ROUTER_FALLBACK_TOKEN_CAP=200000
SMART_ROUTER_MAINLINE_PREFIX=glm
SMART_ROUTER_DEPLOYMENT_COUNT=1
SMART_ROUTER_MAINLINE_GROUP=claude-*
SMART_ROUTER_RULES_FILE=/app/smart_router_rules.json
SMART_ROUTER_DEFAULT_DATA_RESIDENCY=
```

`SMART_ROUTER_DEPLOYMENT_COUNT` defaults to `1`, which makes prefix affinity a
no-op. Set it to the number of mainline upstream deployments to pin each
mainline request to a stable `SMART_ROUTER_MAINLINE_PREFIX-<idx>` alias via a
stateless SHA-256 consistent hash. `metadata.session_id` is the preferred
anchor when the client supplies it; otherwise the hash of the system prompt
plus first user text is used. The hash is plain SHA-256, so it is stable across
restarts. The pinned alias falls back to the `SMART_ROUTER_MAINLINE_GROUP`
same-provider group, which is exempt from the fallback token cap.

Register `smart_router.proxy_handler_instance` in `litellm_settings.callbacks`
after mounting `callback.py` as `/app/smart_router.py` and the rules file as
`/app/smart_router_rules.json`.
