# Snowflake to DataArts

## Purpose

Orchestrate migration of data pipelines and SQL workloads from Snowflake to Huawei Cloud DataArts (Factory + DLI) for demo and proof-of-concept purposes. This is a PARTIAL capability — it does not claim complete production migration. Snowflake source extraction and schema mapping are manual.

## Scenario at a Glance

| Attribute | Value |
|---|---|
| Domain | Migration / Big-Data-Migration |
| Source | Snowflake (SQL tasks, task graphs, schemas) |
| Target | DataArts Factory + DLI |
| Primary service | DataArts |
| Primary mechanism | Artifact-based migration with SQL adaptation |
| Scenario maturity | PARTIAL |
| Highest risk | MEDIUM |
| Skills | 1 |

## Architecture

```
Snowflake (External)
       │
       │ Manual extraction:
       │   - SQL tasks
       │   - Task graphs
       │   - Schemas
       │   - Expected results
       ▼
Migration Artifacts (artifact_dir)
       │
       │ dataarts-deploy-agent MCP
       │   - Plan generation
       │   - SQL adaptation
       │   - Job execution
       ▼
DataArts Factory + DLI
       │
       │ Equivalence validation
       ▼
Comparison Report
```

This architecture reflects only what existing evidence supports. Do not fabricate DataArts components not covered by the dataarts-deploy-agent MCP.

## When to Use This Scenario

- Migrating Snowflake SQL tasks and task graphs to DataArts Factory jobs (demo/POC)
- Validating equivalence between Snowflake and DataArts query results
- Assessing migration feasibility for Snowflake workloads

## When NOT to Use This Scenario

- Full production migration (not yet supported end-to-end)
- Migrating non-Snowflake sources (use appropriate migration path)
- When real-time/CDC migration is required (DataArts is batch-oriented)
- When Snowflake features have no DataArts equivalent (e.g., Snowpipe, Streams)
- When automated source extraction is required (currently manual)

## Skills Included

| Order | Skill | Required | Purpose | Mechanism | Status | Risk |
|---:|---|---|---|---|---|---|
| 1 | [huawei-snowflake-to-dataarts-migration](./huawei-snowflake-to-dataarts-migration/SKILL.md) | Yes | Demo/POC migration orchestration | dataarts-deploy-agent MCP | PARTIAL | MEDIUM |

## Shared Capabilities

| Component | Type | Required / Optional | Purpose |
|---|---|---|---|
| [dataarts-deploy-agent](../shared/mcps/dataarts-deploy-agent/) | MCP | Required | Plan, execute, validate migration |
| [huaweicloud-pricing](../shared/mcps/huaweicloud-pricing/) | MCP | Optional | DataArts/DLI cost estimation |
| [huaweicloud-ticket](../shared/mcps/huaweicloud-ticket/) | MCP | Optional | Support ticket creation |
| [Playwright](../shared/integrations/playwright/) | Integration | Optional | Console exploration if needed |

## Prerequisites

- dataarts-deploy-agent MCP available
- DLI queue pre-configured and available
- DataArts Factory workspace pre-configured
- Migration artifacts prepared (SQL, manifests, expected results)
- Confirmation authority for write operations (confirm=true)
- Snowflake credentials available for manual source extraction

See [huawei-snowflake-to-dataarts-migration prerequisites](./huawei-snowflake-to-dataarts-migration/SKILL.md) for the complete list.

## Execution Sequence

### Phase 1 — Parse Intent

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: job_name, artifact_dir, dli_queue
- **Output**: Complete intent object (`artifacts/dataarts-intent.json`)
- **Approval**: None
- **Verification**: artifact_dir exists, job_name valid
- **Next**: Phase 2

### Phase 2 — Discovery

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: Intent object
- **Output**: Migration scope, existing runs, stale result check
- **Approval**: None (plan-only + status check)
- **Verification**: No stale results; artifact package valid
- **Next**: Phase 3

### Phase 3 — Readiness

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: Discovery results
- **Output**: Environment validation, artifact validation, credential validation
- **Approval**: None
- **Verification**: DLI queue available, DataArts workspace available
- **Next**: Phase 4

### Phase 4 — Execution

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: Approved migration plan
- **Output**: DataArts Factory job executed, DLI SQL run
- **Approval**: EXPLICIT (confirm=true for demo_run or demo_start)
- **Verification**: Execution completed or in progress
- **Next**: Phase 5

### Phase 5 — Validation

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: Run status
- **Output**: Equivalence summary (row count, value match, schema match)
- **Approval**: None
- **Verification**: Equivalence results acceptable
- **Next**: Phase 6

### Phase 6 — Closure

- **Skill**: huawei-snowflake-to-dataarts-migration
- **Input**: All artifacts
- **Output**: Final report with migration scope, equivalence results, recommendations
- **Approval**: None
- **Verification**: Report generated
- **Next**: Completion

Cutover is NOT applicable for demo/POC flow.

## AI Execution Instructions

1. Read this README first.
2. Do not load every skill unnecessarily.
3. Resolve the current phase.
4. Load only the required [SKILL.md](./huawei-snowflake-to-dataarts-migration/SKILL.md).
5. Follow PARSE INTENT.
6. Run discovery (plan-only) before any write.
7. Verify MCP availability (dataarts-deploy-agent required).
8. Obtain explicit approval (confirm=true) for demo_run or demo_start.
9. Execute one controlled phase.
10. Verify.
11. Return to scenario README.
12. Determine next phase.
13. Stop on ambiguity.
14. Use capability builder only for a real gap.

