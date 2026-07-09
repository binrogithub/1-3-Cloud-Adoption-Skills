# cc_glm52_guard

LiteLLM custom callback for the Claude Code -> LiteLLM -> GLM-5.2 server-side path. It is a pre-call hook and does not fork or patch LiteLLM core.

## What it does

- Exports `proxy_handler_instance` from `cc_glm52_guard.callback`.
- Maps `claude-sonnet-4-6`, `glm-5.2`, and `claude-glm1` to `CC_GLM52_EXECUTION_MODEL` (`glm-5.2` by default).
- Treats `claude-sonnet-4-6-backend`, `glm-5.2-backend`, and `claude-glm1-backend`
  as backend fallback aliases. They still route to `CC_GLM52_EXECUTION_MODEL`.
- Routes requests with image content blocks to `CC_GLM52_VISION_MODEL` (`vision-openrouter` by default).
- In backend fallback mode, search-intent prompts get a `litellm_web_search`
  tool so LiteLLM `websearch_interception` can handle backend search.
- Injects or merges Claude context management edits:
  - `clear_tool_uses_20250919` at `CC_GLM52_CLEAR_TOOL_TRIGGER` (`100000`), keeping 3 tool uses.
  - `compact_20260112` at `CC_GLM52_COMPACT_TRIGGER` (`150000`).
- Keeps existing `context_management` and non-matching edits.
- Removes only `thinking` and `redacted_thinking` content blocks from `messages`, `input`, and list-form `system`.
- Adds namespaced audit data to `metadata.cc_glm52_guard`. If a caller already
  provides `extra_body.cc_glm52_guard_audit`, the hook keeps that namespace in
  sync, but it does not create `extra_body` just for audit data.
- Estimates input size with the first-pass fallback `len(serialized_request_fields) / 4`.

## Environment

```bash
export CC_GLM52_EXECUTION_MODEL=glm-5.2
export CC_GLM52_VISION_MODEL=vision-openrouter
export CC_GLM52_SUMMARY_MODEL=opus-summary
export CC_GLM52_SOFT_LIMIT=180000
export CC_GLM52_COMPACT_TRIGGER=150000
export CC_GLM52_CLEAR_TOOL_TRIGGER=100000
export CC_GLM52_SEARCH_MODE=native
export CC_GLM52_CAPABILITY_MODE=frontend_capable
```

`CC_GLM52_SEARCH_MODE=native` keeps Claude Code native search as the default.
Backend fallback mode can be selected by request metadata, backend model aliases,
or `CC_GLM52_CAPABILITY_MODE=backend_fallback`.

## LiteLLM loading

Mount the package into the LiteLLM container so Python can import `cc_glm52_guard`. Example Docker Compose fragment:

```yaml
services:
  litellm:
    volumes:
      - /root/litellm-maas-plugin/litellm_plugins/cc_glm52_guard:/app/cc_glm52_guard:ro
```

Then add the callback to the LiteLLM config:

```yaml
litellm_settings:
  callbacks:
    - cc_glm52_guard.proxy_handler_instance

general_settings:
  context_management_summary_model: opus-summary
```

The current host config is `/root/LiteLLM/assets/config/litellm_config.yaml`; apply the same callback line there during deployment, then restart the LiteLLM container in the normal platform window.

See `config.example.yaml` for a complete key-free config fragment with the `glm-5.2`, `opus-summary`, and `vision-openrouter` aliases.

## Main API

```python
from litellm.integrations.custom_logger import CustomLogger

class CCGLM52Guard(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        ...

proxy_handler_instance = CCGLM52Guard()
```
