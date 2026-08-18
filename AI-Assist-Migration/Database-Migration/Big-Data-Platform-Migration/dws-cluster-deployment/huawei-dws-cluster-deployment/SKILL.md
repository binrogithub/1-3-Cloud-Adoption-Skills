---
name: huawei-dws-cluster-deployment
version: 1.0.0
description: Discover, plan, deploy, validate and configure a Huawei Cloud DWS cluster using verified hcloud CLI operations and controlled approval gates.
category: migration
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Big-Data
  family: Data-Warehouse-Deployment
  service: DWS
  risk_level: high
  status: READY_WITH_WARNINGS
  verified_hcloud_version: 6.2.9
  newer_version_validation_pending: 7.2.12
---

# Purpose

Discover, plan, deploy, validate and configure a Huawei Cloud DWS (GaussDB(DWS)) data warehouse cluster using verified hcloud CLI operations and controlled approval gates, ensuring secure credential handling, capacity planning, and post-deployment validation.

# Supported scenario

- Source: User requirements for a new DWS cluster in a Huawei Cloud region
- Target: Operational DWS cluster with validated connectivity
- Mechanism: hcloud DWS CLI (primary) + optional MCPs for prerequisites
- Topology: Single-AZ or HA cluster with private or public access
- Storage: DWS-managed storage (SSD/SAS/EVS, region-dependent)
- Access: PostgreSQL-compatible protocol (port 8000 default, range 8000-30000)

# When to use this skill

- Deploying a new DWS cluster for data warehousing workloads
- Discovering available DWS node types, versions, and capabilities in a region
- Planning DWS cluster capacity and cost before deployment
- Validating DWS cluster prerequisites (VPC, subnet, security group)
- Configuring snapshot policies for an existing DWS cluster
- Verifying DWS cluster health and connectivity after deployment

# When not to use this skill

- Migrating data between DWS clusters (use DWS snapshot/restore or data migration tools)
- Managing DRS replication tasks (use huawei-postgresql-ecs-to-rds-drs-cross-region skill)
- Deploying DataArts Studio pipelines (use huawei-snowflake-to-dataarts-migration skill)
- When no hcloud CLI is available and cannot be installed
- When automated cluster deletion is required (never automated in this skill)
- When real-time DWS monitoring is required (use Cloud Eye / CES)

# Required inputs

- Region
- Cluster name
- Environment: dev, test, staging, production
- Approval owner
- Password source (never plain text)

# Optional inputs

- Engine version preference
- Node type preference
- Node count
- Storage type and capacity
- HA requirement
- AZ preference
- VPC name
- Subnet name
- Security group name
- Access mode: private-only or public
- EIP requirement
- Database name
- Administrator username (default: dbadmin)
- OBS loading requirement
- Snapshot schedule and retention
- Enterprise project
- Tags
- Estimated budget
- Maintenance window
- Workload type
- Expected data volume
- Expected daily growth
- Concurrency
- Query complexity
- Latency objective

# Required MCPs

None. DWS operations are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-pricing (for cost estimation, read-only)
- huaweicloud-ticket (for support ticket creation if issues arise)
- huaweicloud-deploy (for VPC/subnet/SG infrastructure prerequisites only; NOT for DWS resources)

# Tool selection policy

1. Use hcloud DWS CLI for all DWS cluster lifecycle operations.
2. Use huaweicloud-pricing MCP only for cost estimation (read-only, non-blocking).
3. Use huaweicloud-deploy MCP only for VPC/subnet/SG prerequisites (supported services only).
4. Do NOT use huaweicloud-deploy MCP for DWS resources (DWS not in supported services).
5. Use huaweicloud-ticket MCP only for support ticket preparation (create_ticket requires approval).
6. Use mcp-capability-builder shared skill for future MCP extension design.
7. Never use playwright for DWS write operations.

# Safety and approval gates

1. Every write operation requires explicit approval before execution.
2. CreateCluster requires explicit approval and completed readiness check.
3. DeleteCluster requires explicit approval and pre-deletion snapshot verification.
4. ResizeCluster requires explicit approval and capacity validation.
5. RestartCluster requires explicit approval and active query check.
6. CreateSnapshot requires explicit approval.
7. RestoreCluster requires explicit approval (creates new cluster, incurs cost).
8. BindEIP requires explicit approval and security group validation.
9. ResetPassword requires explicit approval.
10. Never open DWS port to 0.0.0.0/0.
11. Never store or log the database administrator password.
12. Never execute delete or restore operations automatically.

# Rules

