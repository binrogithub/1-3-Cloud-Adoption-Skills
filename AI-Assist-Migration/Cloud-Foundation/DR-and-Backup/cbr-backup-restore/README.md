# CBR Backup Restore

## Purpose

Discover, configure, execute, validate, and restore Huawei Cloud CBR (Cloud Backup and Recovery) backups for supported ECS, EVS, and CCE node scenarios using hcloud CLI as the primary mechanism. No dedicated CBR MCP exists.

## Scenario at a Glance

| Attribute | Value |
|---|---|
| Domain | Cloud-Foundation / DR-and-Backup |
| Source | ECS instance, EVS volume, or CCE node resource |
| Target | Restored resource (new resource by default) |
| Primary service | CBR (Cloud Backup and Recovery) |
| Primary mechanism | hcloud CBR CLI |
| Scenario maturity | READY_WITH_WARNINGS |
| Highest risk | HIGH |
| Skills | 1 |

## Architecture

```
Protected Resource (ECS / EVS / CCE)
        │
        │ CBR agent or snapshot
        ▼
    CBR Vault
        │
        ▼
  Backup / Checkpoint
        │
        ├──────────────┐
        │              │
        ▼              ▼
  Retention      Cross-region copy
  (policy)       (when supported)
                       │
                       ▼
                Replicated Backup
        │
        ▼
  Restore Plan
        │
        ▼
  Restored Resource (new)
```

## When to Use This Scenario

- Creating ad-hoc or scheduled backups of ECS instances, EVS volumes, or CCE node disks
- Restoring an ECS instance or EVS volume from a CBR backup to a new resource
- Setting up a CBR vault and policy for ongoing protection
- Copying a backup cross-region for DR purposes
- Validating backup integrity and restore readiness

## When NOT to Use This Scenario

- Live synchronous replication (use SDRS service instead)
- Database-level backup/restore (use database native tools or DRS)
- Kubernetes application state backup (use Velero instead)
- File-level backup of SFS Turbo or workspace
- When no hcloud CLI is available and cannot be installed

## Skills Included

| Order | Skill | Required | Purpose | Mechanism | Status | Risk |
|---:|---|---|---|---|---|---|
| 1 | [huawei-cbr-backup-restore](./huawei-cbr-backup-restore/SKILL.md) | Yes | Full backup/restore orchestration | hcloud CBR CLI | READY_WITH_WARNINGS | HIGH |

## Shared Capabilities

| Component | Type | Required / Optional | Purpose |
|---|---|---|---|
| [huaweicloud-pricing](../shared/mcps/huaweicloud-pricing/) | MCP | Optional | Cost estimation of vault and backup storage |
| [huaweicloud-ticket](../shared/mcps/huaweicloud-ticket/) | MCP | Optional | Support ticket creation |
| [huaweicloud-deploy](../shared/mcps/huaweicloud-deploy/) | MCP | Optional | VPC/subnet/SG prerequisites only (NOT for CBR) |

## Prerequisites

- hcloud CLI 6.2.9+ installed and authenticated
- CBR service available in target region
- Source ECS, EVS, or CCE resource exists and is compatible with backup
- Vault quota sufficient for backups
- IAM permissions for CBR read/write and ECS/EVS read
- Approval owner designated for write operations

See [huawei-cbr-backup-restore prerequisites](./huawei-cbr-backup-restore/SKILL.md) for the complete list.

## Execution Sequence

### Phase 1 — Parse Intent

- **Skill**: huawei-cbr-backup-restore
- **Input**: Resource type, region, resource name, backup type, schedule, retention, approval owner
- **Output**: Complete intent object (`artifacts/cbr-intent.json`)
- **Approval**: None
- **Verification**: All required fields present
- **Next**: Phase 2

### Phase 2 — Discovery

- **Skill**: huawei-cbr-backup-restore
- **Input**: Intent object
- **Output**: Auth validation, source resource discovery, existing vaults/policies/backups inventory
- **Approval**: None (read-only)
- **Verification**: Source resource found, region accessible, CBR available
- **Next**: Phase 3

