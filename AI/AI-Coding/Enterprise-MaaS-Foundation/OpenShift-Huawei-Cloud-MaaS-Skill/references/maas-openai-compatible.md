# Huawei Cloud MaaS OpenAI-Compatible Reference

## Purpose

Use this reference when mapping Huawei Cloud MaaS settings into Cline's `OpenAI Compatible` provider configuration.

## Field Mapping

- `Base URL`
  - Expected pattern: `https://api-<region>.modelarts-maas.com/openai/v1`
- `Authorization`
  - Use `Authorization: Bearer <MaaS_API_Key>`
- `Model`
  - Use the exact model ID exposed by MaaS, for example `<model_id>` such as `glm-5.1`

## First-Pass Validation

Use a minimal prompt and avoid tool-heavy workflows first.

Good first-pass request shape:

- model set explicitly
- one short user message
- low complexity response target

Example prompt:

```text
Reply with exactly: ok
```

## Compatibility Notes

- An OpenAI-compatible endpoint may be sufficient for:
  - text-only verification
  - simple Cline prompts
- It may still fail for:
  - advanced agent loops
  - tool-calling behavior
  - provider-specific response shapes that differ subtly from OpenAI expectations

## Error Classification

- `401` / `403`
  - authentication or authorization issue
- `404`
  - wrong base URL or wrong path suffix
- `400 model not found`
  - invalid model identifier
- network or certificate failure
  - workspace-to-provider reachability issue, CA trust issue, or outbound restriction
