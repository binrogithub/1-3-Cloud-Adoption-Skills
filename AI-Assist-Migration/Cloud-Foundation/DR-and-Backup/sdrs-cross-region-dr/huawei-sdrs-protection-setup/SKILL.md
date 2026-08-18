---
name: huawei-sdrs-protection-setup
version: 1.0.0
description: Parse protection intent, validate SDRS service and topology, discover production and DR infrastructure, plan DR architecture, and enable SDRS protection under explicit approval.
category: migration
risk_level: high
status: EXPERIMENTAL
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Cloud-Foundation
  family: DR-and-Backup
  service: SDRS
  canonical_name: Storage Disaster Recovery Service
  aliases:
    - SDR
    - SDRS
    - Storage Disaster Recovery Service
  risk_level: high
  status: EXPERIMENTAL
  verified_hcloud_version: 6.2.9
  sdrs_cli_support: NOT_AVAILABLE
  sdrs_mcp_support: NOT_AVAILABLE
  scope: protection_setup_only
  next_skill: huawei-sdrs-dr-drill
---

# Purpose

Parse protection intent, validate SDRS service and topology, discover production and DR-site infrastructure, perform dependency analysis, plan RPO/RTO, design DR architecture, validate readiness, prepare DR gateway when required, and enable SDRS protection under explicit approval. This skill establishes the protection baseline; it does NOT execute DR drills, production failover, reverse reprotection, or failback.

# Terminology

| Term | Canonical name | Notes |
|---|---|---|
| SDRS | Storage Disaster Recovery Service | Current canonical name [VERIFIED_FROM_DOCUMENTATION] |
| SDR | Storage Disaster Recovery | Legacy shorthand, alias only [INFERRED] |
| BRS | Business Recovery Service | Separate service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |
| CBR | Cloud Backup and Recovery | Backup service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |

# Supported scenario

- Source: Huawei Cloud ECS instances with EVS disks in a production region
- Target: Replicated ECS instances with EVS disks in a DR region
- Mechanism: SDRS protection group + protected instances + replication pairs + DR gateway
- Topology: Cross-region (primary), cross-AZ (secondary)
- Replication: Asynchronous (cross-region), synchronous or asynchronous (cross-AZ)
- Operations: Protect, monitor replication status

# When to use this skill

- Setting up cross-region or cross-AZ disaster recovery for ECS instances
- Configuring SDRS protection groups and protected instances
- Monitoring replication status and lag
- Discovering existing SDRS configuration and status

# When not to use this skill

- Executing a DR drill (use huawei-sdrs-dr-drill)
- Executing production failover or failback (use huawei-sdrs-failover-failback)
- Backup-only DR without live replication (use CBR CopyBackup instead)
- Database-level replication (use DRS or database native tools)
- Object storage replication (use OBS cross-region replication)
- File system replication (use SFS Turbo replication)
- When automated SDRS execution is required (no CLI or MCP support exists)
- When the region pair is not supported by SDRS
- When BRS orchestration is required (separate service)

# Required inputs

- Scenario: cross-region or cross-AZ
- Production region
- DR region
- Source ECS names
- Approval owner for protection operations

# Optional inputs

- Production AZ
- DR AZ
- Disk scope (all disks or specific volumes)
- Application type
- Stateful or stateless classification
- Target RPO
- Target RTO
- Replication mode preference (async or sync)
- DR gateway topology
- Network bandwidth requirement
- Target VPC name
- Target subnet name
- Target security groups
- Maintenance window
- Data retention requirement

# Required MCPs

None. No SDRS MCP exists. SDRS operations are performed via MANUAL console execution. Discovery of related resources (ECS, EVS, VPC) uses hcloud CLI.

# Optional MCPs

- huaweicloud-pricing (for cost estimation of DR infrastructure)
- huaweicloud-ticket (for support ticket creation when regional or capacity issues arise)
- huaweicloud-deploy (for VPC, subnet, security group prerequisites only; NOT for SDRS resources)
- playwright (for console exploration and form field discovery only; NEVER for write operations)

# Tool selection policy

- Use hcloud CLI for discovery of related resources ONLY (ECS, EVS, VPC, subnet, security group, EIP, AZ, IAM context)
- NEVER use hcloud for SDRS operations (SDRS is NOT available in hcloud CLI 6.2.9)
- NEVER invent commands like `hcloud SDR ...` or `hcloud SDRS ...`
- Use huaweicloud-pricing for cost estimation only (all tools are read-only)
- Use huaweicloud-ticket for support ticket preparation only; create_ticket requires explicit approval
- Use huaweicloud-deploy ONLY for VPC, subnet, security group prerequisites; do NOT declare SDRS support
- Use playwright ONLY for read-only console exploration; NEVER for write operations or dialog acceptance
- NEVER execute write operations without explicit approval
- NEVER hardcode protection group IDs, instance IDs, volume IDs, or gateway IDs

