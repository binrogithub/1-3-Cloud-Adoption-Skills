---
name: huawei-cce-cross-region-velero-migration
version: 1.0.0
description: Orchestrate migration of Kubernetes workloads between Huawei Cloud CCE clusters in different regions using Velero
category: migration
risk_level: high
status: EXPERIMENTAL
requires_explicit_approval: true
---

# Purpose

Orchestrate a complete migration of Kubernetes workloads between Huawei Cloud CCE (Cloud Container Engine) clusters located in different regions, using Velero as the backup and restore mechanism.

# Supported scenario

- Source: Huawei Cloud CCE cluster in region A
- Target: Huawei Cloud CCE cluster in region B (different region)
- Mechanism: Velero backup (source) + Velero restore (target)
- Storage: OBS (S3-compatible) as backup repository
- Topology: Cross-region

# When to use this skill

- Migrating Kubernetes applications between CCE clusters in different Huawei Cloud regions
- Disaster recovery setup requiring cross-region workload replication
- Cluster consolidation or region migration initiatives

# When not to use this skill

- Same-region CCE migration (use native CCE tools)
- Non-Kubernetes workloads (use DRS for databases, deploy MCP for infrastructure)
- In-cluster migrations (use kubectl or Helm directly)
- When VPN/Direct Connect is required and not yet established

# Required inputs

- Source CCE cluster ID, region, and Kubernetes version
- Target CCE cluster ID, region, and Kubernetes version
- Namespaces to migrate
- OBS bucket for Velero backups
- IAM credentials with appropriate permissions
- Network connectivity plan between regions

# Optional inputs

- Specific resource types to include/exclude (Deployments, StatefulSets, ConfigMaps, Secrets, etc.)
- StorageClass mapping between regions
- DNS migration strategy
- Load Balancer migration strategy
- Image repository migration strategy
- Cutover window definition
- Rollback plan

# Required MCPs

- huaweicloud-deploy (for infrastructure provisioning in target region)

# Optional MCPs

- huaweicloud-pricing (for cost estimation of target region infrastructure)
- huaweicloud-ticket (for support ticket creation if issues arise)
- playwright (for console automation if needed)

# Tool selection policy

- Use huaweicloud-deploy tools ONLY for infrastructure generation and validation
- NEVER use terraform apply or terraform destroy (blocked in MCP code)
- Velero operations are MANUAL (no MCP tool exists)
- CCE operations are MANUAL (no MCP tool exists for CCE)
- Use huaweicloud-pricing for cost estimation only (all tools are read-only)

# Safety and approval gates

1. Infrastructure generation requires review before any manual apply
2. Velero backup operations require explicit approval (data modification)
3. Velero restore operations require explicit approval (cluster modification)
4. DNS cutover requires explicit approval (traffic redirection)
5. Load Balancer modification requires explicit approval
6. Secret migration requires explicit approval and security review
7. Any operation that modifies the source cluster requires explicit approval

# Workflow

## Phase 1 — Discovery

**Classification: ASSISTED**

1. Identify source CCE cluster: region, version, node pools, namespaces
2. List all Kubernetes resources per namespace:
   - Deployments, StatefulSets, DaemonSets
   - Services, Ingress
   - ConfigMaps, Secrets
   - Persistent Volume Claims, Persistent Volumes
   - Custom Resource Definitions, Custom Resources
   - StorageClasses
3. Identify regional dependencies:
   - Load Balancers (ELB) and their EIPs
   - OBS buckets used by applications
   - Image repositories (SWR or external)
   - DNS records
   - Certificates
4. Assess application statefulness:
   - Stateful applications requiring PVC migration
   - Applications with external database connections
   - Applications with region-specific configurations
5. Document Kubernetes version compatibility between source and target

**MCP tools used**: None (manual kubectl/helm commands)

**Capability gaps**:
- No MCP tool for CCE cluster discovery
- No MCP tool for Kubernetes resource enumeration
- No MCP tool for Velero status check

## Phase 2 — Architecture validation

**Classification: ASSISTED**

1. Validate Kubernetes version compatibility (source vs target)
2. Validate StorageClass mapping (source region CSI → target region CSI)
3. Validate OBS bucket accessibility from target region
4. Validate network connectivity between regions
5. Validate IAM permissions for Velero in both clusters
6. Validate Load Balancer and EIP availability in target region
7. Validate image repository accessibility from target region
8. Document incompatibilities and required manual adjustments

