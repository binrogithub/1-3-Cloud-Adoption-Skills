# DWS Cluster Discovery Prompt

## Instructions

You are performing discovery for a DWS cluster deployment. This phase is READ-ONLY.

## Rules

1. Do NOT create any resources
2. Do NOT request passwords
3. Do NOT modify any existing resources
4. Only read and report

## Steps

1. **Verify hcloud CLI and authentication**
   - Run: `hcloud DWS ListClusters --cli-region=<REGION>`
   - Confirm: Command succeeds without auth error

2. **Discover existing clusters**
   - Run: `hcloud DWS ListClusters --cli-region=<REGION>`
   - Report: All existing clusters with names, statuses, and IDs

3. **Discover node types**
   - Run: `hcloud DWS ListNodeTypes --cli-region=<REGION>`
   - Report: All available node types with CPU, memory, and storage details

4. **Discover network resources**
   - Run: `hcloud VPC ListVpcs --cli-region=<REGION>`
   - Run: `hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>`
   - Run: `hcloud VPC ListSecurityGroups --cli-region=<REGION>`
   - Report: Available VPCs, subnets (with IP capacity), security groups

5. **Check for conflicts**
   - If cluster name matches existing: report CONFLICT
   - If multiple matches: report AMBIGUOUS

6. **Generate discovery report**
   - Summarize: available capabilities, existing resources, conflicts
   - Recommend: node type selection, network configuration

## Output

Generate artifacts:
- artifacts/dws-auth-context.md
- artifacts/dws-existing-clusters.json
- artifacts/dws-capability-matrix.md
- artifacts/dws-network-discovery.json
