# DWS Cluster Deployment

## Purpose

Deploy, validate, and configure a Huawei Cloud DWS (GaussDB(DWS)) data warehouse cluster using hcloud CLI as the primary mechanism. DWS is PostgreSQL-compatible but must NOT be presented as standard PostgreSQL. No dedicated DWS MCP exists.

## Scenario at a Glance

| Attribute | Value |
|---|---|
| Domain | Big-Data / Data-Warehouse-Deployment |
| Source | User requirements for new DWS cluster |
| Target | Operational DWS cluster with validated connectivity |
| Primary service | DWS (GaussDB(DWS)) |
| Primary mechanism | hcloud DWS CLI |
| Scenario maturity | READY_WITH_WARNINGS |
| Highest risk | HIGH |
| Skills | 1 |

## Architecture

```
Client / Application
        │
        │ Private connectivity
        │ (or optional controlled EIP)
        ▼
     DWS Cluster
   ┌────┼────┐
 Node  Node  Node
        │
        ├── OBS optional load
        └── Snapshots
```

DWS uses PostgreSQL-compatible protocol (port 8000 default, range 8000-30000). Compatibility is partial — do not assume total PostgreSQL equivalence.

## When to Use This Scenario

- Deploying a new DWS cluster for data warehousing workloads
- Discovering available DWS node types, versions, and capabilities in a region
- Planning DWS cluster capacity and cost before deployment
- Validating DWS cluster prerequisites (VPC, subnet, security group)
- Configuring snapshot policies for an existing DWS cluster

## When NOT to Use This Scenario

- Migrating data between DWS clusters (use DWS snapshot/restore or data migration tools)
- Managing DRS replication tasks (use PostgreSQL ECS to RDS DRS scenario)
- Deploying DataArts Studio pipelines (use Snowflake to DataArts scenario)
- When no hcloud CLI is available and cannot be installed
- When automated cluster deletion is required (never automated in this skill)

## Skills Included

| Order | Skill | Required | Purpose | Mechanism | Status | Risk |
|---:|---|---|---|---|---|---|
| 1 | [huawei-dws-cluster-deployment](./huawei-dws-cluster-deployment/SKILL.md) | Yes | Full deployment orchestration | hcloud DWS CLI | READY_WITH_WARNINGS | HIGH |

## Shared Capabilities

| Component | Type | Required / Optional | Purpose |
|---|---|---|---|
| [huaweicloud-pricing](../shared/mcps/huaweicloud-pricing/) | MCP | Optional | Cost estimation (read-only, non-blocking) |
| [huaweicloud-ticket](../shared/mcps/huaweicloud-ticket/) | MCP | Optional | Support ticket creation |
| [huaweicloud-deploy](../shared/mcps/huaweicloud-deploy/) | MCP | Optional | VPC/subnet/SG prerequisites only (NOT for DWS) |
| [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md) | Shared Skill | Required | Future DWS MCP extension design |

## Prerequisites

- hcloud CLI 6.2.9+ installed and authenticated
- DWS service available in target region
- VPC, subnet, and security group pre-existing or creatable
- Sufficient subnet IP capacity for cluster nodes
- DWS quota sufficient for cluster creation
- Database administrator password source established (never plain text)
- IAM permissions for DWS create/manage
- Approval owner designated for write operations

See [huawei-dws-cluster-deployment prerequisites](./huawei-dws-cluster-deployment/SKILL.md) for the complete list.

## Execution Sequence

### Phase 1 — Parse Intent

- **Skill**: huawei-dws-cluster-deployment
- **Input**: Region, cluster name, environment, workload parameters, approval owner
- **Output**: Complete intent object (`artifacts/dws-intent.json`)
- **Approval**: None
- **Verification**: All required fields present, password not plain text
- **Next**: Phase 2

### Phase 2 — Discovery

- **Skill**: huawei-dws-cluster-deployment
- **Input**: Intent object
- **Output**: Auth context, existing clusters, capability matrix (versions, node types, storage), network discovery
- **Approval**: None (read-only)
- **Verification**: DWS available, node types exist, network resources found
- **Next**: Phase 3

### Phase 3 — Readiness

