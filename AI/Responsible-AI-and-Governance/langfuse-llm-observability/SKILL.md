---
name: langfuse-llm-observability
description: Use this skill when deploying or integrating Langfuse for LLM observability, tracing, generations, usage, latency, cost, errors, evaluations, prompts, or LiteLLM/application instrumentation. Langfuse is not a MaaS token platform, does not issue or manage MaaS API keys, and normally does not call MaaS providers directly.
---

# Langfuse LLM Observability

## Purpose

Use this skill to add or explain Langfuse as an observability layer for LLM applications.

Langfuse records LLM execution telemetry:

- traces, spans, and generations
- prompts, model inputs, outputs, and errors
- model name, provider metadata, latency, token usage, and cost
- user/session/project tags
- evaluation scores and review metadata

Langfuse is not a MaaS token service. It does not issue, rotate, meter, or authenticate Huawei MaaS, OpenAI, Anthropic, or other provider API keys. It only authenticates clients that write observability events into Langfuse.

## Architectural Rule

Treat Langfuse as a sidecar observability system, not as the model provider.

Typical flow:

```text
App / Agent / LiteLLM / IDE integration
  |-- provider API key --> LLM provider or MaaS endpoint
  |
  |-- Langfuse public/secret key --> Langfuse trace ingestion
```

Langfuse API keys are project-scoped ingestion credentials:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`

Provider API keys, such as MaaS keys, must stay with the component that calls the model. Do not send raw provider API keys to Langfuse. If key-level attribution is needed, log a safe alias such as `maas_key_alias=prod-key-01`, never the real secret.

## Use Cases

Use Langfuse when the user wants to:

- monitor LLM calls across apps, agents, IDEs, or gateways
- inspect prompt/response traces
- track token usage, latency, cost, and errors
- evaluate model outputs
- compare prompt or model behavior
- observe a LiteLLM proxy or OpenAI-compatible application
- troubleshoot missing traces or incorrect observability data

Do not frame Langfuse as:

- a MaaS token broker
- a MaaS API gateway
- a model router
- a budget enforcement layer
- a replacement for LiteLLM, API gateway, IAM, or provider billing

For routing, budget limits, virtual keys, and provider key management, prefer a gateway such as LiteLLM or a dedicated token platform. Langfuse can observe those calls if the gateway or application emits traces.

## Integration Patterns

### Application SDK Instrumentation

Use this when the application code can be edited.

1. Install the Langfuse SDK for the application runtime.
2. Configure `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`.
3. Keep provider credentials separate, for example `MAAS_API_KEY` or `OPENAI_API_KEY`.
4. Around each model call, record a generation with:
   - input messages or prompt
   - output text or structured response
   - model name
   - provider name
   - token usage if available
   - latency, error, and status metadata
5. Flush events before short-lived scripts exit.

### LiteLLM or Gateway Instrumentation

Use this when many clients should be observed consistently.

Recommended shape:

```text
IDE / Agent / App
        |
        v
LiteLLM or API Gateway  --->  Langfuse
        |
        v
LLM Provider / MaaS
```

The gateway owns provider keys, routing, budget, retries, and rate limits. Langfuse receives logs/traces from the gateway and is used for inspection and evaluation.

### IDE or Agent Instrumentation

Use this only if the IDE/agent supports callbacks, custom OpenAI wrappers, or a proxy configuration.

Preferred order:

1. Send IDE/agent traffic through LiteLLM and let LiteLLM emit Langfuse logs.
2. If supported, configure the IDE/agent to emit Langfuse traces directly.
3. Patch plugin/agent source code only when necessary and maintainable.

## Verification Checklist

After integration, verify:

- Langfuse health endpoint responds.
- Langfuse auth check succeeds with the project keys.
- A test model call succeeds independently of Langfuse.
- A trace appears in the expected Langfuse project.
- The trace contains a generation observation.
- The generation contains model, input, output, usage, latency/error metadata.
- No raw provider API key appears in trace input, output, metadata, logs, or screenshots.

For short-lived scripts, always call SDK flush/shutdown before exit.

## Troubleshooting

- `401` or `403` from Langfuse: wrong Langfuse public/secret key or wrong project.
- No trace appears: missing flush, wrong host, blocked network path, or tracing disabled.
- Model call works but no usage: provider did not return usage, or the wrapper did not map it.
- Trace appears in the wrong project: wrong Langfuse key pair.
- Provider call fails: debug the provider/MaaS key, endpoint, model ID, network, and auth separately from Langfuse.
- Sensitive data appears in traces: add masking/redaction before sending telemetry.

## Deliverables

When using this skill, prefer producing:

- a clear architecture statement separating provider credentials from Langfuse credentials
- a minimal SDK or gateway configuration
- a test call that creates one trace
- a trace URL or trace ID
- a short validation summary that confirms whether data was ingested
- a warning if raw provider API keys or sensitive prompts could be logged

