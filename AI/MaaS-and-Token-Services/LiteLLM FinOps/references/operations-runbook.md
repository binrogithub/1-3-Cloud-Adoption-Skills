# Operations Runbook

## Roles

Admin login:
- Username: `admin`
- Password: load from `huawei-cloud-credentials`; do not print.
- Admin can view all keys, usage, spend, routes, and model connections.

Virtual-key user login:
- Username/API key: a generated virtual API key.
- Password: shared fixed password loaded from `huawei-cloud-credentials`.
- User can only see its own token usage, spend, quota, selected model, and generated call URLs.

## Virtual Keys

Initial requirement:
- Pre-seed 50 virtual keys.
- Each key has a 20 USD budget.
- Admin can create keys and choose the model connection at creation time.
- Admin can delete generated keys.
- Users can switch among enabled model connections when allowed by the gateway.

Remember: virtual API keys are local gateway keys. They are not Huawei MaaS native API keys.

## Model Connections

Admin can add Huawei Cloud MaaS models. The same base model may have multiple connections:
- Huawei MaaS native interface: `interfaceType = maas-native`
- Huawei MaaS OpenAI-compatible interface: `interfaceType = openai-compatible`

Do not overwrite an existing model when adding another interface type or another route for the same base model. Each connection must have a unique `connectionId`, and virtual keys should bind to that `connectionId`.

## Website/API Endpoints

Important live endpoints:

```text
GET    /api/health
POST   /api/login
POST   /api/logout
GET    /api/admin/keys
POST   /api/admin/keys
DELETE /api/admin/keys/:id
GET    /api/admin/models
POST   /api/admin/models
DELETE /api/admin/models/:connectionId
GET    /api/litellm/config
GET    /api/litellm/routes
GET    /v1/models
POST   /v1/chat/completions
POST   /mcp
```

## Web Search MCP

The gateway exposes JSON-RPC over HTTP at `/mcp`.

Expected tool list includes:

```json
{
  "name": "web_search"
}
```

The implementation uses DuckDuckGo Lite HTML scraping and normalizes DuckDuckGo redirect URLs.

## CSS/OpenSearch

Do not deploy CSS/OpenSearch. The original architecture image included Code Search MCP with CSS/OpenSearch, but the user explicitly excluded CSS deployment for this build.
