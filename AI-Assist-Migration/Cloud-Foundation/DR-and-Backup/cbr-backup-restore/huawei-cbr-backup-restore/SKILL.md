---
name: huawei-cbr-backup-restore
version: 1.0.0
description: Discover, configure, execute, validate and restore Huawei Cloud CBR backups for supported ECS, EVS and CCE node scenarios.
category: migration
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Cloud-Foundation
  family: DR-and-Backup
  service: CBR
  risk_level: high
  status: READY_WITH_WARNINGS
  verified_hcloud_version: 6.2.9
  newer_version_validation_pending: 7.2.12
---

# Purpose

Discover, configure, execute, validate and restore Huawei Cloud CBR (Cloud Backup and Recovery) backups for supported ECS, EVS and CCE node scenarios, using hcloud CLI as the primary mechanism.

# Supported scenario

- Source: Huawei Cloud ECS instance, EVS volume, or CCE node resources in a region
- Target: Restored ECS instance, EVS volume, or CCE-related resource (new resource)
- Mechanism: CBR vault + checkpoint (backup) + RestoreBackup
- Storage: CBR vault (region-local or cross-region copy)
- Topology: In-region backup/restore, cross-region copy

# When to use this skill

- Creating ad-hoc or scheduled backups of ECS instances, EVS volumes, or CCE node disks
- Restoring an ECS instance or EVS volume from a CBR backup to a new resource
- Setting up a CBR vault and policy for ongoing protection
- Copying a backup cross-region for DR purposes
- Validating backup integrity and restore readiness

# When not to use this skill

- Live synchronous replication (use SDR service instead)
- Database-level backup/restore (use database native tools or DRS)
- Kubernetes application state backup (use Velero instead)
- File-level backup of SFS Turbo or workspace (use CBR file-level capabilities directly)
- When no hcloud CLI is available and cannot be installed

# Required inputs

- Resource type: ECS, EVS, or CCE
- Source region
- Source resource name or identifier
- Backup type: ad-hoc or scheduled
- Approval owner

# Optional inputs

- Existing vault name or desired vault name
- Schedule (for policy-based backups)
- Retention by time
- Retention by count
- Cross-region copy requirement and destination region
- Restore target naming convention
- Encryption requirements
- Enterprise project
- Maintenance window
- Acceptable downtime

# Required MCPs

None. CBR operations are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-pricing (for cost estimation of vault and backup storage)
- huaweicloud-ticket (for support ticket creation if issues arise)
- huaweicloud-deploy (for VPC/subnet/SG infrastructure prerequisites only; NOT for CBR resources)

# Tool selection policy

- Use hcloud CLI for ALL CBR operations (vault, backup, restore, policy, agent)
- Use huaweicloud-pricing for cost estimation only (all tools are read-only)
- Use huaweicloud-ticket for support ticket preparation only; create_ticket requires explicit approval
- Use huaweicloud-deploy ONLY for VPC, subnet, security group prerequisites; do NOT declare CBR support
- NEVER use GenerateTerraformFromArchitecture to create CBR resources
- NEVER execute write operations without explicit approval
- NEVER hardcode vault IDs, backup IDs, resource IDs, or policy IDs

# Safety and approval gates

1. Vault creation requires explicit approval (incurs recurring cost)
2. Resource association to vault requires explicit approval (starts incurring backup costs)
3. Policy creation requires explicit approval (schedules automatic backups)
4. Backup execution (CreateCheckpoint) requires explicit approval
5. Restore execution (RestoreBackup) requires explicit approval and impact plan
6. Cross-region copy (CopyBackup) requires explicit approval (egress costs)
7. Any deletion (DeleteVault, DeleteBackup, DeletePolicy) requires explicit approval
8. Restore defaults to creating a new resource; restore-in-place requires double confirmation

# Rules

1. CBR supports protection of ECS (OS::Nova::Server), EVS (OS::Cinder::Volume), and specific CCE-related resources; the exact resource types available must be discovered per region before creating the vault. [VERIFIED_FROM_LOCAL_HELP] [REGION_DEPENDENT]

