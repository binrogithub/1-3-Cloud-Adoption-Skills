# dataarts-deploy-agent

## Purpose

MCP server and deployment agent for Huawei Cloud DataArts Factory, focused on Snowflake-to-DataArts migration demos. Provides one-shot plan/run workflows for migrating SQL pipelines from Snowflake to DataArts/DLI, with equivalence validation comparing results between source and target.

## Scope

**Includes:**
- One-shot migration plan (dry-run)
- One-shot migration execution (synchronous and asynchronous)
- Migration status monitoring and reporting
- Equivalence summary generation (Snowflake vs DataArts/DLI results)
- SQL adaptation for DLI dialect
- DLI queue health and validation
- Migration package loading and validation
- Artifact manifest management
- Runtime engine (native and legacy adapters)

**Does not include:**
- Direct DataArts Factory API calls for job creation (delegated to CLI/scripts)
- Automatic schema translation beyond SQL dialect adaptation
- Production migration orchestration
- Data quality profiling

## Use cases

1. **Snowflake to DataArts migration demo** — One-shot workflow: plan, deploy, run, validate [VERIFIED_FROM_CODE] [VERIFIED_FROM_DOCUMENTATION]
2. **SQL dialect adaptation** — Convert Snowflake SQL to DLI-compatible SQL [VERIFIED_FROM_CODE]
3. **Equivalence validation** — Compare Snowflake expected results vs DLI actual results [VERIFIED_FROM_CODE]
4. **Migration status monitoring** — Track run progress, detect failures, report status [VERIFIED_FROM_CODE]
5. **DLI queue health check** — Validate DLI queue availability before job submission [VERIFIED_FROM_CODE]

## Architecture

- **Runtime:** Node.js (CJS)
- **Entry point:** `src/mcp-server.mjs`
- **Transport:** stdio (MCP SDK)
- **Core modules:**
  - `src/mcp-server.mjs` — Main MCP server with 6 tool handlers
  - `src/demo-one-shot.js` — Full one-shot migration workflow
  - `src/demo-one-shot-plan.js` — Plan-only (dry-run) workflow
  - `src/demo-equivalence-summary.js` — Equivalence comparison
  - `src/demo-one-shot-status.js` — Status monitoring
  - `src/adapt-sql-for-demo-runtime.js` — SQL dialect adaptation
  - `src/runtime-native-execute-guarded.js` — Guarded runtime execution
  - `src/` — 40+ supporting modules for DLI, migration, validation, etc.
- **Dependencies:** `@modelcontextprotocol/sdk`, `dotenv`, `js-yaml`
- **External services:** DataArts Factory, DLI, OBS

## MCP tools exposed

| # | Tool name | Purpose | Read/Write | Risk | Approval required |
|---|-----------|---------|------------|------|-------------------|
| 1 | snowflake_dataarts_demo_plan | Run migration plan only (dry-run) | read-only | none | no |
| 2 | snowflake_dataarts_demo_run | Run full migration synchronously | write | high | yes (confirm=true) |
| 3 | snowflake_dataarts_demo_start | Start migration asynchronously | write | high | yes (confirm=true) |
| 4 | snowflake_dataarts_demo_status | Read migration run status | read-only | none | no |
| 5 | snowflake_dataarts_demo_last_report | Read last migration report | read-only | none | no |
| 6 | snowflake_dataarts_demo_equivalence_summary | Generate equivalence comparison | read-only | none | no |

## Prerequisites

- Node.js >= 18
- Huawei Cloud account with DataArts Factory and DLI access
- AK/SK with DataArts and DLI permissions
- DLI queue configured
- Migration artifacts (SQL files, job definitions)

## Installation

```bash
cd mcps/dataarts-deploy-agent
npm install
```

## Configuration

```bash
export HWCLOUD_ACCESS_KEY=<YOUR_ACCESS_KEY>
export HWCLOUD_SECRET_KEY=<YOUR_SECRET_KEY>
export HWCLOUD_PROJECT_ID=<YOUR_PROJECT_ID>
export HWCLOUD_REGION=<YOUR_REGION>
export DLI_QUEUE=<YOUR_DLI_QUEUE>
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| HWCLOUD_ACCESS_KEY | yes | Huawei Cloud Access Key |
| HWCLOUD_SECRET_KEY | yes | Huawei Cloud Secret Key |
| HWCLOUD_PROJECT_ID | yes | Project ID for DataArts/DLI |
| HWCLOUD_REGION | yes | Region for DataArts Factory |
| DLI_QUEUE | no | DLI queue name (default: "default") |

## Execution

```bash
node src/mcp-server.mjs
```

## Integration with OpenCode

```json
{
  "dataarts-deploy-agent": {
    "type": "local",
    "enabled": true,
    "command": ["node", "<INSTALLATION_ROOT>/mcps/dataarts-deploy-agent/src/mcp-server.mjs"],
    "timeout": 30000
  }
}
```

## Examples

```bash
# Plan migration (dry-run)
# Tool: snowflake_dataarts_demo_plan
# Parameters: { job_name: "orders_pipeline", artifact_dir: "./cases/golden/orders_pipeline_simple", dli_queue: "default" }

# Run migration (requires confirmation)
# Tool: snowflake_dataarts_demo_run
# Parameters: { confirm: true, job_name: "orders_pipeline", artifact_dir: "./cases/golden/orders_pipeline_simple" }

# Check status
# Tool: snowflake_dataarts_demo_status
# Parameters: { job_name: "orders_pipeline" }

# Equivalence summary
# Tool: snowflake_dataarts_demo_equivalence_summary
# Parameters: { job_name: "orders_pipeline" }
```

## Tests

```bash
npm test
```

Node.js built-in test runner with files in `tests/` directory.

## Security

- Write tools require `confirm=true` safety gate [VERIFIED_FROM_CODE]
- Secret scrubbing in all output via `scrubSecrets()` [VERIFIED_FROM_CODE]
- `.env.dataarts` symlink excluded from delivery (points to secrets directory)
- No credentials in reports or equivalence summaries

## Limitations

- Focused on Snowflake-to-DataArts migration demo; not a general-purpose DataArts API client
- Requires pre-prepared migration artifacts
- DLI SQL dialect differences may require manual SQL adaptation
- Equivalence validation depends on both Snowflake and DLI results being available

## Troubleshooting

- **"Environment validation failed"**: Run `npm run validate-env` to check configuration
- **"DLI queue unavailable"**: Run `npm run dli:queue:health` to diagnose
- **"Migration failed"**: Run `npm run diagnose-run-failure` for analysis
- **"Equivalence mismatch"**: Review SQL adaptation and DLI output

## Related use cases

- Snowflake to DataArts migration (see `use-cases/snowflake-to-dataarts-migration/`)

## Status

**READY_WITH_WARNINGS** — 6 tools implemented. Write tools require confirm=true. Depends on external DataArts/DLI services. `.env.dataarts` symlink excluded (contains credentials). Comprehensive documentation available in `docs/`.
