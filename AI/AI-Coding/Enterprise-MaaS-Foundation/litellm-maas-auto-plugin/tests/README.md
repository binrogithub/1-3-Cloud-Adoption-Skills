# Tests

## Unit tests

`test_anthropic_stream_guard.py` is a self-contained regression script. It
covers request normalization, queued user
interjections, Anthropic streaming block repair, terminal event synthesis,
raw tool-markup detection, fail-open behavior, and Prometheus counters.

Run with Python 3.7+:

```bash
python3 tests/test_anthropic_stream_guard.py
python3 tests/test_anthropic_reasoning_filter.py
python3 tests/test_smart_router.py
```

On an older host Python, run it in the pinned LiteLLM image:

```bash
docker run --rm \
  --entrypoint /app/.venv/bin/python \
  -v "$PWD:/workspace:ro" -w /workspace \
  ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 \
  tests/test_anthropic_stream_guard.py
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
