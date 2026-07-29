---
name: huawei-sdr-cross-region-replication
version: 1.0.0
description: Discover, plan, execute under human supervision, validate and recover Huawei Cloud cross-region disaster recovery scenarios using SDRS (Storage Disaster Recovery Service) capabilities.
category: migration
risk_level: critical
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
  risk_level: critical
  status: EXPERIMENTAL
  verified_hcloud_version: 6.2.9
  sdrs_cli_support: NOT_AVAILABLE
  sdrs_mcp_support: NOT_AVAILABLE
---

# Purpose

Discover, plan, execute under human supervision, validate and recover Huawei Cloud cross-region and cross-AZ disaster recovery scenarios using SDRS (Storage Disaster Recovery Service), operating as a controlled runbook with manual console execution due to the absence of CLI and MCP support.

# Terminology

| Term | Canonical name | Notes |
|---|---|---|
| SDRS | Storage Disaster Recovery Service | Current canonical name [VERIFIED_FROM_DOCUMENTATION] |
| SDR | Storage Disaster Recovery | Legacy shorthand, alias only [INFERRED] |
| BRS | Business Recovery Service | Separate service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |
| CBR | Cloud Backup and Recovery | Backup service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |

**Decision**: The canonical service name is **SDRS** (Storage Disaster Recovery Service). The skill directory name remains `huawei-sdr-cross-region-replication` per requirement. All documentation uses SDRS as the canonical reference.

# Supported scenario

- Source: Huawei Cloud ECS instances with EVS disks in a production region
- Target: Replicated ECS instances with EVS disks in a DR region
- Mechanism: SDRS protection group + protected instances + replication pairs + DR gateway
- Topology: Cross-region (primary), cross-AZ (secondary)
- Replication: Asynchronous (cross-region), synchronous or asynchronous (cross-AZ)
- Operations: Protect, monitor, drill, planned failover, unplanned failover, reverse reprotection, failback

# When to use this skill

- Setting up cross-region or cross-AZ disaster recovery for ECS instances
- Configuring SDRS protection groups and protected instances
- Monitoring replication status and lag
- Planning and executing DR drills
- Planning and executing planned or unplanned failover
- Planning reverse reprotection after failover
- Planning failback to the original production site
- Discovering existing SDRS configuration and status

# When not to use this skill

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
- Approval owner for failover operations

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
- DNS cutover strategy
- Recovery order for multi-tier applications
- Maintenance window
- Failback expectation
- Data retention requirement
- DR drill requirement

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
5. DR drill requires explicit approval (creates temporary DR resources)
6. Planned failover requires MANDATORY_EXPLICIT_APPROVAL with impact plan (CRITICAL operation)
7. Unplanned failover requires MANDATORY_EXPLICIT_APPROVAL with impact plan (CRITICAL operation)
8. Reverse reprotection requires explicit approval (changes replication direction)
9. Failback requires explicit approval with separate plan (CRITICAL operation)
10. Gateway installation requires explicit approval (modifies server configuration)
11. DNS changes require explicit approval and manual execution (never automatic)
12. No resource deletion is automatic (production or DR site)

# Rules

1. SDRS protects ECS servers through protected instances and replication pairs within a protection group. A protected instance maps a production server to a DR-site server; replication pairs map individual EVS volumes. Do not reduce the service to "volume replication alone". [VERIFIED_FROM_DOCUMENTATION] [REGION_DEPENDENT]

2. Cross-region and cross-AZ may use different operational models. Cross-region requires a DR gateway and uses asynchronous replication. Cross-AZ may support synchronous replication and may or may not require a gateway depending on version. Validate the model for the specific topology before designing. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

3. Validate the region pair or AZ pair before designing any SDRS resources. Not all region combinations are supported. Consult official documentation or console for supported pairs. [VERIFIED_FROM_DOCUMENTATION] [REGION_DEPENDENT]

4. Do not offer sync and async replication as selectable options without confirming that the scenario, topology, and service version support the chosen mode. Cross-region supports async only. Cross-AZ may support both. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT]

