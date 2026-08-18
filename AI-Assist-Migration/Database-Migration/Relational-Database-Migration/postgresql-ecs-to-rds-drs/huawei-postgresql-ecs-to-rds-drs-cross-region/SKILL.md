---
name: huawei-postgresql-ecs-to-rds-drs-cross-region
version: 1.0.0
description: Orchestrate migration of self-managed PostgreSQL on ECS to Huawei Cloud RDS for PostgreSQL using DRS Full + Incremental, cross-region
category: migration
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Migration
  family: Database-Migration
  service: DRS
  risk_level: high
  status: READY_WITH_WARNINGS
---

# Purpose

Orchestrate a complete migration of a self-managed PostgreSQL database running on Huawei Cloud ECS to Huawei Cloud RDS for PostgreSQL, using DRS (Data Replication Service) with Full + Incremental synchronization, where the source and target are in different regions.

# Supported scenario

- Source: Self-managed PostgreSQL on Huawei Cloud ECS (any region)
- Target: Huawei Cloud RDS for PostgreSQL (different region)
- Mechanism: DRS Full + Incremental (Real-Time Synchronization)
- Network: Public Internet via EIP (VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO)
- Topology: Cross-region

# When to use this skill

- Migrating self-managed PostgreSQL from ECS to managed RDS for PostgreSQL
- Cross-region database migration requiring minimal downtime
- Database consolidation from self-managed to managed service
- When Full + Incremental replication is needed for near-zero-downtime cutover

# When not to use this skill

- Same-region migration where VPN or VPC peering is available (prefer private network)
- Non-PostgreSQL databases (use appropriate DRS task type)
- When zero downtime is required and incremental lag is unacceptable
- When source PostgreSQL version is incompatible with target RDS version
- When VPN connectivity is required (OUT_OF_SCOPE_FOR_THIS_SCENARIO — use a different skill)

# Required inputs

- Source ECS instance ID, region, and PostgreSQL version
- Source database name and replication user credentials
- Source security group ID
- Target RDS instance ID, region, and database name
- Target region for DRS task
- DRS task name

# Optional inputs

- Specific tables/schemas to include or exclude
- Cutover window definition
- Validation queries
- Rollback strategy
- VPN configuration (OUT_OF_SCOPE_FOR_THIS_SCENARIO — this skill uses EIP only)

# Required MCPs

- huaweicloud-drs

# Optional MCPs

- huaweicloud-pricing (for cost estimation of target RDS)
- huaweicloud-ticket (for support ticket creation)

# Tool selection policy

- Use huaweicloud-drs tools for all DRS operations
- Write operations (create task, start task) require explicit_approval=true
- Never approve 0.0.0.0/0 or CIDRs broader than /32 for PostgreSQL port
- Use huaweicloud-pricing for cost estimation only (all tools read-only)
- Use huaweicloud-ticket prepare_ticket before create_ticket

# Safety and approval gates

1. DRS task creation requires explicit_approval=true
2. DRS task start requires explicit_approval=true
3. Source access plan (SG rules, pg_hba.conf) requires review before application
4. CIDR broader than /32 is rejected by DRS MCP safety guards
5. Region must be validated before task start
6. Pre-check must pass before task start
7. Connection test must pass before task start
8. Cutover requires explicit approval
9. Rollback/cleanup requires explicit approval

# Rules

1. Source PostgreSQL must have wal_level=logical, max_replication_slots >= 1, and max_wal_senders >= 1 for DRS incremental replication; verify these settings before creating the DRS task. [VERIFIED_FROM_DOCUMENTATION]

2. VPN connectivity is OUT_OF_SCOPE_FOR_THIS_SCENARIO; the supported architecture uses public EIP with /32 CIDR restrictions. Do not attempt VPN configuration through this skill. [VERIFIED_FROM_DESIGN]

3. DRS task creation and start require explicit_approval=true; no DRS write operation proceeds without explicit boolean approval. [VERIFIED_FROM_CODE]

4. CIDR broader than /32 for PostgreSQL port is rejected by DRS MCP safety guards; never open PostgreSQL to 0.0.0.0/0 or broad CIDRs. [VERIFIED_FROM_TEST]

5. Source access changes (SG rules, pg_hba.conf) must be reviewed before application; do not apply access changes automatically. [INFERRED]

