# SDRS Cross-Region DR

## Purpose

Establish and operate cross-region disaster recovery using Huawei Cloud SDRS (Storage Disaster Recovery Service). This scenario orchestrates three sequential skills: protection setup, DR drill, and failover/failback. All SDRS operations are performed via manual console — no SDRS CLI or MCP exists.

## Scenario at a Glance

| Attribute | Value |
|---|---|
| Domain | Cloud-Foundation / DR-and-Backup |
| Source | ECS instances with EVS disks in production region |
| Target | Replicated ECS instances with EVS disks in DR region |
| Primary service | SDRS (Storage Disaster Recovery Service) |
| Primary mechanism | Supervised manual console |
| Scenario maturity | EXPERIMENTAL |
| Highest risk | CRITICAL |
| Skills | 3 |

## Architecture

```
Primary Site (Production Region)
       │
       │ SDRS protection / replication
       │ (async for cross-region)
       ▼
SDRS Protection Group
       │
       │ Protected instances + replication pairs
       ▼
DR Site (DR Region)
       │
       ├── DR Drill (isolated, no production impact)
       │
       └── Failover (CRITICAL — production traffic shift)
               │
               ▼
        Reverse Reprotection
               │
               ▼
            Failback
```

## When to Use This Scenario

- Setting up cross-region disaster recovery for ECS instances
- Testing DR readiness through a non-production drill
- Executing planned or unplanned failover to DR site
- Returning production to original site after failover

## When NOT to Use This Scenario

- Backup-only DR without live replication (use CBR CopyBackup instead)
- Database-level replication (use DRS or database native tools)
- Object storage replication (use OBS cross-region replication)
- When automated SDRS execution is required (no CLI or MCP support exists)
- When the region pair is not supported by SDRS
- When BRS orchestration is required (separate service)

## Skills Included

| Order | Skill | Required | Purpose | Mechanism | Status | Risk |
|---:|---|---|---|---|---|---|
| 1 | [huawei-sdrs-protection-setup](./huawei-sdrs-protection-setup/SKILL.md) | Yes | Establish SDRS protection and replication | Manual console + hcloud discovery | EXPERIMENTAL | HIGH |
| 2 | [huawei-sdrs-dr-drill](./huawei-sdrs-dr-drill/SKILL.md) | Conditional | Test DR readiness without production impact | Manual console | EXPERIMENTAL | HIGH |
| 3 | [huawei-sdrs-failover-failback](./huawei-sdrs-failover-failback/SKILL.md) | Conditional | Production failover, reverse reprotection, failback | Manual console | EXPERIMENTAL | CRITICAL |

DR drill and failover/failback are CONDITIONAL depending on the user's scenario objective. Do not force all three on every SDRS request.

## Shared Capabilities

| Component | Type | Required / Optional | Purpose |
|---|---|---|---|
| [huaweicloud-pricing](../shared/mcps/huaweicloud-pricing/) | MCP | Optional | Cost estimation of DR infrastructure |
| [huaweicloud-ticket](../shared/mcps/huaweicloud-ticket/) | MCP | Optional | Support ticket creation |
| [huaweicloud-deploy](../shared/mcps/huaweicloud-deploy/) | MCP | Optional | VPC/subnet/SG prerequisites only (NOT for SDRS) |
| [Playwright](../shared/integrations/playwright/) | Integration | Optional | Console exploration (read-only only) |
| [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md) | Shared Skill | Required | Future SDRS MCP design |

## Prerequisites

- hcloud CLI 6.2.9+ installed and authenticated
- SDRS service available in both production and DR regions
- Region pair supported by SDRS
- Production ECS instances and EVS disks discovered
- DR site VPC, subnet, and security group configured
- Sufficient compute capacity at DR site for all protected servers
- DR gateway requirements validated (required for cross-region)
- RPO and RTO targets defined
- Approval owner designated for all operations
- Maintenance window defined

See individual skill prerequisites for complete lists:
- [Protection setup prerequisites](./huawei-sdrs-protection-setup/SKILL.md)
- [DR drill prerequisites](./huawei-sdrs-dr-drill/SKILL.md)
- [Failover/failback prerequisites](./huawei-sdrs-failover-failback/SKILL.md)