5. Before failover, confirm the behavior and accessibility of the secondary (DR-site) resources. The DR-site server may be in a stopped state and must be started after failover. Verify that the DR-site network, security groups, and EIP are configured correctly. [VERIFIED_FROM_DOCUMENTATION]

6. Differentiate clearly between: replication (data sync), protection (SDRS active), DR drill (test exercise), planned failover (controlled switch), unplanned failover (emergency switch), reverse reprotection (reverse replication direction after failover), and failback (return to original primary). These are distinct operations with different prerequisites, risks, and approval requirements. [VERIFIED_FROM_DOCUMENTATION]

7. A DR drill is NOT equivalent to a production failover. A drill creates temporary resources for testing and must be cleaned up. It does not modify production traffic routing. [VERIFIED_FROM_DOCUMENTATION]

8. A disaster recovery gateway is required for cross-region SDRS. Confirm gateway requirements for the specific topology and version before proceeding. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

9. Gateway requirements depend on SDRS version, topology (cross-region vs cross-AZ), and region. Consult current documentation for the specific scenario. [VERIFIED_FROM_DOCUMENTATION] [VERSION_DEPENDENT] [REGION_DEPENDENT]

10. Do not assume that a volume must be detached from its ECS instance for initial SDRS configuration. Confirm the current procedure from official documentation; requirements may vary by version and replication mode. [VERSION_DEPENDENT] [NOT_VERIFIED]

11. The DR architecture must include VPC, subnet, security group, route tables, DNS configuration, EIP or connectivity, and load balancers as applicable. SDRS replicates disks but does not automatically configure network infrastructure at the DR site. [VERIFIED_FROM_DOCUMENTATION]

12. RPO and replication lag depend on data change rate, available bandwidth, inter-region latency, and gateway or channel capacity. Actual RPO may exceed the target under high write load; monitor replication lag continuously and do not treat target RPO as a guarantee. [INFERRED]

13. The DR site should have sufficient compute capacity (ECS flavors, quota) to start or recover all protected servers simultaneously; verify quotas and available capacity before enabling protection as the requirements may vary by workload. [INFERRED]

14. Failover requires explicit approval and a documented impact plan including: affected services, expected downtime, DNS changes, rollback feasibility, and data-loss risk assessment. [INFERRED]

15. Unplanned failover must be used ONLY when the condition of the primary site is confirmed to be unavailable or irrecoverable. It carries higher data-loss risk than planned failover because the last replication state may be uncertain. [VERIFIED_FROM_DOCUMENTATION]

16. Reverse reprotection is NOT equivalent to failback. Reverse reprotection re-establishes replication in the reverse direction (DR site to production site) after failover. Failback is the full process of returning production to the original site, which includes reverse reprotection, synchronization validation, and controlled switchback. [VERIFIED_FROM_DOCUMENTATION]

17. Failback requires a separate plan, synchronization validation, and explicit approval. Do not assume failback is automatic or immediate after reverse reprotection. [VERIFIED_FROM_DOCUMENTATION]

18. Do not update DNS automatically. DNS cutover must be planned, approved, and executed manually or through a separate controlled process; automated DNS changes during failover carry significant risk. [INFERRED]

19. Do not delete production or DR resources automatically. Preserve both sites until explicit cleanup approval; premature deletion may cause irreversible data loss. [INFERRED]

20. DISCOVER BEFORE CREATE: never hardcode protection group IDs, instance IDs, volume IDs, or gateway IDs. Always discover existing resources first. [VERIFIED_FROM_DOCUMENTATION]

21. VERIFY AFTER EVERY STEP: each manual console action should be followed by a verification step to confirm the expected state; the exact verification method depends on the SDRS console capabilities. [INFERRED]

22. No hardcoded IDs in any artifact, command, or example. [INFERRED]

23. Do not continue when multiple ambiguous matches exist for a resource. Present all matches and request clarification. [INFERRED]

24. No write operations without explicit approval. [INFERRED]

