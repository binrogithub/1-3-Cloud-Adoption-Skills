---
name: openllmetry-huawei-maas-agent
description: Build, instrument, troubleshoot, or explain Agent applications that call Huawei Cloud MaaS through an OpenAI-compatible endpoint while using OpenLLMetry / Traceloop / OpenTelemetry for observability. Use when Codex needs to add OpenLLMetry to an Agent, LangChain/LlamaIndex/OpenAI SDK flow, LiteLLM proxy, Cline/Claude-Code-router style MaaS client, or any Huawei MaaS LLM application; generate safe examples; configure OTLP/Traceloop export; validate traces; or prevent MaaS API keys and prompts from leaking into telemetry.
---

# OpenLLMetry Huawei MaaS Agent

## Core Model

Treat OpenLLMetry as the observability layer, not the model provider.

```text
Agent / app logic -> OpenAI SDK or framework -> Huawei Cloud MaaS
Agent / app logic -> OpenLLMetry instrumentation -> OpenTelemetry backend
```

Do not design a direct OpenLLMetry-to-MaaS integration. MaaS is called by the Agent through an OpenAI-compatible client; OpenLLMetry observes the client/framework calls and exports traces to console, Traceloop, OTLP Collector, Jaeger, Grafana Tempo, Datadog, Honeycomb, or another OpenTelemetry backend.

## Workflow

1. Discover how the Agent calls LLMs: OpenAI SDK, LangChain, LlamaIndex, LiteLLM, Cline, custom HTTP, or another framework.
2. Keep the MaaS provider configuration in environment variables:
   - `HUAWEI_MAAS_API_BASE`, for example `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
   - `HUAWEI_MAAS_API_KEY`
   - `HUAWEI_MAAS_MODEL`, for example `glm-5.1`
3. Initialize OpenLLMetry before creating or using the LLM client.
4. Instrument only the libraries in use. Prefer `Instruments.OPENAI` for OpenAI-compatible MaaS calls; add `Instruments.LANGCHAIN` or `Instruments.LLAMA_INDEX` only when the app uses those frameworks.
5. Default to `TRACELOOP_TRACE_CONTENT=false`. Only enable prompt/completion capture when the user explicitly accepts the data exposure.
6. Export locally with `ConsoleSpanExporter` for a smoke test, then switch to OTLP or Traceloop for a web UI.
7. Validate that a trace contains an LLM span such as `openai.chat`, model name, MaaS base URL, latency, token usage, and errors, without raw API keys.

## Safe Defaults

Always protect secrets:

- Do not write raw MaaS API keys into source files, examples, logs, README output, traces, or final answers.
- Do not decorate functions that return API keys with `@task` or `@workflow`; OpenLLMetry can record task input/output attributes.
- Set `TRACELOOP_TRACE_CONTENT=false` unless the user explicitly asks to capture prompts and completions.
- If showing discovered credentials, show only masked values such as `rJsN...6GLw (len=86)`.
- Prefer environment references such as `os.environ["HUAWEI_MAAS_API_KEY"]`.

## Minimal Pattern

Use this pattern for direct OpenAI SDK agents:

```python
import os
from openai import OpenAI
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments

os.environ.setdefault("TRACELOOP_TRACE_CONTENT", "false")

Traceloop.init(
    app_name="huawei-maas-agent",
    exporter=ConsoleSpanExporter(),
    disable_batch=True,
    telemetry_enabled=False,
    instruments={Instruments.OPENAI},
    resource_attributes={
        "service.name": "huawei-maas-agent",
        "llm.provider": "huawei-cloud-maas",
        "agent.name": "example-agent",
    },
)

client = OpenAI(
    api_key=os.environ["HUAWEI_MAAS_API_KEY"],
    base_url=os.environ["HUAWEI_MAAS_API_BASE"],
)

response = client.chat.completions.create(
    model=os.getenv("HUAWEI_MAAS_MODEL", "glm-5.1"),
    messages=[{"role": "user", "content": "Say: MaaS Agent OK"}],
    temperature=0.2,
    max_completion_tokens=128,
)

message = response.choices[0].message
print(message.content or getattr(message, "reasoning_content", "") or "")
```

## Scaffold Script

For a new demo project, run:

```bash
python3 /root/.codex/skills/openllmetry-huawei-maas-agent/scripts/create_maas_agent_demo.py /path/to/output
```

The script creates a minimal Python Agent project with:

- `requirements.txt`
- `.env.example`
- `agent.py`
- `README.md`

Use the generated project for smoke testing, demos, or as a starting point for an existing Agent integration.

## Export Selection

Use console export for local validation:

```python
Traceloop.init(exporter=ConsoleSpanExporter(), disable_batch=True, ...)
```

Use OTLP when the user has a collector or observability backend:

```python
Traceloop.init(
    api_endpoint=os.environ["TRACELOOP_BASE_URL"],
    api_key=os.getenv("TRACELOOP_API_KEY"),
    ...
)
```

For web UI requirements, explain that OpenLLMetry itself is not a UI. Use Traceloop Cloud or an OpenTelemetry backend such as Jaeger/Grafana Tempo/Datadog.

## References

Read `references/integration-patterns.md` when implementing a non-trivial Agent, LangChain/LlamaIndex flow, LiteLLM proxy route, or OTLP backend configuration.
