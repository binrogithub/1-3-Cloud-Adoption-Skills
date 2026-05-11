# Deployment Runbook

## Inputs

Use the `huawei-cloud-credentials` skill first when it is installed. Required values normally come from:
- `E:\codex\.local\huawei-cloud-credentials.env`
- `E:\codex\.local\ai-site-deploy.tfvars`

If another user does not have the credential skill, prompt for the missing values and write them to ignored local files under that user's repo:

- Huawei Cloud access key: `access_key`
- Huawei Cloud secret key: `secret_key`
- IAM account/domain name: `domain_name`
- ECS administrator password: `admin_password`
- Huawei Cloud MaaS API key: `maas_api_key`
- Gateway admin password: `gateway_admin_password`
- Virtual-key user fixed password: `virtual_user_password`
- Optional SSH CIDR: `admin_cidr`

Do not print credential values.

## Target Deployment

- ECS location: Huawei Cloud `la-south-2` / `la-south-2a` (Santiago)
- ECS sizing: 4 vCPU, 8 GB RAM
- EIP: create a new public EIP for each new deployment; do not reuse the original demo EIP in reusable instructions.
- MaaS access: Hong Kong OpenAI-compatible endpoint
- CSS/OpenSearch: disabled
- App runtime: Node.js on Ubuntu, installed by cloud-init
- State path on ECS: `/var/lib/maas-finops-gateway/maas-finops-state.json`

## Files

- Server: `E:\codex\server.js`
- Frontend: `E:\codex\public\index.html`, `E:\codex\public\dashboard.js`, `E:\codex\public\styles.css`
- Model catalog: `E:\codex\data\huawei-maas-models.json`
- Package script: `E:\codex\scripts\package-ai-site.ps1`
- Terraform: `E:\codex\terraform\ai-hardware-config-site`
- Cloud-init template: `E:\codex\terraform\ai-hardware-config-site\templates\cloud-init.yaml.tftpl`
- Deploy archive: `E:\codex\deploy\maas-finops-gateway.tar.gz`

## Normal Validation

Run from `E:\codex`:

```powershell
node --check server.js
npm run package:maas-gateway
terraform -chdir=terraform\ai-hardware-config-site validate
```

If the helper script is installed in the skill directory, this is equivalent:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\l00584501\.codex\skills\huawei-maas-finops-gateway\scripts\Invoke-MaasGatewayRunbook.ps1 -Action Package
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\l00584501\.codex\skills\huawei-maas-finops-gateway\scripts\Invoke-MaasGatewayRunbook.ps1 -Action ValidateTerraform
```

## ECS Replacement Deployment

SSH publishing has been unreliable. If no safer path is available, use Terraform replacement:

```powershell
npm run package:maas-gateway
terraform -chdir=terraform\ai-hardware-config-site validate
terraform -chdir=terraform\ai-hardware-config-site plan -input=false -var-file=E:\codex\.local\ai-site-deploy.tfvars -replace=huaweicloud_compute_instance.site -out=E:\codex\.local\maas-gateway-replace.tfplan
terraform -chdir=terraform\ai-hardware-config-site apply -input=false E:\codex\.local\maas-gateway-replace.tfplan
```

Wait 2-4 minutes after replacement before judging health because cloud-init installs Node.js and dependencies.

## New Environment EIP Flow

For a new user or new environment, create infrastructure through the Terraform module instead of copying a fixed IP:

1. Use a new local tfvars file under `.local\`, with that user's Huawei Cloud AK/SK, IAM domain, MaaS key, admin password, and virtual-user password.
2. Keep `project_name` unique to avoid colliding with an existing VPC, subnet, security group, ECS, or EIP.
3. Let `huaweicloud_compute_instance.site` create the EIP through its `bandwidth` block.
4. Keep `delete_eip_on_termination = true` unless the user explicitly wants to retain and manually manage the EIP.
5. After apply, get the public address from Terraform:

```powershell
terraform -chdir=terraform\ai-hardware-config-site output -raw site_url
terraform -chdir=terraform\ai-hardware-config-site output -raw site_public_ip
```

Use that output as `<gateway-base-url>` for smoke tests, LiteLLM clients, and MCP clients.

## Post-Deploy Smoke

Check:

```text
GET  /api/health
POST /api/login
GET  /api/litellm/routes
GET  /v1/models
POST /mcp tools/list
```

Use the helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\l00584501\.codex\skills\huawei-maas-finops-gateway\scripts\Invoke-MaasGatewayRunbook.ps1 -Action Smoke -BaseUrl <gateway-base-url>
```

If `-BaseUrl` is omitted, the helper tries `MAAS_GATEWAY_BASE_URL`, then Terraform output `site_url`.

Expected outcomes:
- `/api/health` returns OK with an upstream base URL.
- Admin login succeeds using the locally stored gateway admin password.
- `/api/litellm/routes` returns base URL, chat completions URL, models URL, and model routes.
- `/mcp` lists `web_search`.
- 50 seeded virtual keys exist unless the admin deleted or changed them.
