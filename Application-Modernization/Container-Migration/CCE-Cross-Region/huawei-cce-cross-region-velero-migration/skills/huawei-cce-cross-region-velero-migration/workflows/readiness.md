# Readiness Workflow

## Objective
Verify all prerequisites are met before migration execution.

## Steps
1. Verify Velero on source cluster
2. Verify Velero on target cluster
3. Verify OBS bucket accessibility
4. Verify IAM permissions
5. Verify target cluster capacity
6. Verify StorageClass availability
7. Verify network connectivity

## Automation Level
MANUAL — All checks require Velero CLI and kubectl execution

## MCP Tools
None available for Velero/CCE readiness checks

## Capability Gaps
- GAP-CCE-002: No MCP tool for Velero readiness check