# Safety and approval gates

1. Protection group creation requires explicit approval (creates DR infrastructure)
2. Protected instance creation requires explicit approval (starts replication and costs)
3. Replication pair creation requires explicit approval (starts data replication)
4. Enable protection requires explicit approval (begins active replication)
5. Gateway installation requires explicit approval (modifies server configuration)
6. No resource deletion is automatic (production or DR site)

# Rules

1. SDRS protects ECS servers through protected instances and replication pairs within a protection group. A protected instance maps a production server to a DR-site server; replication pairs map individual EVS volumes. Do not reduce the service to "volume replication alone". [VERIFIED_FROM_DOCUMENTATION] [REGION_DEPENDENT]

2. Cross-region and cross-AZ may use different operational models. Cross-region requires a DR gateway and uses asynchronous replication. Cross-AZ may support synchronous replication and may or may not require a gateway depending on version. Validate the model for the specific topology before designing. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

3. Validate the region pair or AZ pair before designing any SDRS resources. Not all region combinations are supported. Consult official documentation or console for supported pairs. [VERIFIED_FROM_DOCUMENTATION] [REGION_DEPENDENT]

4. Do not offer sync and async replication as selectable options without confirming that the scenario, topology, and service version support the chosen mode. Cross-region supports async only. Cross-AZ may support both. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT]

5. A disaster recovery gateway is required for cross-region SDRS. Confirm gateway requirements for the specific topology and version before proceeding. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

6. Gateway requirements depend on SDRS version, topology (cross-region vs cross-AZ), and region. Consult current documentation for the specific scenario. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

7. The DR architecture must include VPC, subnet, security group, route tables, DNS configuration, EIP or connectivity, and load balancers as applicable. SDRS replicates disks but does not automatically configure network infrastructure at the DR site. [VERIFIED_FROM_DOCUMENTATION]

8. RPO and replication lag depend on data change rate, available bandwidth, inter-region latency, and gateway or channel capacity. Actual RPO may exceed the target under high write load; monitor replication lag continuously and do not treat target RPO as a guarantee. [INFERRED]

9. The DR site should have sufficient compute capacity (ECS flavors, quota) to start or recover all protected servers simultaneously; verify quotas and available capacity before enabling protection. [INFERRED]

10. DISCOVER BEFORE CREATE: never hardcode protection group IDs, instance IDs, volume IDs, or gateway IDs. Always discover existing resources first. [VERIFIED_FROM_DOCUMENTATION]

11. VERIFY AFTER EVERY STEP: each manual console action should be followed by a verification step to confirm the expected state. [INFERRED]

12. No hardcoded IDs in any artifact, command, or example. [INFERRED]

13. Do not continue when multiple ambiguous matches exist for a resource. Present all matches and request clarification. [INFERRED]

14. No write operations without explicit approval. [INFERRED]

15. Never include secrets (AK, SK, tokens, passwords, project IDs, private keys, account IDs) in commands, examples, files, or logs. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI 6.2.9 | Yes | Discovery of related resources (ECS, EVS, VPC) | `hcloud version` |
| Huawei Cloud authentication | Yes | API access for discovery | `hcloud ECS ListServersDetails --cli-region=<REGION>` |
| Production region | Yes | Source site region | Specified in intent |
| DR region | Yes | Target site region | Specified in intent |
| Source and target AZ | Yes | Availability zones for SDRS | Specified in intent |
| SDRS regional availability | Yes | Service enabled in both regions | Console verification |
| Source ECS instances | Yes | Servers to protect | `hcloud ECS ListServersDetails --cli-region=<REGION>` |
| Source EVS disks | Yes | Disks to replicate | `hcloud EVS ListVolumes --cli-region=<REGION>` |
| Source VPC and subnet | Yes | Production network | `hcloud VPC ListVpcs --cli-region=<REGION>` |
| Target VPC and subnet | Yes | DR site network | `hcloud VPC ListVpcs --cli-region=<DR_REGION>` |
| Security groups | Yes | Network access control | `hcloud VPC ListSecurityGroups --cli-region=<REGION>` |
| Source and target capacity | Yes | Sufficient compute for DR | Console quota verification |
| DR gateway (when required) | Conditional | Cross-region replication channel | Console verification |
| Required IAM permissions | Yes | SDRS read/write, ECS/EVS read | Verified by successful discovery |
| Bandwidth requirement | Yes | Replication throughput | Network assessment |
| RPO target | Yes | Maximum acceptable data loss | Specified in intent |
| RTO target | Yes | Maximum acceptable recovery time | Specified in intent |
| Maintenance window | Yes | Scheduled operations window | Specified in intent |
| Failover approval owner | Yes | Authority for critical operations | Specified in intent |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| huaweicloud-deploy MCP | No | Infrastructure prerequisites (VPC/SG) | MCP availability check |
| Playwright | No | Console exploration | Integration availability check |
| mcp-capability-builder shared skill | Yes | Future SDRS MCP design | Path verification |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate all required and optional inputs for the DR protection setup.

