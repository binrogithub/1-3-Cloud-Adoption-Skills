# DWS Cluster Deployment Validation

## Pre-Deployment Validation

1. **Authentication**: hcloud CLI authenticated and DWS service accessible
2. **Region**: DWS service available in target region
3. **Node types**: At least one node type available in region
4. **Network**: VPC, subnet, security group exist and are valid
5. **IP capacity**: Subnet has sufficient available IPs
6. **Security group**: No 0.0.0.0/0 rules on DWS port
7. **Quotas**: DWS, compute, and storage quotas sufficient
8. **Name**: Cluster name is unique and meets constraints
9. **Credentials**: Secure password input mechanism established

## Post-Creation Validation

1. **Cluster status**: ShowClusters returns operational state
2. **Configuration**: All parameters match expected values
   - Region
   - AZ
   - Version
   - Node type
   - Node count
   - Storage type and size
   - VPC, subnet, security group
   - Port
   - Public access state
3. **Nodes**: All nodes are healthy (ListClusterNodes)
4. **Endpoint**: Cluster endpoint is accessible
5. **Connectivity**: Database connection succeeds (SELECT version())

## Snapshot Validation

1. **Snapshot list**: ListSnapshots returns expected snapshots
2. **Snapshot details**: Snapshot status is available
3. **Snapshot size**: Snapshot size is reasonable

## Operational Validation

1. **Cluster health**: ShowClusters shows healthy status
2. **Node health**: All nodes in healthy state
3. **Storage usage**: ShowResourceStatistics within expected range
4. **Connectivity**: Database query succeeds
5. **Security group**: Rules match expected configuration
6. **EIP** (if applicable): EIP bound and accessible
7. **Monitoring**: Cloud Eye or LTS monitoring configured

## Validation Commands

```bash
hcloud DWS ShowClusters --cli-region=<REGION>
hcloud DWS ListClusterDetails --cli-region=<REGION>
hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
hcloud DWS ShowResourceStatistics --cli-region=<REGION>
hcloud DWS ListSnapshots --cli-region=<REGION>
hcloud DWS ShowClusterFlavor --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
hcloud DWS ShowClusterVolume --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
```