## Human Execution Instructions

1. Read this scenario README
2. Review architecture diagram
3. Read [SKILL.md](./huawei-snowflake-to-dataarts-migration/SKILL.md)
4. Prepare migration artifacts (SQL, manifests, expected results)
5. Review and approve migration plan
6. Approve execution (confirm=true)
7. Review equivalence results
8. Review final report

## Approval Gates

| Gate | Operation | Risk | Approval required | Skill |
|---|---|---|---|---|
| G1 | demo_run / demo_start | Medium | EXPLICIT (confirm=true) | huawei-snowflake-to-dataarts-migration |
| G2 | Rollback / cleanup | Low | Review | huawei-snowflake-to-dataarts-migration |

## Validation Criteria

- Migration plan generated successfully
- Execution completed without critical errors
- Equivalence summary shows row count match
- Equivalence summary shows value match
- Equivalence summary shows schema match

## Completion Criteria

This scenario is complete when demo/POC objectives are reached:

- Migration plan generated and approved
- DataArts Factory job executed successfully
- Equivalence validation results acceptable for POC scope
- Final report generated with recommendations

This is NOT production migration completion criteria. Current skill cannot meet production migration requirements.

## Rollback / Recovery

1. **Plan failure**: Validate artifact package and environment. Fix and retry.
2. **Execution failure**: Review error in status. May need to fix SQL and re-run.
3. **Equivalence failure**: Review mismatched results. May need SQL adaptation fixes.
4. **Full rollback**: Clean up DataArts/DLI resources manually. Snowflake remains untouched.

No automated rollback of DataArts resources exists.

## Capability Gaps

| Gap | Impact | Core blocker | Current treatment | Future option |
|---|---|---|---|---|
| GAP-DA-001: No automated Snowflake extraction | Source extraction is manual | No | Manual export | Snowflake MCP |
| GAP-DA-002: No automated schema mapping | Schema mapping is manual | No | Manual mapping | Schema mapping tool |
| GAP-DA-003: No SQL compatibility analysis | SQL adaptation is semi-automated | No | Adapter-based + manual review | SQL analyzer |
| GAP-DA-004: No production migration flow | Only demo/POC supported | No | Demo/POC only | Production pipeline |
| GAP-DA-005: No automated rollback | Cleanup is manual | No | Manual cleanup | Rollback automation |
| GAP-DA-006: No incremental/delta migration | Only full migration | No | Full migration only | Incremental support |

For gap resolution, see [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md).

## Known Limitations

- Only demo/POC flow is supported (not production migration)
- Snowflake source extraction is manual
- Schema mapping is manual
- SQL adaptation is semi-automated (adapter-based)
- No incremental/delta migration
- No automated rollback of DataArts resources
- Equivalence validation is limited to query result comparison
- Missing golden fixtures may produce warnings

## Maturity

PARTIAL. 6 dataarts-deploy-agent MCP tools available. 2 write tools require confirm=true. Demo/POC flow works end-to-end. Golden packages validated. Secret scrubbing implemented. Production migration flow NOT available. Snowflake source extraction NOT automated. Schema mapping NOT automated.

## Evidence and Traceability

- Migration plan preserved
- Execution status logged with timestamps
- Equivalence results preserved (row counts, value comparisons)
- Reports generated with secrets scrubbed
- Run IDs tracked for traceability

## AI Reading Order

1. `README.md` (this file)
2. [huawei-snowflake-to-dataarts-migration/SKILL.md](./huawei-snowflake-to-dataarts-migration/SKILL.md)
3. [huawei-snowflake-to-dataarts-migration/references/workflows/discovery.md](./huawei-snowflake-to-dataarts-migration/references/workflows/discovery.md)
4. [huawei-snowflake-to-dataarts-migration/references/workflows/execution.md](./huawei-snowflake-to-dataarts-migration/references/workflows/execution.md)
5. [huawei-snowflake-to-dataarts-migration/references/workflows/validation.md](./huawei-snowflake-to-dataarts-migration/references/workflows/validation.md)
6. [huawei-snowflake-to-dataarts-migration/references/workflows/rollback.md](./huawei-snowflake-to-dataarts-migration/references/workflows/rollback.md)

## Human Reading Order

1. This scenario README
2. Architecture diagram above
3. Prerequisites section
4. [SKILL.md](./huawei-snowflake-to-dataarts-migration/SKILL.md)
5. [Execution runbook](./huawei-snowflake-to-dataarts-migration/references/execution-runbook.md)
6. [Validation](./huawei-snowflake-to-dataarts-migration/references/workflows/validation.md)
7. [Rollback](./huawei-snowflake-to-dataarts-migration/references/workflows/rollback.md)

## Related References

- [DataArts deploy agent documentation](../shared/mcps/dataarts-deploy-agent/docs/README_DATAARTS_MIGRATION.md)
- [DataArts migration architecture](../shared/mcps/dataarts-deploy-agent/docs/dataarts-migration-architecture.md)
- [MVP quickstart](../shared/mcps/dataarts-deploy-agent/docs/mvp-v0.1-quickstart.md)
