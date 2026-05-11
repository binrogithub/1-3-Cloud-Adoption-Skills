# Troubleshooting

## 502 After Replacement

Likely cause: cloud-init is still installing Node.js or dependencies.

Wait 2-4 minutes, then retry:

```powershell
Invoke-RestMethod <gateway-base-url>/api/health
```

If it persists, inspect Terraform outputs and cloud-init logs via the available access method.

## Terraform User Data Too Large

Huawei ECS user_data has a size limit. Keep `deploy\maas-finops-gateway.tar.gz` small:
- Do not include `node_modules`.
- Package only `server.js`, `package.json`, `public`, and `data\huawei-maas-models.json`.
- Prefer `npm run package:maas-gateway`.

## SSH Fails

Port 22 has been reachable, but password login was unreliable. Prefer Terraform replacement unless a new SSH key or access path is confirmed.

## All New Keys Look Like GLM-5.1 Compatible

Check three places:

1. Frontend key creation form sends the selected model connection:

```js
selectedModel: els.keyModel.value
```

2. Admin model dropdown options use `connectionId` as values.
3. Backend key creation uses exact `connectionId` for administrative binding.

Also consider the operator workflow: after adding a new model, the key creation dropdown may default back to the first enabled model. The UI should either auto-select the newly added connection or make the selected connection obvious.

MaaS API key limitation is a separate issue. If the key is only authorized for GLM-5.1, a real DeepSeek call should fail upstream rather than rewriting the local virtual key.

## Real Upstream Call Fails

Check:
- Does `/api/admin/models` show the intended enabled `connectionId`?
- Does `/v1/models` include that exact model ID?
- Is the virtual key active and under its 20 USD budget?
- Does the MaaS API key have entitlement for the upstream model?
- Is the route using the correct interface type: native vs OpenAI-compatible?

## MCP Search Fails

Check:
- `POST /mcp` with `tools/list` returns `web_search`.
- The ECS can reach DuckDuckGo Lite or the selected search backend.
- The JSON-RPC body includes `jsonrpc`, `id`, `method`, and `params`.