## Execution Sequence

### Phase 1 — Parse Intent

- **Skill**: huawei-sdrs-protection-setup
- **Input**: Scenario type, regions, AZs, ECS names, disk scope, RPO, RTO, approval owner
- **Output**: Complete intent object (`artifacts/sdrs-intent.json`)
- **Approval**: None
- **Verification**: All required fields present
- **Next**: Phase 2

### Phase 2 — Discovery

- **Skill**: huawei-sdrs-protection-setup
- **Input**: Intent object
- **Output**: SDRS capability assessment, production inventory, DR site inventory, dependency map
- **Approval**: None (read-only via hcloud CLI + console)
- **Verification**: SDRS available in both regions, region pair supported, resources discovered
- **Next**: Phase 3

### Phase 3 — Readiness

- **Skill**: huawei-sdrs-protection-setup
- **Input**: Discovery results
- **Output**: RPO/RTO plan, architecture plan, readiness report
- **Approval**: None (plan only)
- **Verification**: READY or READY_WITH_WARNINGS
- **Next**: Phase 4

### Phase 4 — Execution (Protection Setup)

- **Skill**: huawei-sdrs-protection-setup
- **Input**: Approved architecture plan
- **Output**: DR gateway configured, protection group created, protected instances created, replication pairs active
- **Approval**: EXPLICIT — gateway installation, protection group creation, protected instance creation, enable protection
- **Verification**: Replication status active, lag within threshold
- **Next**: Phase 5 (drill) or Phase 6 (failover) or Completion

### Phase 5 — DR Drill (CONDITIONAL)

- **Skill**: huawei-sdrs-dr-drill
- **Input**: Protection group ID, drill scope, validation plan
- **Output**: Drill execution, validation results, RPO/RTO measurements, cleanup
- **Approval**: EXPLICIT — drill execution
- **Verification**: DR site servers boot, applications functional, DNS isolation maintained
- **Next**: Completion (drill objective met) or Phase 6 (if failover intended)

**DR DRILL IS NOT PRODUCTION FAILOVER.** A drill creates temporary resources and does not modify production DNS or routing.

### Phase 6 — Failover (CONDITIONAL — CRITICAL)

- **Skill**: huawei-sdrs-failover-failback
- **Input**: Protection group ID, failover type (planned/unplanned), impact plan
- **Output**: Failover executed, DR site serving production, RPO/RTO measured
- **Approval**: MANDATORY EXPLICIT — failover is a CRITICAL operation
- **Verification**: DR site functional, split brain prevented, DNS updated manually
- **Next**: Phase 7 (reverse reprotection) or remain at DR site

### Phase 7 — Reverse Reprotection (after failover)

- **Skill**: huawei-sdrs-failover-failback
- **Input**: Failover result
- **Output**: Reverse replication active (DR site to production site)
- **Approval**: EXPLICIT
- **Verification**: Reverse replication active, lag within threshold
- **Next**: Phase 8 (failback) or remain at DR site

**REVERSE REPROTECTION IS NOT FAILBACK.** It only re-establishes replication direction. Failback is a separate operation.

### Phase 8 — Failback (CONDITIONAL — CRITICAL)

- **Skill**: huawei-sdrs-failover-failback
- **Input**: Failback plan, reverse replication status
- **Output**: Production returned to original site, replication re-established
- **Approval**: MANDATORY EXPLICIT (separate from failover approval) — CRITICAL operation
- **Verification**: Original site functional, DNS restored, replication active
- **Next**: Completion

## Skill Transitions

### Transition 1: Protection Setup → DR Drill

Allowed only when:
- Protection configured and active
- Replication healthy (all pairs replicating)
- Readiness passed
- Drill prerequisites satisfied (DNS isolation plan, cleanup plan)

### Transition 2: Protection Setup → Failover

Allowed only for:
- Real DR condition (primary site unavailable or irrecoverable), OR
- Approved planned failover

Must NOT require DR drill completion as a technical hard requirement. However, prior DR drill is recommended as operational best practice.

### Transition 3: DR Drill → Failover

