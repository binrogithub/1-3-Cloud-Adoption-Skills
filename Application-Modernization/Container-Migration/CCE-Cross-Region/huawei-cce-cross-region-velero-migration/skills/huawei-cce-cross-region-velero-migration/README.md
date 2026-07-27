# huawei-cce-cross-region-velero-migration

## Summary

Skill to orchestrate migration of Kubernetes workloads between Huawei Cloud CCE clusters located in different regions, using Velero as the backup and restore mechanism.

## Problem it solves

Migrating Kubernetes workloads between Huawei Cloud regions requires coordination of multiple components: namespaces, deployments, services, ingress, configmaps, secrets, PVCs, storage classes, load balancers, EIPs, DNS, and image repositories. Without orchestration, the process is error-prone and difficult to track.

## Supported scenario

- **Source**: CCE cluster in region A
- **Target**: CCE cluster in region B (different region)
- **Mechanism**: Velero backup + restore
- **Storage**: OBS as backup repository
- **Topology**: Cross-region

## Architecture

```
Source Region A                    Target Region B
┌─────────────┐                   ┌─────────────┐
│  CCE Cluster │──Velero Backup──>│  OBS Bucket  │
│  (source)    │                   │  (shared)    │
└─────────────┘                   └──────┬───────┘
                                          │
                                   Velero Restore
                                          │
                                   ┌──────▼───────┐
                                   │  CCE Cluster  │
                                   │  (target)     │
                                   └──────────────┘
```

Additional components requiring manual migration:
- Load Balancers (ELB) → recreate in target region
- EIPs → allocate new ones in target region
- DNS → update records
- Image repos → replicate or configure cross-region access
- StorageClasses → map between CSI drivers of each region

## MCPs used

| MCP | Required | Purpose | Read/Write | Risk |
|---|---|---|---|---|
| huaweicloud-deploy | Yes | Generate Terraform for target infrastructure | Read + Write (local .tf) | Low (apply blocked) |
| huaweicloud-pricing | No | Estimate target infrastructure costs | Read-only | None |
| huaweicloud-ticket | No | Create support ticket if issues arise | Read + Write | Medium |
| playwright | No | Console automation if required | Read + Write | Medium |

## Capabilities

- Kubernetes resource discovery from source cluster
- Kubernetes version compatibility validation
- Terraform generation for target infrastructure
- Velero backup/restore command generation
- DNS, Load Balancer, and image migration plan
- Documented rollback procedure

## General flow

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover → 9. Rollback (if needed) → 10. Closure

## Automation level

| Phase | Status | Responsible |
|---|---|---|
| Discovery | ASSISTED | Agent + Human |
| Architecture Validation | ASSISTED | Agent + Human |
| Readiness and Prechecks | MANUAL | Human |
| Plan Generation | ASSISTED | Agent + Human |
| Approval | MANUAL | Human |
| Execution | MANUAL | Human |
| Validation | MANUAL | Human |
| Cutover | MANUAL | Human |
| Rollback | MANUAL | Human |
| Closure and Reporting | ASSISTED | Agent + Human |

## Prerequisites

- Huawei Cloud CCE cluster in source region with Velero installed
- Huawei Cloud CCE cluster in target region with Velero installed
- OBS bucket accessible from both regions
- IAM credentials with permissions for Velero (OBS read/write, CCE admin)
- kubectl configured for both clusters
- Velero CLI installed
- Network connectivity between regions (Internet or VPN/Direct Connect)
- huaweicloud-deploy MCP configured

## Inputs

- source_cluster_id: Source CCE cluster ID
- source_region: Source cluster region (e.g., cn-north-4)
- target_region: Target cluster region (e.g., la-north-2)
- namespaces: List of namespaces to migrate
- obs_bucket: OBS bucket for Velero backups
- kubernetes_version_source: Source K8s version
- kubernetes_version_target: Target K8s version

## Outputs

- discovery-report.md
- architecture-validation-report.md
- readiness-report.md
- migration-plan.md
- terraform/ (.tf files for target infra)
- execution-log.md
- validation-report.md
- rollback-plan.md
- final-report.md

## Installation

```bash
# Configure huaweicloud-deploy MCP
# See shared/docs/installation.md for detailed instructions
```

## Configuration

Configure in opencode.json:

```json
{
  "skills": {
    "huawei-cce-cross-region-velero-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-cce-cross-region-velero-migration"
    }
  },
  "mcp": {
    "huaweicloud-deploy": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-deploy"
    }
  }
}
```

