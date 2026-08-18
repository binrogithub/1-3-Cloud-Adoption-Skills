# PostgreSQL ECS to RDS DRS

## Purpose

Migrate a self-managed PostgreSQL database running on Huawei Cloud ECS to Huawei Cloud RDS for PostgreSQL using DRS (Data Replication Service) with Full + Incremental synchronization, where source and target are in different regions. Connectivity uses public EIP with /32 CIDR restrictions. VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO.

## Scenario at a Glance

| Attribute | Value |
|---|---|
| Domain | Migration / Database-Migration |
| Source | Self-managed PostgreSQL on ECS (any region) |
| Target | RDS for PostgreSQL (different region) |
| Primary service | DRS (Data Replication Service) |
| Primary mechanism | DRS Full + Incremental via public EIP |
| Scenario maturity | READY_WITH_WARNINGS |
| Highest risk | HIGH |
| Skills | 1 |

## Architecture

```
PostgreSQL on ECS (Source Region)
        │
        │ Public EIP
        │ TCP 5432 (/32 CIDR only)
        ▼
       DRS
        │  Full + Incremental
        ▼
RDS for PostgreSQL (Target Region)
```

Network: Public Internet via EIP. VPN is NOT_REQUIRED and OUT_OF_SCOPE_FOR_THIS_SCENARIO. PostgreSQL port (5432) restricted to DRS replication instance EIP with /32 CIDR.

## When to Use This Scenario

- Migrating self-managed PostgreSQL from ECS to managed RDS for PostgreSQL
- Cross-region database migration requiring minimal downtime
- Database consolidation from self-managed to managed service
- When Full + Incremental replication is needed for near-zero-downtime cutover

## When NOT to Use This Scenario

- Same-region migration where VPN or VPC peering is available (prefer private network)
- Non-PostgreSQL databases (use appropriate DRS task type)
- When zero downtime is required and incremental lag is unacceptable
- When source PostgreSQL version is incompatible with target RDS version
- When VPN connectivity is required (OUT_OF_SCOPE_FOR_THIS_SCENARIO — use a different skill)

## Skills Included

| Order | Skill | Required | Purpose | Mechanism | Status | Risk |
|---:|---|---|---|---|---|---|
| 1 | [huawei-postgresql-ecs-to-rds-drs-cross-region](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md) | Yes | Full migration orchestration | DRS Full + Incremental | READY_WITH_WARNINGS | HIGH |

## Shared Capabilities

| Component | Type | Required / Optional | Purpose |
|---|---|---|---|
| [huaweicloud-drs](../shared/mcps/huaweicloud-drs/) | MCP | Required | All DRS operations (create, start, monitor, validate) |
| [huaweicloud-pricing](../shared/mcps/huaweicloud-pricing/) | MCP | Optional | Cost estimation of target RDS (DRS pricing currently BLOCKED) |
| [huaweicloud-ticket](../shared/mcps/huaweicloud-ticket/) | MCP | Optional | Support ticket creation |

A pricing limitation must not prevent the migration workflow. DRS pricing BLOCKED is NON-CORE.

## Prerequisites

- Source ECS with PostgreSQL running and accessible
- Source PostgreSQL configured: `wal_level=logical`, `max_replication_slots >= 1`, `max_wal_senders >= 1`
- Source replication user with REPLICATION privilege
- Source security group ID available for access plan
- Target RDS for PostgreSQL instance ACTIVE in different region
- Target database exists on RDS
- huaweicloud-drs MCP available
- DRS EIP connectivity path validated
- pg_hba.conf allows DRS replication user
- Approval owner designated for write operations

See [huawei-postgresql-ecs-to-rds-drs-cross-region prerequisites](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md) for the complete list.

## Execution Sequence

### Phase 1 — Parse Intent

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: Source ECS, target RDS, regions, database names, DRS task name, approval owner
- **Output**: Complete intent object (`artifacts/pg-drs-intent.json`)
- **Approval**: None
- **Verification**: All required fields present
- **Next**: Phase 2

