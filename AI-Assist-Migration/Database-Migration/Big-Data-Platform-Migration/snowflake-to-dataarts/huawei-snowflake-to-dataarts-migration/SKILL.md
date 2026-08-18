---
name: huawei-snowflake-to-dataarts-migration
version: 1.0.0
description: Orchestrate or assist migration from Snowflake to Huawei Cloud DataArts (DLI + Factory)
category: migration
risk_level: medium
status: PARTIAL
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Migration
  family: Big-Data-Migration
  service: DataArts
  risk_level: medium
  status: PARTIAL
---

# Purpose

Orchestrate or assist the migration of data pipelines and SQL workloads from Snowflake to Huawei Cloud DataArts (DataArts Factory + DLI), leveraging the dataarts-deploy-agent MCP for plan generation, execution, and equivalence validation.

# Supported scenario

- Source: Snowflake (SQL tasks, task graphs, schemas, data)
- Target: Huawei Cloud DataArts Factory + DLI (Data Lake Insight)
- Mechanism: Artifact-based migration with SQL adaptation
- Scope: Currently supports demo/proof-of-concept flow (one-shot)
- Topology: Snowflake (external) → DataArts (Huawei Cloud)

# When to use this skill

- Migrating Snowflake SQL tasks and task graphs to DataArts Factory jobs
- Validating equivalence between Snowflake and DataArts query results
- Proof-of-concept or demo migrations from Snowflake to DataArts
- Assessing migration feasibility for Snowflake workloads

# When not to use this skill

- Full production migration (not yet supported end-to-end)
- Migrating non-Snowflake sources (use appropriate migration path)
- When real-time/CDC migration is required (DataArts is batch-oriented)
- When Snowflake features have no DataArts equivalent (e.g., Snowpipe, Streams, Tasks with CRON beyond Factory support)

# Required inputs

- job_name: DataArts Factory job name for the migration
- artifact_dir: Path to migration artifacts directory (SQL, manifests)
- dli_queue: DLI queue name (default: "default")

# Optional inputs

- run_id: Specific run ID for status check or report retrieval
- Snowflake connection details (for source extraction, not yet automated)
- DLI configuration overrides

# Required MCPs

- dataarts-deploy-agent

# Optional MCPs

- huaweicloud-pricing (for DataArts/DLI cost estimation)
- huaweicloud-ticket (for support ticket creation)
- playwright (for console automation if needed)

# Tool selection policy

- Use dataarts-deploy-agent tools for all migration operations
- Write operations (demo_run, demo_start) require confirm=true
- Use huaweicloud-pricing for cost estimation only (all tools read-only)
- Never execute demo_run or demo_start without explicit approval

# Safety and approval gates

1. demo_run requires confirm=true (executes real DataArts Factory jobs)
2. demo_start requires confirm=true (starts async DataArts Factory jobs)
3. Secret scrubbing is automatic in reports
4. Stale result detection prevents acting on outdated results
5. Plan-only operations (demo_plan) are safe and read-only

# Rules

1. Only demo/POC flow is currently supported; production migration end-to-end is NOT available. Do not represent this skill as production-ready. [VERIFIED_FROM_DOCUMENTATION]

2. Snowflake source extraction is NOT automated; SQL, schemas, and data must be provided as artifacts. [NOT_VERIFIED]

3. Schema mapping between Snowflake and DataArts is NOT automated; manual mapping is required. [NOT_VERIFIED]

4. SQL adaptation is adapter-based and semi-automated; do not assume all Snowflake SQL translates correctly to DLI SQL. [INFERRED]

5. demo_run and demo_start require confirm=true; never execute these without explicit approval. [VERIFIED_FROM_CODE]

6. Stale result detection prevents acting on outdated migration results; verify run_id before interpreting results. [VERIFIED_FROM_CODE]

7. Secret scrubbing is automatic in reports; however, verify that no secrets appear in migration artifacts. [VERIFIED_FROM_CODE]

8. DLI queue must be pre-configured and available; the skill cannot create or configure DLI queues. [INFERRED]

9. DataArts Factory workspace must be pre-configured; the skill cannot create workspaces. [INFERRED]

10. Equivalence validation is limited to query result comparison; it does not verify all semantic equivalences. [INFERRED]

11. No automated rollback of DataArts resources exists; cleanup must be performed manually. [INFERRED]

12. DISCOVER BEFORE CREATE: check for existing runs and stale results before starting a new migration. [VERIFIED_FROM_CODE]

13. VERIFY AFTER EVERY STEP: validate migration status and equivalence after execution. [VERIFIED_FROM_CODE]