The following rules are candidates and must be validated against the specific region, version, and cluster configuration.

1. **PostgreSQL compatibility is partial**: DWS offers compatibility with the PostgreSQL protocol and ecosystem, but must NOT be presented as standard PostgreSQL. Do not assume total compatibility. [VERIFIED_FROM_DOCUMENTATION]

2. **Engine version must be discovered**: The version must be discovered among those available in the region. Do not hardcode a version 8.x.x without verifying availability. [REGION_DEPENDENT]

3. **Node count constraints are configuration-dependent**: The minimum and maximum number of nodes depends on the flavor, version, mode, region, and type of cluster. For a cluster, number_of_node ranges from 3 to 256. For a hybrid data warehouse (standalone), the value is 1. [VERIFIED_FROM_LOCAL_HELP]

4. **Do not assume three nodes is always the minimum**: Differentiate between development (standalone, 1 node), test (3 nodes minimum for cluster), and production (3+ nodes with HA). [VERIFIED_FROM_LOCAL_HELP]

5. **Node types must be discovered**: Use `hcloud DWS ListNodeTypes` to obtain available node types for the region. Do not hardcode flavors. [VERIFIED_FROM_LOCAL_HELP]

6. **Do not hardcode flavors**: Flavors like `m3.xlarge.4` are examples only. Use them only when confirmed available in the queried region. [REGION_DEPENDENT]

7. **Storage types must be discovered**: Do not assume SSD, SAS, or EVS are available in all regions or versions. [REGION_DEPENDENT]

8. **Cluster requires network prerequisites**: The cluster requires a pre-existing VPC, subnet, and security group. [VERIFIED_FROM_LOCAL_HELP]

9. **Subnet IP capacity should be validated**: The subnet should have sufficient addresses for current nodes, internal components, and future growth; the exact number of required IPs may vary by cluster configuration. [INFERRED]

10. **Cluster name constraints**: The cluster name must contain 4 to 64 characters, start with a letter, and contain only letters, digits, hyphens (-), and underscores (_). [VERIFIED_FROM_LOCAL_HELP]

11. **Database username constraints**: The administrator username must consist of lowercase letters, digits, or underscores; start with a lowercase letter or underscore; contain 1 to 63 characters; cannot be a DWS database keyword. [VERIFIED_FROM_LOCAL_HELP]

12. **Port range**: The service port ranges from 8000 to 30000. The default value is 8000. [VERIFIED_FROM_LOCAL_HELP]

13. **HA topology must be validated**: HA and AZ distribution must be validated against the real options of the service. [REGION_DEPENDENT]

14. **Resize capabilities are version-dependent**: Do not assert that nodes can only be added and never removed without evidence for the selected version. [VERSION_DEPENDENT]

15. **Plan capacity before creating**: Resize can be costly, limited, or long-running; verify the resize capabilities and impact for the specific version before executing. [INFERRED]

16. **Snapshot policy is version-dependent**: Automatic or periodic snapshots must be configured according to the real capabilities of the version. [VERSION_DEPENDENT]

17. **Public access requires EIP and security group**: Public access requires EIP and security group rules only if the region and cluster support that mode. [VERIFIED_FROM_LOCAL_HELP]

18. **Never open DWS port to 0.0.0.0/0**: Always restrict to authorized CIDR; the security policy for the specific environment should define the allowed source. [INFERRED]

19. **Cluster name must be unique**: CreateCluster requires a name unique within the scope defined by the API. [VERIFIED_FROM_LOCAL_HELP]

20. **Creation is asynchronous**: Creation takes 10 to 15 minutes per API documentation. Do not treat this as an SLA; use it only as an operational reference. [VERIFIED_FROM_LOCAL_HELP]

21. **Use verified polling**: Use ShowCluster or ListClusters with verified states for polling. [VERIFIED_FROM_LOCAL_HELP]

22. **Never store password in shell history**: Do not place the password in visible command lines or shell history; use secure input mechanisms. [INFERRED]

23. **Never include passwords in examples**: Do not include passwords directly in executable examples. [INFERRED]

24. **Prefer secure credential input**: Use `--cli-jsonInput`, a protected environment variable, or a temporary file with 0600 permissions when the CLI supports it. [VERIFIED_FROM_LOCAL_HELP]

25. **OBS loads require validation**: Loads from OBS require verifying permissions, format, location, and compatibility; the exact requirements may vary by DWS version and OBS configuration. [INFERRED]

26. **External table syntax is version-dependent**: Do not assert a specific external table syntax without validation against the DWS version. [VERSION_DEPENDENT]

