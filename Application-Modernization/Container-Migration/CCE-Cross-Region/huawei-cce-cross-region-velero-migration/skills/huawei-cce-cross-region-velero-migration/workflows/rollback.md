# Rollback Workflow

## Objective
Revert migration if validation fails or issues are discovered.

## Steps
1. Revert DNS records to source cluster
2. Verify traffic routing to source
3. Delete Velero restore on target
4. Destroy target infrastructure (terraform destroy)
5. Verify source cluster operational
6. Document rollback reason

## Automation Level
MANUAL — DNS, Velero, and Terraform operations by human

## MCP Tools
None available for rollback operations

## Safety
- Rollback DNS FIRST to restore source traffic
- Never delete source cluster resources during rollback
