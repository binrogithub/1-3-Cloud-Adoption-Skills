# huaweicloud-drs

## Purpose

MCP server for Huawei Cloud DRS (Data Replication Service) task management with Playwright-based console automation. Enables creation, configuration, and monitoring of database migration tasks — primarily PostgreSQL self-managed on ECS to RDS for PostgreSQL, including cross-region scenarios using public network (EIP).

## Scope

**Includes:**
- DRS task listing and matching
- Task creation with duplicate detection and explicit approval gates
- Connection testing and pre-check execution
- Task status monitoring and reporting
- Source access plan generation (Security Group, pg_hba.conf)
- Replication instance EIP capture
- Task start with validation and explicit approval

**Does not include:**
- Direct database migration execution (DRS service handles this)
- Schema migration or DDL transformation
- VPN/VPC peering configuration
- Automatic rollback of running migrations
- DRS task deletion or forced stop

## Use cases

1. **PostgreSQL ECS to RDS cross-region migration** — Full+Incremental migration via DRS with public network [VERIFIED_FROM_CODE] [VERIFIED_FROM_DOCUMENTATION]
2. **DRS task lifecycle management** — Create, configure, test, start, and monitor tasks [VERIFIED_FROM_CODE]
3. **Source access planning** — Generate Security Group rules and pg_hba.conf entries for DRS [VERIFIED_FROM_CODE]
4. **Task deduplication** — Detect and reuse existing matching tasks [VERIFIED_FROM_CODE]
5. **Migration validation** — Pre-check and connection test before starting replication [VERIFIED_FROM_CODE]

## Architecture

- **Runtime:** Node.js (ESM)
- **Entry point:** `src/server.mjs`
- **Transport:** stdio (MCP SDK)
- **Core modules:**
  - `src/server.mjs` — Main MCP server with 13 tool handlers
  - `src/drsConsole.mjs` — Playwright automation for DRS console operations
  - `src/playwrightSession.mjs` — Playwright browser session management
  - `src/safetyGuards.mjs` — Safety validation (CIDR checks, approval gates)
  - `src/taskMatcher.mjs` — Task matching and deduplication logic
  - `src/reportWriter.mjs` — Non-sensitive report generation
- **Dependencies:** `@modelcontextprotocol/sdk`, `playwright`
- **Automation:** Playwright browser automation for DRS console (no REST API available for DRS v5 task creation)

## MCP tools exposed

| # | Tool name | Purpose | Read/Write | Risk | Approval required |
|---|-----------|---------|------------|------|-------------------|
| 1 | drs_read_context | Read current DRS console state | read-only | none | no |
| 2 | drs_list_tasks | List DRS tasks with filters | read-only | none | no |
| 3 | drs_find_matching_tasks | Search and classify existing tasks | read-only | none | no |
| 4 | drs_select_or_create_task | Select existing or create new task | write | high | yes (explicit_approval) |
| 5 | drs_create_postgresql_full_incremental_task | Create PostgreSQL Full+Incremental task | write | high | yes (explicit_approval) |
| 6 | drs_continue_existing_task | Continue from current task status | read-only | none | no |
| 7 | drs_capture_replication_instance_eip | Read replication instance EIP | read-only | none | no |
| 8 | drs_generate_source_access_plan | Generate source access changes plan | read-only | none | no |
| 9 | drs_run_connection_test | Run connection test | read-only | low | no |
| 10 | drs_run_precheck | Run DRS pre-check | read-only | low | no |
| 11 | drs_start_task | Start DRS task | write | critical | yes (explicit_approval) |
| 12 | drs_get_task_status | Get task status and progress | read-only | none | no |
| 13 | drs_generate_report | Generate non-sensitive task report | read-only | none | no |

## Prerequisites

- Node.js >= 18
- Playwright browsers installed (`npx playwright install chromium`)
- Huawei Cloud console access (cookies/cftk for Playwright)
- DRS service enabled in target region

## Installation

```bash
cd mcps/huaweicloud-drs
npm install
npx playwright install chromium
```

## Configuration

```bash
export HWCLOUD_REGION=<YOUR_REGION>
# Playwright session requires console cookies and CSRF token
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| HWCLOUD_REGION | yes | Default region for DRS operations |

## Execution

```bash
node src/server.mjs
```

## Integration with OpenCode

```json
{
  "huaweicloud-drs": {
    "type": "local",
    "enabled": true,
    "command": ["node", "<INSTALLATION_ROOT>/mcps/huaweicloud-drs/src/server.mjs"],
    "timeout": 60000
  }
}
```

## Examples

```bash
# List DRS tasks
# Tool: drs_list_tasks
# Parameters: { region: "la-north-2" }

# Create PostgreSQL migration task
# Tool: drs_create_postgresql_full_incremental_task
# Parameters: { task_name: "pg-ecs-to-rds", target_region: "cn-north-4", source_region: "la-north-2", explicit_approval: true }

# Run pre-check
# Tool: drs_run_precheck
# Parameters: { region: "cn-north-4", task_name: "pg-ecs-to-rds" }

# Start task
# Tool: drs_start_task
# Parameters: { region: "cn-north-4", task_name: "pg-ecs-to-rds", explicit_approval: true }
```

## Tests

```bash
npm test
```

3 test files: safetyGuards.test.mjs, taskMatcher.test.mjs, dryRun.test.mjs

## Security

- **3 write tools require explicit_approval=true** — task creation and start are gated [VERIFIED_FROM_CODE]
- Safety guards reject 0.0.0.0/0 and CIDRs broader than /32 [VERIFIED_FROM_CODE]
- Task deduplication prevents accidental duplicate creation [VERIFIED_FROM_CODE]
- Reports are non-sensitive — no credentials printed [VERIFIED_FROM_CODE]
- Playwright session requires manual console authentication

## Limitations

- DRS v5 task creation requires Playwright console automation (no REST API)
- Cross-region uses public network (EIP) as the supported architecture; VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO
- Source PostgreSQL must have wal_level=logical and replication slots
- Playwright browser must be installed and maintained
- Console UI changes may break automation selectors

## Troubleshooting

- **"Playwright session invalid"**: Re-initialize session with `init_session` providing fresh cookies/cftk
- **"Task creation failed"**: Verify DRS service is enabled and quotas are available
- **"Connection test failed"**: Check Security Group rules, pg_hba.conf, and EIP connectivity
- **"Pre-check warnings"**: Review BLOCKING items before starting task

## Related use cases

- PostgreSQL ECS to RDS cross-region migration (see `use-cases/postgresql-ecs-to-rds-cross-region/`)

## Status

**READY_WITH_WARNINGS** — 13 tools implemented. Write tools require explicit approval. Playwright dependency requires browser installation. 3 test files available. Cross-region migration validated in demo scenario.
