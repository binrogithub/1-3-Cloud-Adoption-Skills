# Discovery Workflow

## Purpose

Discover existing DWS resources, available capabilities, and network prerequisites before any write operations.

## Inputs

- Region
- Cluster name (for conflict check)
- VPC name, subnet name, security group name (for resolution)

## Steps

1. **Verify hcloud CLI and authentication**
   - Command: `hcloud DWS ListClusters --cli-region=<REGION>`
   - Approval: None
   - Verification: Command succeeds
   - Output: Auth context

2. **Discover existing clusters**
   - Command: `hcloud DWS ListClusters --cli-region=<REGION>`
   - Approval: None
   - Verification: Response received
   - Output: Cluster list
   - Stop: Multiple name matches

3. **Discover node types**
   - Command: `hcloud DWS ListNodeTypes --cli-region=<REGION>`
   - Approval: None
   - Verification: Non-empty response
   - Output: Node type list with CPU, memory, storage

4. **Discover updatable versions** (if existing cluster)
   - Command: `hcloud DWS ListUpdatableVersion --cli-region=<REGION> --cluster_id=<ID>`
   - Approval: None
   - Verification: Response received
   - Output: Version list

5. **Discover VPC**
   - Command: `hcloud VPC ListVpcs --cli-region=<REGION>`
   - Approval: None
   - Verification: Target VPC found
   - Output: VPC ID

6. **Discover subnet**
   - Command: `hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>`
   - Approval: None
   - Verification: Target subnet found, sufficient IPs
   - Output: Subnet ID, available IP count

7. **Discover security group**
   - Command: `hcloud VPC ListSecurityGroups --cli-region=<REGION>`
   - Approval: None
   - Verification: Target SG found, no 0.0.0.0/0 on DWS port
   - Output: Security group ID

8. **Discover EIP** (if public access required)
   - Command: `hcloud VPC ListPublicIps --cli-region=<REGION>`
   - Approval: None
   - Verification: EIP available or quota sufficient
   - Output: EIP list

## Outputs

- artifacts/dws-auth-context.md
- artifacts/dws-existing-clusters.json
- artifacts/dws-capability-matrix.md
- artifacts/dws-network-discovery.json

## Stop Conditions

- Authentication failure
- DWS service unavailable
- Multiple cluster name matches
- No node types available
- VPC/subnet/SG not found
- Insufficient IP capacity
- 0.0.0.0/0 in security group

## Failure Handling

- Report the specific failure
- Suggest remediation
- Do NOT create resources during discovery
