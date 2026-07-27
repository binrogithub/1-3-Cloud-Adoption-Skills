# Execution Runbook: PostgreSQL ECS to RDS DRS Cross-Region

## Phase 1: Discovery
```
drs_read_context()
drs_list_tasks({ region: "cn-north-4", source_engine: "postgresql" })
drs_find_matching_tasks({ region: "cn-north-4", task_name: "...", ... })
```

## Phase 2: Architecture Validation
- Validate source and target regions differ
- Validate PostgreSQL version compatibility
- Validate source PostgreSQL config (manual: SSH to ECS)

## Phase 3: Readiness
```
drs_generate_source_access_plan({ drs_eip: "...", source_security_group_id: "...", ... })
# Apply SG rules and pg_hba.conf manually
drs_run_connection_test({ region: "cn-north-4", task_name: "..." })
drs_run_precheck({ region: "cn-north-4", task_name: "..." })
```

## Phase 4: Plan Generation
- Generate migration plan with timeline
- Generate rollback plan
- Present for approval

## Phase 5: Approval
- Review and approve migration plan

## Phase 6: Execution
```
drs_create_postgresql_full_incremental_task({ ..., explicit_approval: true })
drs_capture_replication_instance_eip({ region: "cn-north-4", task_name: "..." })
drs_run_connection_test({ region: "cn-north-4", task_name: "..." })
drs_run_precheck({ region: "cn-north-4", task_name: "..." })
drs_start_task({ region: "cn-north-4", task_name: "...", explicit_approval: true })
drs_get_task_status({ region: "cn-north-4", task_name: "..." })
```

## Phase 7: Validation
- Monitor full sync completion
- Validate DDL structure
- Validate row counts
- Test incremental replication

## Phase 8: Cutover
- Stop application writes
- Wait for final incremental sync
- Redirect connections to RDS
- Verify application functionality

## Phase 9: Rollback (if needed)
- Redirect connections to ECS
- Stop DRS task (manual)
- Verify source operational

## Phase 10: Closure
```
drs_generate_report({ region: "cn-north-4", task_name: "..." })
```
- Clean up DRS resources
- Remove source access rules
- Archive migration artifacts
