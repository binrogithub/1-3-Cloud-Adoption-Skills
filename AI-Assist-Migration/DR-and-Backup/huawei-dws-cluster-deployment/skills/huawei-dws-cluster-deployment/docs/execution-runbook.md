# DWS Cluster Deployment Execution Runbook

## Step 1: Parse Intent

Extract all deployment parameters from user request. Validate required fields. Generate `artifacts/dws-intent.json`.

## Step 2: Verify Authentication and Service

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

Confirm authentication and DWS service availability. Generate `artifacts/dws-auth-context.md`.

## Step 3: Discover Existing Clusters

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

Check for name conflicts. 0 matches = proceed; 1 exact = evaluate reuse; multiple = STOP.

## Step 4: Discover Capabilities

```bash
hcloud DWS ListNodeTypes --cli-region=<REGION>
```

Record available node types, CPU, memory, storage types. Do NOT hardcode flavors.

## Step 5: Discover Network

```bash
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<REGION>
```

Resolve names to IDs. Validate IP capacity. Reject 0.0.0.0/0.

## Step 6: Capacity and Cost Plan

Build capacity plan. Optionally use huaweicloud-pricing MCP for cost estimation.

## Step 7: Architecture Plan

Design complete architecture. Classify components as EXISTING, REUSE, CREATE_WITH_DEPLOY_MCP, CREATE_WITH_HCLOUD, MANUAL, NOT_REQUIRED, or BLOCKED.

## Step 8: Readiness Check

Validate all prerequisites and quotas. Result: READY, READY_WITH_WARNINGS, NOT_READY, or BLOCKED.

## Step 9: Prepare Network Prerequisites

If VPC/subnet/SG exist, validate and reuse. If missing, plan creation via huaweicloud-deploy MCP or hcloud CLI. Security group: DWS port only from authorized CIDR, never 0.0.0.0/0.

## Step 10: Prepare Secure Credentials

Establish secure password input mechanism. Prefer `--cli-jsonInput`. If using temp file: 0600 permissions, outside repo, secure deletion.

## Step 11: Create Cluster

**Requires explicit approval.**

```bash
hcloud DWS CreateCluster --cli-region=<REGION> \
  --cluster.name=<CLUSTER_NAME> \
  --cluster.node_type=<NODE_TYPE> \
  --cluster.number_of_node=<NODE_COUNT> \
  --cluster.security_group_id=<SG_ID> \
  --cluster.subnet_id=<SUBNET_ID> \
  --cluster.user_name=<USERNAME> \
  --cluster.user_pwd=<SECURE_INPUT> \
  --cluster.vpc_id=<VPC_ID> \
  [--cluster.availability_zone=<AZ>] \
  [--cluster.port=<PORT>] \
  [--cluster.number_of_cn=<CN_COUNT>] \
  [--cluster.enterprise_project_id=<EPS_ID>]
```

**Verification:**

```bash
hcloud DWS ListClusters --cli-region=<REGION>
```

## Step 12: Poll Cluster Creation

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
```

Poll until cluster reaches operational state. Set timeout and failure handling. Do NOT hardcode 15-30 min as SLA.

## Step 13: Verify Cluster

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
hcloud DWS ListClusterDetails --cli-region=<REGION>
hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
```

Validate all configuration parameters match expected values.

## Step 14: Configure Public Access (Optional)

**Requires explicit approval.**

Bind EIP and configure security group rule. Never open to 0.0.0.0/0.

## Step 15: Verify Database Connectivity

```bash
psql -h <ENDPOINT> -p <PORT> -U <USERNAME> -d <DATABASE> -c "SELECT version();"
```

Do NOT include password in command. Do NOT execute during skill generation.

## Step 16: Create Database and Schemas

Execute SQL DDL via psql or JDBC. Requires approval. Do NOT assume full PostgreSQL compatibility.

## Step 17: OBS Data Load (Optional)

Create external tables and INSERT SELECT. Validate OBS access, format, and syntax against DWS version.

## Step 18: Configure Snapshot Policy

```bash
hcloud DWS ListSnapshots --cli-region=<REGION>
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
hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
hcloud DWS ShowResourceStatistics --cli-region=<REGION>
```

## Step 20: Closure

Generate final report with architecture, status, connectivity, capacity, cost, warnings, and follow-up actions.