14. Never include Snowflake credentials, DataArts credentials, or DLI credentials in commands, examples, or logs. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| dataarts-deploy-agent MCP | Yes | All migration operations | MCP availability check |
| job_name | Yes | DataArts Factory job identifier | Specified in intent |
| artifact_dir | Yes | Migration artifacts directory | Path exists on filesystem |
| dli_queue | Yes | DLI execution queue | DLI queue configuration |
| DLI queue availability | Yes | SQL execution environment | Queue status check |
| DataArts Factory workspace | Yes | Job execution environment | Workspace configuration |
| Migration artifacts | Yes | SQL, manifests, expected results | Artifact directory contents |
| Confirmation (confirm=true) | Yes | Explicit approval for writes | Boolean confirmation |
| Snowflake credentials | Conditional | Source extraction (manual) | Not automated |
| DataArts credentials | Conditional | Target service access | MCP configuration |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| Playwright | No | Console exploration | Integration availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate all required and optional inputs for the Snowflake to DataArts migration.

**Inputs**: User request specifying job_name, artifact_dir, dli_queue, optional run_id.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm all required fields are present, artifact_dir exists, job_name is valid.

**Expected result**: Complete intent object with all required fields populated.

**Failure action**: STOP and request clarification. Do not invent values.

**Evidence artifact**: `artifacts/dataarts-intent.json`

Extract:
- job_name
- artifact_dir
- dli_queue (default: "default")
- run_id (optional, for status/report retrieval)
- Snowflake connection details (if source extraction needed)
- DLI configuration overrides

If critical information is missing: do not invent, request clarification, stop write operations.

## Phase 1 — Discovery

**Classification: AUTOMATED**

1. Run plan-only to discover migration scope: `snowflake_dataarts_demo_plan`
2. Review plan output for:
   - SQL tasks to migrate
   - Task graph dependencies
   - Schema mappings
   - Data volume estimates
3. Check for existing runs: `snowflake_dataarts_demo_status`

**MCP tools used**: snowflake_dataarts_demo_plan, snowflake_dataarts_demo_status

## Phase 2 — Architecture validation

**Classification: ASSISTED**

1. Review migration architecture:
   - Source: Snowflake SQL tasks and task graphs
   - Target: DataArts Factory jobs + DLI SQL
   - Adapters: legacy-demo, native-dli, koocli, runtime-engine
2. Validate artifact package structure
3. Validate DLI queue availability
4. Validate DataArts Factory workspace
5. Document compatibility assessment

**MCP tools used**: snowflake_dataarts_demo_plan

**Capability gaps**:
- No automated Snowflake source extraction
- No automated schema mapping
- No automated SQL compatibility analysis

## Phase 3 — Readiness and prechecks

**Classification: ASSISTED**

1. Validate environment: DLI queue, DataArts Factory workspace
2. Validate artifact package: SQL files, manifest, expected results
3. Validate credentials: DataArts, DLI access
4. Check for stale results from previous runs
5. Review migration plan for warnings

**MCP tools used**: snowflake_dataarts_demo_status

## Phase 4 — Plan generation

**Classification: AUTOMATED**

1. Generate migration plan: `snowflake_dataarts_demo_plan`
2. Review plan for:
   - SQL adaptation requirements
   - DDL mappings
   - Data transformation needs
   - Expected equivalence validation queries
3. Present plan for approval

**MCP tools used**: snowflake_dataarts_demo_plan

## Phase 5 — Approval

**Classification: MANUAL**

1. Review migration plan
2. Review SQL adaptations
3. Review expected costs
4. Obtain explicit approval from stakeholder
5. Document approval with timestamp and approver

**MCP tools used**: None

## Phase 6 — Execution

**Classification: ASSISTED**

1. Execute migration (synchronous): `snowflake_dataarts_demo_run` with confirm=true
   OR
   Start migration (asynchronous): `snowflake_dataarts_demo_start` with confirm=true
2. Monitor progress: `snowflake_dataarts_demo_status`
3. Wait for completion

**MCP tools used**: snowflake_dataarts_demo_run OR snowflake_dataarts_demo_start, snowflake_dataarts_demo_status

## Phase 7 — Validation

**Classification: AUTOMATED**

1. Check run status: `snowflake_dataarts_demo_status`
2. Generate equivalence summary: `snowflake_dataarts_demo_equivalence_summary`
3. Retrieve last report: `snowflake_dataarts_demo_last_report`
4. Review equivalence results:
   - Row count match
   - Value match
   - Schema match
5. Document validation results

**MCP tools used**: snowflake_dataarts_demo_status, snowflake_dataarts_demo_equivalence_summary, snowflake_dataarts_demo_last_report

## Phase 8 — Cutover

**Classification: MANUAL**

Not applicable for demo/POC flow. For production migration (future):
1. Validate production DataArts Factory jobs
2. Switch downstream consumers to DataArts
3. Decommission Snowflake tasks