2. The vault must use a region compatible with the protected resources. Never assume cross-region compatibility for direct association. [VERIFIED_FROM_LOCAL_HELP] [REGION_DEPENDENT]

3. The resource state should be validated before backup; verify the expected state for the resource type and backup mode before proceeding. When the backup type may require an active instance, confirm the state rather than assuming compatibility. [INFERRED]

4. A restore must be treated as creation or recovery toward a new resource or an explicitly selected target. Never assume the original resource will be overwritten. [VERIFIED_FROM_LOCAL_HELP]

5. Cross-region copy or replication requires specific capabilities and resources in the destination region. Validate first with ShowReplicationCapabilities. [VERIFIED_FROM_LOCAL_HELP]

6. Differentiate ad-hoc backups from scheduled policies. Policies must declare schedule, retention, and expiration behavior. [VERIFIED_FROM_LOCAL_HELP]

7. A backup related to CCE nodes protects associated disks or resources, but should not be assumed to replace a Kubernetes logical state backup strategy; verify what is and is not covered for the specific CCE backup type. [INFERRED]

8. For EVS, verify attachment status, volume state, and compatibility before initiating backup; the exact preconditions may vary by volume type and region. [INFERRED]

9. Verify vault capacity, quota, and usage before creating a checkpoint; the available capacity may not match the displayed capacity in all cases. [INFERRED]

10. Incremental backups depend on a valid backup chain and a successful base backup. Do not delete dependencies without validating the chain; breaking the chain may affect subsequent incremental backups. [INFERRED]

11. DISCOVER BEFORE CREATE: never hardcode vault IDs, resource IDs, backup IDs, or policy IDs. Always resolve names to IDs via read operations first. [VERIFIED_FROM_LOCAL_HELP]

12. VERIFY AFTER EVERY STEP: each write operation must have a corresponding List or Show operation afterward to confirm the result. [VERIFIED_FROM_LOCAL_HELP]

13. Every write operation requires explicit approval before execution. [VERIFIED_FROM_LOCAL_HELP]

14. Before restore, generate a rollback and impact plan. Do not execute restore without documented plan and approval; the exact impact may vary by resource type and restore mode. [INFERRED]

15. Never include secrets (AK, SK, tokens, passwords, project IDs, private keys) in commands, examples, files, or logs; use secure input mechanisms where available. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI 6.2.9 | Yes | All CBR operations | `hcloud version` |
| Huawei Cloud authentication | Yes | API access | `hcloud CBR ListVault --cli-region=<REGION>` |
| Target region | Yes | CBR vault and resource region | Specified in intent |
| Project or enterprise project context | Yes | Resource scoping | `hcloud CBR ListVault --cli-region=<REGION>` |
| CBR service availability | Yes | Service enabled in region | `hcloud CBR ListVault --cli-region=<REGION>` |
| Source ECS, EVS, or CCE resource | Yes | Resource to protect | `hcloud CBR ListProtectable` |
| IAM permissions | Yes | CBR read/write, ECS/EVS read | Verified by successful ListVault |
| Vault quota | Yes | Sufficient capacity for backups | `hcloud CBR ShowVault` |
| Backup quota | Yes | Sufficient backup count | `hcloud CBR ListBackups` |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| huaweicloud-deploy MCP | No | Infrastructure prerequisites (VPC/SG) | MCP availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate all required and optional inputs for the backup or restore operation.

**Inputs**: User request specifying resource type, region, resource name, backup type, schedule, retention, cross-region requirements, restore requirements, approval owner.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm all required fields are present.

**Expected result**: Complete intent object with all required fields populated.

**Failure action**: If critical information is missing, STOP and request clarification. Do not invent values.

**Evidence artifact**: `artifacts/cbr-intent.json`

