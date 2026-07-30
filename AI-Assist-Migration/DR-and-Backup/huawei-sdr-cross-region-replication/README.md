# Huawei Cloud SDR Cross-Region Replication

This scenario provides a structured workflow for discovering, planning, executing (under human supervision), validating, and recovering Huawei Cloud cross-region disaster recovery scenarios using SDRS (Storage Disaster Recovery Service) capabilities.

## What's Included

| Component | Path | Files | Description |
|-----------|------|-------|-------------|
| Skill | `skills/huawei-sdr-cross-region-replication/` | 23 | SKILL.md, workflows, docs, prompts, examples, tests |
| Shared Skill | `shared-skills/mcp-capability-builder/` | 12 | MCP gap analysis and scaffold generation for future SDRS MCP |
| MCP: Pricing | `shared-mcps/huaweicloud-pricing/` | 58 | Cost estimation for replication resources |
| MCP: Ticket | `shared-mcps/huaweicloud-ticket/` | 10 | Support ticket creation for issues |
| MCP: Deploy | `shared-mcps/huaweicloud-deploy/` | 28 | Terraform generation for VPC/subnet/SG prerequisites |
| Integration: Playwright | `integrations/playwright/` | 3 | Console exploration, form field discovery, visual verification |

## Skill Details

| Field | Value |
|-------|-------|
| Status | EXPERIMENTAL |
| Risk Level | Critical |
| Primary Mechanism | Supervised console (Playwright) |
| Required MCPs | None (SDRS not supported by deploy MCP) |
| Optional MCPs | pricing, ticket, deploy (for prerequisites only) |
| Required Shared Skill | mcp-capability-builder |
| Tests | Local tests |

## Workflow Phases

1. **Discovery** — Identify protected and disaster recovery regions, assess SDRS compatibility
2. **Readiness** — Verify prerequisites, network connectivity, and replication groups
3. **Execution** — Configure replication under human supervision (console-based, Playwright-assisted)
4. **Validation** — Verify replication status, RPO/RTO, and failover readiness
5. **Rollback** — Execute failover or reverse replication with verification

## Important Notes

- SDRS is **not supported** by the huaweicloud-deploy MCP. All SDRS operations are performed via supervised console interaction.
- The `mcp-capability-builder` shared skill is included to design a future SDRS MCP when automation is requested.
- Playwright integration is read-only — it never accepts dialogs, executes writes, or confirms operations.

## Usage

Load the skill in OpenCode or Hermes, then follow the workflow phases. All SDRS operations require explicit human approval.

## License

Apache-2.0
