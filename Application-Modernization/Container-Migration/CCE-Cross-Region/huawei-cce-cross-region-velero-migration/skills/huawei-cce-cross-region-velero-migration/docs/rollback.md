# Rollback Procedure

## Immediate Rollback (< 5 minutes)
1. Revert DNS records to source cluster
2. Verify traffic routing to source
3. Monitor source cluster health

## Full Rollback (< 30 minutes)
1. Revert DNS records
2. Stop traffic to target cluster
3. Delete restored resources on target: `velero restore delete <restore-name>`
4. Destroy target infrastructure: `terraform destroy`
5. Verify source cluster operational

## Partial Rollback
1. Identify failed components
2. Roll back only affected namespaces
3. Keep successfully migrated namespaces on target
4. Update DNS for rolled-back namespaces only