Extract:
- resource_type: ECS, EVS, or CCE
- source_region
- source_resource_name
- existing_vault_name or desired_vault_name
- backup_type: ad-hoc or scheduled
- schedule (if scheduled)
- retention_by_time
- retention_by_count
- cross_region_copy_requirement
- destination_region
- restore_requirement
- restore_target_naming
- encryption_requirements
- enterprise_project
- maintenance_window
- acceptable_downtime
- approval_owner

If critical information is missing: do not invent, request clarification, stop write operations.

## STEP 2 — DISCOVER AUTHENTICATION AND REGION

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI version, authentication, region, project context, and CBR service availability.

**Inputs**: source_region from intent.

**Preconditions**: hcloud CLI installed.

**Commands** (read-only):

```bash
hcloud version
hcloud CBR ListVault --cli-region=<SOURCE_REGION> --limit=1
```

**Approval requirement**: None.

**Verification**: Confirm version is 6.2.9+, confirm region returns vault list (even if empty), confirm CBR is available.

**Expected result**: Authentication valid, region accessible, CBR service available.

**Failure action**: STOP. Report authentication or region error.

**Evidence artifact**: `artifacts/cbr-auth-discovery.json`

## STEP 3 — DISCOVER SOURCE RESOURCES

**Classification: ASSISTED**

**Objective**: Discover the source ECS, EVS, or CCE resource and resolve name to ID.

**Inputs**: resource_type, source_resource_name, source_region.

**Preconditions**: Step 2 completed successfully.

**Commands** (read-only):

For ECS:
```bash
hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>
```

For EVS:
```bash
hcloud EVS ListVolumes --cli-region=<SOURCE_REGION>
```

For CCE:
```bash
hcloud CCE ListClusters --cli-region=<SOURCE_REGION>
```

Also discover protectable resources:
```bash
hcloud CBR ListProtectable --cli-region=<SOURCE_REGION> --protectable_type=<TYPE>
```

**Approval requirement**: None.

**Verification**:
- Exactly one match for source_resource_name (reject zero matches, reject ambiguous multiple matches)
- Resource state is compatible with backup
- Resource region matches source_region
- Enterprise project matches when applicable

**Expected result**: source_resource_id resolved, resource state validated.

**Failure action**: STOP. Report zero matches, ambiguous matches, or incompatible state.

**Evidence artifact**: `artifacts/cbr-source-discovery.json`

## STEP 4 — DISCOVER EXISTING VAULTS AND POLICIES

**Classification: ASSISTED**

**Objective**: List existing vaults, policies, backups, and regional capabilities to apply DISCOVER BEFORE CREATE.

**Inputs**: source_region, resource_type.

**Preconditions**: Step 3 completed successfully.

**Commands** (read-only):

```bash
hcloud CBR ListVault --cli-region=<SOURCE_REGION>
hcloud CBR ListPolicies --cli-region=<SOURCE_REGION>
hcloud CBR ListBackups --cli-region=<SOURCE_REGION>
hcloud CBR ShowReplicationCapabilities --cli-region=<SOURCE_REGION>
```

**Approval requirement**: None.

**Verification**: Catalog existing resources. If a compatible vault exists, present reuse option.

**Expected result**: Complete inventory of existing vaults, policies, backups, and capabilities.

**Failure action**: Continue with empty results (no existing resources is valid).

**Evidence artifact**: `artifacts/cbr-existing-resources.json`

Apply DISCOVER BEFORE CREATE:
- If a compatible vault exists: present reuse option, validate capacity, type, region, association.
- Do not create yet.

## STEP 5 — PLAN VAULT

**Classification: AUTOMATED**

**Objective**: Build a vault plan with name, type, capacity, billing, region, project, tags, reuse decision, quota impact, and estimated cost.

**Inputs**: Intent, source discovery, existing resources.

**Preconditions**: Steps 1-4 completed.

**Command**: None (plan generation logic).

**Approval requirement**: None (plan only, no execution).

**Verification**: Plan contains all required fields.

