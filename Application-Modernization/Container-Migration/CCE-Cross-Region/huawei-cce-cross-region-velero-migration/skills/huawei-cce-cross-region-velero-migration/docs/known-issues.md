# Known Issues

1. **ELB cross-region**: Load Balancers cannot be migrated directly. Must be recreated in target region with new EIPs.
2. **StorageClass mismatch**: CSI drivers may differ between regions. Manual StorageClass mapping required.
3. **Secret encryption**: Velero backs up Secrets unencrypted by default. Configure encryption in production.
4. **CRD compatibility**: Custom Resource Definitions must exist in target cluster before restore.
5. **Image accessibility**: Images in SWR may not be accessible cross-region. Configure cross-region replication.
6. **PVC data**: Velero only backs up PVC metadata, not data. Use CSI snapshots or application-level replication for data.
7. **CCE not in deploy MCP**: Cannot generate CCE Terraform. CCE cluster creation is manual.