25. Never include secrets (AK, SK, tokens, passwords, project IDs, private keys, account IDs) in commands, examples, files, or logs. [INFERRED]

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
| Route and DNS plan | Yes | Failover cutover strategy | Documented in intent |
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

**Objective**: Extract and validate all required and optional inputs for the DR scenario.

**Inputs**: User request specifying scenario, regions, AZs, ECS names, disk scope, RPO, RTO, approval owner, and all optional parameters.

**Preconditions**: None.

**Mechanism**: Parsing logic.

**Approval requirement**: None.

**Verification**: Confirm all required fields are present.

**Expected result**: Complete intent object with all required fields populated.

**Stop condition**: Critical information missing.

**Failure action**: STOP and request clarification. Do not invent values. No write operations.

**Evidence artifact**: `artifacts/sdr-intent.json`

Extract:
- scenario: cross-region or cross-AZ
- production_region
- dr_region
- production_az
- dr_az
- source_ecs_names
- disk_scope
- application_type
- stateful_or_stateless
- target_rpo
- target_rto
- planned_or_unplanned_scenario
- dr_drill_requirement
- gateway_topology
- network_bandwidth
- target_vpc
- target_subnet
- target_security_groups
- dns_cutover_strategy
- recovery_order
- maintenance_window
- approval_owner
- failback_expectation
- data_retention_requirement

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

**Evidence artifact**: `artifacts/sdr-capability-assessment.md`

Determine:
- canonical service name: SDRS (Storage Disaster Recovery Service)
- service availability in both regions
- cross-region support for the region pair
- cross-AZ support for the AZ pair
- supported source and target locations
- supported operating systems
- supported server types
- replication model (async for cross-region, sync or async for cross-AZ)
- gateway requirement
- known limitations

Sources permitted:
- Official Huawei Cloud documentation
- Console read-only exploration (Playwright for form/field discovery)
- Official API documentation
- Official SDK documentation

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

**Verification**:
- Exactly one match for each source ECS name (reject zero matches, reject ambiguous multiple matches)
- All required disks discovered and attached
- VPC, subnet, security group IDs resolved
- Region matches production_region
- Resource states are compatible with SDRS protection

**Expected result**: Complete production resource inventory with names resolved to IDs.

**Stop condition**: Zero matches, ambiguous matches, region mismatch, invalid state, unsupported disk type, unsupported server configuration.

**Failure action**: STOP. Report discovery failure.

**Evidence artifact**: `artifacts/sdr-source-inventory.json`

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

For existing SDRS resources (MANUAL console):
- Check for existing protection groups
- Check for existing protected instances
- Check for existing replication pairs
- Check for existing DR gateway

**Verification**: DR site has required network infrastructure. Existing SDRS resources documented.

**Expected result**: Complete DR site inventory.

**Stop condition**: DR site network infrastructure missing, SDRS not available in DR region.

**Failure action**: STOP. Report missing DR infrastructure.

**Evidence artifact**: `artifacts/sdr-target-inventory.json`

## STEP 5 — APPLICATION DEPENDENCY ANALYSIS

**Classification: AUTOMATED**

**Objective**: Map application components, dependencies, boot order, and consistency requirements.

**Inputs**: source_ecs_names, source inventory, application_type.

**Preconditions**: Steps 3-4 completed.

**Mechanism**: Analysis logic based on discovered resources.

**Approval requirement**: None.

**Verification**: Dependency map is complete and consistent.

**Expected result**: Application dependency map with recovery sequence.

**Stop condition**: Circular dependencies detected, critical dependencies missing.

**Failure action**: STOP. Report dependency analysis failure.

**Evidence artifact**: `artifacts/sdr-application-dependency-map.md`

Inventory:
- Application components (web, app, database tiers)
- Boot order and startup sequence
- Shutdown sequence
- Attached disks per server
- Databases and shared storage
- Load balancers and EIPs
- DNS records
- Certificates and secrets (references only, never values)
- External dependencies
- Region-specific services
- Consistency requirements (application-consistent vs crash-consistent)

