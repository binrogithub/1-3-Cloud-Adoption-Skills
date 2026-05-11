# Model And API Runbook

## Key Principle

Virtual key generation is local gateway state. MaaS API key authorization is upstream provider state.

If a virtual key is generated for DeepSeek but the Huawei Cloud MaaS API key only has GLM-5.1 entitlement, the local key may still be created, but a real upstream DeepSeek call should fail with a MaaS authorization/model error. It should not silently become GLM-5.1.

## Avoid The GLM-Only Selection Bug

When binding a key or user selection to a model, use exact `connectionId` matching. Avoid fuzzy matching by base model name for key creation and user selection because it can select the first matching model connection.

Correct behavior:
- Admin model dropdown value: `model.connectionId`
- `POST /api/admin/keys` body: `{ "selectedModel": "<connectionId>" }`
- Stored key field: `selectedModel = model.connectionId`
- `/v1/models` returns model IDs as `connectionId`
- `/api/litellm/config` uses `model_name = connectionId`

Fuzzy aliases can be acceptable for API request compatibility, but administrative binding should be exact.

## LiteLLM Compatibility

The gateway exposes OpenAI-compatible routes:

```text
Base URL:          <gateway-base-url>/v1
Chat completions:  <gateway-base-url>/v1/chat/completions
Models:            <gateway-base-url>/v1/models
```

Clients should authenticate with:

```text
Authorization: Bearer <virtual-api-key>
```

Use the selected `connectionId` as `model` unless the UI explicitly presents another alias.

## Huawei MaaS Interfaces

For a model connection:
- `openai-compatible` should route to Huawei MaaS OpenAI-compatible `/chat/completions`.
- `maas-native` should keep a distinct connection even if it points to the same model family.

In exported LiteLLM config:
- OpenAI-compatible routes can use `litellm_params.model = openai/<upstream-model-name>`.
- Native routes can use `litellm_params.model = huawei_maas/<upstream-model-name>` or the local adapter pattern implemented in `server.js`.

## Model Catalog

Catalog file: `E:\codex\data\huawei-maas-models.json`

The catalog is not a guarantee of MaaS entitlement. Only display or enable models after the admin creates a model connection. The default live deployment starts with GLM-5.1 enabled because that was the known valid MaaS API key entitlement.
