# huaweicloud-drs-mcp Build Report

**Generated:** 2026-07-08
**MCP Path:** /root/migration-lab/huaweicloud-drs-mcp/
**Build Status:** READY

## Files Created

| File | Purpose |
|------|---------|
| `package.json` | Node.js project config with MCP SDK and Playwright dependencies |
| `server.mjs` | Main MCP server with 13 tool handlers |
| `src/safetyGuards.mjs` | CIDR validation, secret redaction, start/create condition validation |
| `src/taskMatcher.mjs` | Task classification (EXACT/PARTIAL/NAME_ONLY/NOT_MATCHING), matching, strategy resolution |
| `src/playwrightSession.mjs` | Browser session management, navigation, safe text extraction |
| `src/drsConsole.mjs` | DRS console interactions: read context, list tasks, continue, test, precheck, start, status |
| `src/reportWriter.mjs` | Markdown report generation, source access plan generation |
| `examples/santiago-to-beijing-postgresql.json` | Non-sensitive scenario configuration |
| `README.md` | Full documentation |
| `test/safetyGuards.test.mjs` | Safety guard tests (19 assertions) |
| `test/taskMatcher.test.mjs` | Task matcher tests (20 assertions) |
| `test/dryRun.test.mjs` | Dry-run scenario validation tests (12 assertions) |
| `reports/current-drs-context.md` | Report output directory |

## Tools Implemented (13)

1. **drs_read_context** - Read current DRS console state
2. **drs_list_tasks** - List DRS tasks with optional filters
3. **drs_find_matching_tasks** - Classify tasks as EXACT_MATCH, PARTIAL_MATCH, NAME_ONLY_MATCH, NOT_MATCHING
4. **drs_select_or_create_task** - Select existing or create new based on creation_strategy
5. **drs_create_postgresql_full_incremental_task** - Create PostgreSQL Full+Incremental task
6. **drs_continue_existing_task** - Continue existing task from current status
7. **drs_capture_replication_instance_eip** - Read DRS replication instance EIP
8. **drs_generate_source_access_plan** - Generate SG rules, pg_hba.conf, reload command
9. **drs_run_connection_test** - Run source and target Test Connection
10. **drs_run_precheck** - Run DRS pre-check
11. **drs_start_task** - Start DRS task (requires explicit_approval)
12. **drs_get_task_status** - Get task status, phase, progress, delay
13. **drs_generate_report** - Generate non-sensitive Markdown report

## Creation Strategy Support

| Strategy | Behavior |
|----------|----------|
| `reuse_existing` | Select matching task; BLOCKED if none found |
| `create_new` | Create only with explicit_approval; WARNING if duplicate exists |
| `ask_if_matching_exists` | Ask user if match found; create with approval if none |
| `create_new_even_if_matching_exists` | Create with explicit_approval + duplicate_task_approval |

## Existing Task Detection Behavior

- **EXACT_MATCH**: All scenario fields match (all visible, none missing)
- **PARTIAL_MATCH**: All visible fields match but some task fields are missing/empty
- **NAME_ONLY_MATCH**: Task name matches but other fields differ
- **NOT_MATCHING**: No meaningful match

When details are not visible, the classifier marks them as `unknown` rather than guessing, ensuring PARTIAL_MATCH instead of false EXACT_MATCH.

## Known Existing DRS Task Context

| Field | Value |
|-------|-------|
| Region | cn-north-4 / Beijing |
| Task Name | pg-ecs-to-rds-cross-region |
| Status | Configuration |
| DRS EIP | 124.70.109.210 |
| Connection Test | Not run |
| Pre-check | Not run |

This task is classified as EXACT_MATCH against the scenario config.

## Safety Guards

- **CIDR guard**: Rejects 0.0.0.0/0 and CIDRs broader than /32 for port 5432
- **Start guard**: Requires explicit_approval=true, correct region, passed connection test, passed pre-check
- **Create guard**: Requires explicit_approval=true; duplicate_task_approval=true for duplicates
- **Secret redaction**: Passwords, tokens, AK/SK, private keys redacted from all output
- **No full DOM reads**: Uses targeted selectors and accessibility snapshots only
- **Dry-run default**: All irreversible actions default to dry-run

## Test Results

```
tests 58
suites 8
pass 58
fail 0
cancelled 0
skipped 0
```

All 58 tests pass across 8 test suites:
- safetyGuards - redactSecrets (7 tests)
- safetyGuards - rejectBroadCidr (8 tests)
- safetyGuards - validateStartConditions (7 tests)
- safetyGuards - validateCreateConditions (4 tests)
- taskMatcher - classifyTaskMatch (5 tests)
- taskMatcher - findMatchingTasks (4 tests)
- taskMatcher - resolveCreationStrategy (11 tests)
- dryRun - full scenario validation (12 tests)

## How to Register in OpenCode

Add to `opencode.json` or `.opencode/opencode.json`:

```json
{
  "mcpServers": {
    "huaweicloud-drs": {
      "command": "node",
      "args": ["/root/migration-lab/huaweicloud-drs-mcp/server.mjs"]
    }
  }
}
```

## Example Usage

### Reuse existing task

```
drs_find_matching_tasks(region="cn-north-4", source_endpoint="110.238.67.209", source_port=5432, source_database="demodb", target_rds_id="82a6795906de4c6db33e1c0e96594840in03", target_database="demodb", sync_mode="Full + Incremental", network_type="Public Network")

drs_select_or_create_task(region="cn-north-4", task_name="pg-ecs-to-rds-cross-region", creation_strategy="reuse_existing")
```

### Create new task

```
drs_create_postgresql_full_incremental_task(
  task_name="drs-pg-santiago-to-beijing-full-incr-demo",
  target_region="cn-north-4",
  creation_strategy="create_new",
  explicit_approval=true
)
```

### Ask if matching task exists

```
drs_select_or_create_task(region="cn-north-4", task_name="pg-ecs-to-rds-cross-region", creation_strategy="ask_if_matching_exists")
```

## Safety Confirmations

- **No credentials were printed or stored** during MCP build or in any report
- **Port 5432 was not opened to 0.0.0.0/0** - CIDR guard rejects this explicitly
- **No duplicate task was created** during MCP build - no task creation was attempted
- **The existing DRS task was not started** during MCP build - no start was attempted
- **All irreversible actions default to dry-run** without explicit_approval=true