### Phase 3 — Readiness

- **Skill**: huawei-cbr-backup-restore
- **Input**: Discovery results
- **Output**: Vault plan, policy plan, capacity check
- **Approval**: None (plan only)
- **Verification**: Vault capacity sufficient, resource state compatible
- **Next**: Phase 4

### Phase 4 — Execution

- **Skill**: huawei-cbr-backup-restore
- **Input**: Approved plan
- **Output**: Vault created/reused, resource associated, policy configured, backup executed
- **Approval**: EXPLICIT — vault creation, resource association, policy creation, backup execution
- **Verification**: Backup status available, vault shows resource
- **Next**: Phase 5

### Phase 5 — Validation

- **Skill**: huawei-cbr-backup-restore
- **Input**: Backup ID
- **Output**: Backup validation report (status, metadata, consistency)
- **Approval**: None
- **Verification**: Backup status available, protected resource matches, size recorded
- **Next**: Phase 6 (if restore requested) or Completion

### Phase 6 — Restore

- **Skill**: huawei-cbr-backup-restore
- **Input**: Backup ID, restore plan
- **Output**: Restored resource (new), restore validation report
- **Approval**: EXPLICIT — restore execution, impact plan review
- **Verification**: Restored resource functional, matches expectations
- **Next**: Completion

## AI Execution Instructions

1. Read this README first.
2. Do not load every skill unnecessarily.
3. Resolve the current phase.
4. Load only the required [SKILL.md](./huawei-cbr-backup-restore/SKILL.md).
5. Follow PARSE INTENT.
6. Run discovery before any write.
7. Verify CLI availability (hcloud CBR required).
8. Obtain explicit approval for vault, association, backup, and restore.
9. Execute one controlled phase.
10. Verify.
11. Return to scenario README.
12. Determine next phase.
13. Stop on ambiguity.
14. Use capability builder only for a real gap.

## Human Execution Instructions

1. Read this scenario README
2. Review architecture diagram
3. Read [SKILL.md](./huawei-cbr-backup-restore/SKILL.md)
4. Review [prerequisites](./huawei-cbr-backup-restore/references/prerequisites.md)
5. Review [execution runbook](./huawei-cbr-backup-restore/references/execution-runbook.md)
6. Execute discovery (hcloud CLI)
7. Review and approve vault creation, resource association, backup
8. Monitor backup progress
9. Validate backup
10. If restoring: review and approve restore plan, execute restore, validate restored resource
11. Review [rollback procedure](./huawei-cbr-backup-restore/references/rollback.md)

## Approval Gates

| Gate | Operation | Risk | Approval required | Skill |
|---|---|---|---|---|
| G1 | Vault creation | Medium | EXPLICIT (incurs cost) | huawei-cbr-backup-restore |
| G2 | Resource association | Medium | EXPLICIT (starts backup costs) | huawei-cbr-backup-restore |
| G3 | Policy creation | Low | EXPLICIT (schedules backups) | huawei-cbr-backup-restore |
| G4 | Backup execution | Medium | EXPLICIT | huawei-cbr-backup-restore |
| G5 | Restore execution | High | EXPLICIT + impact plan | huawei-cbr-backup-restore |
| G6 | Cross-region copy | Medium | EXPLICIT (egress costs) | huawei-cbr-backup-restore |
| G7 | Any deletion | High | EXPLICIT | huawei-cbr-backup-restore |

## Validation Criteria

**Backup-only intent:**
- Backup status: available
- Protected resource matches source
- Vault shows resource associated
- Size and metadata recorded

**Backup + restore intent:**
- All backup criteria above
- Restored resource exists and is functional
- Restored resource matches expectations (size, state, AZ)
- Application validation on restored resource (if applicable)

## Completion Criteria

**Backup-only intent:**
- Vault created or reused
- Resource associated
- Backup executed and validated
- Retention policy configured (if scheduled)

