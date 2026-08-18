# Readiness Workflow

## Objective
Verify all prerequisites and run pre-migration checks.

## Steps
1. Generate source access plan (SG rules, pg_hba.conf)
2. Apply source access changes (MANUAL)
3. Run connection test
4. Run DRS pre-check
5. Review and address findings

## Automation Level
ASSISTED — MCP generates plans, human applies changes

## MCP Tools
- drs_generate_source_access_plan
- drs_run_connection_test
- drs_run_precheck
