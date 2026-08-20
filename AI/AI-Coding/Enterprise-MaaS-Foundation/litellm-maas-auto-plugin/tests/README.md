# Tests

## Full suite (one command)

The complete unit + integration suite is composable under pytest:

```bash
python3 -m pytest
```

This discovers and runs every `tests/test_*.py` module with no collection
errors. `tests/conftest.py` centralizes the litellm stub so collection order
does not matter.

## Individual scripts

Each `test_*.py` is also a self-contained script (no pytest required):

```bash
python3 tests/test_anthropic_stream_guard.py
python3 tests/test_anthropic_reasoning_filter.py
python3 tests/test_smart_router.py
python3 tests/test_glm_loop_breaker.py
python3 tests/test_sidecar.py
python3 tests/test_tool_argument_guard.py
```

On an older host Python, run in the pinned LiteLLM image:

```bash
docker run --rm \
  --entrypoint /app/.venv/bin/python \
  -v "$PWD:/workspace:ro" -w /workspace \
  ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 \
  -m pytest
```

## Live tests

`live_smoke.py` calls the deployed `/v1/messages` endpoint and checks:

- a normal Anthropic message response;
- a streaming response with ordered start/stop events;
- a structured `tool_use` response.

It reads a scoped virtual key from `LITELLM_KEY`, `ANTHROPIC_API_KEY`, or
`KEY_FILE`.

```bash
LITELLM_KEY=sk-virtual-key python3 tests/live_smoke.py all
```

Never use the MaaS API key or LiteLLM master key for these tests.
