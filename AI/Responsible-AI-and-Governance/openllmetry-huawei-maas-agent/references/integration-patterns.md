# Integration Patterns

## Direct Agent With OpenAI SDK

Use `Instruments.OPENAI` and initialize OpenLLMetry before creating the `OpenAI` client. Huawei MaaS remains an OpenAI-compatible endpoint configured by `base_url`.

Recommended environment:

```bash
HUAWEI_MAAS_API_BASE=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
HUAWEI_MAAS_API_KEY=<secret>
HUAWEI_MAAS_MODEL=glm-5.1
TRACELOOP_TRACE_CONTENT=false
OPENLLMETRY_EXPORTER=console
```

## LangChain or LlamaIndex

Add the framework instrument only if the app uses it:

```python
instruments={Instruments.OPENAI, Instruments.LANGCHAIN}
```

or:

```python
instruments={Instruments.OPENAI, Instruments.LLAMA_INDEX}
```

Keep the underlying model client OpenAI-compatible and pointed at MaaS.

## LiteLLM Proxy In Front Of MaaS

If the Agent calls LiteLLM and LiteLLM calls Huawei MaaS, there are two observability choices:

- Instrument the Agent client call to LiteLLM. This captures user-facing Agent latency and errors.
- Instrument the LiteLLM service separately. This captures provider-facing MaaS behavior.

Use separate resource attributes:

```python
resource_attributes={
    "service.name": "agent-service",
    "agent.name": "risk-agent",
    "llm.gateway": "litellm",
}
```

and:

```python
resource_attributes={
    "service.name": "litellm-proxy",
    "llm.provider": "huawei-cloud-maas",
}
```

## OTLP / Web UI

OpenLLMetry emits OpenTelemetry telemetry; a UI comes from the backend.

Common paths:

- Console exporter for local testing.
- Traceloop Cloud for LLM-focused trace UI.
- OTLP Collector to Jaeger, Grafana Tempo, Datadog, Honeycomb, or another backend.

## Validation Checklist

Confirm:

- An LLM span appears, for example `openai.chat`.
- `gen_ai.request.model` or equivalent contains the MaaS model.
- `gen_ai.openai.api_base` points to the MaaS OpenAI-compatible base URL.
- Token usage appears when the provider returns it.
- No `HUAWEI_MAAS_API_KEY`, `Authorization`, or raw bearer token appears in span attributes, logs, generated docs, or final user output.

## Common Failures

- No spans: initialize `Traceloop.init()` before the LLM client is created or used.
- No web page: configure Traceloop Cloud or an OTLP backend; OpenLLMetry is not itself a UI.
- Authentication failure: verify `HUAWEI_MAAS_API_KEY`, endpoint region, and model name outside the trace output.
- Secret leaked into span: remove `@task` or `@workflow` from credential helper functions and keep `TRACELOOP_TRACE_CONTENT=false`.
- Empty answer with successful response: check whether the model uses a nonstandard field such as `reasoning_content`; use `message.content or getattr(message, "reasoning_content", "")`.
