# DWS Cluster Recovery Prompt

## Instructions

You are recovering from a failed or interrupted DWS cluster deployment. This phase is primarily READ-ONLY with selective manual actions.

## Rules

1. Discover existing cluster state first — do NOT assume
2. Do NOT repeat CreateCluster
3. Do NOT auto-delete any cluster
4. Do NOT re-create EIP
5. Do NOT duplicate snapshots
6. Preserve all evidence
7. Stop if cluster state is uncertain

## Steps

1. **Discover existing cluster**
   - Run: `hcloud DWS ListClusters --cli-region=<REGION>`
   - Identify: target cluster by name
   - Report: current status

2. **Inspect cluster state**
   - If AVAILABLE: deployment may have succeeded — validate
   - If CREATING: continue polling if safe
   - If FAILED: inspect error details
   - If UNKNOWN: STOP and escalate

3. **Continue polling** (if CREATING)
   - Run: `hcloud DWS ShowClusters --cli-region=<REGION>`
   - Set: reasonable timeout
   - Do NOT: assume failure and auto-delete

4. **Inspect failed cluster**
   - Run: `hcloud DWS ShowClusters --cli-region=<REGION>`
   - Run: `hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>`
   - Report: error details, node states
   - Do NOT: auto-delete

5. **Check network resources**
   - Verify: VPC, subnet, security group still exist
   - Do NOT: modify or delete network resources

6. **Check EIP state**
   - Verify: EIP binding state
   - Do NOT: re-bind or unbind without approval

7. **Check snapshots**
   - Run: `hcloud DWS ListSnapshots --cli-region=<REGION>`
   - Do NOT: delete or create snapshots without approval

8. **Generate recovery report**
   - Document: current state, recommended actions, risks
   - Recommend: manual steps or support ticket

## Stop Conditions

- Cluster state is uncertain or unknown
- Multiple clusters match the name
- Approval denied for recommended action
- Dependent resources prevent safe recovery