**Inputs**: User request specifying scenario, regions, AZs, ECS names, disk scope, RPO, RTO, approval owner, and all optional parameters.

**Preconditions**: None.

**Mechanism**: Parsing logic.

**Approval requirement**: None.

**Verification**: Confirm all required fields are present.

**Expected result**: Complete intent object with all required fields populated.

**Stop condition**: Critical information missing.

**Failure action**: STOP and request clarification. Do not invent values. No write operations.

**Evidence artifact**: `artifacts/sdrs-intent.json`

## STEP 2 — VALIDATE SERVICE AND TOPOLOGY

**Classification: ASSISTED**

**Objective**: Determine SDRS service availability, supported topologies, and region pair compatibility.

**Inputs**: scenario, production_region, dr_region, production_az, dr_az.

**Preconditions**: Step 1 completed.

**Mechanism**: Official Huawei Cloud documentation review, console read-only exploration, API documentation review.

**Approval requirement**: None.

**Verification**: Confirm SDRS is available in both regions, confirm region pair is supported, confirm topology is supported.

**Expected result**: SDRS capability assessment with canonical service name, supported operations, and limitations.

**Stop condition**: Topology not supported, region pair not supported, service not available, or critical information ambiguous.

**Failure action**: STOP. Report unsupported topology or region.

**Evidence artifact**: `artifacts/sdrs-capability-assessment.md`

NEVER use commands like `hcloud SDR ...` or `hcloud SDRS ...` (these do not exist).

## STEP 3 — DISCOVER PRODUCTION RESOURCES

**Classification: ASSISTED**

**Objective**: Discover ECS instances, EVS disks, VPC, subnets, security groups, EIPs, and AZs in the production region.

**Inputs**: production_region, source_ecs_names, disk_scope.

**Preconditions**: Step 2 completed.

**Mechanism**: hcloud CLI read-only commands (verified).

**Approval requirement**: None.

**Commands** (read-only):

```bash
hcloud ECS ListServersDetails --cli-region=<PRODUCTION_REGION>
hcloud EVS ListVolumes --cli-region=<PRODUCTION_REGION>
hcloud VPC ListVpcs --cli-region=<PRODUCTION_REGION>
hcloud VPC ListSubnets --cli-region=<PRODUCTION_REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<PRODUCTION_REGION>
hcloud VPC ListSecurityGroupRules --cli-region=<PRODUCTION_REGION> --security_group_id=<SG_ID>
hcloud EIP ListPublicIps --cli-region=<PRODUCTION_REGION>
```

**Verification**: Exactly one match for each source ECS name; all required disks discovered and attached; VPC, subnet, security group IDs resolved; region matches; resource states compatible with SDRS protection.

**Expected result**: Complete production resource inventory with names resolved to IDs.

**Stop condition**: Zero matches, ambiguous matches, region mismatch, invalid state, unsupported disk type, unsupported server configuration.

**Failure action**: STOP. Report discovery failure.

**Evidence artifact**: `artifacts/sdrs-source-inventory.json`

## STEP 4 — DISCOVER DR-SITE RESOURCES

**Classification: ASSISTED**

**Objective**: Discover existing VPC, subnets, security groups, available capacity, routes, DNS dependencies, and any existing SDRS resources at the DR site.

**Inputs**: dr_region, target_vpc, target_subnet, target_security_groups.

**Preconditions**: Step 3 completed.

**Mechanism**: hcloud CLI read-only commands for infrastructure; MANUAL console exploration for existing SDRS resources.

**Approval requirement**: None.

**Commands** (read-only):

