# Huawei Cloud DWS Cluster Deployment

This scenario provides a structured workflow for discovering, planning, deploying, validating, and configuring a Huawei Cloud DWS (Data Warehouse Service) cluster using verified hcloud CLI operations and controlled approval gates.

## What's Included

| Component | Path | Files | Description |
|-----------|------|-------|-------------|
| Skill | `skills/huawei-dws-cluster-deployment/` | 23 | SKILL.md, workflows, docs, prompts, examples, tests |
| Shared Skill | `shared-skills/mcp-capability-builder/` | 12 | MCP gap analysis and scaffold generation for future DWS MCP |
| MCP: Pricing | `shared-mcps/huaweicloud-pricing/` | 58 | Cost estimation for DWS cluster resources |
| MCP: Ticket | `shared-mcps/huaweicloud-ticket/` | 10 | Support ticket creation for issues |
| MCP: Deploy | `shared-mcps/huaweicloud-deploy/` | 28 | Terraform generation for VPC/subnet/SG prerequisites |

## Skill Details

| Field | Value |
|-------|-------|
| Status | READY_WITH_WARNINGS |
| Risk Level | High |
| Primary Mechanism | hcloud DWS CLI |
| Required MCPs | None (uses hcloud CLI directly) |
| Optional MCPs | pricing, ticket, deploy (for prerequisites only) |
| Required Shared Skill | mcp-capability-builder |
| Tests | 45 local tests |
| Verified hcloud | 6.2.9 |

## Workflow Phases

1. **Discovery** — Identify available DWS flavors, node types, and AZs
2. **Readiness** — Verify prerequisites (VPC, subnet, security groups, keypair)
3. **Execution** — Deploy DWS cluster with approval gates
4. **Validation** — Verify cluster health, connectivity, and configuration
5. **Rollback** — Delete cluster and clean up resources

## Important Notes

- DWS is **not supported** by the huaweicloud-deploy MCP. DWS cluster creation is performed via hcloud CLI.
- The deploy MCP is used **only** for VPC/subnet/SG prerequisites, not for DWS resources.
- The `mcp-capability-builder` shared skill is included to design a future DWS MCP extension when automation is requested.

## Usage

Load the skill in OpenCode or Hermes, then follow the workflow phases. The skill contains explicit approval gates for all destructive operations.

## License

Apache-2.0
