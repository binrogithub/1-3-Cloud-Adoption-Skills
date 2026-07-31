# DWS Cluster Deployment Example

This example shows a sanitized walkthrough of deploying a DWS cluster.

## Parameters

| Parameter | Value |
|---|---|
| Region | `<REGION>` |
| Cluster name | `<DWS_CLUSTER_NAME>` |
| Environment | `<ENVIRONMENT>` |
| Version | discovered |
| Node type | discovered |
| Node count | `<NODE_COUNT>` |
| Storage | discovered |
| VPC | `<VPC_NAME>` |
| Subnet | `<SUBNET_NAME>` |
| Security group | `<SECURITY_GROUP_NAME>` |
| Access | private |
| Database | `<DATABASE_NAME>` |
| Snapshot policy | `<SNAPSHOT_POLICY_NAME>` |

## Step 1: Parse Intent

Extract deployment requirements. No password in plain text.

## Step 2: Verify Authentication

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

Expected: Successful response (may be empty list).

## Step 3: Discover Existing Clusters

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

Expected: No cluster with name `<DWS_CLUSTER_NAME>`. If found, evaluate reuse or conflict.

## Step 4: Discover Capabilities

```bash
hcloud DWS ListNodeTypes --cli-region=<REGION>
```

Expected: List of available node types. Select appropriate type for workload.

## Step 5: Discover Network

```bash
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<REGION>
```

Expected: VPC, subnet, and security group found. Resolve names to IDs. Validate IP capacity.

## Step 6: Capacity and Cost Plan

Calculate: CPU total, memory total, storage total, estimated monthly cost.

## Step 7: Architecture Plan

Design: cluster configuration, network, access, snapshots, monitoring.

## Step 8: Readiness Check

Validate: quotas, node type availability, AZ availability, version availability, password mechanism, naming.

## Step 9: Prepare Network Prerequisites

If VPC/subnet/SG exist: validate and reuse. If missing: plan creation (requires approval).

## Step 10: Prepare Secure Credentials

Use `--cli-jsonInput` for password. Example JSON input file:

```json
{
  "cluster.name": "<DWS_CLUSTER_NAME>",
  "cluster.node_type": "<NODE_TYPE>",
  "cluster.number_of_node": <NODE_COUNT>,
  "cluster.security_group_id": "<SG_ID>",
  "cluster.subnet_id": "<SUBNET_ID>",
  "cluster.user_name": "<USERNAME>",
  "cluster.user_pwd": "<SECURE_PASSWORD>",
  "cluster.vpc_id": "<VPC_ID>"
}
```

**Delete the JSON file after use. Never commit it.**

## Step 11: Create Cluster (Approval Required)

```bash
hcloud DWS CreateCluster --cli-region=<REGION> \
  --cluster.name=<DWS_CLUSTER_NAME> \
  --cluster.node_type=<NODE_TYPE> \
  --cluster.number_of_node=<NODE_COUNT> \
  --cluster.security_group_id=<SG_ID> \
  --cluster.subnet_id=<SUBNET_ID> \
  --cluster.user_name=<USERNAME> \
  --cluster.user_pwd=<SECURE_INPUT> \
  --cluster.vpc_id=<VPC_ID>
```

**Verification:**

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

## Step 12: Poll Cluster Creation

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
```

Poll until cluster reaches operational state. Set timeout and failure handling.

## Step 13: Verify Cluster

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
hcloud DWS ListClusterDetails --cli-region=<REGION>
hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
```

## Step 14: Configure Public Access (Not in this example — private access only)

## Step 15: Verify Connectivity

```bash
psql -h <ENDPOINT> -p 8000 -U <USERNAME> -d <DATABASE_NAME> -c "SELECT version();"
```

**Do NOT include password in the command.**

## Step 16: Create Database and Schemas

```sql
CREATE DATABASE <DATABASE_NAME>;
-- Additional schema DDL as needed
```

## Step 17: OBS Data Load (Not in this example)

## Step 18: Configure Snapshot Policy

```bash
hcloud DWS CreateSnapshot --cli-region=<REGION> \
  --snapshot.cluster_id=<CLUSTER_ID> \
  --snapshot.name=<SNAPSHOT_NAME>
```

**Verification:**

```bash
hcloud DWS ListSnapshots --cli-region=<REGION>
```

## Step 19: Operational Validation

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
hcloud DWS ShowResourceStatistics --cli-region=<REGION>
```

## Step 20: Closure

Generate final report with all deployment details, validation results, and follow-up actions.
