# Validation Workflow

## Purpose

Validate the deployed DWS cluster meets all requirements and is operationally ready.

## Inputs

- Cluster ID
- Expected configuration
- Endpoint and port

## Steps

1. **Validate cluster configuration**
   - Command: `hcloud DWS ShowClusters --cli-region=<REGION>`
   - Verify: region, AZ, version, node_type, node_count, storage, VPC, subnet, SG, port, public_access
   - Approval: None
   - Output: Configuration validation result

2. **Validate cluster nodes**
   - Command: `hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>`
   - Verify: All nodes healthy, correct count
   - Approval: None
   - Output: Node validation result

3. **Validate cluster details**
   - Command: `hcloud DWS ListClusterDetails --cli-region=<REGION>`
   - Verify: Detailed configuration matches
   - Approval: None
   - Output: Detail validation result

4. **Validate resource statistics**
   - Command: `hcloud DWS ShowResourceStatistics --cli-region=<REGION>`
   - Verify: Storage usage within expected range
   - Approval: None
   - Output: Resource statistics

5. **Validate connectivity**
   - Test: psql/JDBC connection to endpoint
   - Verify: SELECT version() succeeds
   - Approval: Required (manual step)
   - Output: Connectivity result

6. **Validate security group**
   - Command: `hcloud VPC ListSecurityGroupRules --cli-region=<REGION> --security_group_id=<SG_ID>`
   - Verify: No 0.0.0.0/0 on DWS port
   - Approval: None
   - Output: Security validation result

7. **Validate EIP** (if applicable)
   - Verify: EIP bound, accessible from authorized source
   - Approval: None
   - Output: EIP validation result

8. **Validate snapshots**
   - Command: `hcloud DWS ListSnapshots --cli-region=<REGION>`
   - Verify: Expected snapshots exist and are available
   - Approval: None
   - Output: Snapshot validation result

9. **Validate monitoring**
   - Verify: Cloud Eye or LTS monitoring configured
   - Approval: None
   - Output: Monitoring validation result

10. **Generate operational validation report**
    - Compile all validation results
    - Approval: None
    - Output: artifacts/dws-operational-validation-report.md

## Outputs

- artifacts/dws-cluster-validation-report.md
- artifacts/dws-operational-validation-report.md

## Stop Conditions

- Configuration mismatch
- Node health failure
- Connectivity failure
- Security group violation

## Failure Handling

- Report specific validation failure
- Suggest remediation
- Do NOT execute unauthorized load tests