27. **Advanced features require verification**: CTI, hybrid cluster, IPv6, or other advanced features must be documented only if verified for the cluster type. [VERSION_DEPENDENT]

28. **DISCOVER BEFORE CREATE**: Always discover existing resources before creating new ones. [VERIFIED_FROM_LOCAL_HELP]

29. **VERIFY AFTER EVERY STEP**: Verify the result of every operation. [VERIFIED_FROM_LOCAL_HELP]

30. **No hardcoded IDs**: Resolve names to IDs dynamically. [INFERRED]

31. **Reject ambiguous matches**: Stop if name resolution returns multiple matches. [INFERRED]

32. **All writes require explicit approval**: No write operation executes without approval. [INFERRED]

33. **No automatic delete or restore**: Never execute delete or restore automatically. [INFERRED]

34. **No secrets or customer data**: Never include secrets, customer names, or real cluster IDs. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI 6.2.9 | Yes | DWS cluster lifecycle operations | `hcloud DWS --help` |
| Huawei Cloud authentication | Yes | API access | `hcloud IAM ShowCredential` or configured profile |
| Target region | Yes | DWS service availability | `hcloud DWS ListClusters --cli-region=<REGION>` |
| Project context | Yes | Resource scoping | Configured in hcloud profile |
| DWS service availability | Yes | Service enabled in region | `hcloud DWS ListNodeTypes --cli-region=<REGION>` |
| Supported AZ | Yes | Cluster placement | Discovered via ListNodeTypes or region query |
| Supported engine version | Yes | Cluster version | Discovered via ListUpdatableVersion |
| Supported node type | Yes | Cluster sizing | `hcloud DWS ListNodeTypes --cli-region=<REGION>` |
| Supported storage type | Yes | Cluster storage | Discovered from ListNodeTypes response |
| VPC | Yes | Network isolation | `hcloud VPC ListVpcs` |
| Subnet | Yes | Cluster network | `hcloud VPC ListSubnets` |
| Security group | Yes | Access control | `hcloud VPC ListSecurityGroups` |
| Sufficient subnet IP capacity | Yes | Node addressing | Calculated from subnet CIDR |
| IAM permissions | Yes | DWS create/manage | Policy validation |
| DWS quota | Yes | Cluster limit | Quota check |
| Compute or node quota | Yes | Node limit | Quota check |
| Storage quota | Yes | Storage limit | Quota check |
| Database administrator password source | Yes | Secure credential | Never plain text |
| Private DNS or endpoint plan | Yes | Connectivity | Post-deployment |
| Optional EIP | No | Public access | `hcloud VPC ListPublicIps` |
| Optional OBS bucket | No | Data loading | OBS validation |
| Optional huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| Optional huaweicloud-ticket MCP | No | Support tickets | MCP availability check |
| Optional huaweicloud-deploy MCP | No | Network prerequisites | MCP availability check |
| mcp-capability-builder shared skill | Yes (shared) | Future MCP design | Skill existence check |

# Workflow

## STEP 1 — PARSE INTENT

- **Objective**: Extract and validate all deployment requirements
- **Classification**: AUTOMATED
- **Inputs**: User request with region, cluster name, environment, workload parameters
- **Preconditions**: User has provided deployment intent
- **Command**: None (logic)
- **Approval**: None
- **Verification**: All required fields present
- **Expected result**: Complete intent specification
- **Stop condition**: Missing critical information
- **Failure action**: STOP, ASK FOR CLARIFICATION, NO WRITE OPERATIONS
- **Evidence artifact**: `artifacts/dws-intent.json`

Extract: region, cluster name, environment, workload type, expected data volume, expected daily growth, concurrency, query complexity, latency objective, engine version preference, node type preference, node count, storage type, storage capacity, HA requirement, AZ preference, VPC, subnet, security group, access mode, EIP requirement, database name, administrator username, password source, OBS loading requirement, snapshot schedule, retention, enterprise project, tags, estimated budget, maintenance window, approval owner.

Do NOT accept password in plain text.

## STEP 2 — VERIFY AUTHENTICATION AND SERVICE

- **Objective**: Confirm hcloud CLI, authentication, region, project, and DWS service availability
- **Classification**: ASSISTED
- **Inputs**: Region from intent
- **Preconditions**: hcloud CLI installed
- **Command**: `hcloud DWS ListClusters --cli-region=<REGION>` (read-only)
- **Approval**: None
- **Verification**: Command succeeds without auth error
- **Expected result**: Authenticated context with DWS service available
- **Stop condition**: Auth failure or DWS unavailable
- **Failure action**: STOP, report auth or service issue
- **Evidence artifact**: `artifacts/dws-auth-context.md`

