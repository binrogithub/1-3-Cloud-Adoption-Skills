# huawei-cbr-backup-restore

## Purpose

Discover, configure, execute, validate and restore Huawei Cloud CBR backups for ECS, EVS and CCE node scenarios using hcloud CLI.

## Supported resource types

- ECS instances (OS::Nova::Server)
- EVS volumes (OS::Cinder::Volume)
- CCE node disks (via server/disk type)

## Architecture

```
Source Region
┌──────────────┐     ┌──────────────┐
│  ECS / EVS   │────>│  CBR Vault   │
│  / CCE Node  │     │  (backup)    │
└──────────────┘     └──────┬───────┘
                            │
                     CreateCheckpoint
                            │
                     ┌──────▼───────┐
                     │   Backup     │
                     │  (checkpoint)│
                     └──────┬───────┘
                            │
                      RestoreBackup
                            │
                     ┌──────▼───────┐
                     │  Restored    │
                     │  Resource    │
                     │  (new)       │
                     └──────────────┘
```

Cross-region copy path (optional):
```
Backup (Region A) ──CopyBackup──> Backup Copy (Region B)
```

## Rules summary

1. DISCOVER BEFORE CREATE: resolve names to IDs, never hardcode
2. VERIFY AFTER EVERY STEP: every write has a follow-up read
3. Every write operation requires explicit approval
4. Restore defaults to new resource; in-place requires double confirmation
5. Validate resource state before backup
6. Validate vault capacity before checkpoint
7. Validate cross-region capabilities before copy
8. Never include secrets in commands, examples, or logs

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI 6.2.9 | All CBR operations |
| Huawei Cloud auth | API access |
| Target region | Vault and resource region |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region → 3. Discover Source → 4. Discover Existing → 5. Plan Vault → 6. Create/Reuse Vault → 7. Associate Resource → 8. Create/Reuse Policy → 9. Trigger Backup → 10. Verify Backup → 11. Plan Restore → 12. Execute Restore → 13. Verify Restored → 14. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery | ASSISTED | hcloud CLI read-only |
| Readiness | ASSISTED | hcloud CLI read-only |
| Planning | AUTOMATED | Logic |
| Vault creation | ASSISTED | hcloud CLI + approval |
| Association | ASSISTED | hcloud CLI + approval |
| Policy | ASSISTED | hcloud CLI + approval |
| Backup | ASSISTED | hcloud CLI + approval |
| Restore | ASSISTED | hcloud CLI + approval |
| Validation | ASSISTED | hcloud CLI read-only |
| Closure | AUTOMATED | Logic |

## hcloud compatibility

- Verified: hcloud CLI 6.2.9
- Pending validation: hcloud CLI 7.2.12

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-pricing | No | Cost estimation (read-only) |
| huaweicloud-ticket | No | Support ticket creation |
| huaweicloud-deploy | No | VPC/SG prerequisites only |

No dedicated CBR MCP exists. All CBR operations via hcloud CLI.

## Approval gates

- Vault creation
- Resource association
- Policy creation
- Backup execution
- Restore execution
- Cross-region copy
- Any deletion

## Outputs

- artifacts/cbr-intent.json
- artifacts/cbr-source-discovery.json
- artifacts/cbr-vault-plan.md
- artifacts/cbr-vault-result.json
- artifacts/cbr-backup-result.json
- artifacts/cbr-backup-validation-report.md
- artifacts/cbr-restore-plan.md
- artifacts/cbr-restore-result.json
- artifacts/cbr-restore-validation-report.md
- artifacts/cbr-final-report.md

## Known limitations

- No dedicated CBR MCP (all via hcloud CLI)
- Resource type availability varies by region
- CCE backup protects disks, not Kubernetes state
- Agent required for application-consistent ECS backup
- hcloud 7.2.12 compatibility not yet verified

## Troubleshooting

See [docs/known-issues.md](references/known-issues.md) for detailed troubleshooting.

| Symptom | Action |
|---|---|
| Vault creation fails | Check quota, capacity, billing mode |
| Backup stuck in protecting | Poll with timeout, check resource state |
| Restore fails | Check backup integrity, target AZ, quota |
| Association fails | Check vault type, resource type, region |

## Maturity status

**READY_WITH_WARNINGS**

CBR commands available and verified locally via hcloud CLI 6.2.9. No dedicated MCP. Write operations require approval. No cloud-side tests executed.

## Evidence

| Evidence | Type |
|---|---|
| CBR 68 operations available in hcloud 6.2.9 | VERIFIED_FROM_LOCAL_HELP |
| Key operations verified (ListVault, CreateVault, CreateCheckpoint, RestoreBackup, etc.) | VERIFIED_FROM_LOCAL_HELP |
| No dedicated CBR MCP exists | VERIFIED_FROM_LOCAL_HELP |
| CBR not in huaweicloud-deploy supported services | VERIFIED_FROM_CODE |
