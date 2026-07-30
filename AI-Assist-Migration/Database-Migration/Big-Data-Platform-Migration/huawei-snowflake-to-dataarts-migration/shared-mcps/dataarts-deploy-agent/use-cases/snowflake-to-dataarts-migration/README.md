# Snowflake to DataArts Migration

## Purpose

Migrate SQL-based data pipelines from Snowflake to Huawei Cloud DataArts Factory / DLI, using the one-shot demo workflow provided by the dataarts-deploy-agent MCP.

## Architecture

- **Source:** Snowflake SQL pipelines
- **Target:** DataArts Factory jobs running on DLI
- **Migration tool:** dataarts-deploy-agent one-shot workflow
- **Validation:** Equivalence comparison (Snowflake expected vs DLI actual)

## Prerequisites

1. Snowflake query results available as expected outputs
2. Migration artifacts prepared (SQL files, job definitions, artifact manifest)
3. DataArts Factory instance available
4. DLI queue configured and healthy
5. AK/SK with DataArts and DLI permissions

## Execution runbook

| Step | Description | Classification |
|------|-------------|----------------|
| 1 | Validate environment (`npm run validate-env`) | AUTOMATED |
| 2 | Run migration plan (`snowflake_dataarts_demo_plan`) | AUTOMATED |
| 3 | Review plan output and SQL adaptations | ASSISTED |
| 4 | Execute migration (`snowflake_dataarts_demo_run` with confirm=true) | AUTOMATED |
| 5 | Monitor status (`snowflake_dataarts_demo_status`) | AUTOMATED |
| 6 | Review report (`snowflake_dataarts_demo_last_report`) | AUTOMATED |
| 7 | Generate equivalence summary (`snowflake_dataarts_demo_equivalence_summary`) | AUTOMATED |
| 8 | Review equivalence results and resolve mismatches | ASSISTED |

## Validation

- Equivalence summary comparing Snowflake expected vs DLI actual results
- Row count and value comparison
- SQL execution success verification

## Rollback

1. Delete DataArts Factory jobs created by migration
2. Drop DLI tables/databases created by migration
3. Remove OBS artifacts if applicable

## Known issues

- SQL dialect differences between Snowflake and DLI may require manual adaptation
- Some Snowflake functions have no DLI equivalent
- DLI queue availability affects job execution timing
- Large datasets may require partitioning strategies

## Status

PARTIAL — The one-shot workflow is implemented and tested. Full production migration orchestration is not yet available. See `docs/README_DATAARTS_MIGRATION.md` and `docs/dataarts-migration-architecture.md` for detailed architecture documentation.