Do NOT display secrets.

## STEP 3 — DISCOVER EXISTING CLUSTERS

- **Objective**: Find existing DWS clusters to detect conflicts or reuse candidates
- **Classification**: ASSISTED
- **Inputs**: Region, cluster name
- **Preconditions**: Step 2 completed
- **Command**: `hcloud DWS ListClusters --cli-region=<REGION>`
- **Approval**: None
- **Verification**: Response received
- **Expected result**: List of existing clusters
- **Stop condition**: Multiple name matches
- **Failure action**: STOP on ambiguous match
- **Evidence artifact**: `artifacts/dws-existing-clusters.json`

Results: 0 matches = proceed to planning; 1 exact match = evaluate reuse or conflict; multiple matches = STOP.

## STEP 4 — DISCOVER VERSIONS, NODE TYPES AND CAPABILITIES

- **Objective**: Discover available versions, node types, storage types, and constraints
- **Classification**: ASSISTED
- **Inputs**: Region
- **Preconditions**: Step 2 completed
- **Commands**:
  - `hcloud DWS ListNodeTypes --cli-region=<REGION>`
  - `hcloud DWS ListUpdatableVersion --cli-region=<REGION> --cluster_id=<ID>` (if existing cluster)
- **Approval**: None
- **Verification**: Non-empty response
- **Expected result**: Capability matrix with versions, node types, CPU, memory, storage
- **Stop condition**: No node types available in region
- **Failure action**: STOP, report region limitation
- **Evidence artifact**: `artifacts/dws-capability-matrix.md`

Do NOT hardcode flavors.

## STEP 5 — DISCOVER NETWORK

- **Objective**: Discover VPC, subnet, security group, IP capacity, and EIP availability
- **Classification**: ASSISTED
- **Inputs**: Region, VPC name, subnet name, security group name
- **Preconditions**: Step 2 completed
- **Commands**:
  - `hcloud VPC ListVpcs --cli-region=<REGION>`
  - `hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>`
  - `hcloud VPC ListSecurityGroups --cli-region=<REGION>`
  - `hcloud VPC ListPublicIps --cli-region=<REGION>` (if public access required)
- **Approval**: None
- **Verification**: All required network resources found
- **Expected result**: Network resource IDs resolved from names
- **Stop condition**: No matches, multiple matches, region mismatch, insufficient IP, overly permissive SG
- **Failure action**: STOP, report network issue
- **Evidence artifact**: `artifacts/dws-network-discovery.json`

Resolve names to IDs. Reject ambiguous matches. Reject 0.0.0.0/0 in security groups.

## STEP 6 — CAPACITY AND COST PLAN

- **Objective**: Build capacity plan with resource sizing and optional cost estimation
- **Classification**: AUTOMATED
- **Inputs**: Node type, node count, storage, workload parameters
- **Preconditions**: Steps 4 and 5 completed
- **Command**: Logic + optional huaweicloud-pricing MCP
- **Approval**: None
- **Verification**: Plan is internally consistent
- **Expected result**: Capacity and cost plan
- **Stop condition**: Insufficient capacity for requirements
- **Failure action**: Adjust parameters and re-plan
- **Evidence artifact**: `artifacts/dws-capacity-cost-plan.md`

Include: node type, node count, CPU total, memory total, storage type, storage total, expected usable capacity, data growth, concurrency, HA, expansion assumptions, snapshot capacity, estimated monthly cost (when pricing available), cost estimation limitation (when pricing unavailable).

Do NOT assert estimates without source.

## STEP 7 — ARCHITECTURE PLAN

- **Objective**: Design the complete DWS deployment architecture
- **Classification**: AUTOMATED
- **Inputs**: All discovery results
- **Preconditions**: Steps 3-6 completed
- **Command**: Logic
- **Approval**: None
- **Verification**: Plan covers all components
- **Expected result**: Architecture plan with component classification
- **Stop condition**: Unresolvable dependency
- **Failure action**: STOP, report blocker
- **Evidence artifact**: `artifacts/dws-architecture-plan.md`

Classify components: EXISTING, REUSE, CREATE_WITH_DEPLOY_MCP, CREATE_WITH_HCLOUD, MANUAL, NOT_REQUIRED, BLOCKED.

## STEP 8 — READINESS AND QUOTA CHECK