## Phase 9 — Rollback

**Classification: MANUAL**

1. Review failed step from status
2. Clean up DataArts Factory jobs created during migration
3. Clean up DLI tables/data created during migration
4. Revert to Snowflake as source of truth
5. Document rollback reason

**MCP tools used**: snowflake_dataarts_demo_status (for diagnosis only)

## Phase 10 — Closure and reporting

**Classification: AUTOMATED**

1. Generate final report: `snowflake_dataarts_demo_last_report`
2. Generate equivalence summary: `snowflake_dataarts_demo_equivalence_summary`
3. Document:
   - Migration scope (tasks migrated, SQL adapted)
   - Equivalence results
   - Issues encountered
   - Recommendations for production migration
4. Archive migration artifacts

**MCP tools used**: snowflake_dataarts_demo_last_report, snowflake_dataarts_demo_equivalence_summary

# Capability gap handling

Known capability gaps:
- GAP-DA-001: No automated Snowflake source extraction (SQL, schemas, data)
- GAP-DA-002: No automated schema mapping between Snowflake and DataArts
- GAP-DA-003: No automated SQL compatibility analysis
- GAP-DA-004: No production migration flow (only demo/POC)
- GAP-DA-005: No automated rollback of DataArts resources
- GAP-DA-006: No incremental/delta migration support

# Output artifacts

- migration-plan.md — Plan output from demo_plan
- execution-status.json — Run status and progress
- equivalence-summary.md — Source vs target equivalence results
- demo-report.md — Full migration report
- validation-results.json — Equivalence validation details

# Failure handling

- Plan generation failure: Check artifact package structure, DLI queue, credentials
- Execution failure: Check DataArts Factory logs, DLI job logs, SQL errors
- Equivalence mismatch: Review SQL adaptation, data types, NULL handling
- Stale results: Clear previous run state before re-execution

# Recovery procedure

1. If plan fails: Validate artifact package and environment. Fix and retry.
2. If execution fails: Review error in status. May need to fix SQL and re-run.
3. If equivalence fails: Review mismatched results. May need SQL adaptation fixes.
4. For rollback: Clean up DataArts/DLI resources. Snowflake remains untouched.

# Evidence and traceability

- Migration plan preserved
- Execution status logged with timestamps
- Equivalence results preserved (row counts, value comparisons)
- Reports generated with secrets scrubbed
- Run IDs tracked for traceability

# Known limitations

- Only demo/POC flow is supported (not production migration)
- Snowflake source extraction is manual
- Schema mapping is manual
- SQL adaptation is semi-automated (adapter-based)
- No incremental/delta migration
- No automated rollback of DataArts resources
- Equivalence validation is limited to query result comparison
- DLI queue must be pre-configured
- DataArts Factory workspace must be pre-configured

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| Plan generation fails | Invalid artifact package or DLI queue | Check artifact_dir structure, DLI queue | Validate artifact package, verify DLI queue name |
| Execution fails | DataArts Factory or DLI job error | `snowflake_dataarts_demo_status` | Check DataArts Factory logs, DLI job logs, SQL errors |
| Equivalence mismatch | SQL adaptation or data type difference | `snowflake_dataarts_demo_equivalence_summary` | Review SQL adaptation, data types, NULL handling |
| Stale results detected | Previous run state not cleared | `snowflake_dataarts_demo_status` | Clear previous run state, re-execute with new run_id |
| DLI queue not found | Queue not configured or wrong name | DLI error in execution | Verify DLI queue name and availability |
| Artifact directory missing | Path does not exist | Filesystem check | Verify artifact_dir path, create if needed |
| Secret found in report | Scrubbing missed a pattern | Review report output | Report as bug, manually redact |
| Demo timeout | Long-running DataArts job | `snowflake_dataarts_demo_status` | Use demo_start (async) instead of demo_run (sync) |
| Partial migration | Some SQL tasks failed | Equivalence summary partial results | Review failed tasks, fix SQL, re-run |

See also: `references/known-issues.md` when available.

# Status justification

Status: PARTIAL

Evidence:
- 6 dataarts-deploy-agent MCP tools available [VERIFIED_FROM_CODE]
- 2 write tools require confirm=true [VERIFIED_FROM_CODE]
- Demo/POC flow works end-to-end [VERIFIED_FROM_DOCUMENTATION]
- Golden packages validated (orders_pipeline_simple, customer_status_pipeline_simple) [VERIFIED_FROM_DOCUMENTATION]
- Secret scrubbing implemented [VERIFIED_FROM_CODE]
- Production migration flow NOT available [VERIFIED_FROM_DOCUMENTATION]
- Snowflake source extraction NOT automated [NOT_VERIFIED]
- Schema mapping NOT automated [NOT_VERIFIED]