A successful drill increases confidence but does not automatically authorize failover. Failover always requires its own explicit approval.

## AI Execution Instructions

1. Read this README first.
2. Do not load every skill unnecessarily.
3. Resolve the current phase and user objective (protection only? drill? failover?).
4. Load only the required SKILL.md for the current phase.
5. Follow PARSE INTENT.
6. Run discovery before any write.
7. Verify CLI availability (hcloud for discovery; SDRS is manual console).
8. Obtain explicit approval for each write operation.
9. Execute one controlled phase.
10. Verify.
11. Return to scenario README.
12. Determine next phase based on user objective.
13. Stop on ambiguity.
14. Never proceed to failover without MANDATORY EXPLICIT approval.
15. Use capability builder only for a real gap.

## Human Execution Instructions

1. Read this scenario README
2. Review architecture diagram and skill transitions
3. Read [protection setup SKILL.md](./huawei-sdrs-protection-setup/SKILL.md)
4. Review [architecture](./references/architecture.md) and [prerequisites](./references/prerequisites.md)
5. Execute protection setup (manual console)
6. Monitor replication status
7. If drill: read [drill SKILL.md](./huawei-sdrs-dr-drill/SKILL.md), execute drill
8. If failover: read [failover/failback SKILL.md](./huawei-sdrs-failover-failback/SKILL.md), obtain CRITICAL approval, execute failover
9. If failback: validate reverse reprotection, obtain separate approval, execute failback
10. Review [validation](./references/validation.md) and [known issues](./references/known-issues.md)

## Approval Gates

| Gate | Operation | Risk | Approval required | Skill |
|---|---|---|---|---|
| G1 | Protection group creation | High | EXPLICIT | huawei-sdrs-protection-setup |
| G2 | Protected instance creation | High | EXPLICIT | huawei-sdrs-protection-setup |
| G3 | Enable protection | High | EXPLICIT | huawei-sdrs-protection-setup |
| G4 | DR gateway installation | High | EXPLICIT | huawei-sdrs-protection-setup |
| G5 | DR drill execution | High | EXPLICIT | huawei-sdrs-dr-drill |
| G6 | Planned failover | CRITICAL | MANDATORY EXPLICIT | huawei-sdrs-failover-failback |
| G7 | Unplanned failover | CRITICAL | MANDATORY EXPLICIT | huawei-sdrs-failover-failback |
| G8 | Reverse reprotection | High | EXPLICIT | huawei-sdrs-failover-failback |
| G9 | Failback | CRITICAL | MANDATORY EXPLICIT (separate) | huawei-sdrs-failover-failback |
| G10 | DNS changes | High | EXPLICIT + manual execution | huawei-sdrs-failover-failback |

## Validation Criteria

**Protection setup:**
- Protection group created and active
- All protected instances created
- All replication pairs active
- Replication lag within threshold

**DR drill:**
- DR site servers boot successfully
- Application functional at DR site
- DNS isolation maintained (no production impact)
- RPO and RTO measured

**Failover:**
- DR site serving production
- Split brain prevented
- RPO and RTO measured
- DNS updated to DR site

**Failback:**
- Original site serving production
- Replication re-established in original direction
- DNS restored to original site

## Completion Criteria

Completion depends on the requested objective:

**Protection only:**
- Protection group active, all instances protected, replication healthy

**Drill:**
- Protection criteria met + drill executed, validated, and cleaned up

**Failover:**
- Protection criteria met + failover executed, DR site validated, DNS updated

**Failback:**
- Failover criteria met + failback executed, original site validated, DNS restored, replication active

A scenario may end after a DR drill when the user's objective was only a drill.

## Rollback / Recovery

**Protection setup failure:**
- Gateway: Clean up gateway resources manually. Verify network. Retry.
- Protection config: Verify status of each resource. Clean up partial protection manually. Retry.
- Replication: Monitor lag. If broken, assess data consistency and re-enable protection.

**Drill failure:**
- Clean up drill resources manually. Verify production is unaffected.

**Failover failure:**
- Both sites may be in uncertain state. DO NOT modify either automatically. Assess state manually.