- **Objective**: Validate all prerequisites and quotas before deployment
- **Classification**: ASSISTED
- **Inputs**: Architecture plan, discovery results
- **Preconditions**: Step 7 completed
- **Commands**: Quota queries, validation checks
- **Approval**: None
- **Verification**: All checks pass or have acceptable warnings
- **Expected result**: READY, READY_WITH_WARNINGS, NOT_READY, or BLOCKED
- **Stop condition**: NOT_READY or BLOCKED
- **Failure action**: STOP, report failing checks
- **Evidence artifact**: `artifacts/dws-readiness-report.md`

Do NOT continue if not READY or READY_WITH_WARNINGS.

## STEP 9 — PREPARE NETWORK PREREQUISITES

- **Objective**: Validate or plan VPC, subnet, and security group
- **Classification**: ASSISTED
- **Inputs**: Network discovery results
- **Preconditions**: Step 8 completed
- **Commands**: VPC/subnet/SG validation or creation via huaweicloud-deploy MCP
- **Approval**: Required for any creation
- **Verification**: Network resources exist and are valid
- **Expected result**: Valid VPC, subnet, security group with IDs
- **Stop condition**: Creation failure
- **Failure action**: STOP, report network creation failure
- **Evidence artifact**: Network resource IDs

Security group: allow DWS port only from authorized CIDR, never 0.0.0.0/0.

## STEP 10 — PREPARE SECURE DATABASE CREDENTIAL INPUT

- **Objective**: Establish secure mechanism for database administrator password
- **Classification**: MANUAL
- **Inputs**: Password source from intent
- **Preconditions**: Step 9 completed
- **Commands**: None (credential handling)
- **Approval**: Required
- **Verification**: Password not in shell history, logs, or versioned files
- **Expected result**: Secure credential input mechanism
- **Stop condition**: No secure mechanism available
- **Failure action**: STOP, request secure input method
- **Evidence artifact**: `artifacts/dws-credential-handling-plan.md`

Supported mechanisms (hcloud 6.2.9): `--cli-jsonInput` (file-based input), protected environment variable. If using temporary file: permissions 0600, outside repository, secure deletion after use, never include in artifacts.

## STEP 11 — CREATE CLUSTER

- **Objective**: Create the DWS cluster with approved configuration
- **Classification**: ASSISTED
- **Inputs**: Architecture plan, network IDs, secure credentials
- **Preconditions**: Steps 8-10 completed, explicit approval received
- **Command**: `hcloud DWS CreateCluster --cli-region=<REGION> --cluster.name=<NAME> --cluster.node_type=<TYPE> --cluster.number_of_node=<COUNT> --cluster.security_group_id=<SG_ID> --cluster.subnet_id=<SUBNET_ID> --cluster.user_name=<USERNAME> --cluster.user_pwd=<SECURE_INPUT> --cluster.vpc_id=<VPC_ID> [optional parameters]`
- **Approval**: EXPLICIT APPROVAL REQUIRED
- **Verification**: `hcloud DWS ListClusters --cli-region=<REGION>` shows new cluster
- **Expected result**: Cluster creation initiated, cluster ID returned
- **Stop condition**: Creation request rejected
- **Failure action**: STOP, report creation failure
- **Evidence artifact**: `artifacts/dws-cluster-creation-request.json`

Do NOT execute during skill generation. Do NOT print password. Capture: request ID, cluster ID, start time, selected configuration.

## STEP 12 — POLL CLUSTER CREATION

- **Objective**: Monitor cluster creation until operational
- **Classification**: AUTOMATED
- **Inputs**: Cluster ID, region
- **Preconditions**: Step 11 completed
- **Commands**:
  - `hcloud DWS ShowClusters --cli-region=<REGION>`
  - `hcloud DWS ListClusters --cli-region=<REGION>`
- **Approval**: None
- **Verification**: Cluster status reaches operational state
- **Expected result**: Cluster in AVAILABLE/operational state
- **Stop condition**: Cluster enters FAILED state or polling timeout
- **Failure action**: Report failure, do NOT auto-delete
- **Evidence artifact**: `artifacts/dws-cluster-creation-status.md`

Polling must include: interval, timeout, success status, failure statuses, degraded states, request correlation. Do NOT hardcode 15-30 minutes as fixed timeout.

## STEP 13 — VERIFY CLUSTER

- **Objective**: Validate cluster matches expected configuration
- **Classification**: ASSISTED
- **Inputs**: Cluster ID, expected configuration
- **Preconditions**: Step 12 completed
- **Commands**:
  - `hcloud DWS ShowClusters --cli-region=<REGION>`
  - `hcloud DWS ListClusterDetails --cli-region=<REGION>`
  - `hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<ID>`
