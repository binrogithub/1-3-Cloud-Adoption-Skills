# huawei-postgresql-ecs-to-rds-drs-cross-region

## Summary

Skill to orchestrate migration of self-managed PostgreSQL on ECS to Huawei Cloud RDS for PostgreSQL using DRS Full + Incremental, with source and target in different regions.

## Problem it solves

Migrating PostgreSQL databases from self-managed servers to managed RDS requires coordination of multiple steps: source configuration, DRS task creation, connectivity tests, pre-checks, full + incremental synchronization, validation, and cutover. Without orchestration, the process is prone to configuration errors and difficult to track.

## Supported scenario

- **Source**: Self-managed PostgreSQL on ECS (region A)
- **Target**: RDS for PostgreSQL (region B, different)
- **Mechanism**: DRS Full + Incremental (Real-Time Synchronization)
- **Network**: Public Internet via EIP (supported architecture; VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO)
- **Topology**: Cross-region

## Architecture

```
Source Region A                        Target Region B
┌──────────────────┐                  ┌──────────────────┐
│  ECS + PostgreSQL │◄──SG Rule───────│  DRS Instance    │
│  (self-managed)   │   /32 CIDR      │  (EIP)           │
│  pg_hba.conf      │◄──Replication───│                  │
│  wal_level=logical│                  │                  │
└──────────────────┘                  └────────┬─────────┘
                                               │
                                        Full + Incremental
                                               │
                                      ┌────────▼─────────┐
                                      │  RDS PostgreSQL   │
                                      │  (managed)        │
                                      └──────────────────┘
```

## MCPs used

| MCP | Required | Purpose | Read/Write | Risk |
|---|---|---|---|---|
| huaweicloud-drs | Yes | DRS task management (create, test, precheck, start, monitor) | Read + Write | High (write requires approval) |
| huaweicloud-pricing | No | Estimate target RDS costs | Read-only | None |
| huaweicloud-ticket | No | Create support ticket if issues arise | Read + Write | Medium |

## Capabilities

- Discovery of existing DRS tasks
- Duplicate task detection (EXACT_MATCH, PARTIAL_MATCH)
- Source access plan generation (SG rules, pg_hba.conf)
- Source-target connectivity test
- DRS pre-check
- DRS Full + Incremental task creation
- DRS task start with explicit approval
- Synchronization progress monitoring
- Migration report generation
- Safety guards: CIDR /32, region, pre-check, duplicates

## General flow

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover → 9. Rollback (if needed) → 10. Closure

## Automation level

| Phase | Status | Responsible |
|---|---|---|
| Discovery | AUTOMATED | Agent |
| Architecture Validation | AUTOMATED | Agent |
| Readiness and Prechecks | ASSISTED | Agent + Human |
| Plan Generation | AUTOMATED | Agent |
| Approval | MANUAL | Human |
| Execution | ASSISTED | Agent + Human |
| Validation | ASSISTED | Agent + Human |
| Cutover | MANUAL | Human |
| Rollback | MANUAL | Human |
| Closure and Reporting | AUTOMATED | Agent |

## Prerequisites

- PostgreSQL on ECS with wal_level=logical, max_replication_slots>=1
- Replication user configured on source PostgreSQL
- RDS for PostgreSQL created in target region
- Source Security Group allows PostgreSQL access from DRS EIP
- pg_hba.conf configured for replication user from DRS EIP
- huaweicloud-drs MCP configured and operational
- Playwright installed (required by huaweicloud-drs MCP)

## Inputs

- source_region: Source ECS region (e.g., la-south-2)
- target_region: Target RDS region (e.g., cn-north-4)
- source_endpoint: IP/EIP of source ECS
- source_port: Source PostgreSQL port (default: 5432)
- source_database: Source database name
- source_username: Replication user
- target_rds_id: Target RDS instance ID
- target_database: Target database name
- task_name: DRS task name
- source_security_group_id: Source ECS Security Group ID

## Outputs

- discovery-report.md
- architecture-validation-report.md
- source-access-plan.md
- readiness-report.md
- migration-plan.md
- drs-task-config.json
- execution-log.md
- validation-report.md
- drs-report.md
- rollback-plan.md
- final-report.md

## Installation

```bash
# Install huaweicloud-drs MCP
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs
npm install
npx playwright install chromium

# Verify installation
node server.mjs --help
```

## Configuration

```json
{
  "skills": {
    "huawei-postgresql-ecs-to-rds-drs-cross-region": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-postgresql-ecs-to-rds-drs-cross-region"
    }
  },
  "mcp": {
    "huaweicloud-drs": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs"
    }
  }
}
```

## Usage with OpenCode or Hermes

1. Load the skill: `skill huawei-postgresql-ecs-to-rds-drs-cross-region`
2. Follow the workflow documented in SKILL.md
3. AUTOMATED phases will be executed by the agent
4. ASSISTED phases require human review
5. MANUAL phases require human execution

## Safe example