**MCP tools used**: 
- `RunTerraformPlan` (to preview target infrastructure)
- `ExplainTerraformPlan` (to review planned changes)

**Capability gaps**:
- No MCP tool for CCE version validation
- No MCP tool for StorageClass mapping
- No MCP tool for OBS cross-region access validation

## Phase 3 — Readiness and prechecks

**Classification: MANUAL**

1. Verify Velero is installed and operational on source cluster
2. Verify Velero is installed and operational on target cluster
3. Verify OBS bucket is configured as Velero backup location
4. Verify IAM credentials for Velero backup/restore
5. Verify target cluster has sufficient capacity (nodes, CPU, memory)
6. Verify PVC storage is available in target region
7. Verify no critical operations are running on source cluster during backup window
8. Run Velero pre-check: `velero backup-location get`
9. Run Velero pre-check: `velero snapshot-location get`

**MCP tools used**: None (manual Velero CLI commands)

**Capability gaps**:
- No MCP tool for Velero readiness check
- No MCP tool for CCE cluster capacity check

## Phase 4 — Plan generation

**Classification: ASSISTED**

1. Generate Terraform for target region infrastructure (VPC, Subnets, Security Groups, ELB, EIP)
2. Generate Velero backup command with namespace selectors
3. Generate Velero restore command with resource mapping
4. Generate DNS migration plan
5. Generate Load Balancer migration plan
6. Generate image repository migration plan
7. Generate StorageClass mapping configuration
8. Document rollback procedure
9. Present complete plan for approval

**MCP tools used**:
- `GenerateTerraformFromArchitecture` (to generate target infrastructure)
- `ValidateTerraformConfiguration` (to validate generated Terraform)

## Phase 5 — Approval

**Classification: MANUAL**

1. Review complete migration plan
2. Review Terraform plan for target infrastructure
3. Review Velero backup scope
4. Review Velero restore mapping
5. Review rollback procedure
6. Obtain explicit approval from stakeholder
7. Document approval with timestamp and approver

**MCP tools used**: None

## Phase 6 — Execution

**Classification: MANUAL**

1. Apply Terraform for target region infrastructure (MANUAL: terraform apply)
2. Install Velero on target cluster (if not already installed)
3. Configure Velero backup location on target cluster
4. Execute Velero backup on source cluster:
   ```
   velero backup create <backup-name> \
     --include-namespaces <ns1,ns2,...> \
     --snapshot-volumes=false
   ```
5. Wait for backup completion
6. Verify backup in OBS bucket
7. Execute Velero restore on target cluster:
   ```
   velero restore create <restore-name> \
     --from-backup <backup-name> \
     --namespace-mappings <src-ns>:<tgt-ns>
   ```
8. Wait for restore completion
9. Verify restored resources on target cluster

**MCP tools used**: None (all operations are manual)

**Capability gaps**:
- No MCP tool for Velero backup execution
- No MCP tool for Velero restore execution
- No MCP tool for CCE cluster operations
- terraform apply is BLOCKED in deploy MCP (by design)

## Phase 7 — Validation

**Classification: MANUAL**

1. Verify all Deployments are running on target cluster
2. Verify all Services are accessible
3. Verify Ingress configuration
4. Verify ConfigMaps and Secrets are restored correctly
5. Verify PVCs are bound in target region
6. Verify application functionality (smoke tests)
7. Verify Load Balancer and EIP assignment
8. Verify DNS resolution (if migrated)
9. Compare resource counts between source and target

**MCP tools used**: None (manual kubectl commands)

## Phase 8 — Cutover

**Classification: MANUAL**

1. Stop application traffic on source cluster
2. Perform final incremental backup (if applicable)
3. Update DNS records to point to target region
4. Verify traffic routing to target cluster
5. Monitor application health in target region
6. Declare cutover complete or initiate rollback

**MCP tools used**: None

## Phase 9 — Rollback

**Classification: MANUAL**

1. Revert DNS records to source cluster
2. Restore source cluster traffic
3. Clean up target cluster resources (if needed)
4. Destroy target infrastructure (manual terraform destroy)
5. Document rollback reason and lessons learned

**MCP tools used**: None

## Phase 10 — Closure and reporting

**Classification: ASSISTED**