- **Approval**: None
- **Verification**: All configuration parameters match
- **Expected result**: Validated cluster
- **Stop condition**: Configuration mismatch
- **Failure action**: Report mismatch, recommend corrective action
- **Evidence artifact**: `artifacts/dws-cluster-validation-report.md`

Verify: exact cluster, status, region, AZ, version, node type, node count, storage, VPC, subnet, security group, endpoint, port, public access state, HA state, creation timestamp.

## STEP 14 — CONFIGURE OPTIONAL PUBLIC ACCESS

- **Objective**: Bind EIP and configure security group for public access (if requested)
- **Classification**: ASSISTED
- **Inputs**: EIP requirement, authorized CIDR
- **Preconditions**: Step 13 completed, user requested public access
- **Commands**: EIP binding via hcloud or console
- **Approval**: EXPLICIT REQUIRED
- **Verification**: EIP bound, security group rule valid, connectivity from authorized source
- **Expected result**: Public access configured with restricted CIDR
- **Stop condition**: EIP quota exceeded or security policy violation
- **Failure action**: Report failure, do NOT open global access
- **Evidence artifact**: EIP binding result

Do NOT open access globally. Validate: EIP support, EIP availability, authorized CIDR, security group rule, organizational policy, security approval.

## STEP 15 — VERIFY DATABASE CONNECTIVITY

- **Objective**: Verify PostgreSQL-compatible connectivity to the cluster
- **Classification**: MANUAL
- **Inputs**: Cluster endpoint, port, database name, username
- **Preconditions**: Step 13 completed (or Step 14 if public access)
- **Commands**: `psql -h <ENDPOINT> -p <PORT> -U <USERNAME> -d <DATABASE> -c "SELECT version();"` (example, not executed during generation)
- **Approval**: Required
- **Verification**: Connection succeeds, version query returns
- **Expected result**: Validated connectivity
- **Stop condition**: Connection refused or TLS error
- **Failure action**: Report connectivity issue
- **Evidence artifact**: Connectivity validation result

Sanitized examples for: psql, JDBC, ODBC (when applicable). Do NOT include passwords. Verify: DNS or host, port, TLS requirements, database, username, authentication.

## STEP 16 — CREATE DATABASE AND SCHEMAS

- **Objective**: Prepare database and schemas within the cluster
- **Classification**: MANUAL
- **Inputs**: Database name, schema definitions, ownership plan
- **Preconditions**: Step 15 completed
- **Commands**: SQL DDL via psql or JDBC
- **Approval**: Required
- **Verification**: Database and schemas exist
- **Expected result**: Database and schemas created
- **Stop condition**: SQL error
- **Failure action**: Report error, do NOT auto-retry
- **Evidence artifact**: `artifacts/dws-database-schema-plan.sql`

Do NOT assume special syntax if PostgreSQL-compatible does not imply total compatibility. File must contain placeholders and security comments.

## STEP 17 — OPTIONAL OBS DATA LOAD

- **Objective**: Plan data loading from OBS (if requested)
- **Classification**: MANUAL
- **Inputs**: OBS bucket, object path, data format, target table
- **Preconditions**: Step 16 completed
- **Commands**: External table creation and INSERT SELECT
- **Approval**: Required
- **Verification**: Data loaded successfully
- **Expected result**: Data available in target table
- **Stop condition**: OBS access denied or format error
- **Failure action**: Report error
- **Evidence artifact**: `artifacts/dws-obs-load-plan.md`

Validate: OBS bucket region, object path, IAM, data format, delimiter, compression, encoding, schema, target table, DWS version, supported external table syntax, encryption, error handling. Do NOT include unverified syntax as fact.

## STEP 18 — CONFIGURE SNAPSHOT POLICY

- **Objective**: Configure snapshot schedule and retention
- **Classification**: ASSISTED
- **Inputs**: Snapshot schedule, retention, cluster ID
- **Preconditions**: Step 13 completed
- **Commands**:
  - `hcloud DWS ListSnapshots --cli-region=<REGION>`
  - `hcloud DWS CreateSnapshot --cli-region=<REGION> --snapshot.cluster_id=<ID> --snapshot.name=<NAME>` (for manual snapshot)
- **Approval**: Required for write operations
- **Verification**: Snapshot or policy created and listed
- **Expected result**: Snapshot policy configured
- **Stop condition**: Snapshot creation failure
- **Failure action**: Report failure
- **Evidence artifact**: `artifacts/dws-snapshot-policy-report.md`

