---
name: huawei-mrs-deploy-operations
version: 1.0.0
description: Deploy and operate Huawei Cloud MapReduce Service (MRS) CUSTOM clusters via hcloud CLI (KooCLI), enabling any combination of MRS components (Hadoop, Spark, HBase, Hive, Kafka, Flink, ZooKeeper, ClickHouse, Ranger, and more) supported by the target cluster version. Uses only the current MRS API V2, since MRS's own documentation states MRS 3.x does not support the older V1.1 API — including the confirmed gap that V2 has no list/show/delete-cluster operation, documented explicitly rather than substituted with an unconfirmed V1.1 call.
category: database-operations
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Big-Data-Provisioning
  family: Cloud-Cluster-Deployment
  service: MRS
  risk_level: high
  status: READY_WITH_WARNINGS
  create_operation_verification: FULL_PARAMETER_TABLE_VERIFIED_NOT_LIVE_TESTED
---

# Purpose

Deploy and operate Huawei Cloud MapReduce Service (MRS) CUSTOM clusters using hcloud CLI (KooCLI) as the only mechanism. A CUSTOM cluster is the only MRS cluster type that lets the caller enable any combination of MRS components (Hadoop, Spark, HBase, Hive, Kafka, Flume, Flink, ZooKeeper, HetuEngine, Ranger, Tez, ClickHouse, and more, depending on the target MRS version) in a single cluster, rather than the fixed component sets of the ANALYSIS, STREAMING, MIXED, or DORIS cluster types. This skill discovers network prerequisites and available versions/components, and — using CreateCluster, ListNodes, and AddComponent, each independently confirmed with a full request/response parameter table from MRS's own current (V2) API Reference — creates a custom cluster with the requested components, verifies it, and (optionally, post-creation) adds further components. MRS 3.x does not support the older V1.1 API namespace (per MRS's own documentation); this skill never falls back to it.

This skill is deployment-only. It does not submit or manage MRS jobs, does not manage data inside HDFS/Hive/HBase/etc., does not configure auto scaling policies, and does not create the VPC/subnet a cluster uses — it only consumes their already-existing IDs.

# Supported scenario

- Source: an operation intent naming the action (discover, create, add-component, or verify), region, and the desired MRS components
- Target: an MRS CUSTOM cluster, fully identified by its own `cluster_id` once created
- Mechanism: the MRS management-plane V2 REST API called through hcloud CLI, under the service name `MRS`; no dedicated MCP exists
- Storage: none beyond the artifacts this skill itself generates
- Topology: single-region, single-cluster operation per invocation

| Service | `hcloud` service name | API generation used |
|---|---|---|
| MapReduce Service | `MRS` | API V2 only — MRS's own documentation states MRS 3.x does not support API V1.1 |

# When to use this skill

- Creating an MRS CUSTOM cluster with any combination of components the target MRS version supports (for example Hadoop + Spark + HBase + Hive + Flink + ZooKeeper + Ranger + Tez, or any other subset/superset)
- Checking which MRS versions and node specifications are available before sizing a cluster
- Listing the nodes of a specific, already-known cluster and their component health, to verify a deployment
- Adding further components to an existing CUSTOM cluster (MRS 3.1.2 normal / 3.1.2-LTS.2 or later) after initial creation
- Auditing the node/component state of a specific MRS cluster whose `cluster_id` is already known

# When not to use this skill

- Creating, modifying, or deleting the VPC or subnet a cluster will use — resolve these read-only from the networking service/console; this skill only consumes their IDs
- Submitting, managing, or monitoring MRS jobs (MapReduce, Spark, Hive SQL, etc.) — these are MRS Job Management APIs, out of this skill's scope
- Managing data inside HDFS, Hive, HBase, or any other component once the cluster is running — use the component's own client/console, not hcloud
- Scaling (ExpandCluster/ShrinkCluster), auto-scaling policy configuration, cluster renaming, or upgrading an existing cluster — these are confirmed to exist in the MRS V2 API catalogue by name (see `# Per-service operations` → MRS → Out of scope) but were not independently parameter-verified during authoring
- Listing all clusters in a project, showing full cluster details by name, or deleting a cluster, for an MRS 3.x cluster — no confirmed V2 operation exists for these (`GAP-MRS-OPS-101`); use the MRS console instead, and do not substitute the deprecated V1.1 `ListClusters`/`ShowClusterDetails`/`DeleteCluster` operations without a fresh live check
- When hcloud CLI is not available and cannot be installed

# Required inputs