```
# Phase 1: Discovery
drs_list_tasks({ region: "cn-north-4", source_engine: "postgresql" })

drs_find_matching_tasks({
  region: "cn-north-4",
  task_name: "pg-ecs-to-rds-migration",
  source_engine: "postgresql",
  target_engine: "postgresql",
  source_region: "la-south-2",
  target_region: "cn-north-4"
})

# Phase 3: Readiness
drs_generate_source_access_plan({
  drs_eip: "1.92.124.245",
  source_security_group_id: "sg-xxxxx",
  source_database: "demodb",
  source_user: "drs_replication"
})

drs_run_connection_test({ region: "cn-north-4", task_name: "pg-ecs-to-rds-migration" })

drs_run_precheck({ region: "cn-north-4", task_name: "pg-ecs-to-rds-migration" })

# Phase 6: Execution (requires explicit_approval=true)
drs_create_postgresql_full_incremental_task({
  task_name: "pg-ecs-to-rds-migration",
  target_region: "cn-north-4",
  explicit_approval: true,
  ...
})

drs_start_task({
  region: "cn-north-4",
  task_name: "pg-ecs-to-rds-migration",
  explicit_approval: true
})
```

## Required approvals

- Create DRS task (explicit_approval=true)
- Start DRS task (explicit_approval=true)
- Select existing DRS task (explicit_approval=true)
- Apply source access changes (SG rules, pg_hba.conf)
- Execute cutover (redirect application connections)
- Execute rollback
- Delete post-migration resources

## Validation

- DDL comparison: Source vs target table structure
- Row count validation: Record count per table
- Incremental test: Insert data in source, verify replication to target
- Application smoke tests post-cutover

## Rollback

1. Redirect application connections to source ECS
2. Stop DRS task (manual console)
3. Verify source database is operational
4. Clean target RDS data if necessary
5. Document rollback reason

## Capability gap handling

| Gap ID | Description | Decision |
|---|---|---|
| GAP-PG-001 | No MCP tool for PostgreSQL config validation | MANUAL_STEP |
| GAP-PG-002 | No MCP tool for extension compatibility | MANUAL_STEP |
| GAP-PG-003 | No MCP tool for DRS task stop | MANUAL_STEP |
| GAP-PG-004 | VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO | NOT_REQUIRED |
| GAP-PG-005 | No MCP tool for app connection update | MANUAL_STEP |
| GAP-PG-006 | No MCP tool for DDL comparison | MANUAL_STEP |
| GAP-PG-007 | No MCP tool for row count validation | MANUAL_STEP |

## Testing

- 58 tests in 8 test suites pass [VERIFIED_FROM_TEST]
- Safety guards: CIDR /32, region, pre-check, duplicates [VERIFIED_FROM_TEST]
- Secret redaction verified [VERIFIED_FROM_TEST]
- Connection test and pre-check verified [VERIFIED_FROM_TEST]
- DRS task creation and start require explicit_approval [VERIFIED_FROM_CODE]

## Security

- CIDR /32 enforced for PostgreSQL access (no 0.0.0.0/0)
- Source access plan generated for review before applying
- Secrets redacted in DRS reports
- Public Internet exposure is a risk (mitigated by /32 CIDR)
- VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO (EIP architecture is intentional, security mitigated by /32 CIDR)
- Replication user must have minimum required permissions

## Limitations

- VPN out of scope (EIP architecture is the supported one for this scenario)
- PostgreSQL configuration requires manual SSH
- DRS task stop requires manual console
- DRS pricing BLOCKED on huaweicloud-pricing MCP
- Connection string update is manual
- DDL and row count validation are manual

## Troubleshooting

| Problem | Solution |
|---|---|
| Connection test fails | Verify SG rules, pg_hba.conf, PostgreSQL status, EIP |
| Pre-check fails | Review BLOCKING items, resolve before starting |
| Task creation fails | Verify duplicates, parameters, DRS limits |
| Full sync slow | Verify data size, bandwidth, DRS instance size |
| Incremental lag high | Verify write volume, bandwidth, DRS size |
| Cutover fails | Revert connections to source immediately |

## Maturity status

**READY_WITH_WARNINGS**

Most DRS operations are automated with safety guards. Main limitations: VPN not implemented, PostgreSQL configuration manual, and DRS task stop manual.

## Evidence used

| Evidence | Type |
|---|---|
| 13 DRS MCP tools available | VERIFIED_FROM_CODE |
| 3 write tools require explicit_approval | VERIFIED_FROM_CODE |
| 58 tests pass in 8 test suites | VERIFIED_FROM_TEST |
| Safety guards implemented | VERIFIED_FROM_TEST |
| 18-step runbook documented | VERIFIED_FROM_DOCUMENTATION |
| VPN OUT_OF_SCOPE | VERIFIED_FROM_DESIGN |
| DRS pricing BLOCKED | VERIFIED_FROM_DOCUMENTATION |
| Source config validation requires SSH | INFERRED |
| DRS task stop requires console | NOT_VERIFIED |
