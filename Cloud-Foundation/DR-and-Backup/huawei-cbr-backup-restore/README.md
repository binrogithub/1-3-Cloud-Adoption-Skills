# Huawei Cloud CBR Backup and Restore

This scenario provides a structured workflow for discovering, configuring, executing, validating, and restoring Huawei Cloud CBR (Cloud Backup and Recovery) backups for supported ECS, EVS, and CCE node scenarios.

## What's Included

| Component | Path | Files | Description |
|-----------|------|-------|-------------|
| Skill | `skills/huawei-cbr-backup-restore/` | 22 | SKILL.md, workflows, docs, prompts, examples, tests |
| MCP: Pricing | `shared-mcps/huaweicloud-pricing/` | 58 | Cost estimation for backup resources |
| MCP: Ticket | `shared-mcps/huaweicloud-ticket/` | 10 | Support ticket creation for issues |
| MCP: Deploy | `shared-mcps/huaweicloud-deploy/` | 28 | Terraform generation for VPC/subnet/SG prerequisites |

## Skill Details

| Field | Value |
|-------|-------|
| Status | READY_WITH_WARNINGS |
| Risk Level | High |
| Primary Mechanism | hcloud CBR CLI |
| Required MCPs | None (uses hcloud CLI directly) |
| Optional MCPs | pricing, ticket, deploy |
| Tests | 27 local tests |
| Verified hcloud | 6.2.9 |

## Workflow Phases

1. **Discovery** — Identify resources to protect (ECS, EVS, CCE nodes)
2. **Readiness** — Verify prerequisites and CBR vault configuration
3. **Execution** — Create backup policies and trigger backups
4. **Validation** — Verify backup integrity and restore points
5. **Rollback** — Restore from backup with verification

## Usage

Load the skill in OpenCode or Hermes, then follow the workflow phases. The skill contains explicit approval gates for all destructive operations.

## License

Apache-2.0