### Phase 2 — Discovery

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: Intent object
- **Output**: DRS console context, existing tasks, source/target details
- **Approval**: None (read-only via DRS MCP)
- **Verification**: Source and target regions are different; no duplicate tasks
- **Next**: Phase 3

### Phase 3 — Readiness

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: Discovery results
- **Output**: Source access plan, connection test result, pre-check result
- **Approval**: Review source access plan (SG rules, pg_hba.conf) before application
- **Verification**: Connection test PASS, pre-check PASS
- **Next**: Phase 4

### Phase 4 — Execution

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: Approved migration plan
- **Output**: DRS task created and started, full sync in progress
- **Approval**: EXPLICIT — DRS task creation, DRS task start
- **Verification**: DRS task status shows full synchronization progressing
- **Next**: Phase 5

### Phase 5 — Validation

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: DRS task status
- **Output**: Validation report (DDL comparison, row counts, DRS report)
- **Approval**: None
- **Verification**: Full sync completed, DDL matches, row counts match
- **Next**: Phase 6

### Phase 6 — Cutover

- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Input**: Incremental lag status
- **Output**: Application connections redirected to target RDS
- **Approval**: EXPLICIT — cutover decision
- **Verification**: Application functional on target RDS, data consistent
- **Next**: Completion or Rollback

## AI Execution Instructions

1. Read this README first.
2. Do not load every skill unnecessarily.
3. Resolve the current phase.
4. Load only the required [SKILL.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md).
5. Follow PARSE INTENT.
6. Run discovery before any write.
7. Verify MCP availability (huaweicloud-drs required).
8. Obtain explicit approval for DRS create, DRS start, and cutover.
9. Execute one controlled phase.
10. Verify.
11. Return to scenario README.
12. Determine next phase.
13. Stop on ambiguity.
14. Use capability builder only for a real gap.

## Human Execution Instructions

1. Read this scenario README
2. Review architecture diagram
3. Read [SKILL.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md)
4. Review [prerequisites](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/prerequisites.md)
5. Review [architecture](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/architecture.md)
6. Verify source PostgreSQL configuration (wal_level, replication slots)
7. Apply source access changes (SG rules, pg_hba.conf) manually
8. Review and approve DRS task creation and start
9. Monitor migration progress
10. Validate data (DDL, row counts)
11. Approve and execute cutover
12. Review [rollback procedure](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/rollback.md)

## Approval Gates

| Gate | Operation | Risk | Approval required | Skill |
|---|---|---|---|---|
| G1 | Source access plan (SG + pg_hba.conf) | Medium | Review before apply | huawei-postgresql-ecs-to-rds-drs-cross-region |
| G2 | DRS task creation | High | EXPLICIT (explicit_approval=true) | huawei-postgresql-ecs-to-rds-drs-cross-region |
| G3 | DRS task start | High | EXPLICIT (explicit_approval=true) | huawei-postgresql-ecs-to-rds-drs-cross-region |
| G4 | Cutover | High | EXPLICIT | huawei-postgresql-ecs-to-rds-drs-cross-region |
| G5 | Rollback / cleanup | Medium | EXPLICIT | huawei-postgresql-ecs-to-rds-drs-cross-region |

## Validation Criteria

- DRS connection test: PASS
- DRS pre-check: PASS (no BLOCKING items)
- Full synchronization: completed
- DDL structure: source matches target
- Row counts: source matches target
- Incremental replication: active and lag acceptable

## Completion Criteria

- DRS precheck passed
- Full migration completed
- Incremental replication validated
- Source/target data checks passed
- Application cutover approved
- Rollback decision recorded

## Rollback / Recovery

1. **During task creation**: No data impact. Review parameters and retry.
2. **During full sync**: Target may have partial data. Stop task, clean target, retry.
3. **During incremental sync**: Source and target may diverge. Assess lag, may need restart.
4. **During cutover**: Revert application connections to source. Source is still operational.
5. **Post-cutover**: Assess data integrity. May need reverse sync or manual repair.