```bash
hcloud VPC ListVpcs --cli-region=<DR_REGION>
hcloud VPC ListSubnets --cli-region=<DR_REGION> --vpc_id=<TARGET_VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<DR_REGION>
hcloud ECS ListServersDetails --cli-region=<DR_REGION>
hcloud EVS ListVolumes --cli-region=<DR_REGION>
hcloud EIP ListPublicIps --cli-region=<DR_REGION>
```

**Expected result**: Complete DR site inventory.

**Stop condition**: DR site network infrastructure missing, SDRS not available in DR region.

**Failure action**: STOP. Report missing DR infrastructure.

**Evidence artifact**: `artifacts/sdrs-target-inventory.json`

## STEP 5 — APPLICATION DEPENDENCY ANALYSIS

**Classification: AUTOMATED**

**Objective**: Map application components, dependencies, boot order, and consistency requirements.

**Inputs**: source_ecs_names, source inventory, application_type.

**Preconditions**: Steps 3-4 completed.

**Mechanism**: Analysis logic based on discovered resources.

**Approval requirement**: None.

**Expected result**: Application dependency map with recovery sequence.

**Stop condition**: Circular dependencies detected, critical dependencies missing.

**Failure action**: STOP. Report dependency analysis failure.

**Evidence artifact**: `artifacts/sdrs-application-dependency-map.md`

## STEP 6 — RPO, RTO AND BANDWIDTH PLAN

**Classification: ASSISTED**

**Objective**: Calculate or document RPO, RTO, bandwidth, and monitoring requirements.

**Inputs**: target_rpo, target_rto, network_bandwidth, source inventory.

**Preconditions**: Step 5 completed.

**Mechanism**: Analysis based on data change rate, available bandwidth, and SDRS replication characteristics.

**Approval requirement**: None.

**Expected result**: RPO/RTO plan with monitoring thresholds.

**Stop condition**: Required RPO cannot be achieved with available bandwidth.

**Failure action**: Report RPO/bandwidth gap. Recommend bandwidth upgrade or adjusted RPO.

**Evidence artifact**: `artifacts/sdrs-rpo-rto-plan.md`

## STEP 7 — ARCHITECTURE PLAN

**Classification: AUTOMATED**

**Objective**: Design the complete DR architecture including protection groups, protected instances, replication pairs, gateway, network, and failover/failback procedures.

**Inputs**: All artifacts from Steps 1-6.

**Preconditions**: Steps 1-6 completed.

**Mechanism**: Architecture design logic.

**Approval requirement**: None (plan only, no execution).

**Expected result**: Complete DR architecture plan.

**Stop condition**: Insufficient information to design architecture.

**Failure action**: STOP. Report missing information.

**Evidence artifact**: `artifacts/sdrs-architecture-plan.md`

## STEP 8 — READINESS REVIEW

**Classification: ASSISTED**

**Objective**: Validate all prerequisites and readiness conditions before proceeding to execution.

**Inputs**: All artifacts from Steps 1-7.

**Preconditions**: Step 7 completed.

**Mechanism**: Checklist validation.

**Approval requirement**: None.

**Verification**: All critical items pass.

**Expected result**: READY, READY_WITH_WARNINGS, NOT_READY, or BLOCKED.

**Stop condition**: NOT_READY or BLOCKED.

**Failure action**: STOP. Report readiness failures.

**Evidence artifact**: `artifacts/sdrs-readiness-report.md`

Do NOT continue if result is NOT_READY or BLOCKED.

## STEP 9 — PREPARE DR GATEWAY

**Classification: MANUAL**

**Objective**: Install and configure the DR gateway when required by the topology.

**Inputs**: Gateway requirements from architecture plan.

**Preconditions**: Step 8 result is READY or READY_WITH_WARNINGS. Gateway is required.

**Mechanism**: MANUAL_CONSOLE or MANUAL_SCRIPT.

**Approval requirement**: EXPLICIT.

**Verification**: Gateway service is healthy; network connectivity between gateway and both sites; required ports are open; source and target registration confirmed; no credentials exposed.

**Expected result**: DR gateway operational and registered.

**Stop condition**: Gateway installation fails, registration fails, or connectivity fails.

**Failure action**: STOP. Report gateway failure. Do not continue with protection configuration.

**Evidence artifact**: `artifacts/sdrs-gateway-result.md`

IMPORTANT: Do not include secrets in commands or documentation. Replace credentials with placeholders. Warn about credential exposure in shell history.

## STEP 10 — CONFIGURE PROTECTION

**Classification: MANUAL**