**Backup + restore intent:**
- All backup-only criteria
- Restore plan approved
- Restore executed successfully
- Restored resource validated

## Rollback / Recovery

1. **Vault creation failure**: No data loss. Review error. Retry with corrected parameters.
2. **Association failure**: Resource is unprotected. Verify vault/resource compatibility. Retry.
3. **Backup failure**: No data loss. Check vault capacity and resource state. Retry.
4. **Restore failure**: Original resource is intact. New resource may be partially created. Assess and clean up manually.
5. **Validation failure**: Original and/or restored resources exist. Do not delete either automatically.

See [rollback procedure](./huawei-cbr-backup-restore/references/rollback.md) for details.

## Capability Gaps

| Gap | Impact | Core blocker | Current treatment | Future option |
|---|---|---|---|---|
| GAP-CBR-001: No dedicated CBR MCP | All operations via hcloud CLI | No | hcloud CLI | CBR MCP |
| GAP-CBR-002: CBR not in deploy MCP | Cannot generate CBR Terraform | No | hcloud CLI | Extend deploy MCP |
| GAP-CBR-003: No structured error handling | CLI errors are unstructured | No | Manual error parsing | CBR MCP |
| GAP-CBR-004: Cross-region copy varies by region | Must validate per execution | No | Per-execution validation | Region capability map |
| GAP-CBR-005: Agent verification is CLI-only | Application-consistent backup needs agent | No | CLI agent check | CBR MCP |

For gap resolution, see [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md).

## Known Limitations

- No dedicated CBR MCP exists; all operations via hcloud CLI
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending
- CBR is NOT supported by huaweicloud-deploy MCP
- Resource type availability varies by region
- Cross-region copy capability varies by region
- CCE node backup protects disks but not Kubernetes logical state
- Restore always creates a new resource; in-place restore requires double confirmation
- hcloud CLI operations lack structured retry logic

## Maturity

READY_WITH_WARNINGS. CBR service available in hcloud CLI v6.2.9 with 68 operations. Key operations verified. No dedicated CBR MCP. All write operations require explicit approval. No cloud-side tests executed. Compatibility verified only with hcloud 6.2.9.

## Evidence and Traceability

- All hcloud CLI commands logged with timestamps
- Vault IDs, backup IDs, and resource IDs recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Validation results preserved in artifacts
- No secrets in any artifact

## AI Reading Order

1. `README.md` (this file)
2. [huawei-cbr-backup-restore/SKILL.md](./huawei-cbr-backup-restore/SKILL.md)
3. [huawei-cbr-backup-restore/references/prerequisites.md](./huawei-cbr-backup-restore/references/prerequisites.md)
4. [huawei-cbr-backup-restore/references/architecture.md](./huawei-cbr-backup-restore/references/architecture.md)
5. [huawei-cbr-backup-restore/references/workflows/discovery.md](./huawei-cbr-backup-restore/references/workflows/discovery.md)
6. [huawei-cbr-backup-restore/references/workflows/execution.md](./huawei-cbr-backup-restore/references/workflows/execution.md)
7. [huawei-cbr-backup-restore/references/validation.md](./huawei-cbr-backup-restore/references/validation.md)
8. [huawei-cbr-backup-restore/references/rollback.md](./huawei-cbr-backup-restore/references/rollback.md)

## Human Reading Order

1. This scenario README
2. Architecture diagram above
3. Prerequisites section
4. [SKILL.md](./huawei-cbr-backup-restore/SKILL.md)
5. [Execution runbook](./huawei-cbr-backup-restore/references/execution-runbook.md)
6. [Validation](./huawei-cbr-backup-restore/references/validation.md)
7. [Rollback](./huawei-cbr-backup-restore/references/rollback.md)
8. [Known issues](./huawei-cbr-backup-restore/references/known-issues.md)

## Related References

- [Capability gap policy](./huawei-cbr-backup-restore/references/capability-gap-policy.md)
- [Lessons learned](./huawei-cbr-backup-restore/references/lessons-learned.md)