## STEP 6 — RPO, RTO AND BANDWIDTH PLAN

**Classification: ASSISTED**

**Objective**: Calculate or document RPO, RTO, bandwidth, and monitoring requirements.

**Inputs**: target_rpo, target_rto, network_bandwidth, source inventory.

**Preconditions**: Step 5 completed.

**Mechanism**: Analysis based on data change rate, available bandwidth, and SDRS replication characteristics.

**Approval requirement**: None.

**Verification**: Plan is internally consistent.

**Expected result**: RPO/RTO plan with monitoring thresholds.

**Stop condition**: Required RPO cannot be achieved with available bandwidth.

**Failure action**: Report RPO/bandwidth gap. Recommend bandwidth upgrade or adjusted RPO.

**Evidence artifact**: `artifacts/sdr-rpo-rto-plan.md`

Calculate or document:
- target RPO
- target RTO
- peak changed-data rate (estimated)
- available bandwidth
- replication lag threshold
- monitoring interval
- expected recovery sequence and timing
- acceptance criteria

Note: Do not invent product-specific formulas. Document SDRS replication behavior based on official documentation.

## STEP 7 — ARCHITECTURE PLAN

**Classification: AUTOMATED**

**Objective**: Design the complete DR architecture including production site, DR site, protection groups, protected instances, replication pairs, gateway, network, and failover/failback procedures.

**Inputs**: All artifacts from Steps 1-6.

**Preconditions**: Steps 1-6 completed.

**Mechanism**: Architecture design logic.

**Approval requirement**: None (plan only, no execution).

**Verification**: Plan covers all required components.

**Expected result**: Complete DR architecture plan.

**Stop condition**: Insufficient information to design architecture.

**Failure action**: STOP. Report missing information.

**Evidence artifact**: `artifacts/sdr-architecture-plan.md`

Design:
- Production site layout
- DR site layout
- Protection groups (name, domain, source AZ, target AZ)
- Protected instances (source server, target server, replication pairs)
- Replication pairs (source volume, target volume, replication mode)
- DR gateway (when required, placement, network)
- VPC, subnets, security groups at DR site
- Route tables and DNS configuration
- EIP and load balancer mapping
- Monitoring strategy
- Ticket escalation procedure
- Rollback procedure
- Failback procedure

Classify each element:
- EXISTING: already present, no action needed
- REUSE: existing resource can be reused with modification
- CREATE_MANUALLY: must be created via console
- CREATE_WITH_EXISTING_MCP: can be created using deploy MCP (VPC/SG only)
- FUTURE_SDRS_MCP: would require a dedicated SDRS MCP (not yet available)
- NOT_REQUIRED: not needed for this scenario

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

**Evidence artifact**: `artifacts/sdr-readiness-report.md`

Validate:
- Regional support confirmed
- Quotas sufficient in both regions
- IAM permissions verified
- OS support confirmed for all ECS instances
- Agent or gateway prerequisites met
- Target compute capacity sufficient
- Network connectivity between regions verified
- Bandwidth sufficient for replication
- Application dependencies satisfied
- DNS plan documented
- DR drill plan documented (if required)
- Failover plan documented
- Failback plan documented
- Approval owners identified and available

Result classification:
- READY: All checks pass
- READY_WITH_WARNINGS: Non-critical warnings present
- NOT_READY: Critical prerequisites missing
- BLOCKED: Fundamental blocker exists (e.g., unsupported region pair)

Do NOT continue if result is NOT_READY or BLOCKED.

## STEP 9 — PREPARE DR GATEWAY

**Classification: MANUAL**

**Objective**: Install and configure the DR gateway when required by the topology.

**Inputs**: Gateway requirements from architecture plan.

**Preconditions**: Step 8 result is READY or READY_WITH_WARNINGS. Gateway is required.

**Mechanism**: MANUAL_CONSOLE or MANUAL_SCRIPT.

**Approval requirement**: EXPLICIT.

**Verification**:
- Gateway service is healthy
- Network connectivity between gateway and both sites
- Required ports are open
- Source and target registration confirmed
- No credentials exposed in configuration

