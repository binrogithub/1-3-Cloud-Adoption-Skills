---
name: huawei-maas-finops-gateway
description: Deploy, update, validate, and troubleshoot the Huawei Cloud MaaS FinOps gateway website in E:\codex. Use when Codex is asked to operate the Santiago ECS deployment, Huawei Cloud MaaS Hong Kong access, LiteLLM/OpenAI-compatible routes, FinOps virtual API keys, admin/user login, model connection management, or the Web Search MCP server for this gateway.
---

# Huawei MaaS FinOps Gateway

## Core Rule

Use the `huawei-cloud-credentials` skill before any deployment, Terraform, ECS, MaaS, admin-login, or virtual-user-password operation when that skill exists. If the credential skill is not installed, ask the user for the missing Huawei Cloud AK/SK, IAM domain, MaaS API key, gateway admin password, virtual-user password, and ECS admin password, then store them only in ignored local files under `.local`. Never print secrets.

Current project root: `E:\codex`

Deployment URL handling:
- Do not hard-code a public EIP in reusable runbooks.
- Resolve the live website URL from `-BaseUrl`, `MAAS_GATEWAY_BASE_URL`, or Terraform output `site_url`.
- OpenAI-compatible base URL: `<gateway-base-url>/v1`
- Chat completions URL: `<gateway-base-url>/v1/chat/completions`
- Models URL: `<gateway-base-url>/v1/models`
- Web Search MCP: `<gateway-base-url>/mcp`
- Huawei Cloud ECS region: `la-south-2`, AZ `la-south-2a`, 4C8G flavor
- Huawei Cloud MaaS upstream: `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`

## Workflow

1. Load credentials with `huawei-cloud-credentials` when available; otherwise prompt for missing values and write them to ignored local files under `.local`.
2. Inspect the requested task:
   - Deployment or replacement: read `references/deployment-runbook.md`.
   - Website/API/model/key changes: read `references/operations-runbook.md`.
   - LiteLLM, MaaS interface types, or virtual key behavior: read `references/model-and-api-runbook.md`.
   - Failures, 502, model mismatch, SSH, or upstream MaaS errors: read `references/troubleshooting.md`.
3. Prefer existing project scripts and Terraform:
   - Package: `npm run package:maas-gateway`
   - Terraform module: `terraform\ai-hardware-config-site`
   - Deployment archive: `deploy\maas-finops-gateway.tar.gz`
4. Validate locally before redeploying:
   - `node --check server.js`
   - `npm run package:maas-gateway`
   - `terraform -chdir=terraform\ai-hardware-config-site validate`
5. After deployment or live edits, run a smoke test. Prefer `scripts\Invoke-MaasGatewayRunbook.ps1 -Action Smoke`.

## One-Command Helper

Use the bundled helper for repeatable operations:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\l00584501\.codex\skills\huawei-maas-finops-gateway\scripts\Invoke-MaasGatewayRunbook.ps1 -Action Smoke
```

Supported actions: `Smoke`, `Package`, `ValidateTerraform`, `PlanReplace`, `ApplyReplace`, `FullReplace`.

`FullReplace` packages the site, validates Terraform, plans an ECS replacement, applies it, waits for cloud-init, and smokes the public site. Treat it as disruptive because it replaces the ECS instance.

## Architecture Memory

The source architecture diagram described:
- Developers, IDEs, or Claude Code call a router/gateway.
- The gateway runs on a single secured ECS node.
- LiteLLM-style gateway behavior provides unified API access, virtual keys, budget/rate controls, audit, spend tracking, and OpenAI compatibility.
- Huawei Cloud MaaS is the upstream model provider.
- Web Search MCP is enabled for search.
- CSS/OpenSearch code search was explicitly excluded from this deployment.
- The QR in the source image pointed to a technical blog, but the actual QR URL was not required for the deployed gateway.

## Safety

- Do not deploy CSS/OpenSearch unless the user explicitly changes the requirement.
- Keep all secrets under `E:\codex\.local\` or existing environment variables.
- Do not commit `.local`, tfvars with secrets, state backups containing secrets, generated API keys, or MaaS API keys.
- Do not assume every catalog model is authorized by the MaaS API key. A virtual key can be locally bound to a model connection, but real upstream calls only work if the MaaS API key has permission for that model.
