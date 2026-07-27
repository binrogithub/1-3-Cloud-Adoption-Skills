# Prerequisites

## Source Cluster
- Huawei Cloud CCE cluster running Kubernetes 1.19+
- Velero CLI installed and configured
- Velero server component installed on cluster
- OBS bucket configured as backup storage location
- IAM user with OBS read/write and CCE admin permissions
- kubectl configured with source cluster context

## Target Cluster
- Huawei Cloud CCE cluster running compatible Kubernetes version
- Velero CLI installed and configured
- Velero server component installed on cluster
- Same OBS bucket accessible from target region
- Sufficient node capacity for migrated workloads
- StorageClasses available for PVC binding

## Network
- OBS endpoint accessible from both clusters
- Inter-region connectivity (Internet or VPN/Direct Connect)
- DNS management access for cutover

## MCP
- huaweicloud-deploy MCP configured and operational
- (Optional) huaweicloud-pricing MCP for cost estimation
- (Optional) huaweicloud-ticket MCP for support tickets