6. Pre-check and connection test must pass before DRS task start; do not bypass these validations. [VERIFIED_FROM_CODE]

7. Cutover requires stopping application writes to the source database and waiting for final incremental sync; do not cutover while replication lag is significant. [INFERRED]

8. DRS task stop/termination requires manual console operation; no MCP tool exists for this operation. [NOT_VERIFIED]

9. DISCOVER BEFORE CREATE: use drs_find_matching_tasks before creating a new DRS task to avoid duplicates. [VERIFIED_FROM_CODE]

10. VERIFY AFTER EVERY STEP: validate DRS task status after each operation. [VERIFIED_FROM_CODE]

11. No hardcoded IPs, RDS IDs, or ECS IDs; resolve names to IDs dynamically. [VERIFIED_FROM_CODE]

12. Never include secrets (AK, SK, database passwords, replication user passwords) in commands, examples, files, or logs. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| Source ECS with PostgreSQL | Yes | Database to migrate | SSH access, `pg_isready` |
| Source PostgreSQL version | Yes | Version compatibility | `SELECT version()` |
| Source database name | Yes | Migration scope | `\l` in psql |
| Source replication user | Yes | DRS replication | PostgreSQL role with REPLICATION |
| Source security group | Yes | Network access control | `hcloud VPC ListSecurityGroups` |
| Target RDS for PostgreSQL | Yes | Migration destination | RDS instance ACTIVE |
| Target region | Yes | Cross-region DRS task | Region code |
| Target database name | Yes | Migration destination | RDS database exists |
| DRS MCP (huaweicloud-drs) | Yes | All DRS operations | MCP availability check |
| DRS EIP connectivity | Yes | Public network path | DRS replication instance EIP |
| Source SG allows DRS EIP | Yes | PostgreSQL port access | SG rule verification |
| pg_hba.conf allows DRS user | Yes | Replication authentication | pg_hba.conf entry |
| Precheck passed | Yes | Migration readiness | `drs_run_precheck` |
| Approval owner | Yes | Authority for write operations | Specified in intent |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate all required and optional inputs for the PostgreSQL cross-region migration.

**Inputs**: User request specifying source ECS, target RDS, regions, database names, DRS task name, approval owner.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm all required fields are present.

**Expected result**: Complete intent object with all required fields populated.

**Failure action**: STOP and request clarification. Do not invent values.

**Evidence artifact**: `artifacts/pg-drs-intent.json`

Extract:
- source_ecs_instance_id, source_region, source_postgresql_version
- source_database_name, source_replication_user
- source_security_group_id
- target_rds_instance_id, target_region, target_database_name
- drs_task_name
- tables_to_include, tables_to_exclude
- cutover_window
- validation_queries
- rollback_strategy
- approval_owner

If critical information is missing: do not invent, request clarification, stop write operations.

## Phase 1 — Discovery

**Classification: AUTOMATED**

1. Read DRS console context: `drs_read_context`
2. List existing DRS tasks: `drs_list_tasks` with source_engine=postgresql
3. Find matching tasks: `drs_find_matching_tasks` with source/target details
4. Capture source ECS details (region, PostgreSQL version, database)
5. Capture target RDS details (region, instance ID, database)
6. Document current state

**MCP tools used**: drs_read_context, drs_list_tasks, drs_find_matching_tasks

## Phase 2 — Architecture validation

**Classification: AUTOMATED**

1. Validate source and target regions are different (cross-region requirement)
2. Validate PostgreSQL version compatibility
3. Validate source PostgreSQL configuration:
   - wal_level = logical
   - max_replication_slots >= 1
   - max_wal_senders >= 1
4. Validate target RDS instance is accessible
5. Validate network architecture (public Internet via EIP)
6. Document architecture validation results

**MCP tools used**: drs_read_context

**Capability gaps**:
- No MCP tool for PostgreSQL configuration validation (manual SSH required)
- No MCP tool for extension compatibility check

## Phase 3 — Readiness and prechecks

**Classification: ASSISTED**

1. Generate source access plan: `drs_generate_source_access_plan`
   - SG rule for DRS EIP
   - pg_hba.conf entry for replication user
   - Review plan before applying
2. Apply source access changes (MANUAL: SSH to ECS, modify pg_hba.conf, reload PostgreSQL)
3. Run connection test: `drs_run_connection_test`
4. Run DRS pre-check: `drs_run_precheck`
5. Review pre-check results
6. Address any BLOCKING or NEEDS_USER_DECISION items