- **Skill**: huawei-dws-cluster-deployment
- **Input**: Discovery results
- **Output**: Capacity/cost plan, architecture plan, readiness report, credential handling plan
- **Approval**: None (plan only)
- **Verification**: READY or READY_WITH_WARNINGS, no 0.0.0.0/0 in security groups
- **Next**: Phase 4

### Phase 4 — Execution

- **Skill**: huawei-dws-cluster-deployment
- **Input**: Approved architecture plan, network IDs, secure credentials
- **Output**: DWS cluster created, polling until operational
- **Approval**: EXPLICIT — CreateCluster, network writes, EIP (if public)
- **Verification**: Cluster status operational, configuration matches plan
- **Next**: Phase 5

### Phase 5 — Validation

- **Skill**: huawei-dws-cluster-deployment
- **Input**: Cluster ID
- **Output**: Cluster validation, connectivity validation, operational validation
- **Approval**: Required for connectivity test and database/schema creation
- **Verification**: Cluster healthy, connectivity works, security verified
- **Next**: Phase 6

### Phase 6 — Closure

- **Skill**: huawei-dws-cluster-deployment
- **Input**: All artifacts
- **Output**: Snapshot policy configured, final deployment report
- **Approval**: EXPLICIT for snapshot creation
- **Verification**: Snapshot policy active, report complete
- **Next**: Completion

## AI Execution Instructions

1. Read this README first.
2. Do not load every skill unnecessarily.
3. Resolve the current phase.
4. Load only the required [SKILL.md](./huawei-dws-cluster-deployment/SKILL.md).
5. Follow PARSE INTENT.
6. Run discovery before any write.
7. Verify CLI availability (hcloud DWS required).
8. Obtain explicit approval for CreateCluster, EIP, and snapshot operations.
9. Execute one controlled phase.
10. Verify.
11. Return to scenario README.
12. Determine next phase.
13. Stop on ambiguity.
14. Use capability builder only for a real gap.

## Human Execution Instructions

1. Read this scenario README
2. Review architecture diagram
3. Read [SKILL.md](./huawei-dws-cluster-deployment/SKILL.md)
4. Review [prerequisites](./huawei-dws-cluster-deployment/references/prerequisites.md)
5. Review [architecture](./huawei-dws-cluster-deployment/references/architecture.md)
6. Execute discovery (hcloud CLI)
7. Review and approve deployment plan
8. Prepare secure password input mechanism
9. Approve and execute CreateCluster
10. Monitor cluster creation (polling)
11. Validate cluster configuration
12. Verify database connectivity
13. Configure snapshot policy
14. Review [rollback procedure](./huawei-dws-cluster-deployment/references/rollback.md)

## Approval Gates

| Gate | Operation | Risk | Approval required | Skill |
|---|---|---|---|---|
| G1 | Network prerequisites (VPC/SG) | Medium | EXPLICIT for creation | huawei-dws-cluster-deployment |
| G2 | CreateCluster | High | EXPLICIT | huawei-dws-cluster-deployment |
| G3 | BindEIP (public access) | Medium | EXPLICIT + SG validation | huawei-dws-cluster-deployment |
| G4 | CreateSnapshot | Low | EXPLICIT | huawei-dws-cluster-deployment |
| G5 | ResetPassword | Medium | EXPLICIT | huawei-dws-cluster-deployment |
| G6 | DeleteCluster | High | EXPLICIT + pre-deletion snapshot | huawei-dws-cluster-deployment |

## Validation Criteria

- Cluster status: AVAILABLE/operational
- Configuration matches plan (node type, count, storage, version, network)
- Connectivity validated (psql/JDBC connection succeeds)
- Security group: no 0.0.0.0/0, authorized CIDR only
- Snapshot policy configured (if requested)
- EIP bound and restricted (if public access)

## Completion Criteria

- Cluster created and status operational
- Configuration verified against plan
- Database connectivity validated
- Security verified (no 0.0.0.0/0, authorized CIDR)
- Snapshot/recovery plan recorded
- Operational validation report generated

## Rollback / Recovery

1. Do NOT automatically delete a failed cluster.
2. Do NOT automatically re-execute CreateCluster.
3. If cluster in CREATING state after timeout: continue polling or investigate manually.
4. If cluster in FAILED state: inspect error via ShowClusters. Do NOT auto-delete.
5. Network prerequisites may need manual cleanup.
6. EIP rollback is independent of cluster rollback.
7. Security group rollback is independent of cluster rollback.
8. Snapshots are never deleted automatically.
9. Restore operations are never executed automatically.

