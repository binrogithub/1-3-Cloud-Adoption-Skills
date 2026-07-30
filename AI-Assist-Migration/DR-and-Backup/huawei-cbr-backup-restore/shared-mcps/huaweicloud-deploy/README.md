# huaweicloud-deploy

## Purpose

MCP server for Huawei Cloud infrastructure deployment using Terraform. Generates Terraform configurations from architecture definitions, validates them, and runs `terraform plan` to preview changes. Never applies changes — no `terraform apply` or `terraform destroy` is exposed.

## Scope

**Includes:**
- Terraform file generation from architecture JSON (VPC, Subnet, Security Group, ECS, ELB, EIP, RDS MySQL, OBS)
- Terraform configuration validation (fmt, init, validate)
- Terraform plan execution and analysis
- Plan explanation and risk assessment
- Architecture validation against supported services

**Does not include:**
- `terraform apply` — never exposed [VERIFIED_FROM_CODE]
- `terraform destroy` — never exposed [VERIFIED_FROM_CODE]
- Direct cloud resource creation
- State management or remote backend configuration
- Secret injection into generated Terraform files

## Use cases

1. **Infrastructure-as-code generation** — Generate Terraform files from architecture definitions [VERIFIED_FROM_CODE]
2. **Pre-deployment validation** — Validate Terraform configs before any cloud changes [VERIFIED_FROM_CODE]
3. **Cost preview via plan** — Preview infrastructure changes with `terraform plan` [VERIFIED_FROM_CODE]
4. **Architecture safety review** — Explain plan results and identify risks [VERIFIED_FROM_CODE]
5. **CCE cross-region migration with Velero** — Assisted workflow for Kubernetes cluster migration [INFERRED]

## Architecture

- **Runtime:** Node.js (ESM)
- **Entry point:** `src/server.mjs`
- **Transport:** stdio (MCP SDK)
- **Core modules:**
  - `src/server.mjs` — Main MCP server with 4 tool handlers
  - `src/terraform-generator.mjs` — Generates .tf files from architecture JSON
  - `src/terraform-executor.mjs` — Executes terraform CLI commands with safety guards
  - `src/architecture-validator.mjs` — Validates architecture definitions
  - `src/plan-analyzer.mjs` — Analyzes and explains terraform plan output
  - `config/supported-services.json` — Supported service definitions
- **Dependencies:** `@modelcontextprotocol/sdk`
- **External tools:** Terraform CLI (required for validate and plan)

## MCP tools exposed

| # | Tool name | Purpose | Read/Write | Risk | Approval required |
|---|-----------|---------|------------|------|-------------------|
| 1 | GenerateTerraformFromArchitecture | Generate Terraform files from architecture JSON | write (local FS) | low | no |
| 2 | ValidateTerraformConfiguration | Run terraform fmt/init/validate | write (local FS) | low | no |
| 3 | RunTerraformPlan | Run terraform plan to preview changes | write (local FS) | medium | no |
| 4 | ExplainTerraformPlan | Analyze and explain plan results | read-only | none | no |

**Key safety:** `terraform apply` and `terraform destroy` are explicitly forbidden in `terraform-executor.mjs` via `FORBIDDEN_COMMANDS`.

## Prerequisites

- Node.js >= 18
- Terraform CLI >= 1.5
- Huawei Cloud provider credentials (for plan)

## Installation

```bash
cd mcps/huaweicloud-deploy
npm install
```

## Configuration

```bash
export HWCLOUD_ACCESS_KEY=<YOUR_ACCESS_KEY>
export HWCLOUD_SECRET_KEY=<YOUR_SECRET_KEY>
export HWCLOUD_REGION=<YOUR_REGION>
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| HWCLOUD_ACCESS_KEY | yes | Huawei Cloud Access Key |
| HWCLOUD_SECRET_KEY | yes | Huawei Cloud Secret Key |
| HWCLOUD_REGION | no | Default region |

## Execution

```bash
node src/server.mjs
```

## Integration with OpenCode

```json
{
  "huaweicloud-deploy": {
    "type": "local",
    "enabled": true,
    "command": ["node", "<INSTALLATION_ROOT>/mcps/huaweicloud-deploy/src/server.mjs"],
    "timeout": 30000
  }
}
```

## Examples

```bash
# Generate Terraform from architecture
# Tool: GenerateTerraformFromArchitecture
# Parameters: { architecture: { architecture_id: "my-app", region: "la-north-2", deployment_mode: "terraform", components: [{ service: "vpc", name: "main-vpc", cidr: "192.168.0.0/16" }] } }

# Validate configuration
# Tool: ValidateTerraformConfiguration
# Parameters: { architecture_id: "my-app" }

# Run plan
# Tool: RunTerraformPlan
# Parameters: { architecture_id: "my-app" }
```

## Tests

```bash
npm test
```

9 test files: generation, validation, no-secrets, unsupported, no-apply, phase2, ELB discovery, NAT gateway, workspace path.

## Security

- `terraform apply` and `terraform destroy` are **explicitly forbidden** [VERIFIED_FROM_CODE]
- Generated .tf files do not contain secrets [VERIFIED_FROM_TEST]
- `terraform.tfvars.example` uses placeholders, not real values
- Plan output is read-only; no infrastructure changes are made

## Limitations

- Only supports services defined in `config/supported-services.json`
- Requires Terraform CLI installed locally
- Plan execution requires cloud credentials (read-only API calls)
- Workspace-based: each architecture gets its own directory

## Troubleshooting

- **"Terraform not found"**: Install Terraform CLI and ensure it's in PATH
- **"Unsupported service"**: Check `config/supported-services.json` for supported services
- **"Plan failed"**: Verify credentials and region configuration

## Related use cases

- CCE cross-region migration with Velero (see `use-cases/cce-cross-region-velero/`)
- Infrastructure-as-code generation and validation

## Status

**READY** — 4 tools implemented. `terraform apply`/`destroy` explicitly forbidden. 9 test files available. Phase 2 (generate + validate + plan) complete.