**Expected result**: DR gateway operational and registered.

**Stop condition**: Gateway installation fails, registration fails, or connectivity fails.

**Failure action**: STOP. Report gateway failure. Do not continue with protection configuration.

**Evidence artifact**: `artifacts/sdr-gateway-result.md`

IMPORTANT:
- Do not include secrets in commands or documentation
- Replace credentials with placeholders (e.g., `<GATEWAY_ACCESS_KEY>`)
- Warn about credential exposure in shell history
- Recommend secure credential delivery mechanism

## STEP 10 — CONFIGURE PROTECTION

**Classification: MANUAL**

**Objective**: Create protection group, protected instances, and replication pairs; enable protection.

**Inputs**: Architecture plan, gateway status.

**Preconditions**: Step 9 completed (or gateway not required).

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT for each action.

**Verification**: After each action, verify state in console:
- Protection group: created, status active
- Protected instance: created, replication initializing
- Replication pair: created, status active
- Protection enabled: replication status replicating

**Expected result**: All resources protected, replication active.

**Stop condition**: Any creation or enable operation fails.

**Failure action**: STOP. Report failure. Do not continue to next sub-step.

**Evidence artifact**: `artifacts/sdr-protection-result.md`

Each action requires:
1. Approval from approval_owner
2. Execution in console
3. Verification of status
4. Capture of sanitized identifier
5. Timestamp recording
6. Result recording

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

**Evidence artifact**: `artifacts/sdr-replication-status-report.md`

Monitor:
- Protection status per instance
- Replication state per pair
- Replication lag per pair
- Warnings or errors
- Gateway health
- Network health between sites
- Protected instance count
- Failed or degraded pairs

Define stop conditions and alert thresholds.

## STEP 12 — PREPARE DR DRILL

**Classification: MANUAL**

**Objective**: Prepare a DR drill plan with defined scope, validation criteria, and cleanup procedure.

**Inputs**: Protection group, application dependency map, RPO/RTO targets.

**Preconditions**: Step 10 completed and replication is active.

**Mechanism**: Plan generation.

**Approval requirement**: EXPLICIT (drill plan approval).

**Verification**: Plan is complete and consistent.

**Expected result**: DR drill plan ready for execution.

**Stop condition**: Protection not active, or prerequisites missing.

**Failure action**: STOP. Report missing prerequisites.

**Evidence artifact**: `artifacts/sdr-drill-plan.md`

The drill plan must include:
- Defined scope (which instances, which applications)
- Isolation mechanism (does not modify production)
- Validation plan (what to verify at DR site)
- Cleanup plan (how to remove drill resources)
- DNS isolation (drill must not affect production DNS)
- Business validation criteria
- RPO and RTO measurement method
- Approval from approval_owner

## STEP 13 — EXECUTE AND VALIDATE DR DRILL

**Classification: MANUAL**

**Objective**: Execute the DR drill and validate recovery at the DR site.

**Inputs**: DR drill plan.

**Preconditions**: Step 12 plan approved.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT.

**Verification**: All validation criteria pass.

**Expected result**: DR drill successful, RPO and RTO measured.

**Stop condition**: Drill creation fails, or DR server cannot boot.

**Failure action**: Report drill failure. Execute cleanup. Do NOT affect production.

**Evidence artifact**: `artifacts/sdr-drill-result.md`

Verify at DR site:
- Recovered servers boot successfully
- Disk state is consistent
- Application start order is correct
- Network connectivity is functional
- Security groups are applied correctly
- DNS isolation is maintained
- Data consistency is acceptable
- Application tests pass
- RPO is within target
- RTO is within target

IMPORTANT: A drill is NOT a production failover. Do not modify production DNS or routing.

## STEP 14 — PLAN FAILOVER

**Classification: MANUAL**

**Objective**: Create a comprehensive failover plan with impact analysis, trigger criteria, and rollback strategy.

**Inputs**: Protection group status, replication status, application dependency map, DNS configuration.