- action (discover, create, add-component, or verify)
- source_region
- vpc_name, subnet_id, subnet_name (resolved read-only; this skill does not create them)
- cluster_name
- cluster_version (for example "MRS 3.3.0-LTS")
- components (comma-separated list; any combination the target cluster_version's CUSTOM cluster type supports)
- node_groups (at minimum a master_node_default_group; additional groups as needed, each with node_num, node_size, and disk configuration)
- manager_admin_password, login_mode (PASSWORD or KEYPAIR) and node_root_password or node_keypair_name
- approval_owner (required whenever action is create or add-component)

# Optional inputs

- availability_zone (single-AZ only; MRS does not support multi-AZ clusters)
- safe_mode (SIMPLE or KERBEROS)
- charge_info (defaults to pay-per-use / postPaid unless yearly/monthly is explicitly requested)
- security_groups_id, auto_create_default_security_group
- enterprise_project_id, tags
- eip_address / eip_id (to bind an EIP for MRS Manager access)
- template_id (management/control node deployment topology for CUSTOM clusters)
- component_configs (custom component configuration overrides)
- cluster_id (required for add-component and verify actions on an existing cluster)

# Required MCPs

None. All operations are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-ticket (only to open a support ticket if a capability-gap probe fails for a critical-path operation and manual escalation is desired)

# Tool selection policy

- Use hcloud CLI for ALL MRS operations: discovery, creation, component addition, and verification
- Always use the service name `MRS` and only its V2 operations (CreateCluster, AddComponent, ListNodes, ExpandCluster, ShrinkCluster, ShowMrsVersionList, ShowMrsFlavors, and — only after a live probe — any further one); never call a `/v1.1/...`-style operation for an MRS 3.x cluster, since MRS's own documentation states that generation is unsupported for 3.x
- Because CreateCluster's request body is a large nested JSON object (node_groups array, charge_info, and more), always pass it through KooCLI's `--cli-jsonInput=<file>` option, never as flattened `--param` flags; the same applies to AddComponent's `components_install_mode` array
- Never assume an operation beyond CreateCluster/AddComponent/ListNodes is available without probing it live first (`hcloud MRS <OPERATION> --help`) and cross-checking its own API Explorer CLI Examples tab
- Never use huaweicloud-ticket to substitute a missing capability with an invented command; it is for support escalation only
- Never use this skill to create, modify, or delete a VPC or subnet; resolve their IDs read-only from the networking service/console
- Never substitute the V1.1 `ListClusters`/`ShowClusterDetails`/`DeleteCluster` operations for a missing V2 equivalent on an MRS 3.x cluster (`GAP-MRS-OPS-101`); route to the console instead

# Safety and approval gates

1. Any create or add-component action requires explicit approval before execution — an MRS cluster is a billable, multi-node cloud resource, and Kerberos/security-mode choices affect who can use the cluster afterward
2. Reusing an existing cluster instead of creating a new one requires explicit confirmation from the approval owner
3. Passwords (manager_admin_password, node_root_password, component_user_password, component_default_password) are never generated, guessed, or printed by this skill; they must be supplied by the approval owner out of band
4. Enabling Kerberos (`safe_mode: KERBEROS`) versus SIMPLE mode is treated as a security-relevant configuration choice and should be called out explicitly to the approval owner before the create step
5. Component and node-group choices at creation, and any later AddComponent call, should be confirmed against the target `cluster_version`'s actual supported-component list (Step 3 in the per-service workflow) before requesting approval, since an unsupported component name will simply fail cluster creation or component addition

# Rules

1. MRS is exposed through hcloud CLI under the service name `MRS`. This is directly confirmed: the API Explorer "CLI Examples" link on the ListNodes operation's own page uses the URL parameter pattern `openapi/mrs/cli?version=v2&api=ListNodes`, confirming both the lowercase-normalized service segment (`mrs`, matching the `MRS` product abbreviation used throughout its own documentation) and the literal operation name `ListNodes`. [VERIFIED_FROM_PUBLIC_API_DOCS]

2. MRS publishes two API generations: a current 'API V2' (`/v2/{project_id}/clusters...`) and an older 'API V1.1' (`/v1.1/{project_id}/clusters...`). MRS's own "Before You Start" documentation states explicitly: "MRS 3.x does not support V1.1 APIs. You need to use V2 APIs." This skill uses ONLY the V2 namespace for cluster creation and post-creation operations on MRS 3.x clusters, and never calls a V1.1-style URI for a 3.x cluster. [VERIFIED_FROM_PUBLIC_API_DOCS]

3. `CreateCluster` (`POST /v2/{project_id}/clusters`) is confirmed with a full request/response parameter table from its own current API Reference page. Required fields include `cluster_version`, `cluster_name`, `cluster_type` (use `CUSTOM` to enable any component combination — CUSTOM is supported only by MRS 3.x), `region`, `vpc_name`, `subnet_name` (subnet_id and/or subnet_name required), `components` (a comma-separated string — this is the field that lets the caller enable any combination of the target version's supported components), `availability_zone`, `safe_mode`, `manager_admin_password`, `login_mode`, and `node_groups` (array, at minimum a `master_node_default_group`). The response returns `cluster_id`. [VERIFIED_FROM_PUBLIC_API_DOCS]

4. `AddComponent` (`POST /v2/{project_id}/clusters/{cluster_id}/components`) is confirmed with a full request/response parameter table from its own current API Reference page. It only applies to CUSTOM clusters on MRS 3.1.2 (normal) / 3.1.2-LTS.2 (LTS) or later. Its body is `components_install_mode`, an array of `{component, node_groups: [{name, assigned_roles}], component_user_password?, component_default_password?}` objects; `assigned_roles` values are role-name expressions specific to each component (documented in MRS's "Roles and components supported by MRS" reference). [VERIFIED_FROM_PUBLIC_API_DOCS]

5. `ListNodes` (`GET /v2/{project_id}/clusters/{cluster_id}/nodes`) is confirmed with a full query-parameter and response-schema table from its own current API Reference page, and is additionally confirmed by its own "CLI Examples" API Explorer link (`api=ListNodes`). Query parameters: `node_group`, `limit` (default 10), `offset` (default 1), `node_name`, `sort_key`, `sort_dir`, `query_node_detail` (set `true` to also return `component_infos` with each component's `running_status`), `query_ecs_detail`, `internal_ip`. This is this skill's primary verification mechanism for a specific, already-known cluster. [VERIFIED_FROM_PUBLIC_API_DOCS]

6. Operations beyond the three above — `UpdateClusterName`, `CreateClusterAndSubmitJob`, `ListSecurityRuleStatus`, `ExpandCluster`, `ShrinkCluster`, `ShowMrsVersionList`, `ShowMrsFlavors`, job management APIs, auto-scaling APIs, data-connection management, agency management, IAM synchronization, and tag management — are confirmed to exist by name and URI in MRS's own current API Overview (`# Per-service operations` → MRS → Out of scope lists each), but none had its own parameter table independently fetched during authoring. Probe any of them with `hcloud MRS <OPERATION> --help` and its own API Explorer CLI Examples tab before scripting a call. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

7. **Critical, confirmed gap**: `ListClusters`, `ShowClusterDetails`, and `DeleteCluster` are confirmed to exist in MRS's own API Reference, but ONLY under the V1.1 namespace (`GET /v1.1/{project_id}/clusters`, `GET /v1.1/{project_id}/clusters/{cluster_id}`, `DELETE /v1.1/{project_id}/clusters/{cluster_id}`) — and per Rule 2, MRS 3.x does not support V1.1. No V2 equivalent for listing clusters, showing full cluster details by name/search, or deleting a cluster was found in MRS's current API Overview at authoring time. This skill treats cluster-level list/show/delete for an MRS 3.x cluster as an unresolved capability gap (`GAP-MRS-OPS-101`): it records every `cluster_id` returned by `CreateCluster` as the durable reference, uses `ListNodes` (Rule 5) for node/component-level verification of an already-known cluster, and routes list/show/delete requests to the MRS console rather than guessing whether a V1.1 operation still functions against a 3.x cluster. [VERIFIED_FROM_PUBLIC_API_DOCS] [USE_MANUAL_CONSOLE_FALLBACK]

8. DISCOVER BEFORE CREATE: always resolve `project_id`, `vpc_name`, `subnet_id`/`subnet_name`, and the target `cluster_version`'s actual supported-component list before creating a cluster; never hardcode them or assume a component name is valid for a version without checking. [VERIFIED_FROM_PUBLIC_API_DOCS]

9. CreateCluster's and AddComponent's request bodies are nested JSON objects; always build them as JSON files and pass them with `--cli-jsonInput=<file>`, never as flattened `--param` flags. [VERIFIED_FROM_PUBLIC_API_DOCS]

10. VERIFY AFTER EVERY CREATE OR ADD-COMPONENT: every `CreateCluster` call must be followed by `ListNodes` (with `query_node_detail=true`), polling until every node's `node_status` is `started` and every relevant component's `running_status` is `GOOD`; every `AddComponent` call must be followed by the same, checking the newly added component specifically. [VERIFIED_FROM_PUBLIC_API_DOCS]

11. Every create or add-component action requires explicit approval before execution. [INFERRED]

12. This skill's scope excludes VPC/subnet creation, job submission/management, and in-cluster data management entirely; it only resolves networking IDs read-only and never touches cluster job or data-plane operations. [INFERRED] (explicit scope boundary requested when this skill was authored)

13. Never include secrets (AK, SK, manager_admin_password, node_root_password, component passwords) in commands, JSON body files, examples, or logs; use the credentials already configured in the local hcloud profile, and require the approval owner to supply all cluster passwords out of band. [INFERRED]

14. This skill was authored and verified from MRS's own official public "API V2" API Reference pages for CreateCluster, AddComponent, and ListNodes — each with a full parameter table independently fetched and read, and ListNodes additionally confirmed via its own API Explorer CLI Examples link. It was **not** executed against a live hcloud CLI installation or a live Huawei Cloud tenant. The first real use of this skill in any environment MUST start with `hcloud MRS --help` before relying on any operation name exactly as written here, and MUST re-confirm before using any operation beyond CreateCluster/AddComponent/ListNodes, and especially before assuming any list/show/delete-cluster capability exists for an MRS 3.x cluster. [NOT_LIVE_TESTED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI (KooCLI) | Yes | All MRS operations | `hcloud version` |
| Huawei Cloud authentication (AK/SK) | Yes | API access | `hcloud configure show --cli-profile=default` |
| An existing VPC and subnet in the target region | Yes | CreateCluster requires vpc_name, subnet_id/subnet_name | Resolve read-only via the VPC service/console; this skill does not create them |
| Target region (MRS-supported) | Yes | Service region/endpoint | Confirm via a successful `hcloud MRS --help`/discovery call |
| Project ID | Yes | Path parameter on every MRS V2 operation | `hcloud IAM KeystoneListProjects` (GET /v3/projects), per MRS's own "Obtaining a Project ID" appendix |
| Cluster passwords (manager_admin_password, node_root_password or a key pair) | Yes for create | Initial cluster administrator and node-login credentials | Supplied out of band by the approval owner; never generated by this skill |
| MRS resource-creation permission | Only if action=create or add-component | Ability to create the target cluster / add components | Confirmed only by a successful call or console check |
| Approval owner | Yes (for create/add-component actions) | Authorizes write operations | Specified in intent |
| huaweicloud-ticket MCP | No | Support escalation if a capability gap blocks a request | MCP availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract action, region, and cluster parameters (including the desired component list) from the request.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm action is one of `discover`, `create`, `add-component`, or `verify`.

**Expected result**: Complete intent object.

**Failure action**: If action is missing or ambiguous, STOP and request clarification.

**Evidence artifact**: `artifacts/mrs-ops-intent.json`

## STEP 2 — DISCOVER AUTHENTICATION, REGION, PROJECT, AND NETWORK PREREQUISITES

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI is installed/configured, resolve the project ID, and resolve vpc_name/subnet_id/subnet_name.

**Inputs**: source_region, vpc_name, subnet_name_or_id.

**Preconditions**: hcloud CLI installed (see `# Prerequisites` above).

**Commands** (read-only):

```bash
hcloud version
hcloud configure show --cli-profile=default
hcloud IAM KeystoneListProjects --cli-region=<REGION> --name="<REGION>"
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id="<VPC_ID>"
```

`IAM KeystoneListProjects` is the standard, cross-service Huawei Cloud project-ID lookup (`GET /v3/projects`); it is the same API MRS's own API Reference points to under "Obtaining a Project ID". VPC/subnet operation names above follow the same `hcloud VPC <Operation>` convention documented on API Explorer; they are listed here for discovery convenience only — this skill does not create or modify any of them, and if any name has drifted, probe `hcloud VPC --help` rather than guess. [PROBE_HELP_BEFORE_USE]

**Approval requirement**: None.

**Verification**: Version and profile confirmed; exactly one project/VPC/subnet resolves for the given name/ID.

**Expected result**: Authentication valid; `project_id`, `vpc_name`, `subnet_id`, `subnet_name` resolved.

**Failure action**: STOP. If zero or multiple resources match, do not guess; report and request the operator to disambiguate or create the missing networking resource first (outside this skill).

**Evidence artifact**: `artifacts/mrs-ops-auth-discovery.json`, `artifacts/mrs-ops-project-network-resolution.json`

## STEP 3 — CONFIRM MRS REACHABILITY AND TARGET VERSION/COMPONENTS

**Classification: ASSISTED**

**Objective**: Confirm the MRS service responds, list its operations, and confirm which components the target `cluster_version` actually supports for a CUSTOM cluster.

**Inputs**: cluster_version, requested components.

**Preconditions**: Step 2 completed.

**Commands** (read-only):

```bash
hcloud MRS --help
hcloud MRS ShowMrsVersionList --cli-region=<REGION>
```

`ShowMrsVersionList` is confirmed to exist by name in MRS's API Overview; its own query-parameter table was not independently fetched during authoring — confirm parameters on its own CLI Examples tab. Cross-check the requested component list against the target `cluster_version`'s documented CUSTOM-cluster component set on CreateCluster's own API Reference page (the supported set differs materially by version — for example MRS 3.6.0-LTS's CUSTOM set differs from MRS 3.1.5's).

**Approval requirement**: None.

**Verification**: The command lists operations rather than erroring; every requested component name appears in the target version's documented CUSTOM-cluster component list.

**Expected result**: MRS confirmed reachable; requested components confirmed valid for the target version.

**Failure action**: STOP if a requested component is not in the target version's supported list; report which components are valid instead of guessing an equivalent.

**Evidence artifact**: `artifacts/mrs-ops-service-capability-probe.json`

## STEP 4 — RUN THE MRS MODULE

**Classification: ASSISTED**

**Objective**: Execute the Discover → Create → Verify (→ optional Add-Component) sequence documented in `# Per-service operations` → MRS, using ONLY CreateCluster/AddComponent/ListNodes unless a further operation was freshly probed and approved.

**Inputs**: project_id, vpc_name, subnet_id, subnet_name, cluster_name, cluster_version, components, node_groups, safe_mode, manager_admin_password, login_mode, node_root_password/node_keypair_name, action, cluster_id (for add-component/verify).

**Preconditions**: Steps 1-3 completed.

If action is `discover`: run only `ShowMrsVersionList` (and, if a `cluster_id` is already known, `ListNodes`); stop after recording results.

If action is `create`: request explicit approval (naming cluster_name, cluster_version, the full components list, node_groups shape, and safe_mode), build the nested JSON request body, save it to a file, run `CreateCluster` with `--cli-jsonInput=<file>`, record the returned `cluster_id`, then immediately run `ListNodes` with `query_node_detail=true`, polling until every node is `started` and every component's `running_status` is `GOOD`.

If action is `add-component`: request explicit approval (naming cluster_id, the component, and its node-group/role assignment), confirm the cluster is CUSTOM and on MRS 3.1.2 (normal) / 3.1.2-LTS.2 (LTS) or later, build the `components_install_mode` JSON body, run `AddComponent`, then run `ListNodes` with `query_node_detail=true` to confirm the new component's `running_status` reaches `GOOD`.

If action is `verify`: run `ListNodes` directly with the known `cluster_id` (useful for re-checking a cluster created in a previous run).

**Approval requirement**: EXPLICIT for create and add-component; none for discover/verify.

**Verification**: Every node's `node_status` is `started`; every relevant component's `running_status` is `GOOD`.

**Expected result**: The requested cluster/component state confirmed.

**Failure action**: STOP on any error; do not retry with a different, invented command; do not fall back to a V1.1 operation to work around a missing V2 capability.

**Evidence artifact**: `artifacts/mrs-ops-execution-result.json`, `artifacts/mrs-ops-verification.json`

## STEP 5 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-4.

**Preconditions**: All previous steps completed.

Generate:
- Final summary (action, region, project_id, cluster_id, cluster_version, components enabled, node/component status, result)
- Capability probe result (so future runs against the same tenant/CLI version can skip re-probing CreateCluster/AddComponent/ListNodes, but MUST re-probe any further operation, and MUST always re-check whether a V2 list/show/delete-cluster operation has since been published before relying on `GAP-MRS-OPS-101` being still open)
- Warnings (for example, if the V1.1/V2 gap was encountered and routed to the console)
- Explicit statement that no networking resource and no job/data-plane operation was touched during this run beyond what was requested
- Follow-up actions (for example: "record this cluster_id somewhere durable, since MRS 3.x has no confirmed list-clusters API")
- Unresolved risks

Do NOT perform any rollback/delete action automatically in this closure step.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/mrs-ops-final-report.md`

# Per-service operations

### MRS (service name: `MRS`)

Managed big-data platform running Hadoop-ecosystem components on managed clusters.

Confirmed operations (full parameter table verified against the operation's own current V2 API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateCluster` | `POST /v2/{project_id}/clusters` | cluster_version (required), cluster_name (required), cluster_type (required — use CUSTOM for any component combination), region (required), vpc_name (required), subnet_id/subnet_name (at least one required), components (required, comma-separated), availability_zone (required), safe_mode (required), manager_admin_password (required), login_mode (required), node_root_password or node_keypair_name, node_groups (required array), charge_info, security_groups_id, enterprise_project_id, eip_address/eip_id, template_id, tags, component_configs, smn_notify |
| `AddComponent` | `POST /v2/{project_id}/clusters/{cluster_id}/components` | components_install_mode (required array of {component, node_groups: [{name, assigned_roles}], component_user_password?, component_default_password?}) — CUSTOM clusters on MRS 3.1.2 (normal) / 3.1.2-LTS.2 (LTS) or later only |
| `ListNodes` | `GET /v2/{project_id}/clusters/{cluster_id}/nodes` | node_group, limit, offset, node_name, sort_key, sort_dir, query_node_detail, query_ecs_detail, internal_ip |

**Discover:**
```bash
hcloud MRS --help
hcloud MRS ShowMrsVersionList --cli-region=<REGION>
```

**Create/write** (`CreateCluster`) — requires EXPLICIT approval:
```bash
hcloud MRS CreateCluster --cli-region=<REGION> --project_id="<PROJECT_ID>" --cli-jsonInput=./mrs-create.json
```
Contents of `mrs-create.json` (a CUSTOM cluster enabling any combination of the target version's supported components):
```json
{
  "cluster_version": "MRS 3.3.0-LTS",
  "cluster_name": "<cluster-name>",
  "cluster_type": "CUSTOM",
  "charge_info": { "charge_mode": "postPaid" },
  "region": "<region>",
  "availability_zone": "<az>",
  "vpc_name": "<vpc_name>",
  "subnet_id": "<subnet_id>",
  "subnet_name": "<subnet_name>",
  "components": "Hadoop,Spark,HBase,Hive,Flink,ZooKeeper,Ranger,Tez",
  "safe_mode": "SIMPLE",
  "manager_admin_password": "<manager_password>",
  "login_mode": "PASSWORD",
  "node_root_password": "<root_password>",
  "node_groups": [
    { "group_name": "master_node_default_group", "node_num": 2, "node_size": "<node_flavor>",
      "root_volume": { "type": "SAS", "size": 480 }, "data_volume": { "type": "SAS", "size": 600 }, "data_volume_count": 1 },
    { "group_name": "node_group_1", "node_num": 3, "node_size": "<node_flavor>",
      "root_volume": { "type": "SAS", "size": 480 }, "data_volume": { "type": "SAS", "size": 600 }, "data_volume_count": 1 }
  ]
}
```

**Verify:**
```bash
hcloud MRS ListNodes --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --query_node_detail=true
```
Poll until every node's `node_status` is `started` and every relevant component's `running_status` is `GOOD`.

**Add component (optional, post-creation)** — requires EXPLICIT approval:
```bash
hcloud MRS AddComponent --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --cli-jsonInput=./mrs-addcomponent.json
```
Contents of `mrs-addcomponent.json`:
```json
{
  "components_install_mode": [
    { "component": "HBase", "node_groups": [ { "name": "master_node_default_group", "assigned_roles": [ "RegionServer", "HMaster" ] } ] }
  ]
}
```

Known gap (`GAP-MRS-OPS-101`): `ListClusters`, `ShowClusterDetails`, and `DeleteCluster` are confirmed to exist in MRS's own API Reference, but only under the V1.1 namespace, which MRS's own documentation states MRS 3.x does not support. No V2 equivalent was found at authoring time. Record every `cluster_id` returned by `CreateCluster` as the durable reference; use the MRS console for list/show/delete operations on MRS 3.x clusters; probe `hcloud MRS --help` yourself before assuming a V1.1-style operation still works against a 3.x cluster.

Out of scope for this service module (confirmed to exist by name/URI in MRS's own current API Overview, but not independently parameter-verified — probe `hcloud MRS <OPERATION> --help` before use):

| Operation area | Example operation names |
|---|---|
| Rename / scale a cluster | UpdateClusterName, ExpandCluster, ShrinkCluster |
| Create a cluster and submit a job in one call | CreateClusterAndSubmitJob |
| Cluster communication security status | ListSecurityRuleStatus |
| Version/specification metadata | ShowMrsVersionList, ShowMrsFlavors |
| Job management | CreateExecuteJob, ShowJobList, ShowSingleJob, StopJob, ShowSqlResultWithJob, BatchDeleteJobs |
| Auto scaling | ShowAutoScalingPolicy, UpdateAutoScalingPolicy, DeleteAutoScalingPolicy, CreateAutoScalingPolicy |
| HDFS file listing | ShowHdfsFileList |
| SQL execution | ExecuteSql, ShowSqlResult, CancelSql |
| Agency management | ShowAgencyMapping, UpdateAgencyMapping |
| Data connection management | CreateDataConnector, ListDataConnector, UpdateDataConnector, DeleteDataConnector |
| IAM synchronization | ListClusterSyncTaskStatus, ListClusterSyncStatus, ShowSyncIamUser, UpdateSyncIamUser, CancelSyncIamUser |
| Tag management | SwitchClusterTags, ShowDefaultTagStatus, ShowTagQuota |

Also out of scope: all MRS **job and data-plane** operations (submitting/managing jobs, HDFS/Hive/HBase data operations, SQL execution) — these operate on cluster workloads, not on the cluster instance itself, and are a different API surface entirely from the cluster-management operations this skill covers.

# Capability gap handling

When a capability required for an MRS operation is not available or not confirmed:

1. Document the gap with Gap ID and impact (see above and the known gaps below)
2. Classify the gap: critical path (blocks the requested action) or optional
3. Evaluate alternatives:
   - Can the step be performed via hcloud CLI after a live `--help` probe? → PROBE_HELP_BEFORE_USE (preferred)
   - Can it only be done manually in the console? → USE_MANUAL_CONSOLE_FALLBACK
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL (not applicable to any gap in this skill)
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort; not applicable to any gap in this skill)
4. Never auto-activate a generated MCP or invent an undocumented command as a workaround
5. Never substitute a V1.1 operation for a missing V2 one on an MRS 3.x cluster — if the V2 operation is genuinely unavailable, use the console
6. Update this document's `# Known limitations` section if critical gaps remain

Known capability gaps:

- GAP-MRS-OPS-101 (critical path for cluster-level list/show/delete): `ListClusters`, `ShowClusterDetails`, and `DeleteCluster` are confirmed to exist in MRS's own API Reference, but only under the V1.1 namespace, which MRS's own documentation states MRS 3.x does not support. No V2 equivalent was found in MRS's current API Overview at authoring time.
- GAP-MRS-OPS-102: Every MRS operation beyond CreateCluster/AddComponent/ListNodes (rename, scale, submit-and-run, security-status, version/flavor metadata, job management, auto scaling, HDFS listing, SQL execution, agency management, data connections, IAM sync, tag management) is confirmed to exist by name/URI in MRS's current API Overview, but none had its own parameter table independently fetched during authoring.
- GAP-MRS-OPS-000: No dedicated MCP exists for MRS; all operations via hcloud CLI. [VERIFIED_FROM_PUBLIC_API_DOCS]
- GAP-MRS-OPS-999: This skill has not been executed against a live hcloud CLI or live tenant. All CLI syntax is derived from MRS's own public API Reference documentation (HTTP method/path/parameter tables), not from `--help` output captured live, except ListNodes's operation name, which is additionally confirmed via its own API Explorer CLI Examples link. [NOT_LIVE_TESTED]

# Output artifacts

- artifacts/mrs-ops-intent.json — Parsed intent (action, region, cluster parameters including component list)
- artifacts/mrs-ops-auth-discovery.json — Authentication and hcloud version/profile check
- artifacts/mrs-ops-project-network-resolution.json — Resolved project_id, vpc_name, subnet_id, subnet_name
- artifacts/mrs-ops-service-capability-probe.json — MRS reachability, operation-name confirmation, and target-version component validation
- artifacts/mrs-ops-execution-result.json — Result of the discover/create/add-component/verify action executed
- artifacts/mrs-ops-verification.json — Post-action verification (ListNodes read-back) result
- artifacts/mrs-ops-final-report.md — Closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| `hcloud: command not found` | KooCLI not installed or not in PATH | `hcloud version` | Install KooCLI; add `/usr/local/bin` to PATH |
| Authentication failure | hcloud profile misconfigured | `hcloud configure show --cli-profile=default` | Re-run `hcloud configure init` |
| Region rejected | Region not valid for MRS in this tenant | Try a region already confirmed for other services in the tenant | Use a confirmed region |
| No VPC/subnet resolves | Networking resources not yet created | N/A (out of this skill's scope) | Create them via the networking service/console first |
| `CreateCluster` returns `MRS.0002` ("The parameter is invalid.") | A component name isn't supported by the target cluster_version, or a network/node_size field is invalid | Re-check the components list against CreateCluster's own API Reference component table for the target version (Step 3) | Correct the components list or node/network parameters and retry |
| `hcloud MRS --help` lists a `v1.1`-style operation that doesn't seem to behave against an MRS 3.x cluster | Matches the documented, confirmed V1.1/V2 split (`GAP-MRS-OPS-101`) | Compare the operation's own URI against `/v1.1/...` vs `/v2/...` | Use the console instead of the V1.1 operation for an MRS 3.x cluster |
| Lost track of a cluster's `cluster_id` | No confirmed V2 list-clusters operation exists (`GAP-MRS-OPS-101`) | N/A | Look it up on the MRS console's Active Clusters > Dashboard page, or from the original `CreateCluster` response if still available |
| `AddComponent` fails for a component you expected to be addable | Cluster isn't CUSTOM, or is on an MRS version earlier than 3.1.2 (normal) / 3.1.2-LTS.2 (LTS) | Check cluster_type and cluster_version | Use a CUSTOM cluster on a supported version, or include the component at CreateCluster time instead |
| A node stays in a non-`started` status, or a component's `running_status` stays non-`GOOD`, for a long time | Normal provisioning time for larger clusters, or an underlying provisioning failure | Poll `ListNodes` with `query_node_detail=true`; check the console for a failure reason | Wait for provisioning; escalate to the console/support if status never advances |
| A write operation is rejected (403/permission) | Tenant lacks the specific MRS permission for that action | Error message from the call | Request the specific permission from an administrator |
| Region mismatch between plan and call | `--cli-region` omitted or wrong on a later command | Compare command flags across steps | Ensure every command for the same operation uses the same `--cli-region` |

# Failure handling

- Authentication failure: verify hcloud config, region, IAM permissions. Do not retry with different credentials without operator confirmation.
- Networking prerequisites or project ID not resolved: stop; this skill does not create VPCs/subnets or projects.
- Service unreachable / operation missing: cross-check against `# Per-service operations` before assuming a transient error; if genuinely missing, use the console fallback, never an invented command, and never a V1.1 substitute for an MRS 3.x cluster.
- Write operation rejected for a permission reason: report; do not retry with different credentials without operator confirmation.
- Write operation rejected for any other reason: STOP, preserve evidence, report to approval owner; do not retry with a different, invented command.
- Verification failure, or a node/component stuck in a non-ready state: report; do not delete or recreate the resource automatically.

# Recovery procedure

1. If failure during discovery (Steps 2-3): no resource created. Fix authentication/region/networking/project/component-validity issue and retry from Step 2.
2. If failure during the MRS module (Step 4) discover/verify sub-actions: re-run discovery; no resource was created, retry once the root cause is fixed.
3. If failure during the create or add-component sub-action: check the error. If authorization-related, request the specific permission with a new approval request. If a parameter/component/network error (e.g. `MRS.0002`), correct and retry with a fresh approval if the cluster shape (components, node_groups, safe_mode) changed.
4. If failure during verification, or nodes/components stuck in a non-ready state: do not delete/recreate automatically; report and await a decision. Because `GAP-MRS-OPS-101` means this skill cannot confirm deletion readiness or perform the delete itself, any decision to remove a failed cluster must go through the MRS console.
5. Never expand recovery into a V1.1 operation, or into networking resource changes, to compensate for a failure in MRS.

# Rollback

Because `GAP-MRS-OPS-101` means no confirmed V2 delete-cluster operation exists for MRS 3.x, this skill has **no automated rollback mechanism** for a cluster created in error. The only confirmed corrective actions within this skill's scope are:

- `AddComponent` (to add a missing component to an existing CUSTOM cluster rather than recreating it) — see `# Per-service operations` → MRS
- Reporting the `cluster_id` to the approval owner so the cluster can be terminated from the MRS console

Never invent a `DeleteCluster`-style V2 call. Never call the V1.1 `DeleteCluster` operation against an MRS 3.x cluster without first confirming live (via `hcloud MRS --help` and its own API Explorer CLI Examples tab, or direct testing in a non-production tenant) that it still functions for that cluster generation — do not assume it does or doesn't. Do NOT delete or recreate a cluster automatically after a downstream failure — report and let the approval owner decide, and route the actual deletion through the console unless and until `GAP-MRS-OPS-101` is resolved with a live-confirmed V2 operation. Do NOT touch networking resources as part of any rollback in this skill.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- project_id, vpc_name, subnet_id, subnet_name, cluster_id, and the exact components list recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Capability probe results recorded and reusable across runs against the same tenant/CLI version (re-probe if either changes, and always re-probe any operation beyond CreateCluster/AddComponent/ListNodes, and re-check whether `GAP-MRS-OPS-101` has been resolved with a published V2 operation)
- No secrets (AK/SK, cluster passwords) in any artifact

# Known limitations

- No dedicated MCP exists for MRS [VERIFIED_FROM_PUBLIC_API_DOCS]
- No confirmed V2 operation exists to list clusters, show full cluster details, or delete a cluster for MRS 3.x; the only V1.1 equivalents are explicitly unsupported for MRS 3.x per MRS's own documentation [GAP-MRS-OPS-101] — this also means this skill has no automated rollback/delete capability
- Every MRS operation beyond CreateCluster/AddComponent/ListNodes is unverified at the parameter level [GAP-MRS-OPS-102]
- This skill's scope excludes VPC/subnet creation, job submission/management, in-cluster data operations, scaling, and auto-scaling configuration
- No live hcloud CLI or tenant test was performed during authoring

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- MRS (`MRS`): `CreateCluster` and `AddComponent` each confirmed with a full request/response parameter table from their own current (V2) public API Reference page; `ListNodes` confirmed the same way and additionally confirmed via its own API Explorer CLI Examples link (`api=ListNodes`), which is the strongest confirmation obtained for any operation across this skill and its companion skills. [VERIFIED_FROM_PUBLIC_API_DOCS]
- The V1.1 cluster-management namespace, including the only confirmed `ListClusters`/`ShowClusterDetails`/`DeleteCluster` operations, is explicitly stated by MRS's own documentation to be unsupported for MRS 3.x. This is a genuine, critical-path capability gap (`GAP-MRS-OPS-101`), not a documentation-fetch shortfall: the operations exist, but not for the cluster generation this skill targets. [VERIFIED_FROM_PUBLIC_API_DOCS]
- Every operation beyond the three core ones is confirmed to exist by name/URI only, not parameter-verified. [PARTIAL]
- No dedicated MCP exists for MRS [VERIFIED_FROM_PUBLIC_API_DOCS]
- All create/add-component operations require explicit approval [INFERRED]
- No cloud-side or CLI-side live test was executed; this authoring environment had web-search/fetch access to public documentation only, not a live hcloud CLI install or Huawei Cloud credentials [NOT_LIVE_TESTED]
- Because of the above, this skill mandates a live `hcloud MRS --help` probe before any workflow instance relies on an operation name exactly as documented here, mandates a fresh probe plus approval before using any operation beyond the three core ones, and documents an explicit console fallback (with no automated rollback) for cluster-level list/show/delete until `GAP-MRS-OPS-101` is resolved with a live-confirmed V2 operation
