# Rollback Workflow
## Objective
Revert migration if validation fails.
## Steps
1. Diagnose failure via status
2. Clean up DataArts/DLI resources (manual)
3. Revert to Snowflake
## Automation Level
MANUAL
## MCP Tools
- snowflake_dataarts_demo_status (diagnosis only)