**Expected result**: Vault plan document ready for review.

**Failure action**: STOP. Report planning error.

**Evidence artifact**: `artifacts/cbr-vault-plan.md`

Plan includes:
- vault_name
- resource_type (server, disk, turbo)
- protect_type (backup, replication)
- capacity
- billing
- region
- enterprise_project
- tags
- existing or new decision
- quota impact
- estimated cost (if pricing MCP available)

## STEP 6 — CREATE OR REUSE VAULT

**Classification: ASSISTED**

**Objective**: Create a new vault or reuse an existing one based on the plan.

**Inputs**: Vault plan, approval.

**Preconditions**: Step 5 plan approved.

If reusing:
- Re-verify vault state and capacity.

If creating:
- **Approval requirement**: EXPLICIT. Request approval before creation.
- **Command**:

```bash
hcloud CBR CreateVault --cli-region=<SOURCE_REGION> \
  --vault.name='<VAULT_NAME>' \
  --vault.billing.consistent_with_server=false \
  --vault.billing.charging_mode=<CHARGING_MODE> \
  --vault.billing.size=<CAPACITY_GB> \
  --vault.resource_type=<RESOURCE_TYPE> \
  --vault.prot_type=<PROTECT_TYPE>
```

**Verification** (after creation or reuse):

```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

Confirm: ID resolved, status active, capacity matches, region matches.

**Expected result**: Vault ID resolved and validated.

**Failure action**: STOP. Preserve error evidence. Do not continue.

**Evidence artifact**: `artifacts/cbr-vault-result.json`

## STEP 7 — ASSOCIATE RESOURCE

**Classification: ASSISTED**

**Objective**: Associate the source resource with the vault.

**Inputs**: vault_id, source_resource_id, resource_type.

**Preconditions**: Step 6 completed. Resource not already associated with an incompatible vault.

Before associating:
- Verify resource is not associated with another vault incompatibly
- Verify vault type matches resource type
- Verify vault region matches resource region
- Verify resource state is compatible

**Approval requirement**: EXPLICIT.

**Command**:

```bash
hcloud CBR AddVaultResource --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --resources='[{"id":"<RESOURCE_ID>","type":"<RESOURCE_TYPE>"}]'
```

**Verification**:

```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

Confirm: Resource appears in vault resource list.

**Expected result**: Resource successfully associated with vault.

**Failure action**: STOP. Report association error.

**Evidence artifact**: `artifacts/cbr-association-result.json`

## STEP 8 — CREATE OR REUSE BACKUP POLICY

**Classification: ASSISTED**

**Objective**: Create a scheduled policy or confirm ad-hoc backup mode.

**Inputs**: backup_type, schedule, retention, vault_id.

**Preconditions**: Step 7 completed.

For ad-hoc backup: Skip policy creation. Document as ad-hoc.

For scheduled policy:
- Apply DISCOVER BEFORE CREATE: check existing policies for compatible schedule.
- **Approval requirement**: EXPLICIT.

**Command**:

```bash
hcloud CBR CreatePolicy --cli-region=<SOURCE_REGION> \
  --policy.name='<POLICY_NAME>' \
  --policy.enabled=<ENABLED> \
  --policy.trigger.properties.schedule='<SCHEDULE>' \
  --policy.trigger.type=time \
  --policy.operation_definition.retention_duration_days=<RETENTION_DAYS>
```

Associate policy with vault:

```bash
hcloud CBR AssociateVaultPolicy --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --policy_id=<POLICY_ID>
```

**Verification**:

```bash
hcloud CBR ShowPolicy --cli-region=<SOURCE_REGION> --policy_id=<POLICY_ID>
```

Confirm: schedule matches, retention matches, enabled state matches.

**Expected result**: Policy created and associated, or ad-hoc mode confirmed.

**Failure action**: STOP. Report policy creation error.

**Evidence artifact**: `artifacts/cbr-policy-result.json`

## STEP 9 — TRIGGER BACKUP

