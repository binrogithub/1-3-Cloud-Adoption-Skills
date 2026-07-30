# Architecture: CCE Cross-Region Velero Migration

## Overview

Migration of Kubernetes workloads between Huawei Cloud CCE clusters in different regions using Velero.

## Components

### Source Region
- CCE Cluster (Kubernetes)
- Velero (backup agent)
- OBS Bucket (backup storage, cross-region accessible)
- ELB + EIP (application ingress)
- SWR (image repository)

### Target Region
- CCE Cluster (Kubernetes)
- Velero (restore agent)
- ELB + EIP (new application ingress)
- SWR (image repository, may need replication)

### Shared
- OBS Bucket (Velero backup storage)
- IAM (cross-region permissions)

## Data Flow

```
Source CCE → Velero Backup → OBS Bucket → Velero Restore → Target CCE
```

## Key Design Decisions

1. **Velero over native CCE migration**: Velero provides namespace-scoped backup/restore with resource filtering, which is not available in CCE native tools.
2. **OBS as backup storage**: OBS is S3-compatible and accessible cross-region, making it ideal for Velero backup storage.
3. **No CSI snapshot migration**: PVC data must be handled separately (manual copy or application-level replication).
4. **Infrastructure as Code**: Target region infrastructure defined in Terraform via huaweicloud-deploy MCP.

## Limitations

- CCE is NOT supported by huaweicloud-deploy MCP
- Velero operations are entirely manual
- PVC data migration is out of scope for Velero (metadata only)
- Load Balancers and EIPs are region-specific and must be recreated