DRS task stop/termination requires manual console operation (no MCP tool exists).

See [rollback procedure](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/rollback.md) for details.

## Capability Gaps

| Gap | Impact | Core blocker | Current treatment | Future option |
|---|---|---|---|---|
| GAP-PG-001: No PG config validation MCP | wal_level, replication slots checked manually | No | Manual SSH | Extend DRS MCP |
| GAP-PG-002: No extension compatibility MCP | Extensions checked manually | No | Manual check | Extend DRS MCP |
| GAP-PG-003: No DRS task stop MCP | Task stop requires console | No | Manual console | Extend DRS MCP |
| GAP-PG-004: VPN OUT_OF_SCOPE | VPN not supported by this scenario | No | Use EIP architecture | Separate VPN skill |
| GAP-PG-005: No app connection update MCP | Connection string update is manual | No | Manual update | Application MCP |
| GAP-PG-006: No DDL comparison MCP | DDL validation is manual | No | Manual SQL comparison | Extend DRS MCP |
| GAP-PG-007: No row count validation MCP | Row count validation is manual | No | Manual SQL queries | Extend DRS MCP |

For gap resolution, see [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md).

## Known Limitations

- VPN connectivity is OUT_OF_SCOPE_FOR_THIS_SCENARIO (public EIP with /32 CIDR is the supported architecture)
- Source PostgreSQL configuration validation requires manual SSH access
- Extension compatibility must be checked manually
- DRS task stop/termination requires manual console operation
- Application connection string update is manual
- DDL comparison is manual
- Row count validation is manual
- DRS pricing is BLOCKED in huaweicloud-pricing MCP
- Public Internet exposure of PostgreSQL port is a security risk (mitigated by /32 CIDR)

## Maturity

READY_WITH_WARNINGS. 10 of 13 DRS MCP tools are available and functional. 3 write tools require explicit_approval=true. Safety guards implemented (CIDR /32, region guard, pre-check guard, duplicate guard). 58 tests pass. VPN NOT_REQUIRED. DRS pricing BLOCKED is non-core. Source PostgreSQL config validation requires manual SSH. DRS task stop requires manual console.

## Evidence and Traceability

- DRS task ID and configuration preserved
- Connection test and pre-check results preserved
- Task status progression logged with timestamps
- Validation results (DDL, row counts) preserved
- Approval decisions recorded with approver identity
- DRS report generated with non-sensitive data only

## AI Reading Order

1. `README.md` (this file)
2. [huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md)
3. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/prerequisites.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/prerequisites.md)
4. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/architecture.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/architecture.md)
5. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/workflows/discovery.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/workflows/discovery.md)
6. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/workflows/execution.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/workflows/execution.md)
7. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/validation.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/validation.md)
8. [huawei-postgresql-ecs-to-rds-drs-cross-region/references/rollback.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/rollback.md)

## Human Reading Order

1. This scenario README
2. Architecture diagram above
3. Prerequisites section
4. [SKILL.md](./huawei-postgresql-ecs-to-rds-drs-cross-region/SKILL.md)
5. [Execution runbook](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/execution-runbook.md)
6. [Validation](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/validation.md)
7. [Rollback](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/rollback.md)
8. [Known issues](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/known-issues.md)

## Related References

- [DRS MCP use case: PostgreSQL ECS to RDS cross-region](../shared/mcps/huaweicloud-drs/use-cases/postgresql-ecs-to-rds-cross-region/README.md)
- [DRS Internet runbook](../shared/mcps/huaweicloud-drs/use-cases/postgresql-ecs-to-rds-cross-region/drs-internet-runbook.md)
- [Capability gap policy](./huawei-postgresql-ecs-to-rds-drs-cross-region/references/capability-gap-policy.md)