**Reverse reprotection failure:**
- DR site is unprotected. This is critical. Establish reverse reprotection ASAP.

**Failback failure:**
- Remain at DR site. Verify DR site is functional. Re-attempt after resolving failure cause.

See [protection rollback](./huawei-sdrs-protection-setup/references/rollback.md) and [failover rollback](./huawei-sdrs-failover-failback/references/rollback.md).

## Capability Gaps

| Gap | Impact | Core blocker | Current treatment | Future option |
|---|---|---|---|---|
| GAP-SDR-001: No SDRS CLI | All operations manual console | Yes | Manual console | SDRS CLI in hcloud |
| GAP-SDR-002: No SDRS MCP | No automation possible | Yes | Manual console | SDRS MCP |
| GAP-SDR-003: No failover automation | Critical ops have no safeguard | Yes | Manual runbook | SDRS MCP |
| GAP-SDR-005: SDRS not in deploy MCP | Cannot generate SDRS Terraform | No | Manual console | Extend deploy MCP |
| GAP-SDR-006: Region pair manual check | Must verify per deployment | No | Manual verification | Region capability API |
| GAP-SDR-007: Gateway manual install | Gateway setup is manual | No | Manual procedure | Gateway automation |

For gap resolution, see [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md).

## Known Limitations

- No SDRS CLI support in hcloud 6.2.9
- No SDRS MCP exists
- All SDRS operations are MANUAL via console
- Failover is a critical operation with no automation safeguard
- Cross-region requires async replication only
- DR gateway is required for cross-region
- DR site network must be manually configured
- DNS cutover is manual (never automatic)
- No resource deletion is automatic
- SDRS is NOT supported by huaweicloud-deploy MCP

## Maturity

EXPERIMENTAL. SDRS is NOT available in hcloud CLI. No SDRS MCP exists. All operations must be performed manually via console. No cloud-side tests were executed. Region pair support is region-dependent. The workflow provides value as a controlled runbook for manual execution. Capability builder integration enables future MCP design.

## Evidence and Traceability

- All hcloud CLI discovery commands logged with timestamps
- All manual console actions documented with timestamps and results
- Protection group, instance, and replication pair identifiers recorded (sanitized)
- Approval decisions recorded with approver identity and timestamp
- RPO and RTO measurements recorded
- No secrets in any artifact

## AI Reading Order

1. `README.md` (this file)
2. [huawei-sdrs-protection-setup/SKILL.md](./huawei-sdrs-protection-setup/SKILL.md)
3. [huawei-sdrs-protection-setup/references/execution-runbook.md](./huawei-sdrs-protection-setup/references/execution-runbook.md)
4. [huawei-sdrs-dr-drill/SKILL.md](./huawei-sdrs-dr-drill/SKILL.md)
5. [huawei-sdrs-dr-drill/references/drill-validation.md](./huawei-sdrs-dr-drill/references/drill-validation.md)
6. [huawei-sdrs-failover-failback/SKILL.md](./huawei-sdrs-failover-failback/SKILL.md)
7. [huawei-sdrs-failover-failback/references/rollback.md](./huawei-sdrs-failover-failback/references/rollback.md)
8. [references/validation.md](./references/validation.md)
9. [references/known-issues.md](./references/known-issues.md)

## Human Reading Order

1. This scenario README
2. Architecture diagram and skill transitions
3. Prerequisites section
4. [Protection setup SKILL.md](./huawei-sdrs-protection-setup/SKILL.md)
5. [Protection execution runbook](./huawei-sdrs-protection-setup/references/execution-runbook.md)
6. [DR drill SKILL.md](./huawei-sdrs-dr-drill/SKILL.md) (if drill intended)
7. [Failover/failback SKILL.md](./huawei-sdrs-failover-failback/SKILL.md) (if failover intended)
8. [Validation](./references/validation.md)
9. [Known issues](./references/known-issues.md)
10. [Lessons learned](./references/lessons-learned.md)

## Related References

- [SDRS MCP capability request](./references/sdrs-mcp-capability-request.md)
- [Capability gap policy](./references/capability-gap-policy.md)
- [Architecture](./references/architecture.md)
