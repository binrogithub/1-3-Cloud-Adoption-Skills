# Smart Router

Deterministic LiteLLM pre-call routing with four supported languages:
Chinese, English, Brazilian Portuguese, and Spanish.

Routing order:

1. Image content -> `vision-openrouter`.
2. Estimated input above 198000 tokens -> `premium-openrouter`.
3. Visual/UI design, visual inspection, wireframe, diagram, graph, and mockup
   output -> `vision-openrouter`.
4. Advisor/strategy, architecture, database design, strict output contracts,
   complex debugging, security review, production incidents, and infrastructure
   changes -> `premium-openrouter`.
5. Everything else remains on the requested GLM-backed Claude alias.

The score is observational only. Each request records `estimated_tokens`,
`matched_rule`, `complexity_score`, `router_version`, `fallback_chain`, and,
when applicable, `provider_capability_reason` under `metadata.smart_router`.
Ordinary code generation, test generation, and simple refactors remain on GLM
unless a higher-priority hard rule matches.

Rules live in `smart_router_rules.json` and are described by
`smart_router_rules.schema.json`. The callback validates the configuration at
import time and fails fast on unknown keys, invalid regexes, duplicate IDs, or
invalid scoring weights.

Fallbacks are request-scoped:

- GLM execution can fall back to Premium unless sensitive/data-residency
  language blocks a China-to-US transfer.
- Premium can fall back to GLM only below the context limit and only when its
  matched rule explicitly permits downgrade.
- Vision can fall back only to `vision-openrouter-secondary`.

High-risk payment/authentication/PCI changes, race conditions, repeated failed
fixes, protected paths, and production/infrastructure migrations route to
Premium and cannot downgrade to GLM.

Prometheus metrics:

```text
smart_router_requests_total{route,matched_rule,router_version}
smart_router_fallbacks_total{source,target,reason}
smart_router_cross_border_blocks_total{matched_rule}
smart_router_complexity_score{route}
```

Environment overrides:

```bash
SMART_ROUTER_GLM_MODEL=claude-*
SMART_ROUTER_VISION_MODEL=vision-openrouter
SMART_ROUTER_VISION_FALLBACK_MODEL=vision-openrouter-secondary
SMART_ROUTER_PREMIUM_MODEL=premium-openrouter
SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD=198000
SMART_ROUTER_RULES_FILE=/app/smart_router_rules.json
```

Register `smart_router.proxy_handler_instance` in `litellm_settings.callbacks`
after mounting `callback.py` as `/app/smart_router.py` and the rules file as
`/app/smart_router_rules.json`.
