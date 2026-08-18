# huaweicloud-drs-mcp

MCP server for Huawei Cloud DRS (Data Replication Service) task management with Playwright automation.

## Purpose

Automate DRS real-time synchronization task lifecycle for cross-region PostgreSQL migration (self-managed PostgreSQL on ECS → Huawei Cloud RDS for PostgreSQL) using the Huawei Cloud console via Playwright.

## Scenario

- **Source**: Self-managed PostgreSQL on ECS (la-south-2 / Santiago)
- **Target**: Huawei Cloud RDS for PostgreSQL (cn-north-4 / Beijing)
- **Migration type**: Real-Time Synchronization, Full + Incremental
- **Network**: Public Network / controlled EIP
- **Known existing task**: `pg-ecs-to-rds-cross-region` in Configuration status with DRS EIP 198.51.100.2

## MCP Tools

| Tool | Purpose |
|------|---------|
| `drs_read_context` | Read current DRS console state (region, page, task status, EIP) |
| `drs_list_tasks` | List DRS tasks with optional filters |
| `drs_find_matching_tasks` | Classify existing tasks as EXACT_MATCH, PARTIAL_MATCH, NAME_ONLY_MATCH, or NOT_MATCHING |
| `drs_select_or_create_task` | Select existing or create new task based on creation_strategy |
| `drs_create_postgresql_full_incremental_task` | Create a new PostgreSQL Full+Incremental DRS task |
| `drs_continue_existing_task` | Open and continue an existing task from its current status |
| `drs_capture_replication_instance_eip` | Read the DRS replication instance EIP |
| `drs_generate_source_access_plan` | Generate SG rules, pg_hba.conf entries, and reload command |
| `drs_run_connection_test` | Run source and target Test Connection |
| `drs_run_precheck` | Run DRS pre-check |
| `drs_start_task` | Start the DRS task (requires explicit_approval) |
| `drs_get_task_status` | Get current task status, phase, progress, delay |
| `drs_generate_report` | Generate non-sensitive Markdown report |

## Task Creation Strategy

The MCP supports four creation strategies:

1. **`reuse_existing`**: Find matching tasks. If exact/partial match exists, select it. If none, BLOCKED.
2. **`create_new`**: Create a new task only if `explicit_approval=true`. Warn if matching task exists.
3. **`ask_if_matching_exists`**: Find matching tasks first. If candidate exists, ask user. If none and approved, create. If none and not approved, return READY_TO_CREATE_PENDING_APPROVAL.
4. **`create_new_even_if_matching_exists`**: Create new task only if `explicit_approval=true` AND `duplicate_task_approval=true`.

## Existing Task Detection

`drs_find_matching_tasks` classifies each existing task:

- **EXACT_MATCH**: All visible fields match the scenario exactly
- **PARTIAL_MATCH**: All visible fields match but some task fields are missing/empty
- **NAME_ONLY_MATCH**: Task name matches but other fields differ
- **NOT_MATCHING**: Task does not match the scenario

## How to Create a New Task

1. Call `drs_find_matching_tasks` to check for existing tasks
2. Call `drs_select_or_create_task` with `creation_strategy="create_new"` and `explicit_approval=true`
3. Or call `drs_create_postgresql_full_incremental_task` directly with `explicit_approval=true`
4. Enter passwords manually in the browser (never stored or printed)
5. Do NOT start the task automatically

## How to Reuse an Existing Task

1. Call `drs_find_matching_tasks` to find matching tasks
2. Call `drs_select_or_create_task` with `creation_strategy="reuse_existing"`
3. Or call `drs_continue_existing_task` with the task name
4. Continue from Configuration: run connection test, pre-check, then start

## How to Avoid Duplicate Tasks

- Always call `drs_find_matching_tasks` before creating
- Use `creation_strategy="ask_if_matching_exists"` (default)
- Duplicate creation requires `duplicate_task_approval=true`
- The MCP never silently creates duplicates

## Required Manual Password Entry

Passwords for source and target databases must be entered manually in the browser. The MCP:
- Does not print passwords
- Does not save passwords
- Does not put passwords into reports
- Pauses for manual secure input in the browser

## Safety Model

- **Default dry-run**: All irreversible actions require `explicit_approval=true`
- **CIDR guard**: Rejects `0.0.0.0/0` and CIDRs broader than `/32` for port 5432
- **Region guard**: Start blocked unless region is `cn-north-4`
- **Pre-check guard**: Start blocked unless pre-check passed
- **Duplicate guard**: Duplicate creation blocked unless `duplicate_task_approval=true`
- **Secret redaction**: Passwords, tokens, AK/SK, private keys are redacted from all output
- **No full DOM reads**: Uses targeted selectors and accessibility snapshots only

## How to Run Locally

```bash
cd /root/migration-lab/huaweicloud-drs-mcp/
npm install
npm start
```

## How to Register in OpenCode

Add to your `opencode.json` or `.opencode/opencode.json`:

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

## Example Calls

### Reuse existing task

```
drs_find_matching_tasks(region="cn-north-4", source_endpoint="198.51.100.1", source_port=5432, source_database="demodb", target_rds_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03", target_database="demodb", sync_mode="Full + Incremental", network_type="Public Network")

drs_select_or_create_task(region="cn-north-4", task_name="pg-ecs-to-rds-cross-region", creation_strategy="reuse_existing")
```

### Create new task

```
drs_create_postgresql_full_incremental_task(
  task_name="drs-pg-santiago-to-beijing-full-incr-demo",
  source_region="la-south-2",
  target_region="cn-north-4",
  source_endpoint="198.51.100.1",
  source_port=5432,
  source_database="demodb",
  source_username="drs_replication",
  target_rds_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03",
  target_database="demodb",
  network_type="Public Network",
  sync_mode="Full + Incremental",
  creation_strategy="create_new",
  explicit_approval=true
)
```

### Ask if matching task exists

```
drs_select_or_create_task(region="cn-north-4", task_name="pg-ecs-to-rds-cross-region", creation_strategy="ask_if_matching_exists")
```

## Known Limitations

- Requires an active browser session with Huawei Cloud console logged in
- Cannot fully automate the DRS creation wizard (password entry is manual)
- Task matching depends on visible fields in the console UI
- Selectors may change if Huawei Cloud updates the DRS console
- Only supports PostgreSQL → PostgreSQL for this scenario
- Does not manage VPN/VPC peering (public network only for DRS connection)

## Troubleshooting

- **Session not active**: Start a browser session and navigate to the DRS console first
- **Task not found**: Verify the region and task name; check filters
- **Start blocked**: Review blockers in the response; ensure all conditions are met
- **Connection test fails**: Verify source SG allows DRS EIP on port 5432; verify pg_hba.conf
- **Pre-check fails**: Review BLOCKING items; resolve before starting
