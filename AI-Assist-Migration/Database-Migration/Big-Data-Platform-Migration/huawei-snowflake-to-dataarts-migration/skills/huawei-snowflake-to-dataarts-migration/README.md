# huawei-snowflake-to-dataarts-migration

## Summary

Skill to orchestrate or assist migration from Snowflake to Huawei Cloud DataArts (Factory + DLI), using the dataarts-deploy-agent MCP for plan generation, execution, and equivalence validation.

## Problem it solves

Migrating analytical workloads from Snowflake to Huawei Cloud DataArts requires SQL adaptation, schema mapping, DataArts Factory job creation, DLI execution, and result equivalence validation. Without orchestration, the process is manual and prone to inconsistencies.

## Supported scenario

- **Source**: Snowflake (SQL tasks, task graphs, schemas)
- **Target**: Huawei Cloud DataArts Factory + DLI
- **Mechanism**: Artifact-based migration with SQL adaptation
- **Current scope**: Demo/POC flow (one-shot)

## Architecture

```
Snowflake                          Huawei Cloud
┌──────────────┐                   ┌──────────────────────┐
│ SQL Tasks    │──manual extract──>│ Migration Artifacts  │
│ Task Graphs  │                   │ (SQL, manifest)      │
│ Schemas      │                   └──────────┬───────────┘
└──────────────┘                              │
                                    dataarts-deploy-agent
                                              │
                                   ┌──────────▼───────────┐
                                   │ DataArts Factory     │
                                   │  └── Jobs (adapted) │
                                   │ DLI                  │
                                   │  └── SQL execution   │
                                   └──────────────────────┘
```

Adapters available: legacy-demo, native-dli, koocli, runtime-engine

## MCPs used

| MCP | Required | Purpose | Read/Write | Risk |
|---|---|---|---|---|
| dataarts-deploy-agent | Yes | Plan, execute, monitor, and validate Snowflake→DataArts migration | Read + Write | Medium (write requires confirm) |
| huaweicloud-pricing | No | Estimate DataArts/DLI costs | Read-only | None |
| huaweicloud-ticket | No | Create support ticket | Read + Write | Medium |
| playwright | No | Console automation | Read + Write | Medium |

## Capabilities

- Plan generation (read-only, safe)
- Synchronous execution (demo_run with confirm=true)
- Asynchronous execution (demo_start with confirm=true)
- Status monitoring
- Equivalence validation (source vs target results)
- Report generation with secret scrubbing
- Stale result detection

## General flow

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover (N/A for demo) → 9. Rollback → 10. Closure

## Automation level

| Phase | Status | Responsible |
|---|---|---|
| Discovery | AUTOMATED | Agent |
| Architecture Validation | ASSISTED | Agent + Human |
| Readiness and Prechecks | ASSISTED | Agent + Human |
| Plan Generation | AUTOMATED | Agent |
| Approval | MANUAL | Human |
| Execution | ASSISTED | Agent + Human |
| Validation | AUTOMATED | Agent |
| Cutover | NOT_IMPLEMENTED | N/A (demo only) |
| Rollback | MANUAL | Human |
| Closure and Reporting | AUTOMATED | Agent |

## Prerequisites

- Migration artifacts prepared (SQL files, manifest, expected results)
- DLI queue configured and available
- DataArts Factory workspace configured
- Huawei Cloud credentials with DataArts and DLI access
- dataarts-deploy-agent MCP configured and operational

## Inputs

- job_name: DataArts Factory job name
- artifact_dir: Path to migration artifacts directory
- dli_queue: DLI queue name (default: "default")

## Outputs

- migration-plan.md
- execution-status.json
- equivalence-summary.md
- demo-report.md
- validation-results.json

## Installation

```bash
cd <INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent
npm install
```

## Configuration

```json
{
  "skills": {
    "huawei-snowflake-to-dataarts-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-snowflake-to-dataarts-migration"
    }
  },
  "mcp": {
    "dataarts-deploy-agent": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent"
    }
  }
}
```

