# CCE Cross-Region Migration with Velero

## Purpose

Migrate a Kubernetes cluster (CCE) from one Huawei Cloud region to another using Velero backup/restore with OBS as the backup storage backend.

## Architecture

- **Source:** CCE cluster in source region
- **Target:** CCE cluster in target region
- **Backup tool:** Velero
- **Storage:** OBS bucket (cross-region accessible)
- **IAM:** Service accounts with OBS and CCE permissions
- **VPC:** Separate VPCs in source and target regions

## Prerequisites

1. Velero installed on source CCE cluster
2. OBS bucket created and accessible from both regions
3. IAM credentials with OBS and CCE permissions
4. Target CCE cluster created with compatible Kubernetes version
5. Network connectivity between clusters and OBS

## Execution runbook

| Step | Description | Classification |
|------|-------------|----------------|
| 1 | Install Velero on source CCE with OBS backend | MANUAL |
| 2 | Create backup of source cluster resources | ASSISTED |
| 3 | Verify backup in OBS bucket | ASSISTED |
| 4 | Install Velero on target CCE with same OBS backend | MANUAL |
| 5 | Restore backup to target cluster | ASSISTED |
| 6 | Verify restored resources | ASSISTED |
| 7 | Handle region-specific resources | MANUAL |
| 8 | Update DNS and external endpoints | MANUAL |
| 9 | Validate application functionality | MANUAL |
| 10 | Cutover traffic to target cluster | MANUAL |

## Validation

- Resource count comparison (source vs target)
- Application health checks
- Pod status verification
- Service endpoint testing

## Rollback

1. Switch DNS/traffic back to source cluster
2. Delete restored resources from target cluster
3. Remove Velero restore history

## Known issues

- **Load balancers (ELB):** ELB resources are region-specific; must be recreated
- **EIP:** Cannot be transferred cross-region; new EIPs required
- **DNS:** Must be manually updated to point to new endpoints
- **StorageClasses:** May differ between regions; verify CSI driver compatibility
- **Persistent Volumes:** OBS-backed PVs can be restored; EVS-backed PVs cannot cross regions
- **Kubernetes version:** Source and target must be compatible
- **Secrets:** Restored as-is; verify encryption compatibility
- **Private images:** Container registry may be region-specific; ensure images are accessible
- **Regional service dependencies:** RDS, DCS, etc. are region-specific
- **ConfigMaps with endpoints:** May contain region-specific URLs; update manually
- **CSI drivers:** May differ between CCE versions/regions
- **Ingress:** ELB-backed Ingress creates new load balancers in target
- **Certificates:** TLS certificates may be region-specific
- **Stateful applications:** Require special handling for data migration

## Lessons learned

- Always test with a non-production cluster first
- Document all region-specific dependencies before migration
- EVS-backed Persistent Volumes cannot cross regions; use OBS for portable storage
- Plan DNS cutover carefully to minimize downtime
- Verify image availability in target region before restore
NOT_IMPLEMENTED — This use case is documented based on known Velero migration patterns. Automated tooling for CCE cross-region migration is not yet implemented in the deploy MCP. The deploy MCP currently supports Terraform generation/validation/plan only.
