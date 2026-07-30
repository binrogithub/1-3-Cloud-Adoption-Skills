# Rollback Workflow

## Objective
Revert migration if validation fails.

## Steps
1. Redirect application connections to source
2. Stop DRS task (MANUAL console operation)
3. Verify source database operational
4. Clean up if needed
5. Document rollback

## Automation Level
MANUAL — DRS task stop not available in MCP

## MCP Tools
None for rollback operations

## Capability Gap
- GAP-PG-003: No MCP tool for DRS task stop
