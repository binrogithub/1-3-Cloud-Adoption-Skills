# Execution Workflow

## Objective
Execute Velero backup on source and restore on target cluster.

## Steps
1. Apply Terraform for target infrastructure (MANUAL)
2. Execute Velero backup on source
3. Wait for backup completion
4. Verify backup in OBS
5. Execute Velero restore on target
6. Wait for restore completion
7. Verify restored resources

## Automation Level
MANUAL — Velero CLI commands executed by human

## MCP Tools
None available for Velero operations

## Capability Gaps
- GAP-CCE-002: No MCP tool for Velero backup/restore
- GAP-CCE-007: CCE not in deploy MCP supported services

## Safety
- All operations require explicit approval
- terraform apply is BLOCKED in deploy MCP (by design)
- Velero backup includes --snapshot-volumes=false for metadata-only