**Classification: ASSISTED**

**Objective**: Execute an ad-hoc backup (CreateCheckpoint) or confirm scheduled backup is active.

**Inputs**: vault_id, backup_type.

**Preconditions**: Steps 7-8 completed.

For ad-hoc:
- **Approval requirement**: EXPLICIT.

**Command**:

```bash
hcloud CBR CreateCheckpoint --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID>
```

For scheduled: Confirm policy is enabled and next run time.

**Verification**: Poll backup status.

```bash
hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID> --status=available
```

Polling:
- Use `hcloud CBR ShowBackup --backup_id=<BACKUP_ID>` or ListBackups with filter
- Handle timeout (default: 30 minutes for ECS, 10 minutes for EVS)
- Handle failed state: STOP and report
- Handle partial success: report and await decision
- Record backup_id, start timestamp, completion timestamp

**Expected result**: Backup ID resolved, status available.

**Failure action**: STOP. Report backup failure with error details.

**Evidence artifact**: `artifacts/cbr-backup-result.json`

## STEP 10 — VERIFY BACKUP

**Classification: ASSISTED**

**Objective**: Validate backup integrity, metadata, and consistency.

**Inputs**: backup_id.

**Preconditions**: Step 9 completed.

**Commands** (read-only):

```bash
hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
```

Validate:
- Backup exists
- Backup status: available
- Protected resource matches source
- Vault matches
- Region matches
- Size recorded
- Creation time recorded
- Expiration time (if policy-based)
- Incremental or full relationship
- Checksum or consistency metadata (when available)

**Expected result**: Backup fully validated.

**Failure action**: STOP. Report validation failure.

**Evidence artifact**: `artifacts/cbr-backup-validation-report.md`

## STEP 11 — PLAN RESTORE

**Classification: AUTOMATED**

**Objective**: Build a restore plan with impact analysis and rollback strategy.

**Inputs**: backup_id, restore requirements from intent.

**Preconditions**: Step 10 completed.

Before restore:
- Identify exact backup
- Validate restore capability for resource type
- Select destination (new resource by default)
- Define restored resource name
- Evaluate network, subnet, SG, and AZ requirements
- Evaluate IP conflict risk
- Evaluate application impact
- Define rollback strategy
- **Approval requirement**: EXPLICIT (plan review)

**Expected result**: Restore plan document ready for approval.

**Failure action**: STOP. Report planning error.

**Evidence artifact**: `artifacts/cbr-restore-plan.md`

## STEP 12 — EXECUTE RESTORE

**Classification: ASSISTED**

**Objective**: Execute the restore operation to create a new resource from the backup.

**Inputs**: backup_id, restore_plan.

**Preconditions**: Step 11 plan approved.

**Approval requirement**: EXPLICIT.

**Command**:

```bash
hcloud CBR RestoreBackup --cli-region=<SOURCE_REGION> \
  --backup_id=<BACKUP_ID> \
  --restore='<RESTORE_SPEC>'
```

**Verification**: Poll restore status.

```bash
hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
```

Monitor restore:
- Capture request ID
- Poll for completion
- Stop on error
- Do NOT delete the original resource

**Expected result**: Restore completed, new resource created.

**Failure action**: STOP. Preserve original resource. Report restore failure.

**Evidence artifact**: `artifacts/cbr-restore-result.json`

## STEP 13 — VERIFY RESTORED RESOURCE

**Classification: ASSISTED**

**Objective**: Validate the restored resource is functional and matches expectations.

**Inputs**: restored_resource_id, resource_type.

**Preconditions**: Step 12 completed.

For ECS:
- New instance visible: `hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>`
- Status: ACTIVE
- Disks attached
- Network configured
- Security groups applied
- Boot validation

For EVS:
- New volume visible: `hcloud EVS ListVolumes --cli-region=<SOURCE_REGION>`
- Status: available
- Size matches
- AZ matches
- Attachment status
- Filesystem or application validation