**Preconditions**: Step 10 completed and replication is active.

**Mechanism**: Plan generation.

**Approval requirement**: EXPLICIT (plan approval).

**Verification**: Plan is complete and consistent.

**Expected result**: Failover plan ready for execution.

**Stop condition**: Replication not active, or critical information missing.

**Failure action**: STOP. Report missing prerequisites.

**Evidence artifact**: `artifacts/sdr-failover-plan.md`

Differentiate:
- **Planned failover**: Production is accessible; applications can be quiesced; last replication sync is confirmed; lower data-loss risk.
- **Unplanned failover**: Production is unavailable; last replication state may be uncertain; higher data-loss risk; use ONLY when primary site condition is confirmed.

The plan must include:
- Trigger criteria and authority
- Production site current state
- Last replication status and lag
- Application shutdown procedure (if planned)
- DNS change procedure
- Route change procedure
- Validation procedure
- Communication plan
- Rollback feasibility assessment
- Data-loss risk assessment
- Timestamps for all steps

## STEP 15 — EXECUTE FAILOVER

**Classification: MANUAL**

**Objective**: Execute the failover operation.

**Inputs**: Failover plan, explicit approval.

**Preconditions**: Step 14 plan approved.

**Mechanism**: MANUAL_CONSOLE.

**Risk**: CRITICAL

**Approval requirement**: MANDATORY_EXPLICIT_APPROVAL

**Verification**: DR site resources are active, applications are functional, DNS is updated.

**Expected result**: Production workload running at DR site.

**Stop condition**: Failover operation fails in console.

**Failure action**: STOP. Preserve both sites. Report failure. Do NOT delete resources.

**Evidence artifact**: `artifacts/sdr-failover-result.md`

After failover, verify:
- DR site servers are running
- Replication state reflects failover
- Applications are functional at DR site
- Network connectivity is correct
- DNS points to DR site (manual update)
- RPO measured (data loss assessment)
- RTO measured (recovery time)
- Production site resources are preserved
- Incident timeline documented

## STEP 16 — REVERSE REPROTECTION

**Classification: MANUAL**

**Objective**: Re-establish replication in the reverse direction (DR site to production site) after failover.

**Inputs**: Failover result, protection group status.

**Preconditions**: Step 15 completed successfully.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT.

**Verification**: Reverse replication is active, lag is within threshold.

**Expected result**: Reverse replication protecting the new primary (DR site).

**Stop condition**: Reverse reprotection unavailable or fails.

**Failure action**: Alert. DR site is unprotected. Escalate immediately.

**Evidence artifact**: `artifacts/sdr-reverse-reprotection-plan.md`

Validate before reverse reprotection:
- Source and target roles are correctly identified
- Replication direction is understood
- Data consistency at DR site is confirmed
- Network connectivity between sites is functional
- Gateway is operational
- Capacity at original production site is sufficient
- Application state at DR site is stable

IMPORTANT: Reverse reprotection is NOT failback. It only re-establishes replication. Failback is a separate, subsequent operation.

## STEP 17 — FAILBACK

**Classification: MANUAL**

**Objective**: Return production to the original site with a controlled process.

**Inputs**: Reverse reprotection status, original production site status.

**Preconditions**: Step 16 completed. Reverse replication is active.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT (separate from failover approval).

**Verification**: Production site is active, applications are functional, replication is re-established in original direction.

**Expected result**: Production running at original site, replication active.

**Stop condition**: Synchronization not complete, or original site not ready.

**Failure action**: STOP. Remain at DR site. Report failback failure.

**Evidence artifact**: `artifacts/sdr-failback-plan.md`

Failback requires a separate plan including:
- Recovery of original primary site infrastructure
- Resynchronization validation (replication lag is zero or minimal)
- Consistency validation at original site
- Application shutdown or quiescence at DR site
- Reverse direction failover (DR site to production site)
- DNS restoration to original production
- Application verification at original site
- RPO and RTO measurement
- Rollback alternative (remain at DR site)
- Explicit approval from approval_owner