Plan: schedule, retention, naming, storage impact, restore test cadence, compliance requirements.

## STEP 19 — OPERATIONAL VALIDATION

- **Objective**: Validate cluster health, connectivity, and operational readiness
- **Classification**: ASSISTED
- **Inputs**: Cluster ID, endpoint
- **Preconditions**: Step 13 completed
- **Commands**:
  - `hcloud DWS ShowClusters --cli-region=<REGION>`
  - `hcloud DWS ListClusterNodes --cli-region=<REGION> --cluster_id=<ID>`
  - `hcloud DWS ShowResourceStatistics --cli-region=<REGION>`
- **Approval**: None
- **Verification**: All health checks pass
- **Expected result**: Operational validation report
- **Stop condition**: Health check failure
- **Failure action**: Report issue, recommend support
- **Evidence artifact**: `artifacts/dws-operational-validation-report.md`

Validate: cluster health, node health, endpoint, connectivity, simple query, storage usage, snapshot readiness, monitoring, security group, EIP (when applicable), logs and alerts, ownership, support path. Do NOT execute unauthorized load tests.

## STEP 20 — CLOSURE

- **Objective**: Generate final summary and handoff
- **Classification**: AUTOMATED
- **Inputs**: All artifacts
- **Preconditions**: Step 19 completed
- **Command**: Logic
- **Approval**: None
- **Verification**: Summary complete
- **Expected result**: Final deployment report
- **Stop condition**: None
- **Failure action**: None
- **Evidence artifact**: `artifacts/dws-final-report.md`

Generate: final summary, selected architecture, cluster status, connectivity result, capacity assumptions, cost estimate, snapshot configuration, warnings, unresolved gaps, support recommendations, recovery recommendations, follow-up actions. Do NOT delete resources automatically.

# Capability gap handling

| Gap ID | Description | Decision |
|---|---|---|
| GAP-DWS-001 | No dedicated DWS MCP; all DWS operations via hcloud CLI | USE_HCLOUD_CLI |
| GAP-DWS-002 | DWS not in huaweicloud-deploy supported services | EXTEND_EXISTING_MCP |
| GAP-DWS-003 | hcloud CLI operations lack structured error handling and retry logic | USE_HCLOUD_CLI |
| GAP-DWS-004 | Node type availability varies by region | REGION_DEPENDENT |
| GAP-DWS-005 | Storage type availability varies by region | REGION_DEPENDENT |
| GAP-DWS-006 | Password handling in CLI is a security concern | SECURE_INPUT_REQUIRED |
| GAP-DWS-007 | Cluster creation time is variable and not SLA-guaranteed | POLLING_REQUIRED |

# Output artifacts

- artifacts/dws-intent.json
- artifacts/dws-auth-context.md
- artifacts/dws-existing-clusters.json
- artifacts/dws-capability-matrix.md
- artifacts/dws-network-discovery.json
- artifacts/dws-capacity-cost-plan.md
- artifacts/dws-architecture-plan.md
- artifacts/dws-readiness-report.md
- artifacts/dws-credential-handling-plan.md
- artifacts/dws-cluster-creation-request.json
- artifacts/dws-cluster-creation-status.md
- artifacts/dws-cluster-validation-report.md
- artifacts/dws-database-schema-plan.sql
- artifacts/dws-obs-load-plan.md
- artifacts/dws-snapshot-policy-report.md
- artifacts/dws-operational-validation-report.md
- artifacts/dws-final-report.md

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| DWS service unavailable in region | Service not enabled or region unsupported | `hcloud DWS ListClusters` error | Suggest alternative region or contact support |
| Cluster name already exists | Name conflict | `hcloud DWS ListClusters` | Evaluate reuse or rename |
| Node type unavailable | Region-specific availability | `hcloud DWS ListNodeTypes` | Select available node type for region |
| VPC/subnet not found | Network not created or wrong region | `hcloud VPC ListVpcs` | Create or select existing VPC/subnet |
| Security group too permissive | 0.0.0.0/0 rule detected | SG rule inspection | Reject, require authorized CIDR |
| CreateCluster rejected | Quota, parameter, or network error | API error response | Review error, check quota, validate parameters |
| Cluster enters FAILED state | Configuration or resource issue | `hcloud DWS ShowClusters` | Inspect error, do NOT auto-delete |
| Polling timeout | Cluster creation slower than expected | `hcloud DWS ShowClusters` status | Continue polling or investigate manually |
| EIP quota exceeded | EIP limit reached | EIP creation error | Request quota increase |
| Password policy violation | Password does not meet requirements | CreateCluster error | Provide compliant password via secure mechanism |
| Connection refused | SG or endpoint misconfiguration | psql/JDBC connection test | Check SG rules, endpoint, TLS configuration |
| OBS load fails | Permissions or format mismatch | DWS error log | Verify OBS IAM, format, delimiter, encoding |