For CCE-related:
- Disks or nodes recovered per scope
- Do NOT assume deployments and runtime were restored automatically

**Expected result**: Restored resource fully validated.

**Failure action**: Report validation failure. Do NOT delete restored resource automatically.

**Evidence artifact**: `artifacts/cbr-restore-validation-report.md`

## STEP 14 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-13.

**Preconditions**: All previous steps completed.

Generate:
- Final summary
- Resource IDs sanitized for sharing
- Cost information (if pricing MCP was used)
- Backup and restore result
- Warnings
- Follow-up actions
- Cleanup recommendations
- Retention confirmation
- Unresolved risks

Do NOT delete backups, vaults, or restored resources automatically.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/cbr-final-report.md`

# Capability gap handling

When a capability required for CBR backup/restore is not available in existing MCPs:

1. Document the gap in capability-gap-policy.md with Gap ID, phase, and impact
2. Classify the gap: critical path or optional
3. Evaluate alternatives:
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL
   - Can an existing MCP be extended? → EXTEND_EXISTING_MCP
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort)
   - Can the step be performed via hcloud CLI? → USE_HCLOUD_CLI
4. Invoke mcp-capability-builder for gaps requiring EXTEND_EXISTING_MCP or CREATE_NEW_MCP
5. Update skill status if critical gaps remain
6. Never auto-activate generated MCPs

Known capability gaps:
- GAP-CBR-001: No dedicated CBR MCP exists. All CBR operations via hcloud CLI. [VERIFIED_FROM_LOCAL_HELP]
- GAP-CBR-002: CBR is not in huaweicloud-deploy supported services. Cannot generate CBR Terraform. [VERIFIED_FROM_CODE]
- GAP-CBR-003: hcloud CLI operations lack structured error handling and retry logic that MCPs provide. [INFERRED]
- GAP-CBR-004: Cross-region copy capability varies by region and must be validated per execution. [REGION_DEPENDENT]
- GAP-CBR-005: Agent-based backup (ECS application-consistent) requires agent verification which is CLI-only. [VERIFIED_FROM_LOCAL_HELP]

# Output artifacts

- artifacts/cbr-intent.json — Parsed intent
- artifacts/cbr-auth-discovery.json — Authentication and region validation
- artifacts/cbr-source-discovery.json — Source resource discovery
- artifacts/cbr-existing-resources.json — Existing vaults, policies, backups
- artifacts/cbr-vault-plan.md — Vault plan
- artifacts/cbr-vault-result.json — Vault creation or reuse result
- artifacts/cbr-association-result.json — Resource association result
- artifacts/cbr-policy-result.json — Policy creation or reuse result
- artifacts/cbr-backup-result.json — Backup execution result
- artifacts/cbr-backup-validation-report.md — Backup validation report
- artifacts/cbr-restore-plan.md — Restore plan
- artifacts/cbr-restore-result.json — Restore execution result
- artifacts/cbr-restore-validation-report.md — Restore validation report
- artifacts/cbr-final-report.md — Final closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| Authentication failure | hcloud config or IAM issue | `hcloud version` and test command | Verify hcloud config, region, IAM permissions |
| Resource not found | Wrong name, region, or enterprise project | `hcloud CBR ListProtectable` | Verify resource name, region, enterprise project |
| Multiple matches for resource name | Ambiguous naming | List results with matching name | Present all matches, do not auto-select |
| Vault creation fails | Quota, capacity, or billing issue | `hcloud CBR ShowVault` error | Check quota, capacity, billing mode |
| Association fails | Vault/resource type or region mismatch | ShowVault resource list | Verify vault type, resource type, region compatibility |
| Backup fails or stuck | Vault capacity, resource state, or agent | `hcloud CBR ShowBackup` status | Check vault capacity, resource state, agent status |
| Restore fails | Backup integrity, target AZ, or network | Restore error details | Check backup integrity, target AZ, network, quota |
| Cross-region copy fails | Replication capability or egress quota | `ShowReplicationCapabilities` | Validate destination region, check egress quota |
| Policy creation fails | Schedule syntax or retention params | `hcloud CBR ShowPolicy` error | Validate schedule syntax, retention parameters |
| Vault capacity insufficient | Quota exceeded or backup size | `hcloud CBR ShowVault` usage | Request quota increase or clean up old backups |

See also: `references/known-issues.md`

# Failure handling

- Authentication failure: Verify hcloud config, region, IAM permissions. Do not retry with different credentials.
- Resource not found: Verify resource name, region, enterprise project. Do not invent IDs.
- Multiple matches: Present all matches. Do not auto-select.
- Vault creation failure: Check quota, capacity, billing mode. Report and await decision.
- Association failure: Check vault type, resource type, region compatibility. Verify resource not already associated.
- Backup failure: Check vault capacity, resource state, agent status (for ECS). Report error details.
- Backup stuck in protecting: Poll with timeout. If timeout exceeded, report and await decision.
- Restore failure: Check backup integrity, target AZ, network, quota. Preserve original resource.
- Restore creates wrong resource: Validate restore spec before execution. Do not delete automatically.
- Policy creation failure: Check schedule syntax, retention parameters. Validate against hcloud help.
- Cross-region copy failure: Validate ShowReplicationCapabilities for destination region. Check egress quota.

# Recovery procedure

1. If failure during vault creation: No data loss. Review error. Retry with corrected parameters or different capacity.
2. If failure during association: Resource is unprotected. Verify vault and resource compatibility. Retry.
3. If failure during backup: No data loss (no backup created). Check vault capacity and resource state. Retry.
4. If failure during restore: Original resource is intact. New resource may be partially created. Assess and clean up manually.
5. If failure during validation: Original and/or restored resources exist. Assess which is functional. Do not delete either automatically.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- Vault IDs, backup IDs, and resource IDs recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Validation results preserved in artifacts
- Backup metadata (size, status, creation time, expiration) recorded
- Restore metadata (target resource, AZ, network) recorded
- Cost estimates preserved when pricing MCP used
- No secrets in any artifact

# Known limitations

- No dedicated CBR MCP exists; all operations via hcloud CLI [VERIFIED_FROM_LOCAL_HELP]
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending [VERSION_DEPENDENT]
- CBR is NOT supported by huaweicloud-deploy MCP [VERIFIED_FROM_CODE]
- Resource type availability varies by region [REGION_DEPENDENT]
- Cross-region copy capability varies by region [REGION_DEPENDENT]
- CCE node backup protects disks but not Kubernetes logical state [INFERRED]
- Agent-based backup requires agent installed on ECS for application-consistent backup [VERIFIED_FROM_LOCAL_HELP]
- Backup consistency (crash vs application) depends on agent and resource type [INFERRED]
- Incremental backup chain must not be broken by deleting base backup [INFERRED]
- Restore always creates a new resource; in-place restore requires explicit double confirmation [VERIFIED_FROM_LOCAL_HELP]
- hcloud CLI operations lack structured retry logic [INFERRED]

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- CBR service is available in hcloud CLI v6.2.9 with 68 operations [VERIFIED_FROM_LOCAL_HELP]
- Key operations verified: ListVault, ShowVault, CreateVault, CreateCheckpoint, RestoreBackup, CopyBackup, ListBackups, ShowBackup, ListPolicies, CreatePolicy, AddVaultResource, ListProtectable, ShowReplicationCapabilities [VERIFIED_FROM_LOCAL_HELP]
- No dedicated CBR MCP exists [VERIFIED_FROM_LOCAL_HELP]
- All write operations require explicit approval [INFERRED]
- No cloud-side tests were executed [INFERRED]
- Compatibility verified only with hcloud 6.2.9 [VERIFIED_FROM_LOCAL_HELP]
- hcloud 7.2.12 validation is pending [NOT_VERIFIED]