1. Generate migration report with:
   - Source and target cluster details
   - Migrated namespaces and resource counts
   - Validation results
   - Issues encountered and resolutions
   - Time elapsed per phase
2. Clean up temporary resources
3. Archive Velero backup (or set retention policy)
4. Update documentation

**MCP tools used**: None

# Capability gap handling

When a capability required for this migration is not available in existing MCPs:

1. Document the gap in the capability-gap-report.md
2. Invoke the `mcp-capability-builder` shared skill
3. Evaluate whether the gap can be filled by:
   - An existing tool in another MCP (prefer this)
   - An extension of an existing MCP
   - A new MCP (last resort)
4. Until the gap is resolved, classify the affected phase as MANUAL or NOT_IMPLEMENTED

Known capability gaps for this skill:
- GAP-CCE-001: No MCP tool for CCE cluster discovery and resource enumeration
- GAP-CCE-002: No MCP tool for Velero backup/restore operations
- GAP-CCE-003: No MCP tool for Kubernetes version compatibility validation
- GAP-CCE-004: No MCP tool for StorageClass cross-region mapping
- GAP-CCE-005: No MCP tool for DNS record migration
- GAP-CCE-006: No MCP tool for Load Balancer/EIP cross-region migration
- GAP-CCE-007: CCE is not in huaweicloud-deploy supported services

# Output artifacts

- discovery-report.md — Source cluster inventory and dependency map
- architecture-validation-report.md — Compatibility assessment
- readiness-report.md — Precheck results
- migration-plan.md — Complete execution plan with Velero commands
- terraform/ — Target infrastructure Terraform files
- execution-log.md — Step-by-step execution log
- validation-report.md — Post-migration validation results
- rollback-plan.md — Rollback procedure
- final-report.md — Migration summary and lessons learned

# Failure handling

- Velero backup failure: Check OBS connectivity, IAM permissions, disk space. Retry or use alternative namespace scope.
- Velero restore failure: Check resource compatibility, StorageClass mapping, PVC availability. Use `--exclude-resources` to skip problematic resources.
- Terraform validation failure: Review architecture JSON, fix unsupported services, regenerate.
- Target cluster capacity insufficient: Scale up node pools before restore.
- DNS cutover failure: Revert DNS immediately, investigate routing.

# Recovery procedure

1. If failure occurs during backup: No data loss. Clean up partial backup. Investigate and retry.
2. If failure occurs during restore: Target cluster may have partial state. Use `velero restore delete` to clean up. Retry with adjusted scope.
3. If failure occurs during cutover: Revert DNS immediately. Source cluster is still operational.
4. If failure occurs post-cutover: Assess impact. May need to cutover back to source if critical.

# Evidence and traceability

- All Velero backup/restore operations logged with timestamps
- Terraform plan output preserved
- Resource counts before and after migration documented
- Approval decisions recorded with approver identity
- Validation results preserved in artifacts

# Known limitations

- CCE is NOT supported by huaweicloud-deploy MCP (cannot generate CCE Terraform)
- Velero backup/restore has NO MCP automation (all manual)
- Stateful application PVC migration requires manual StorageClass mapping
- Secrets are backed up unencrypted by default (configure Velero encryption)
- Cross-region OBS access may have latency implications
- Load Balancers cannot be migrated directly (must be recreated in target region)
- EIPs are region-specific (must be allocated in target region)
- Image repositories may require cross-region replication setup
- Kubernetes version differences may cause incompatibilities
- Custom Resource Definitions may not exist in target cluster
- CSI drivers may differ between regions

# Status justification

Status: EXPERIMENTAL

Evidence:
- CCE cross-region Velero migration is DOCUMENTED in huaweicloud-deploy use-cases but marked NOT_IMPLEMENTED [VERIFIED_FROM_DOCUMENTATION]
- huaweicloud-deploy MCP does NOT support CCE service [VERIFIED_FROM_CODE]
- No Velero MCP tool exists [VERIFIED_FROM_CODE]
- No CCE discovery MCP tool exists [VERIFIED_FROM_CODE]
- terraform apply is BLOCKED in deploy MCP [VERIFIED_FROM_CODE]
- 7 out of 10 phases are MANUAL or NOT_IMPLEMENTED [INFERRED]
- Only Phase 4 (Plan generation) has partial MCP support [VERIFIED_FROM_CODE]