## Usage with OpenCode or Hermes

1. Load the skill: `skill huawei-snowflake-to-dataarts-migration`
2. Follow the workflow documented in SKILL.md
3. AUTOMATED phases will be executed by the agent
4. ASSISTED phases require human review
5. MANUAL phases require human execution

## Safe example

```
# Phase 1: Discovery (read-only)
snowflake_dataarts_demo_plan({
  job_name: "customer_status_pipeline",
  artifact_dir: "./artifacts/customer_status_pipeline_simple",
  dli_queue: "default"
})

# Phase 4: Plan generation (read-only)
snowflake_dataarts_demo_plan({
  job_name: "customer_status_pipeline",
  artifact_dir: "./artifacts/customer_status_pipeline_simple"
})

# Phase 7: Validation (read-only)
snowflake_dataarts_demo_equivalence_summary({
  job_name: "customer_status_pipeline"
})

snowflake_dataarts_demo_last_report({
  job_name: "customer_status_pipeline"
})
```

## Required approvals

- Execute migration (demo_run with confirm=true)
- Start async migration (demo_start with confirm=true)
- Cutover (not applicable in demo, required in future production)
- Rollback of DataArts/DLI resources

## Validation

- Equivalence summary: Comparison of Snowflake vs DataArts/DLI results
- Row count match
- Value match
- Schema match
- Report review

## Rollback

1. Clean up DataArts Factory jobs created
2. Clean up DLI tables/data created
3. Revert to Snowflake as source of truth
4. Document rollback reason

## Capability gap handling

| Gap ID | Description | Decision |
|---|---|---|
| GAP-DA-001 | No automated Snowflake source extraction | MANUAL_STEP |
| GAP-DA-002 | No automated schema mapping | MANUAL_STEP |
| GAP-DA-003 | No automated SQL compatibility analysis | MANUAL_STEP |
| GAP-DA-004 | No production migration flow | NOT_REQUIRED (demo only) |
| GAP-DA-005 | No automated rollback of DataArts resources | MANUAL_STEP |
| GAP-DA-006 | No incremental/delta migration support | NOT_REQUIRED (demo only) |

## Testing

- Golden package validation: orders_pipeline_simple (runtime-confirmed) [VERIFIED_FROM_DOCUMENTATION]
- Golden package validation: customer_status_pipeline_simple (package/dry-run validated) [VERIFIED_FROM_DOCUMENTATION]
- Secret scrubbing verified [VERIFIED_FROM_CODE]
- confirm=true gate verified [VERIFIED_FROM_CODE]
- Stale result detection verified [VERIFIED_FROM_CODE]

## Security

- Automatic secret scrubbing in reports
- confirm=true required for write operations
- Stale result detection prevents use of obsolete results
- No credentials exposed in reports

## Limitations

- Only demo/POC flow supported
- Snowflake extraction is manual
- Schema mapping is manual
- No incremental/delta migration
- No automated DataArts rollback
- Cutover not applicable in demo

## Troubleshooting

| Problem | Solution |
|---|---|
| Plan generation fails | Verify artifact package, DLI queue, credentials |
| Execution fails | Review DataArts Factory logs, DLI job logs, SQL errors |
| Equivalence mismatch | Review SQL adaptation, data types, NULL handling |
| Stale results | Clean previous run state |

## Maturity status

**PARTIAL**

The demo/POC flow works end-to-end with equivalence validation. Full production migration is not available.

## Evidence used

| Evidence | Type |
|---|---|
| 6 dataarts-deploy-agent tools available | VERIFIED_FROM_CODE |
| 2 write tools require confirm=true | VERIFIED_FROM_CODE |
| Golden packages validated | VERIFIED_FROM_DOCUMENTATION |
| Secret scrubbing implemented | VERIFIED_FROM_CODE |
| Demo flow documented | VERIFIED_FROM_DOCUMENTATION |
| Production migration NOT available | VERIFIED_FROM_DOCUMENTATION |
| Snowflake extraction NOT automated | NOT_VERIFIED |