## STEP 18 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-17.

**Preconditions**: All completed steps.

**Mechanism**: Report generation logic.

**Approval requirement**: None.

**Verification**: Report is complete.

**Expected result**: Final closure report.

**Stop condition**: None.

**Failure action**: Report with incomplete sections marked.

**Evidence artifact**: `artifacts/sdr-final-report.md`

Generate:
- Final summary
- Architecture deployed (or planned)
- Drill or failover result (if executed)
- RPO result (measured or estimated)
- RTO result (measured or estimated)
- Unresolved risks
- Manual actions required
- Capability gaps identified
- MCP recommendation (SDRS MCP candidate)
- Ticket recommendation (if issues found)
- Next test date recommendation

Do NOT delete resources automatically.

# Capability gap handling

When a capability required for SDRS DR is not available in existing MCPs or CLI:

1. Document the gap in capability-gap-policy.md with Gap ID, phase, and impact
2. Classify the gap: critical path or optional
3. Evaluate alternatives:
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL
   - Can an existing MCP be extended? → EXTEND_EXISTING_MCP
   - Is a new MCP needed? → CREATE_NEW_MCP_CANDIDATE (last resort)
   - Can the step be performed manually via console? → MANUAL_CONSOLE
   - Can the step be documented for future MCP? → FUTURE_MCP_CAPABILITY
4. Invoke mcp-capability-builder for gaps requiring CREATE_NEW_MCP_CANDIDATE
5. Update skill status if critical gaps remain
6. Never auto-activate generated MCPs

Known capability gaps:
- GAP-SDR-001: No SDRS CLI support in hcloud 6.2.9. All SDRS operations are MANUAL_CONSOLE. [NOT_AVAILABLE]
- GAP-SDR-002: No SDRS MCP exists. No automation possible for SDRS operations. [NOT_AVAILABLE]
- GAP-SDR-003: Failover, reverse reprotection, and failback are critical operations with no automation safeguard. [NOT_AVAILABLE]
- GAP-SDR-004: Replication monitoring requires manual console checks. No automated alerting via this skill. [NOT_AVAILABLE]
- GAP-SDR-005: SDRS is not in huaweicloud-deploy supported services. Cannot generate SDRS Terraform. [VERIFIED_FROM_CODE]
- GAP-SDR-006: Region pair support must be verified manually. No programmatic capability check available. [REGION_DEPENDENT]
- GAP-SDR-007: DR gateway installation and configuration are manual operations. [NOT_AVAILABLE]

# Output artifacts

- artifacts/sdr-intent.json — Parsed intent
- artifacts/sdr-capability-assessment.md — SDRS capability assessment
- artifacts/sdr-source-inventory.json — Production resource inventory
- artifacts/sdr-target-inventory.json — DR site resource inventory
- artifacts/sdr-application-dependency-map.md — Application dependency map
- artifacts/sdr-rpo-rto-plan.md — RPO/RTO and bandwidth plan
- artifacts/sdr-architecture-plan.md — DR architecture plan
- artifacts/sdr-readiness-report.md — Readiness review report
- artifacts/sdr-gateway-result.md — Gateway setup result
- artifacts/sdr-protection-result.md — Protection configuration result
- artifacts/sdr-replication-status-report.md — Replication monitoring report
- artifacts/sdr-drill-plan.md — DR drill plan
- artifacts/sdr-drill-result.md — DR drill result
- artifacts/sdr-failover-plan.md — Failover plan
- artifacts/sdr-failover-result.md — Failover result
- artifacts/sdr-reverse-reprotection-plan.md — Reverse reprotection plan
- artifacts/sdr-failback-plan.md — Failback plan
- artifacts/sdr-final-report.md — Final closure report

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
| Failover rejected | Protection status or replication state | Console task status | Verify protection status, replication state, approval |
| Unplanned failover uncertain state | Primary site condition unknown | Manual assessment | Assess data loss risk, verify DR site consistency |
| Reverse reprotection unavailable | SDRS version or region support | Console capability check | Check SDRS version, region support, gateway |
| Target capacity insufficient | DR site quota or flavor limits | Quota check | Request quota increase, verify available flavors |
| Console field differs from docs | Documentation lag | Console field inspection | Use console as source of truth, report via ticket |

