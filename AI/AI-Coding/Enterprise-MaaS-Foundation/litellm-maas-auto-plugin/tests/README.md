# EPIC-10 Test Fixtures

These pytest tests are contract tests for `litellm_plugins.cc_glm52_guard`.
They do not call a real LiteLLM service and do not require provider API keys.

Run from the project root:

```bash
cd /root/litellm-maas-plugin
PYTHONPATH=/root/litellm-maas-plugin pytest -q tests
```

Until `litellm_plugins.cc_glm52_guard` exists, pytest will report these tests as
skipped with an explicit message.

Current coverage:

- text requests route to the GLM-5.2 execution model (`glm-5.2`)
- image/multimodal requests route to the LiteLLM vision alias (`vision-openrouter`)
- backend fallback search requests inject the `litellm_web_search` tool
- missing `context_management` injects the two default edits
- existing `context_management` is preserved, merged, and clamped to safe limits