**MCP tools used**: drs_generate_source_access_plan, drs_run_connection_test, drs_run_precheck

## Phase 4 — Plan generation

**Classification: AUTOMATED**

1. Determine creation strategy based on discovery results
2. Generate DRS task configuration
3. Generate execution plan with estimated timeline
4. Generate rollback plan
5. Generate validation plan (DDL comparison, row counts, incremental test)
6. Present plan for approval

**MCP tools used**: drs_read_context, drs_list_tasks

## Phase 5 — Approval

**Classification: MANUAL**

1. Review complete migration plan
2. Review source access changes
3. Review DRS task configuration
4. Review rollback plan
5. Obtain explicit approval from stakeholder
6. Document approval with timestamp and approver

**MCP tools used**: None

## Phase 6 — Execution

**Classification: ASSISTED**

1. Select or create DRS task:
   - If matching task exists: `drs_select_or_create_task` with creation_strategy
   - If no match: `drs_create_postgresql_full_incremental_task` with explicit_approval=true
2. Capture DRS replication instance EIP: `drs_capture_replication_instance_eip`
3. Update source access plan with actual DRS EIP (if different from initial)
4. Re-run connection test: `drs_run_connection_test`
5. Re-run pre-check: `drs_run_precheck`
6. Start DRS task: `drs_start_task` with explicit_approval=true
7. Monitor task progress: `drs_get_task_status`

**MCP tools used**: drs_select_or_create_task OR drs_create_postgresql_full_incremental_task, drs_capture_replication_instance_eip, drs_run_connection_test, drs_run_precheck, drs_start_task, drs_get_task_status

## Phase 7 — Validation

**Classification: ASSISTED**

1. Monitor DRS task status: `drs_get_task_status`
2. Wait for Full synchronization to complete
3. Validate DDL structure (source vs target)
4. Validate row counts (source vs target)
5. Generate DRS report: `drs_generate_report`
6. Document validation results

**MCP tools used**: drs_get_task_status, drs_generate_report

## Phase 8 — Cutover

**Classification: MANUAL**

1. Verify incremental lag is acceptable
2. Stop application writes to source database
3. Wait for final incremental sync
4. Verify final row counts match
5. Redirect application connections to target RDS
6. Verify application functionality
7. Declare cutover complete or initiate rollback

**MCP tools used**: drs_get_task_status (for lag monitoring)

## Phase 9 — Rollback

**Classification: MANUAL**

1. Redirect application connections back to source ECS PostgreSQL
2. Stop DRS task (manual operation in DRS console)
3. Verify source database is operational
4. Clean up target RDS data if needed
5. Document rollback reason and lessons learned

**MCP tools used**: None (DRS task stop requires manual console operation)

**Capability gap**: No MCP tool for DRS task stop/termination

## Phase 10 — Closure and reporting

**Classification: AUTOMATED**

1. Generate final DRS report: `drs_generate_report`
2. Document migration summary:
   - Source and target details
   - DRS task configuration
   - Validation results
   - Cutover timestamp
   - Issues encountered
3. Recommend cleanup actions:
   - Remove DRS replication instance
   - Remove source SG rules for DRS EIP
   - Remove pg_hba.conf entries for DRS
   - Consider source ECS decommission timeline
4. Archive migration artifacts

**MCP tools used**: drs_generate_report

# Capability gap handling

Known capability gaps:
- GAP-PG-001: No MCP tool for PostgreSQL configuration validation (wal_level, replication slots)
- GAP-PG-002: No MCP tool for PostgreSQL extension compatibility check
- GAP-PG-003: No MCP tool for DRS task stop/termination
- GAP-PG-004: VPN connectivity OUT_OF_SCOPE_FOR_THIS_SCENARIO (public EIP is the supported architecture)
- GAP-PG-005: No MCP tool for application connection string update
- GAP-PG-006: No MCP tool for DDL comparison between source and target
- GAP-PG-007: No MCP tool for row count validation

# Output artifacts