See also: `docs/known-issues.md`

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
- Replication pair degraded or failed: Check network, source volume health, target volume health. Escalate.
- Drill creation fails: Check quotas, capacity, protection status. Do not affect production.
- Drill server cannot boot: Check DR site network, security groups, OS image. Do not affect production.
- Failover rejected: Check protection status, replication state, approval. Verify all prerequisites.
- Unplanned failover uncertain state: Assess data loss risk. Verify DR site data consistency. Do not assume primary is lost.
- Reverse reprotection unavailable: Check SDRS version, region support, gateway. DR site is unprotected — escalate.
- Failback blocked: Check reverse replication status, original site capacity, synchronization. Remain at DR site.
- Target capacity insufficient: Verify DR site quotas and available ECS flavors. Request quota increase.
- IAM permission denied: Verify required permissions in both regions. Request IAM admin assistance.
- Quota exceeded: Request quota increase via ticket. Do not proceed without sufficient quota.
- Console field differs from documentation: Document discrepancy. Use console as source of truth. Report via ticket.
- API or service version mismatch: Verify SDRS API version in both regions. Document version.

# Recovery procedure

1. If failure during gateway setup: Gateway may be partially installed. Clean up gateway resources manually. Verify network. Retry with corrected configuration.
2. If failure during protection configuration: Some resources may be partially protected. Verify status of each resource in console. Clean up partial protection manually. Retry.
3. If failure during replication: Replication may be degraded but not lost. Monitor lag. If replication is broken, assess data consistency and re-enable protection.
4. If failure during drill: Drill resources may exist. Clean up drill resources manually. Verify production is unaffected. Document drill failure.
5. If failure during failover: Both sites may be in uncertain state. DO NOT modify either site automatically. Assess state of both sites manually. Decide next action based on data consistency assessment.
6. If failure during reverse reprotection: DR site is unprotected. This is a critical state. Establish reverse reprotection as soon as possible. If not possible, consider alternative protection (CBR backup).
7. If failure during failback: Remain at DR site. Verify DR site is functional. Re-attempt failback only after resolving the failure cause. Do not force failback.

# Evidence and traceability

- All hcloud CLI discovery commands logged with timestamps
- All manual console actions documented with timestamps and results
- Protection group, instance, and replication pair identifiers recorded (sanitized)
- Approval decisions recorded with approver identity and timestamp
- Replication status and lag recorded periodically
- RPO and RTO measurements recorded
- Failover and failback timelines documented
- DNS changes documented with before/after state
- No secrets in any artifact
- Console screenshots or exports preserved when possible (sanitized)

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
- DNS cutover is manual [INFERRED]
- CBR CopyBackup is backup-based DR, not live replication [VERIFIED_FROM_DOCUMENTATION]
- SDRS is NOT supported by huaweicloud-deploy MCP [VERIFIED_FROM_CODE]
- No automated monitoring or alerting via this skill [NOT_AVAILABLE]
- Failover is a critical operation with no automation safeguard [NOT_AVAILABLE]
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending [VERSION_DEPENDENT]

# Status justification

Status: EXPERIMENTAL

Evidence:
- SDRS service is NOT available in hcloud CLI v6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations must be performed manually via console [NOT_AVAILABLE]
- Failover, reverse reprotection, and failback are critical operations with no automation [NOT_AVAILABLE]
- No cloud-side tests were executed [NOT_VERIFIED]
- Region pair support is region-dependent [REGION_DEPENDENT]
- The workflow provides value as a controlled runbook for manual execution [INFERRED]
- Discovery of related resources (ECS, EVS, VPC) is possible via hcloud CLI [VERIFIED_FROM_LOCAL_HELP]
- Capability builder integration enables future MCP design [VERIFIED_FROM_CODE]
