# DWS Cluster Deployment Rollback

## Principles

1. Do NOT automatically delete a failed cluster.
2. Do NOT automatically re-execute CreateCluster.
3. Original resources must be preserved.
4. Each component has independent rollback considerations.

## Rollback Scenarios

### CreateCluster Failed

- The cluster may be in FAILED state or partially created.
- **Action**: Inspect via `hcloud DWS ShowClusters`. Do NOT auto-delete.
- **Decision**: Manual — delete after review, or contact support.
- **Verification**: Check billing for partial resources.

### CreateCluster Timeout

- The cluster may still be creating.
- **Action**: Continue polling or investigate manually.
- **Decision**: Manual — wait, investigate, or delete.
- **Do NOT**: Assume failure and auto-delete.

### Network Prerequisites Created

- If VPC, subnet, or security group were created for this deployment:
  - VPC rollback is independent of cluster rollback.
  - Security group rollback is independent.
  - **Action**: Evaluate whether to keep or delete.
  - **Decision**: Manual with approval.
  - **Risk**: Other resources may depend on the VPC/subnet.

### EIP Binding

- EIP rollback is independent of cluster rollback.
- **Action**: Unbind EIP if cluster creation failed.
- **Decision**: Manual with approval.
- **Risk**: EIP may have costs.

### Snapshot Operations

- Snapshots are NOT deleted automatically during rollback.
- **Action**: Evaluate snapshot retention.
- **Decision**: Manual with approval.

### RestoreCluster

- Restore creates a NEW cluster — never executed automatically.
- **Action**: If restore was initiated, monitor the new cluster.
- **Decision**: Manual with approval.

### Database/Schema Changes

- Database and schema changes require a separate rollback plan.
- **Action**: Prepare DDL rollback scripts before execution.
- **Decision**: Manual with approval.

## Rollback Order (if full rollback is approved)

1. Unbind EIP (if bound)
2. Delete cluster (with explicit approval, after snapshot)
3. Delete security group (if created for this deployment)
4. Delete subnet (if created for this deployment)
5. Delete VPC (if created for this deployment)

**Each step requires explicit approval.**

## Verification After Rollback

- Confirm cluster is deleted: `hcloud DWS ListClusters`
- Confirm no orphaned resources
- Confirm billing stopped for deleted resources