## Usage with OpenCode or Hermes

1. Load the skill: `skill huawei-cce-cross-region-velero-migration`
2. Follow the workflow documented in SKILL.md
3. ASSISTED phases will be guided by the agent
4. MANUAL phases require human execution

## Safe example

```
# Phase 4: Generate Terraform for target infrastructure
GenerateTerraformFromArchitecture({
  "architecture": {
    "architecture_id": "cce-target-infra",
    "region": "la-north-2",
    "deployment_mode": "terraform",
    "components": [
      {"service": "vpc", "name": "target-vpc", "cidr": "192.168.0.0/16"},
      {"service": "subnet", "name": "target-subnet", "cidr": "192.168.0.0/24"},
      {"service": "security_group", "name": "target-sg", "rules": [...]}
    ]
  }
})

# Validate generated Terraform
ValidateTerraformConfiguration({"architecture_id": "cce-target-infra"})

# Preview changes
RunTerraformPlan({"architecture_id": "cce-target-infra"})
```

## Required approvals

- Approval of the complete migration plan
- Approval of terraform apply (manual execution outside the MCP)
- Approval of Velero backup (modifies data in OBS)
- Approval of Velero restore (modifies target cluster state)
- Approval of DNS cutover (redirects traffic)
- Approval of rollback (if needed)

## Validation

- Verify Deployments are running in the target
- Verify Services are accessible
- Verify Ingress is configured
- Verify PVCs are bound in target region
- Compare resource counts source vs target
- Run application smoke tests

## Rollback

1. Revert DNS to source cluster
2. Restore traffic to source cluster
3. Clean up resources in target cluster
4. Destroy target infrastructure (manual terraform destroy)
5. Document lessons learned

## Capability gap handling

The following gaps require attention:

| Gap ID | Description | Decision |
|---|---|---|
| GAP-CCE-001 | No MCP tool for CCE discovery | MANUAL_STEP |
| GAP-CCE-002 | No MCP tool for Velero operations | MANUAL_STEP |
| GAP-CCE-003 | No MCP tool for K8s version validation | MANUAL_STEP |
| GAP-CCE-004 | No MCP tool for StorageClass mapping | MANUAL_STEP |
| GAP-CCE-005 | No MCP tool for DNS migration | MANUAL_STEP |
| GAP-CCE-006 | No MCP tool for ELB/EIP migration | MANUAL_STEP |
| GAP-CCE-007 | CCE not in deploy MCP supported services | EXTEND_EXISTING_MCP |

## Testing

- Validate that SKILL.md exists and is valid
- Validate that skill.yaml is valid
- Validate that referenced MCPs exist
- Validate that mentioned tools exist in the MCPs
- Validate that no non-existent tools are mentioned
- Execution tests require real CCE clusters (SKIPPED_CLOUD_SIDE_EFFECT)

## Security

- Kubernetes secrets are migrated without additional encryption by Velero (configure encryption)
- IAM credentials for OBS must have minimum required permissions
- Do not run terraform apply from the MCP (blocked by design)
- Do not expose EIPs publicly unnecessarily
- Document all operations with timestamps

## Limitations

- CCE is not supported by huaweicloud-deploy MCP
- Velero has no MCP automation
- Most phases are MANUAL
- Cross-region PVCs require manual StorageClass mapping
- Load Balancers must be recreated in target region
- EIPs are region-specific
- Kubernetes version must be compatible between regions

## Troubleshooting

| Problem | Solution |
|---|---|
| Velero backup fails | Verify OBS connectivity, IAM permissions, disk space |
| Velero restore fails | Verify resource compatibility, StorageClass mapping, PVC availability |
| Terraform validation fails | Review architecture JSON, supported services |
| Target cluster lacks capacity | Scale node pools before restore |
| DNS does not resolve | Verify DNS propagation, TTL, fallback to source |

## Maturity status

**EXPERIMENTAL**

CCE cross-region migration with Velero is documented but not implemented in the current MCP. Most phases require manual execution.

## Evidence used

| Evidence | Type |
|---|---|
| CCE Velero use-case documented as NOT_IMPLEMENTED | VERIFIED_FROM_DOCUMENTATION |
| huaweicloud-deploy does not support CCE | VERIFIED_FROM_CODE |
| No Velero MCP tool exists | VERIFIED_FROM_CODE |
| terraform apply blocked in deploy MCP | VERIFIED_FROM_CODE |
| 7/10 phases are MANUAL or NOT_IMPLEMENTED | INFERRED |