**Objective**: Create protection group, protected instances, and replication pairs; enable protection.

**Inputs**: Architecture plan, gateway status.

**Preconditions**: Step 9 completed (or gateway not required).

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT for each action.

**Verification**: After each action, verify state in console: protection group created and active; protected instance created and replication initializing; replication pair created and active; protection enabled and replication status replicating.

**Expected result**: All resources protected, replication active.

**Stop condition**: Any creation or enable operation fails.

**Failure action**: STOP. Report failure. Do not continue to next sub-step.

**Evidence artifact**: `artifacts/sdrs-protection-result.md`

Each action requires: approval from approval_owner, execution in console, verification of status, capture of sanitized identifier, timestamp recording, result recording.

NEVER use invented hcloud SDRS commands.

## STEP 11 — MONITOR REPLICATION

**Classification: ASSISTED**

**Objective**: Monitor replication status, lag, and health of protected instances and replication pairs.

**Inputs**: Protection group and instance identifiers.

**Preconditions**: Step 10 completed.

**Mechanism**: MANUAL console status check (periodic).

**Approval requirement**: None (read-only monitoring).

**Verification**: Replication status is active, lag is within threshold.

**Expected result**: Replication status report.

**Stop condition**: Replication failed, lag exceeds threshold, or gateway unhealthy.

**Failure action**: Alert. Escalate if critical.

**Evidence artifact**: `artifacts/sdrs-replication-status-report.md`

## STEP 12 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions for protection setup.

**Inputs**: All artifacts from Steps 1-11.

**Preconditions**: All completed steps.

**Mechanism**: Report generation logic.

**Approval requirement**: None.

**Expected result**: Final closure report for protection setup phase.

**Evidence artifact**: `artifacts/sdrs-protection-setup-report.md`

Generate: final summary, architecture deployed, replication status, RPO/RTO plan, unresolved risks, manual actions required, capability gaps identified, MCP recommendation, next skill reference (huawei-sdrs-dr-drill for drill testing, huawei-sdrs-failover-failback for production failover).

Do NOT delete resources automatically.

# Scope boundary

This skill is responsible for protection setup ONLY. It MUST NOT include operational ownership of:

- DR drill execution (use huawei-sdrs-dr-drill)
- Production failover (use huawei-sdrs-failover-failback)
- Reverse reprotection (use huawei-sdrs-failover-failback)
- Failback (use huawei-sdrs-failover-failback)

This skill may reference the next skill in the sequence (huawei-sdrs-dr-drill) for drill testing after protection is established.

# Capability gap handling

When a capability required for SDRS protection setup is not available in existing MCPs or CLI:

1. Document the gap with Gap ID, phase, and impact
2. Classify the gap: critical path or optional
3. Evaluate alternatives: USE_EXISTING_TOOL, EXTEND_EXISTING_MCP, CREATE_NEW_MCP_CANDIDATE, MANUAL_CONSOLE, FUTURE_MCP_CAPABILITY
4. Invoke mcp-capability-builder for gaps requiring CREATE_NEW_MCP_CANDIDATE
5. Update skill status if critical gaps remain
6. Never auto-activate generated MCPs

Known capability gaps:
- GAP-SDR-001: No SDRS CLI support in hcloud 6.2.9. All SDRS operations are MANUAL_CONSOLE. [NOT_AVAILABLE]
- GAP-SDR-002: No SDRS MCP exists. No automation possible for SDRS operations. [NOT_AVAILABLE]
- GAP-SDR-005: SDRS is not in huaweicloud-deploy supported services. Cannot generate SDRS Terraform. [VERIFIED_FROM_CODE]
- GAP-SDR-006: Region pair support must be verified manually. No programmatic capability check available. [REGION_DEPENDENT]
- GAP-SDR-007: DR gateway installation and configuration are manual operations. [NOT_AVAILABLE]

# Output artifacts