See [rollback procedure](./huawei-dws-cluster-deployment/references/rollback.md) for details.

## Capability Gaps

| Gap | Impact | Core blocker | Current treatment | Future option |
|---|---|---|---|---|
| GAP-DWS-001: No dedicated DWS MCP | All operations via hcloud CLI | No | hcloud CLI | DWS MCP |
| GAP-DWS-002: DWS not in deploy MCP | Cannot generate DWS Terraform | No | hcloud CLI | Extend deploy MCP |
| GAP-DWS-003: No structured error handling | CLI errors are unstructured | No | Manual error parsing | DWS MCP |
| GAP-DWS-004: Node type varies by region | Must discover per region | No | Per-region discovery | Region capability map |
| GAP-DWS-005: Storage type varies by region | Must discover per region | No | Per-region discovery | Region capability map |
| GAP-DWS-006: Password in CLI is security concern | Secure input required | No | Secure input mechanism | DWS MCP |
| GAP-DWS-007: Creation time variable | Not SLA-guaranteed | No | Polling with timeout | DWS MCP |

For gap resolution, see [mcp-capability-builder](../shared/skills/mcp-capability-builder/SKILL.md).

## Known Limitations

- No dedicated DWS MCP exists; all operations via hcloud CLI
- DWS is not in huaweicloud-deploy supported services
- DWS is PostgreSQL-compatible, NOT standard PostgreSQL
- Node type and storage availability vary by region
- Cluster creation time is variable (10-15 min reference, not SLA)
- Password must be passed to CreateCluster; secure handling is critical
- External table syntax for OBS loading is version-dependent
- hcloud CLI 7.2.12 compatibility not validated
- No cloud-side tests were executed

## Maturity

READY_WITH_WARNINGS. DWS service available in hcloud CLI v6.2.9 with 70+ operations. 28 key operations verified. CreateCluster parameters verified. Cluster name, node count, port range, and username constraints verified. No dedicated DWS MCP. No cloud-side tests executed. Compatibility verified only with hcloud 6.2.9.

## Evidence and Traceability

- All CLI commands logged with timestamps (secrets redacted)
- All approval decisions recorded
- All verification results preserved in artifacts
- All IDs sanitized in reports
- No secrets in any artifact or log

## AI Reading Order

1. `README.md` (this file)
2. [huawei-dws-cluster-deployment/SKILL.md](./huawei-dws-cluster-deployment/SKILL.md)
3. [huawei-dws-cluster-deployment/references/prerequisites.md](./huawei-dws-cluster-deployment/references/prerequisites.md)
4. [huawei-dws-cluster-deployment/references/architecture.md](./huawei-dws-cluster-deployment/references/architecture.md)
5. [huawei-dws-cluster-deployment/references/workflows/discovery.md](./huawei-dws-cluster-deployment/references/workflows/discovery.md)
6. [huawei-dws-cluster-deployment/references/workflows/execution.md](./huawei-dws-cluster-deployment/references/workflows/execution.md)
7. [huawei-dws-cluster-deployment/references/validation.md](./huawei-dws-cluster-deployment/references/validation.md)
8. [huawei-dws-cluster-deployment/references/rollback.md](./huawei-dws-cluster-deployment/references/rollback.md)

## Human Reading Order

1. This scenario README
2. Architecture diagram above
3. Prerequisites section
4. [SKILL.md](./huawei-dws-cluster-deployment/SKILL.md)
5. [Execution runbook](./huawei-dws-cluster-deployment/references/execution-runbook.md)
6. [Validation](./huawei-dws-cluster-deployment/references/validation.md)
7. [Rollback](./huawei-dws-cluster-deployment/references/rollback.md)
8. [Known issues](./huawei-dws-cluster-deployment/references/known-issues.md)

## Related References

- [DWS MCP extension request](./huawei-dws-cluster-deployment/references/dws-mcp-extension-request.md)
- [Capability gap policy](./huawei-dws-cluster-deployment/references/capability-gap-policy.md)
- [Lessons learned](./huawei-dws-cluster-deployment/references/lessons-learned.md)
