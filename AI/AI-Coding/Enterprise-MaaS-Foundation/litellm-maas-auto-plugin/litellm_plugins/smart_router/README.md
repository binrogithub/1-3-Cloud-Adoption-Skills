# Smart Router

Deterministic LiteLLM pre-call routing with four supported languages:
Chinese, English, Brazilian Portuguese, and Spanish.

Routing order:

1. Image content -> `vision-openrouter`.
2. Estimated input above 198000 tokens -> `premium-openrouter`.
3. Visual/UI design -> `vision-openrouter`.
4. Architecture, database design, complex debugging, security review,
   production incidents, and infrastructure changes -> `premium-openrouter`.
5. Everything else remains on the requested GLM-backed Claude alias.

Environment overrides:

```bash
SMART_ROUTER_GLM_MODEL=claude-*
SMART_ROUTER_VISION_MODEL=vision-openrouter
SMART_ROUTER_PREMIUM_MODEL=premium-openrouter
SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD=198000
```

Register `smart_router.proxy_handler_instance` in `litellm_settings.callbacks`
after mounting `callback.py` as `/app/smart_router.py`.
