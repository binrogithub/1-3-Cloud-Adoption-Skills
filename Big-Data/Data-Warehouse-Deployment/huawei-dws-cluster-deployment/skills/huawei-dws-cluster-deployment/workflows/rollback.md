# Rollback Workflow

## Purpose

Safely reverse or mitigate a failed DWS cluster deployment without causing additional damage.

## Inputs

- Cluster ID (if created)
- Network resource IDs (if created)
- Deployment artifacts
- Failure context

## Steps

1. **Assess failure context**
   - Determine which steps completed successfully
   - Determine which resources were created
   - Determine cluster state (CREATING, FAILED, AVAILABLE, etc.)
   - Approval: None
   - Output: Failure assessment

2. **Handle cluster in CREATING state**
   - If cluster is still creating: continue polling or wait
   - Do NOT auto-delete
   - Approval: Required for any action
   - Output: Decision

3. **Handle cluster in FAILED state**
   - Inspect error details via `hcloud DWS ShowClusters`
   - Do NOT auto-delete
   - Consider creating support ticket via huaweicloud-ticket MCP
   - Approval: Required for deletion
   - Output: Error details

4. **Handle cluster in AVAILABLE state** (partial deployment failure)
   - Cluster was created but subsequent steps failed
   - Evaluate: keep cluster (fix issues) or delete (start over)
   - If deleting: create snapshot first
   - Approval: Required for deletion
   - Output: Decision

5. **Rollback EIP** (if bound)
   - Unbind EIP from cluster
   - EIP rollback is independent of cluster rollback
   - Approval: Required
   - Output: EIP status

6. **Rollback security group changes** (if modified)
   - Remove any rules added for this deployment
   - Security group rollback is independent
   - Approval: Required
   - Output: SG status

7. **Rollback network resources** (if created for this deployment)
   - Evaluate: VPC, subnet, security group
   - Check for other dependent resources before deleting
   - Approval: Required for each deletion
   - Output: Network resource status

8. **Preserve snapshots**
   - Snapshots are NOT deleted automatically
   - Evaluate retention
   - Approval: Required for snapshot deletion
   - Output: Snapshot status

9. **Preserve database changes**
   - Database/schema changes require separate rollback plan
   - Prepare DDL rollback scripts
   - Approval: Required
   - Output: Rollback SQL

10. **Generate rollback report**
    - Document all actions taken
    - Document remaining resources
    - Document billing implications
    - Approval: None
    - Output: Rollback report

## Outputs

- Rollback report with all actions and remaining resources

## Principles

1. Do NOT automatically delete a failed cluster
2. Do NOT automatically re-execute CreateCluster
3. Original resources must be preserved
4. Each component has independent rollback
5. Every deletion requires explicit approval
6. Create snapshot before deleting any cluster
7. Verify billing after rollback

## Stop Conditions

- Uncertain cluster state — stop and escalate
- Approval denied for required action
- Dependent resources prevent deletion
