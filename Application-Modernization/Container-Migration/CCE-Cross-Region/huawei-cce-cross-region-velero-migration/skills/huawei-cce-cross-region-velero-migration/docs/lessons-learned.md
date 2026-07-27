# Lessons Learned

## From Documentation (VERIFIED_FROM_DOCUMENTATION)

1. CCE cross-region migration with Velero is a known pattern but NOT implemented in any MCP
2. The primary challenge is regional dependency migration (ELB, EIP, DNS, Storage)
3. Velero handles namespace-scoped resources well but struggles with cluster-scoped resources
4. PVC data migration is a separate concern from metadata migration
5. Kubernetes version compatibility is critical and must be validated early

## Recommendations

1. Prioritize CCE support in huaweicloud-deploy MCP
2. Consider a dedicated CCE/Velero MCP for automation
3. Implement StorageClass mapping as a configurable transform
4. Add DNS migration support via API
5. Add ELB/EIP cross-region migration support