- discovery-report.md — Source/target inventory and DRS task state
- architecture-validation-report.md — Compatibility and configuration assessment
- source-access-plan.md — SG rules and pg_hba.conf changes
- readiness-report.md — Connection test and pre-check results
- migration-plan.md — Complete execution plan
- drs-task-config.json — DRS task configuration
- execution-log.md — Step-by-step execution log
- validation-report.md — DDL and data validation results
- drs-report.md — DRS-generated migration report
- rollback-plan.md — Rollback procedure
- final-report.md — Migration summary and recommendations

# Failure handling

- Connection test failure: Check SG rules, pg_hba.conf, PostgreSQL status, network connectivity
- Pre-check failure: Address BLOCKING items. Review NEEDS_USER_DECISION items.
- Task creation failure: Check for duplicate tasks, validate parameters, review DRS limits
- Task start failure: Ensure connection test passed, pre-check passed, region validated
- Full sync failure: Check DRS logs, source database locks, target RDS capacity
- Incremental lag excessive: Check source write volume, network bandwidth, DRS instance size

# Recovery procedure

1. If failure during task creation: No data impact. Review parameters and retry.
2. If failure during full sync: Target may have partial data. Stop task, clean target, retry.
3. If failure during incremental sync: Source and target may diverge. Assess lag, may need restart.
4. If failure during cutover: Revert application connections to source. Source is still operational.
5. If failure post-cutover: Assess data integrity. May need reverse sync or manual repair.

# Evidence and traceability

- DRS task ID and configuration preserved
- Connection test results preserved
- Pre-check results preserved
- Task status progression logged with timestamps
- Validation results (DDL, row counts) preserved
- Approval decisions recorded with approver identity
- DRS report generated with non-sensitive data only

# Known limitations

- VPN connectivity is OUT_OF_SCOPE_FOR_THIS_SCENARIO (public EIP is the intended architecture, security mitigated by /32 CIDR)
- Source PostgreSQL configuration validation requires manual SSH access
- Extension compatibility must be checked manually
- DRS task stop/termination requires manual console operation
- Application connection string update is manual
- DDL comparison is manual (no automated tool)
- Row count validation is manual (no automated tool)
- DRS pricing is BLOCKED in huaweicloud-pricing MCP (resource_spec not found)
- Public Internet exposure of PostgreSQL port is a security risk (mitigated by /32 CIDR)

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| Connection test fails | SG rules or pg_hba.conf | `drs_run_connection_test` result | Verify SG allows DRS EIP on PostgreSQL port, check pg_hba.conf entry |
| Pre-check returns BLOCKING | Incompatible configuration | `drs_run_precheck` result | Address BLOCKING items before proceeding |
| DRS task creation fails | Duplicate task or invalid params | `drs_find_matching_tasks` | Check for existing tasks, validate parameters |
| DRS task start fails | Pre-check or connection not passed | Task status and error | Ensure pre-check passed, connection test passed |
| Full sync stalls | Source locks or target capacity | `drs_get_task_status` | Check source database locks, target RDS capacity |
| Incremental lag excessive | High write volume or bandwidth | `drs_get_task_status` delay | Check source write volume, network bandwidth, DRS instance size |
| Cutover data mismatch | Incomplete incremental sync | Row count comparison | Wait for lag to reach zero, verify final counts |
| VPN connectivity expected | Misunderstood architecture | Review skill scope | This skill uses EIP only; VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO |
| pg_hba.conf change fails | SSH access or PostgreSQL reload | SSH error or reload error | Verify SSH access, run `pg_ctl reload` or `SELECT pg_reload_conf()` |
| DRS task cannot be stopped | No MCP tool for task stop | Manual console required | Stop task in DRS console manually |

See also: `references/known-issues.md` when available.

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- 10 of 13 DRS MCP tools are available and functional [VERIFIED_FROM_CODE]
- 3 write tools require explicit_approval=true [VERIFIED_FROM_CODE]
- Safety guards implemented: CIDR /32, region guard, pre-check guard, duplicate guard [VERIFIED_FROM_TEST]
- 58 tests pass across 8 test suites [VERIFIED_FROM_TEST]
- Use case documented with 18-step runbook [VERIFIED_FROM_DOCUMENTATION]
- VPN NOT_REQUIRED (public EIP is the supported architecture for this scenario) [VERIFIED_FROM_DESIGN]
- DRS pricing BLOCKED [VERIFIED_FROM_DOCUMENTATION]
- Source PostgreSQL config validation requires manual SSH [INFERRED]
- DRS task stop requires manual console operation [NOT_VERIFIED]
