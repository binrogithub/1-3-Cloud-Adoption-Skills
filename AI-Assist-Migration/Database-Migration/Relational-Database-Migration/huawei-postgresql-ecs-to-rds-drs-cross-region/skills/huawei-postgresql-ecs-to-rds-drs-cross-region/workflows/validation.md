# Validation Workflow

## Objective
Validate migration success through DRS monitoring and data verification.

## Steps
1. Monitor DRS task status
2. Wait for full sync completion
3. Validate DDL structure (MANUAL)
4. Validate row counts (MANUAL)
5. Test incremental replication (MANUAL)
6. Generate DRS report

## Automation Level
ASSISTED — MCP monitors, human validates data

## MCP Tools
- drs_get_task_status
- drs_generate_report
