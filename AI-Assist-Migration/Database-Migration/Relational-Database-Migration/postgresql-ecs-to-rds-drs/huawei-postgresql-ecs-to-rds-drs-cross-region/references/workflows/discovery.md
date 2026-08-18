# Discovery Workflow

## Objective
Discover existing DRS tasks and source/target environment state.

## Steps
1. Read DRS console context
2. List existing DRS tasks for PostgreSQL
3. Find matching tasks for the migration scenario
4. Document current state

## Automation Level
AUTOMATED — All steps use DRS MCP read tools

## MCP Tools
- drs_read_context
- drs_list_tasks
- drs_find_matching_tasks