See also: `references/known-issues.md`

# Failure handling

| Failure mode | Detection | Response |
|---|---|---|
| DWS service unavailable in region | ListClusters returns service error | STOP, suggest alternative region |
| Cluster name already exists | ListClusters shows matching name | STOP, evaluate reuse or rename |
| Node type unavailable | ListNodeTypes does not include requested type | STOP, suggest available types |
| VPC/subnet not found | ListVpcs/ListSubnets returns no match | STOP, suggest creation or alternative |
| Security group too permissive | SG rule allows 0.0.0.0/0 | REJECT, require authorized CIDR |
| Insufficient subnet IP capacity | Available IPs < required nodes + buffer | STOP, suggest larger subnet |
| CreateCluster rejected | API returns error | STOP, report error details |
| Cluster enters FAILED state | ShowClusters shows FAILED | STOP, report failure, do NOT auto-delete |
| Polling timeout | Cluster not operational within timeout | Report, allow manual investigation |
| EIP quota exceeded | EIP creation fails | STOP, request quota increase |
| DWS quota exceeded | CreateCluster returns quota error | STOP, request quota increase |
| Password policy violation | CreateCluster rejects password | Request compliant password |
| Connection refused | psql/JDBC connection fails | Report, check SG and endpoint |
| TLS certificate error | Connection fails with TLS error | Report, check certificate configuration |

# Recovery procedure

1. Do NOT automatically delete a failed cluster.
2. Do NOT automatically re-execute CreateCluster.
3. If cluster is in CREATING state after timeout, continue polling or investigate manually.
4. If cluster is in FAILED state, inspect error details via ShowClusters.
5. If network prerequisites were created, they may need manual cleanup.
6. EIP rollback is independent of cluster rollback.
7. Security group rollback is independent of cluster rollback.
8. Snapshots are not deleted automatically.
9. Restore operations are never executed automatically.
10. Database changes require a separate plan.
11. Original resources must be preserved.
12. Contact support via huaweicloud-ticket MCP if needed.

# Evidence and traceability

- All CLI commands are logged with timestamps (secrets redacted).
- All approval decisions are recorded.
- All verification results are preserved in artifacts.
- All IDs are sanitized in reports (placeholders in examples).
- No secrets appear in any artifact or log.

# Known limitations

1. No dedicated DWS MCP exists; all operations via hcloud CLI.
2. DWS is not in huaweicloud-deploy supported services; Terraform generation for DWS is not available.
3. Node type availability varies by region and must be discovered.
4. Storage type availability varies by region and version.
5. Cluster creation time is variable (10-15 min reference, not SLA).
6. Password must be passed to CreateCluster; secure handling is critical.
7. PostgreSQL compatibility is partial; not all PostgreSQL features are supported.
8. External table syntax for OBS loading is version-dependent.
9. hcloud CLI 7.2.12 compatibility is not validated.
10. No cloud-side tests were executed during skill generation.
11. HA topology options are region-dependent and not fully documented.
12. Resize and shrink capabilities are version-dependent.

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- DWS service available in hcloud CLI v6.2.9 with 70+ operations [VERIFIED_FROM_LOCAL_HELP]
- 28 key operations verified from local help [VERIFIED_FROM_LOCAL_HELP]
- CreateCluster parameters verified from local help [VERIFIED_FROM_LOCAL_HELP]
- Cluster name constraints verified (4-64 chars, letter start) [VERIFIED_FROM_LOCAL_HELP]
- Node count constraints verified (3-256 for cluster, 1 for standalone) [VERIFIED_FROM_LOCAL_HELP]
- Port range verified (8000-30000, default 8000) [VERIFIED_FROM_LOCAL_HELP]
- Username constraints verified [VERIFIED_FROM_LOCAL_HELP]
- No dedicated DWS MCP exists [VERIFIED_FROM_LOCAL_HELP]
- No cloud-side tests executed [NOT_VERIFIED]
- Compatibility verified only with hcloud 6.2.9 [VERIFIED_FROM_LOCAL_HELP]
- hcloud 7.2.12 validation pending [NOT_VERIFIED]
- Node type and storage availability are region-dependent [REGION_DEPENDENT]
- Password handling requires secure input mechanism [INFERRED]