- artifacts/sdrs-intent.json
- artifacts/sdrs-capability-assessment.md
- artifacts/sdrs-source-inventory.json
- artifacts/sdrs-target-inventory.json
- artifacts/sdrs-application-dependency-map.md
- artifacts/sdrs-rpo-rto-plan.md
- artifacts/sdrs-architecture-plan.md
- artifacts/sdrs-readiness-report.md
- artifacts/sdrs-gateway-result.md
- artifacts/sdrs-protection-result.md
- artifacts/sdrs-replication-status-report.md
- artifacts/sdrs-protection-setup-report.md

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| SDRS not available in region | Service not supported in region pair | Console service list | Verify region support, consider alternative DR region |
| Region pair not supported | SDRS limitation | Documentation check | Select supported region pair |
| Gateway installation failure | Network, ports, or OS compatibility | Gateway logs | Check network, ports, OS, IAM permissions |
| Protection group creation fails | Quota or region pair issue | Console error | Check quotas, region pair, IAM permissions |
| Protected instance creation fails | ECS compatibility or OS support | Console error | Check ECS compatibility, OS support, disk type |
| Replication pair creation fails | Volume type or AZ mismatch | Console error | Check volume type, size, AZ compatibility |
| Replication lag exceeds threshold | Bandwidth or data change rate | Console replication status | Check bandwidth, data change rate, gateway health |
| Target capacity insufficient | DR site quota or flavor limits | Quota check | Request quota increase, verify available flavors |
| Console field differs from docs | Documentation lag | Console field inspection | Use console as source of truth, report via ticket |

See also: scenario-level `../references/known-issues.md`

# Failure handling

- Authentication failure: Verify hcloud config, region, IAM permissions. Do not retry with different credentials.
- Resource not found: Verify resource name, region, enterprise project. Do not invent IDs.
- Multiple matches: Present all matches. Do not auto-select.
- SDRS not available in region: Verify region support. Consider alternative region or CBR CopyBackup.
- Region pair not supported: Verify supported pairs in documentation. Select alternative DR region.
- Gateway installation failure: Check network, ports, OS compatibility, IAM permissions. Review gateway logs.
- Gateway registration failure: Check gateway health, connectivity, credentials. Do not expose credentials.
- Protection group creation failure: Check quotas, region pair, IAM permissions. Review console error.
- Protected instance creation failure: Check ECS compatibility, OS support, disk type. Verify server is not already protected.
- Replication pair creation failure: Check volume type, size, AZ compatibility. Verify volume is not already replicated.
- Enable protection failure: Check all replication pairs are active. Check gateway health.
- Replication lag exceeds threshold: Check network bandwidth, data change rate, gateway health. Consider bandwidth upgrade.
- Target capacity insufficient: Verify DR site quotas and available ECS flavors. Request quota increase.

# Recovery procedure

1. If failure during gateway setup: Gateway may be partially installed. Clean up gateway resources manually. Verify network. Retry with corrected configuration.
2. If failure during protection configuration: Some resources may be partially protected. Verify status of each resource in console. Clean up partial protection manually. Retry.
3. If failure during replication: Replication may be degraded but not lost. Monitor lag. If replication is broken, assess data consistency and re-enable protection.

# Evidence and traceability

- All hcloud CLI discovery commands logged with timestamps
- All manual console actions documented with timestamps and results
- Protection group, instance, and replication pair identifiers recorded (sanitized)
- Approval decisions recorded with approver identity and timestamp
- Replication status and lag recorded periodically
- No secrets in any artifact

# Known limitations

- No SDRS CLI support in hcloud 6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations are MANUAL via console [NOT_AVAILABLE]
- SDRS service availability varies by region [REGION_DEPENDENT]
- Region pair support must be verified per deployment [REGION_DEPENDENT]
- Cross-region requires async replication only [VERIFIED_FROM_DOCUMENTATION]
- DR gateway is required for cross-region [VERIFIED_FROM_DOCUMENTATION]
- Gateway requirements vary by version and topology [VERSION_DEPENDENT]
- Replication lag depends on data change rate and bandwidth [INFERRED]
- DR site network must be manually configured [VERIFIED_FROM_DOCUMENTATION]
- CBR CopyBackup is backup-based DR, not live replication [VERIFIED_FROM_DOCUMENTATION]
- SDRS is NOT supported by huaweicloud-deploy MCP [VERIFIED_FROM_CODE]
- No automated monitoring or alerting via this skill [NOT_AVAILABLE]
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending [VERSION_DEPENDENT]

# Status justification

Status: EXPERIMENTAL

Evidence:
- SDRS service is NOT available in hcloud CLI v6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations must be performed manually via console [NOT_AVAILABLE]
- No cloud-side tests were executed [NOT_VERIFIED]
- Region pair support is region-dependent [REGION_DEPENDENT]
- The workflow provides value as a controlled runbook for manual execution [INFERRED]
- Discovery of related resources (ECS, EVS, VPC) is possible via hcloud CLI [VERIFIED_FROM_LOCAL_HELP]
- Capability builder integration enables future MCP design [VERIFIED_FROM_CODE]
