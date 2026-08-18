# Execution Workflow

## Objective
Create and start DRS task for Full + Incremental migration.

## Steps
1. Create DRS task (requires explicit_approval=true)
2. Capture DRS replication instance EIP
3. Update source access if needed
4. Re-run connection test
5. Re-run pre-check
6. Start DRS task (requires explicit_approval=true)
7. Monitor task progress

## Automation Level
ASSISTED — MCP executes with approval gates

## MCP Tools
- drs_select_or_create_task OR drs_create_postgresql_full_incremental_task
- drs_capture_replication_instance_eip
- drs_run_connection_test
- drs_run_precheck
- drs_start_task
- drs_get_task_status

## Safety
- All write operations require explicit_approval=true
- CIDR /32 enforced
- Pre-check must pass before start
