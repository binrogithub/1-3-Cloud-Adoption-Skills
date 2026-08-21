---
name: huawei-mrs-migration-operations
version: 1.0.0
description: Migrate a complete big-data system — components and internal data — from an on-premises Hadoop distribution (Apache Hadoop, CDH, Hortonworks, FusionInsight), AWS (EMR/S3), Azure (HDInsight/Blob Storage), or Google Cloud (Dataproc/Cloud Storage) into a Huawei Cloud MapReduce Service (MRS) CUSTOM cluster, via hcloud CLI (KooCLI). Lands a target cluster whose component set reproduces the source inventory, moves bulk object data with OMS into OBS, loads it into the cluster with MRS DistCp jobs, and rebuilds table metadata with MRS Hive jobs. Uses only the current MRS API V2, since MRS's own documentation states MRS 3.x does not support the older V1.1 API — including the confirmed gap that V2 has no list/show/delete-cluster operation, documented explicitly rather than substituted with an unconfirmed V1.1 call.
category: database-operations
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Big-Data-Migration
  family: Cloud-Platform-Migration
  service: MRS, OMS
  risk_level: high
  status: READY_WITH_WARNINGS
  create_operation_verification: FULL_PARAMETER_TABLE_VERIFIED_NOT_LIVE_TESTED
---

# Purpose

Migrate an entire big-data system into Huawei Cloud MapReduce Service (MRS) using hcloud CLI (KooCLI) as the primary mechanism. "Entire system" means both halves of a platform migration: the **components** (Hadoop, Spark, HBase, Hive, Kafka, Flink, ZooKeeper, Ranger, Tez, ClickHouse, and more, depending on the target MRS version) and the **internal data** those components hold (HDFS files, Hive tables and partitions, HBase tables, and the object-storage datasets the cluster reads).

The target is always an MRS **CUSTOM** cluster, because CUSTOM is the only MRS cluster type that lets the caller enable any combination of MRS components in a single cluster — which is precisely what makes it possible to reproduce a source cluster's component inventory rather than accept the fixed component sets of the ANALYSIS, STREAMING, MIXED, or DORIS types. CUSTOM is supported only by MRS 3.x.

The migration runs on three planes, each with its own confirmed mechanism:

1. **Bulk object plane** — OMS `CreateTask` moves objects from AWS S3, Azure Blob Storage, Google Cloud Storage, or another supported provider into Huawei Cloud OBS.
2. **Cluster data plane** — MRS `CreateExecuteJob` with `job_type: DistCp` loads the staged data from OBS into the target cluster's own HDFS.
3. **Metadata plane** — MRS `CreateExecuteJob` with `job_type: HiveSql` or `HiveScript` rebuilds table definitions on the target so the copied files are actually queryable.

This skill is migration-only. It never modifies the source platform, does not create the VPC/subnet or the network path (Direct Connect/VPN) a migration may need, does not manage the ongoing workload after cutover, and does not configure auto scaling.

# Supported scenario

- Source: a big-data system on one of the supported source platforms, described by an inventory collected outside this skill
- Target: an MRS CUSTOM cluster, fully identified by its own `cluster_id` once created
- Mechanism: the MRS and OMS management-plane V2 REST APIs called through hcloud CLI, under the service names `MRS` and `OMS`; no dedicated MCP exists for either
- Staging: an OBS bucket in the target region, used as the landing zone between OMS and DistCp
- Topology: single-region, single-target-cluster migration per invocation

| Source platform | Compute inventoried | Object storage migrated by OMS (`cloud_type`) |
|---|---|---|
| On-premises | Apache Hadoop, CDH, Hortonworks, FusionInsight | n/a — DistCp over a private network path, or `URLSource` |
| AWS | EMR | `AWS` (ak/sk) |
| Azure | HDInsight | `Azure` (connection_string) |
| Google Cloud | Dataproc | `Google` (json_auth_file) |

| Service | `hcloud` service name | API generation used |
|---|---|---|
| MapReduce Service | `MRS` | API V2 only — MRS's own documentation states MRS 3.x does not support API V1.1 |
| Object Storage Migration Service | `OMS` | APIs V2 (`/v2/{project_id}/tasks`) |

# When to use this skill

- Migrating an on-premises Hadoop cluster, AWS EMR, Azure HDInsight, or Google Dataproc workload onto MRS, components and data together
- Landing an MRS CUSTOM cluster whose component set is derived from a source-cluster inventory rather than chosen from scratch
- Moving bulk object data from S3, Blob Storage, or Cloud Storage into OBS as a migration staging step
- Loading staged OBS data into a target cluster's HDFS, or copying directly from a reachable source HDFS, with DistCp
- Rebuilding Hive table definitions on the target so migrated files become queryable
- Verifying, before cutover, that what landed on the target matches what left the source

# When not to use this skill

- Any write, reconfiguration, or decommission action against the **source** platform — this skill only ever reads the source, and the source is the rollback path
- Deploying a *new* MRS cluster with no migration involved — use `huawei-mrs-deploy-operations` instead
- Creating, modifying, or deleting the VPC or subnet, or establishing the Direct Connect/VPN path a private-network DistCp needs — resolve these read-only; this skill only consumes their IDs
- Ongoing job scheduling or workload management after cutover — this skill ends at verified cutover readiness
- Managing data inside HDFS/Hive/HBase as business-as-usual operations (as opposed to the one-time migration load) — use the component's own client/console
- Scaling (ExpandCluster/ShrinkCluster), auto-scaling policy configuration, cluster renaming, or upgrading — name/URI-confirmed only, out of scope
- Listing all clusters in a project, showing full cluster details by name, or deleting a cluster, for an MRS 3.x cluster — no confirmed V2 operation exists (`GAP-MRS-MIG-101`); use the MRS console
- HBase table migration mechanics (snapshot/export/import) — performed with the component's own in-cluster tooling, not through the MRS management API
- When hcloud CLI is not available and cannot be installed

# Required inputs

- action (inventory, land, migrate-data, migrate-metadata, verify, or add-component)
- source_platform (onprem, aws, azure, or gcp)
- source_inventory (component list with versions, dataset sizes, table/partition counts — collected outside this skill; see Step 3)
- source_read_credentials (read-only, supplied out of band; never written to by this skill)
- source_region and source_bucket (for aws/azure/gcp object-storage migration)
- target_region
- vpc_name, subnet_id, subnet_name (resolved read-only; this skill does not create them)
- obs_staging_bucket (must be in the same region as the OMS endpoint being called)
- cluster_name, cluster_version (for example "MRS 3.3.0-LTS")
- components (comma-separated; derived from source_inventory, validated against the target version)
- node_groups (at minimum a master_node_default_group; sized against the source data footprint)
- manager_admin_password, login_mode (PASSWORD or KEYPAIR) and node_root_password or node_keypair_name
- approval_owner (required for land, migrate-data, migrate-metadata, and add-component)

# Optional inputs

- availability_zone (single-AZ only; MRS does not support multi-AZ clusters)
- safe_mode (SIMPLE or KERBEROS)
- charge_info (defaults to pay-per-use / postPaid unless yearly/monthly is explicitly requested)
- bandwidth_policy (OMS traffic caps, up to five non-overlapping periods, 1,048,576–209,715,200 bytes/s)
- consistency_check (`size_last_modified`, `crc64`, or `no_check`), object_overwrite_mode, dst_storage_policy
- migrate_since (epoch seconds — for the incremental/delta pass before cutover)
- security_groups_id, enterprise_project_id, tags, eip_address/eip_id, template_id, component_configs
- cluster_id (required for migrate-data, migrate-metadata, verify, add-component)
- task_id, job_execution_id (for tracking an in-flight migration)

# Required MCPs

None. All operations are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-ticket (only to open a support ticket if a capability-gap probe fails for a critical-path operation and manual escalation is desired)

# Tool selection policy

- Use hcloud CLI for ALL MRS and OMS operations
- Always use the service names `MRS` and `OMS`, and for MRS only its V2 operations (CreateCluster, AddComponent, ListNodes, CreateExecuteJob, ShowSingleJob, ShowJobList, StopJob, ShowHdfsFileList, and — only after a live probe — any further one); never call a `/v1.1/...`-style operation for an MRS 3.x cluster
- Because CreateCluster, CreateTask, and CreateExecuteJob all take nested JSON request bodies, always pass them through KooCLI's `--cli-jsonInput=<file>` option, never as flattened `--param` flags
- Never assume an operation beyond the confirmed set is available without probing it live first (`hcloud MRS <OPERATION> --help`, `hcloud OMS <OPERATION> --help`) and cross-checking its own API Explorer CLI Examples tab
- Use MgC (console + MgC Agent) for source inventory collection and post-migration consistency verification; it has no confirmed hcloud operation surface (`GAP-MRS-MIG-102`), so never invent one
- Never use this skill to create, modify, or delete a VPC, subnet, or network interconnect; resolve their IDs read-only
- Never issue a write operation against the source platform — read-only credentials only
- Never substitute the V1.1 `ListClusters`/`ShowClusterDetails`/`DeleteCluster` operations for a missing V2 equivalent on an MRS 3.x cluster (`GAP-MRS-MIG-101`); route to the console instead

# Safety and approval gates

1. Any land, migrate-data, migrate-metadata, or add-component action requires explicit approval before execution — an MRS cluster is a billable, multi-node cloud resource, and a data migration moves production data across a provider boundary
2. Reusing an existing target cluster instead of creating a new one requires explicit confirmation from the approval owner
3. Passwords and credentials (manager_admin_password, node_root_password, component passwords, source AK/SK, Azure connection_string, Google json_auth_file) are never generated, guessed, printed, or logged by this skill; they must be supplied by the approval owner out of band
4. Source credentials MUST be read-only. The source platform is the only rollback path this workflow has, and it must remain intact and running until verification passes
5. Enabling Kerberos (`safe_mode: KERBEROS`) versus SIMPLE mode is a security-relevant choice and must be called out explicitly before the land step — it determines who can use the cluster after migration
6. Component and node-group choices must be confirmed against the target `cluster_version`'s supported-component list (Step 4) before requesting approval; node groups must be sized against the actual source data footprint from Step 3
7. Cutover is a separate, human decision. This skill reaches "verified and ready to cut over" and stops; it never re-points production pipelines
8. A migration that copies data into a cluster that failed verification must not be presented as complete — report the discrepancy instead

# Rules

1. MRS is exposed through hcloud CLI under the service name `MRS`. This is directly confirmed: the API Explorer "CLI Examples" link on the ListNodes operation's own page uses the URL parameter pattern `openapi/mrs/cli?version=v2&api=ListNodes`, confirming both the lowercase-normalized service segment (`mrs`) and the literal operation name `ListNodes`. [VERIFIED_FROM_PUBLIC_API_DOCS]

2. OMS is exposed through hcloud CLI under the service name `OMS`. This is directly confirmed: the API Explorer "CLI Examples" link on the CreateTask operation's own page uses the URL parameter pattern `openapi/oms/cli?api=CreateTask`. [VERIFIED_FROM_PUBLIC_API_DOCS]

3. MRS publishes two API generations: a current 'API V2' (`/v2/{project_id}/clusters...`) and an older 'API V1.1'. MRS's own "Before You Start" documentation states explicitly: "MRS 3.x does not support V1.1 APIs. You need to use V2 APIs." This skill uses ONLY the V2 namespace and never calls a V1.1-style URI for a 3.x cluster. [VERIFIED_FROM_PUBLIC_API_DOCS]

4. `CreateCluster` (`POST /v2/{project_id}/clusters`) is confirmed with a full request/response parameter table. Required fields include `cluster_version`, `cluster_name`, `cluster_type` (use `CUSTOM`), `region`, `vpc_name`, `subnet_name` (subnet_id and/or subnet_name required), `components` (comma-separated string — the field that reproduces the source inventory on the target), `availability_zone`, `safe_mode`, `manager_admin_password`, `login_mode`, and `node_groups`. The response returns `cluster_id`. [VERIFIED_FROM_PUBLIC_API_DOCS]

5. `CreateExecuteJob` (`POST /v2/{project_id}/clusters/{cluster_id}/job-executions`) is confirmed with a full request/response parameter table. Its `job_type` value range explicitly includes **`DistCp`**, documented as "a Hadoop tool used to efficiently import and export data between distributed file systems (such as HDFS)" — this is this skill's primary in-cluster data-movement mechanism. It also includes `HiveSql`, `HiveScript`, `SparkSubmit`, `SparkPython`, `SparkScript`, `SparkSql`, `MapReduce`, and `Flink`. Body fields: `job_type` (required), `job_name` (required), `arguments` (array; for DistCp, source path then destination path), `properties` (map; for example `fs.obs.endpoint`). Response returns `job_submit_result` with `job_id` and `state` (`COMPLETE` = submitted, `FAILED` = not submitted). [VERIFIED_FROM_PUBLIC_API_DOCS]

6. `state: COMPLETE` from `CreateExecuteJob` means the job was **submitted**, not that it finished. Execution outcome must be read from `ShowSingleJob` or `ShowJobList`. Never report a migration step as done on the strength of a submission response. [VERIFIED_FROM_PUBLIC_API_DOCS]

7. MRS's own documentation warns that parameters containing sensitive information may appear in job details and logs. Therefore never place an AK/SK in `arguments`; prefer an agency or cluster-side credential configuration, and treat `properties` as logged output. [VERIFIED_FROM_PUBLIC_API_DOCS]

8. `AddComponent` (`POST /v2/{project_id}/clusters/{cluster_id}/components`) is confirmed with a full parameter table. It applies only to CUSTOM clusters on MRS 3.1.2 (normal) / 3.1.2-LTS.2 (LTS) or later. Body is `components_install_mode`, an array of `{component, node_groups: [{name, assigned_roles}], component_user_password?, component_default_password?}`. In a migration this is the cheap remedy for an inventory miss — far cheaper than rebuilding and re-copying. [VERIFIED_FROM_PUBLIC_API_DOCS]

9. `ListNodes` (`GET /v2/{project_id}/clusters/{cluster_id}/nodes`) is confirmed with a full query-parameter and response-schema table, and additionally confirmed by its own API Explorer CLI Examples link. Query parameters: `node_group`, `limit`, `offset`, `node_name`, `sort_key`, `sort_dir`, `query_node_detail`, `query_ecs_detail`, `internal_ip`. Set `query_node_detail=true` to return `component_infos` with each component's `running_status`. [VERIFIED_FROM_PUBLIC_API_DOCS]

10. `ShowHdfsFileList` (`GET /v2/{project_id}/clusters/{cluster_id}/files`, "Obtaining the List of Files from a Specified Directory") is confirmed to exist by name and URI in MRS's current API V2 overview under "Cluster HDFS File API"; its own parameter table was not independently fetched during authoring. Probe before scripting. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

11. `CreateTask` (`POST /v2/{project_id}/tasks`) is confirmed with a full request/response parameter table. `src_node.cloud_type` documented values include `AWS`, `Azure`, `Google`, `Aliyun`, `Tencent`, `HuaweiCloud`, `QingCloud`, `KingsoftCloud`, `Baidu`, `Qiniu`, `UCloud`, and `URLSource`. Authentication differs by platform: AWS uses `ak`/`sk`, Azure Blob uses `connection_string`, Google Cloud Storage uses `json_auth_file`. `task_type` is one of `object`, `prefix`, `list`, or `url_list`; setting `object_key` to `[""]` migrates an entire bucket. A created task starts automatically. Response returns `id` and `task_name`. [VERIFIED_FROM_PUBLIC_API_DOCS]

12. OMS Migration Task Management confirms, by name and URI in its own API Reference index, the operations `CreateTask`, `ListTasks`, `ShowTask`, `StartTask`, `StopTask`, `DeleteTask`, `UpdateBandwidthPolicy`, and `BatchUpdateTasks`. Only `CreateTask` had its full parameter table independently fetched during authoring; probe the others before scripting. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

13. OMS documented constraints that shape a migration plan: a tenant can create at most 1,500 migration tasks in 24 hours; Huawei Cloud recommends a migration **task group** rather than a single task when a source bucket holds more than 3 TB or more than 5 million objects; the destination OBS bucket must be in the same region as the OMS endpoint being called; and `enable_failed_object_recording` (default true) writes a failed-object list into the destination bucket. Read that list rather than assuming a completed task copied everything. [VERIFIED_FROM_PUBLIC_API_DOCS]

14. INVENTORY BEFORE LAND: the target component list is **derived from the source**, never guessed. No Huawei Cloud API can read the source cluster; the inventory is collected on the source side (MgC Agent, or the source platform's own tooling) and is a required input to Step 5. If a source component has no MRS equivalent on the target version, STOP and resolve the gap explicitly rather than dropping it silently. [INFERRED]

15. VERIFY AFTER EVERY WRITE: every `CreateCluster` must be followed by `ListNodes` (with `query_node_detail=true`) polled until every node is `started` and every component's `running_status` is `GOOD`, before any data is copied; every `CreateTask` must be followed by `ShowTask` and a failed-object-list check; every `CreateExecuteJob` must be followed by `ShowSingleJob` to completion; every `AddComponent` must be followed by `ListNodes`. [VERIFIED_FROM_PUBLIC_API_DOCS]

16. FILE PRESENCE IS NOT EQUIVALENCE. `ShowHdfsFileList` confirms files landed where expected; it does not confirm the data matches the source. Row-count and checksum comparison per table is required before cutover readiness is declared, and MgC provides this as a big-data consistency verification feature for Hive, HBase, Doris, ClickHouse, Delta Lake, and Hudi. [VERIFIED_FROM_PUBLIC_API_DOCS]

17. Copying files does not migrate table definitions, and restoring DDL does not register partitions. A partitioned Hive table whose partitions were never registered reads as empty even when every file is present — check this before concluding data is missing. [INFERRED]

18. The source platform is never written to, reconfigured, or decommissioned by this skill, and must remain running until verification passes. Because `GAP-MRS-MIG-101` means this skill cannot delete a target cluster, the source is the only rollback path available. [INFERRED]

19. Never include secrets (AK/SK, cluster passwords, source credentials, Azure connection strings, Google service-account JSON) in commands, JSON body files, examples, artifacts, or logs. [INFERRED]

20. This skill was authored and verified from Huawei Cloud's own official public API Reference pages — MRS API V2 for CreateCluster, AddComponent, ListNodes, and CreateExecuteJob, and OMS APIs V2 for CreateTask — each with a full parameter table independently fetched and read. It was **not** executed against a live hcloud CLI installation or a live Huawei Cloud tenant, and no live migration was performed. The first real use MUST start with `hcloud MRS --help` and `hcloud OMS --help` before relying on any operation name exactly as written here. [NOT_LIVE_TESTED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI (KooCLI) | Yes | All MRS and OMS operations | `hcloud version` |
| Huawei Cloud authentication (AK/SK) | Yes | API access | `hcloud configure show --cli-profile=default` |
| Source-platform read-only credentials | Yes | Inventory and object-storage read | Supplied out of band; never written to |
| An existing VPC and subnet in the target region | Yes | CreateCluster requires vpc_name, subnet_id/subnet_name | Resolve read-only; this skill does not create them |
| An OBS bucket in the target region | Yes for migrate-data | Staging landing zone between OMS and DistCp | Must match the OMS endpoint region |
| Target region (MRS- and OMS-supported) | Yes | Service region/endpoint | Confirm via successful `hcloud MRS --help` / `hcloud OMS --help` |
| Project ID | Yes | Path parameter on every MRS and OMS V2 operation | `hcloud IAM KeystoneListProjects` (GET /v3/projects) |
| Source inventory | Yes | Determines the target component set and node sizing | Collected outside this skill (MgC Agent or source tooling) |
| MgC Agent + MgC console | Only for assisted inventory/verification | Source metadata collection and consistency verification | MgC console; no confirmed hcloud surface |
| Private network path (Direct Connect/VPN) | Only for direct hdfs:// DistCp | Source HDFS reachability | Out of this skill's scope to create |
| Cluster passwords | Yes for land | Cluster administrator and node-login credentials | Supplied out of band by the approval owner |
| MRS + OMS resource-creation permission | Yes for write actions | Ability to create the cluster, tasks, and jobs | Confirmed only by a successful call or console check |
| Approval owner | Yes (for write actions) | Authorizes write operations | Specified in intent |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract action, source_platform, target region, and migration parameters from the request.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm action is one of `inventory`, `land`, `migrate-data`, `migrate-metadata`, `verify`, or `add-component`, and that source_platform is one of `onprem`, `aws`, `azure`, `gcp`.

**Expected result**: Complete intent object.

**Failure action**: If action or source_platform is missing or ambiguous, STOP and request clarification.

**Evidence artifact**: `artifacts/mrs-mig-intent.json`

## STEP 2 — DISCOVER AUTHENTICATION, REGION, PROJECT, AND NETWORK PREREQUISITES

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI is installed/configured, resolve the project ID, and resolve vpc_name/subnet_id/subnet_name and the OBS staging bucket.

**Inputs**: target_region, vpc_name, subnet_name_or_id, obs_staging_bucket.

**Preconditions**: hcloud CLI installed.

**Commands** (read-only):

```bash
hcloud version
hcloud configure show --cli-profile=default
hcloud IAM KeystoneListProjects --cli-region=<REGION> --name="<REGION>"
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id="<VPC_ID>"
```

VPC operation names follow the `hcloud VPC <Operation>` convention documented on API Explorer; they are listed for discovery convenience only — this skill does not create or modify any of them. If any name has drifted, probe `hcloud VPC --help` rather than guess. [PROBE_HELP_BEFORE_USE]

**Approval requirement**: None.

**Verification**: Version and profile confirmed; exactly one project/VPC/subnet resolves; the OBS staging bucket is in the same region as the OMS endpoint.

**Expected result**: `project_id`, `vpc_name`, `subnet_id`, `subnet_name`, `obs_staging_bucket` resolved.

**Failure action**: STOP. Do not guess; report and request the operator to disambiguate or create the missing resource first (outside this skill).

**Evidence artifact**: `artifacts/mrs-mig-auth-discovery.json`, `artifacts/mrs-mig-project-network-resolution.json`

## STEP 3 — INVENTORY THE SOURCE SYSTEM

**Classification: MANUAL / ASSISTED**

**Objective**: Produce a complete, evidence-backed inventory of what is being migrated.

**Inputs**: source_platform, source_read_credentials.

**Preconditions**: Step 2 completed.

Collect, for every source system:

- Component list with versions (Hadoop, Hive, Spark, HBase, Kafka, Flink, ZooKeeper, and so on)
- HDFS and/or object-storage footprint in TB per dataset
- Table and partition counts per database
- Job inventory: which components each production job actually depends on
- Security posture: whether the source runs Kerberos (drives the target `safe_mode` decision)

**Commands**: None in this skill. There is no Huawei Cloud API that reads a source cluster (`GAP-MRS-MIG-103`). Use the MgC Agent installed on a server inside the source network — it connects to Hive Metastore, HBase, Doris, ClickHouse, Delta Lake, or Hudi and produces a metadata inventory, driven from the MgC console — or the source platform's own tooling.

**Approval requirement**: None (read-only), but the inventory must be reviewed before Step 5.

**Verification**: Every production job's component dependencies appear in the inventory; dataset sizes are measured, not estimated.

**Expected result**: A component list and a data footprint that Step 4 can validate and Step 5 can consume.

**Failure action**: STOP. Never proceed to `land` on a guessed inventory — an unmapped component becomes a failed cutover, and an under-measured footprint becomes an undersized cluster.

**Evidence artifact**: `artifacts/mrs-mig-source-inventory.json`

## STEP 4 — CONFIRM SERVICE REACHABILITY AND MAP COMPONENTS TO THE TARGET VERSION

**Classification: ASSISTED**

**Objective**: Confirm MRS and OMS respond, and confirm the target `cluster_version` supports every component in the inventory.

**Inputs**: cluster_version, source inventory from Step 3.

**Preconditions**: Steps 2-3 completed.

**Commands** (read-only):

```bash
hcloud MRS --help
hcloud OMS --help
hcloud MRS ShowMrsVersionList --cli-region=<REGION>
```

`ShowMrsVersionList` is confirmed to exist by name in MRS's API Overview; its own query-parameter table was not independently fetched — confirm parameters on its own CLI Examples tab. Cross-check every inventoried component against the target `cluster_version`'s documented CUSTOM-cluster component set on CreateCluster's own API Reference page; the supported set differs materially by version.

**Approval requirement**: None.

**Verification**: Both services list operations rather than erroring; every inventoried component maps to a component name valid for the target version.

**Expected result**: A validated `components` string, ready for Step 5.

**Failure action**: STOP if any source component has no equivalent on the target version. Report the unmapped components and let the approval owner decide (change target version, replace the component, or accept the loss explicitly) — never drop it silently.

**Evidence artifact**: `artifacts/mrs-mig-service-capability-probe.json`, `artifacts/mrs-mig-component-mapping.json`

## STEP 5 — LAND THE TARGET CLUSTER

**Classification: ASSISTED**

**Objective**: Create the MRS CUSTOM cluster whose component set reproduces the source inventory, and confirm it is healthy before any data moves.

**Inputs**: project_id, vpc_name, subnet_id, subnet_name, cluster_name, cluster_version, components, node_groups, safe_mode, credentials.

**Preconditions**: Steps 1-4 completed.

**Approval requirement**: EXPLICIT. Name the cluster_name, cluster_version, full components list, node_groups shape (with the source footprint that justifies the sizing), and safe_mode.

Build the nested JSON body, save it to a file, and run:

```bash
hcloud MRS CreateCluster --cli-region=<REGION> --project_id="<PROJECT_ID>" --cli-jsonInput=./mrs-create.json
```

Record the returned `cluster_id` immediately and durably — MRS 3.x has no confirmed V2 list-clusters operation. Then poll:

```bash
hcloud MRS ListNodes --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --query_node_detail=true
```

**Verification**: Every node's `node_status` is `started`; every component's `running_status` is `GOOD`.

**Expected result**: A healthy target cluster ready to receive data.

**Failure action**: STOP on any error. Do not begin the data migration against a partially provisioned cluster — copying into it wastes the transfer. On `MRS.0002`, re-check the components list against Step 4 and the network/node parameters.

**Evidence artifact**: `artifacts/mrs-mig-cluster-landing.json`, `artifacts/mrs-mig-cluster-verification.json`

## STEP 6 — MIGRATE THE BULK OBJECT DATA

**Classification: ASSISTED**

**Objective**: Move the source object-storage datasets into the OBS staging bucket.

**Inputs**: project_id, source_platform, source credentials, source_bucket, obs_staging_bucket, bandwidth_policy.

**Preconditions**: Step 5 verified healthy.

**Approval requirement**: EXPLICIT. Name the source bucket(s), the destination bucket, the data volume, and the bandwidth policy.

Build the task body — `cloud_type` selects the platform (`AWS` with ak/sk, `Azure` with connection_string, `Google` with json_auth_file) — and run:

```bash
hcloud OMS CreateTask --cli-region=<REGION> --project_id="<PROJECT_ID>" --cli-jsonInput=./oms-task.json
```

A created task starts automatically. Track it with:

```bash
hcloud OMS ShowTask --cli-region=<REGION> --project_id="<PROJECT_ID>" --task_id="<TASK_ID>"
```

If a source bucket exceeds 3 TB or 5 million objects, use a migration task group rather than a single task. Set a `bandwidth_policy` so the copy does not saturate the source network during business hours.

**Verification**: Task reaches a completed state AND the failed-object list in the destination bucket is read and is empty (or its contents are re-run).

**Expected result**: Source datasets staged in OBS, with a reconciled object count.

**Failure action**: STOP. A destination-bucket region mismatch is rejected outright — fix the bucket, not the call. Never treat "task completed" as "everything copied" without reading the failed-object list.

**Evidence artifact**: `artifacts/mrs-mig-oms-tasks.json`, `artifacts/mrs-mig-failed-objects.json`

## STEP 7 — LOAD THE DATA INTO THE CLUSTER

**Classification: ASSISTED**

**Objective**: Move the staged data from OBS into the target cluster's HDFS.

**Inputs**: project_id, cluster_id, obs paths, hdfs target paths.

**Preconditions**: Step 6 reconciled.

**Approval requirement**: EXPLICIT.

```bash
hcloud MRS CreateExecuteJob --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --cli-jsonInput=./mrs-distcp.json
```

Body: `{"job_name": "...", "job_type": "DistCp", "arguments": ["obs://<bucket>/<src>/", "/user/<dst>/"], "properties": {"fs.obs.endpoint": "<endpoint>"}}`. The first argument is source, the second destination. If the source HDFS is reachable over a private network path, DistCp can read an `hdfs://` source directly instead of staging through OBS — that network path is not created by this skill.

Never place an AK/SK in `arguments`; sensitive parameters may surface in job details and logs.

Track to completion:

```bash
hcloud MRS ShowSingleJob --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --job_execution_id="<JOB_ID>"
```

**Verification**: `ShowSingleJob` reports the job actually finished. A submission `state` of `COMPLETE` is not completion.

**Expected result**: Data present in the target cluster's HDFS.

**Failure action**: STOP; read the job log for the real cause. Do not retry with an invented command.

**Evidence artifact**: `artifacts/mrs-mig-distcp-jobs.json`

## STEP 8 — REBUILD THE METADATA

**Classification: ASSISTED**

**Objective**: Recreate table definitions on the target so the migrated files are queryable.

**Inputs**: project_id, cluster_id, exported DDL.

**Preconditions**: Step 7 completed.

**Approval requirement**: EXPLICIT.

```bash
hcloud MRS CreateExecuteJob --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --cli-jsonInput=./mrs-hive.json
```

Body: `{"job_name": "...", "job_type": "HiveScript", "arguments": ["obs://<bucket>/ddl/create_tables.sql"]}` — or `HiveSql` to pass statements inline. Point each table's LOCATION at the path the data now occupies.

After the DDL runs, register partitions for partitioned tables (for example with `MSCK REPAIR TABLE`) — otherwise the table reads as empty even though every file is present.

HBase tables are migrated with their own snapshot/export tooling from inside the cluster, not through this API.

**Verification**: Tables exist AND return rows; partition counts match the Step 3 inventory.

**Expected result**: A queryable platform on the target.

**Failure action**: STOP. An empty table is more often unregistered partitions than missing data — check that before re-copying.

**Evidence artifact**: `artifacts/mrs-mig-metadata-jobs.json`

## STEP 9 — VERIFY AND RECONCILE

**Classification: ASSISTED / MANUAL**

**Objective**: Prove the target matches the source, per dataset.

**Inputs**: cluster_id, Step 3 inventory.

**Preconditions**: Steps 6-8 completed.

```bash
hcloud MRS ShowHdfsFileList --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --path="<HDFS_PATH>"
```

This confirms files landed where expected. It does **not** confirm equivalence. Compare row counts and checksums per table against the source; MgC provides this as a big-data consistency verification feature (Hive, HBase, Doris, ClickHouse, Delta Lake, Hudi), driven from the MgC console.

Run the source's own critical jobs against the target and diff the output.

Before cutover, run a delta pass for anything written to the source since the full copy — OMS `migrate_since` restricts a task to objects modified after a given timestamp.

**Approval requirement**: None to verify; EXPLICIT human approval to declare cutover readiness.

**Verification**: Per-table row counts and checksums match; critical job output matches.

**Expected result**: An evidence-backed statement of cutover readiness — or an itemised list of discrepancies.

**Failure action**: Report discrepancies. Never declare a migration complete on transfer success alone. The source stays running.

**Evidence artifact**: `artifacts/mrs-mig-verification.json`, `artifacts/mrs-mig-reconciliation-report.md`

## STEP 10 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate the final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-9.

Generate:

- Final summary (source platform, action, region, project_id, cluster_id, cluster_version, components migrated, datasets migrated with sizes, verification result)
- Capability probe results (reusable across runs against the same tenant/CLI version; MUST re-probe any operation beyond the confirmed set, and MUST re-check whether a V2 list/show/delete-cluster operation has since been published before relying on `GAP-MRS-MIG-101` being still open)
- Warnings (for example, gaps routed to the MgC or MRS console)
- Explicit statement that the source platform was never written to, and that no networking resource was created
- Explicit cutover-readiness statement, including anything still unverified
- Follow-up actions (for example: "record this cluster_id durably; keep the source cluster running until cutover is signed off")
- Unresolved risks

Do NOT perform any cutover, rollback, or delete action automatically in this closure step.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/mrs-mig-final-report.md`

# Per-service operations

### MRS (service name: `MRS`)

Managed big-data platform running Hadoop-ecosystem components on managed clusters. In this skill it is both the migration target and the engine that executes the data-movement jobs.

Confirmed operations (full parameter table verified against the operation's own current V2 API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateCluster` | `POST /v2/{project_id}/clusters` | cluster_version, cluster_name, cluster_type (CUSTOM), region, vpc_name, subnet_id/subnet_name, components, availability_zone, safe_mode, manager_admin_password, login_mode, node_root_password/node_keypair_name, node_groups, charge_info, security_groups_id, enterprise_project_id, eip_address/eip_id, template_id, tags, component_configs |
| `CreateExecuteJob` | `POST /v2/{project_id}/clusters/{cluster_id}/job-executions` | job_type (required — **DistCp** for data movement, HiveSql/HiveScript for metadata, also SparkSubmit/SparkPython/SparkScript/SparkSql/MapReduce/Flink), job_name (required), arguments (array), properties (map) |
| `AddComponent` | `POST /v2/{project_id}/clusters/{cluster_id}/components` | components_install_mode (array of {component, node_groups:[{name, assigned_roles}], component_user_password?, component_default_password?}) — CUSTOM clusters on MRS 3.1.2 / 3.1.2-LTS.2 or later only |
| `ListNodes` | `GET /v2/{project_id}/clusters/{cluster_id}/nodes` | node_group, limit, offset, node_name, sort_key, sort_dir, query_node_detail, query_ecs_detail, internal_ip |

Confirmed by name/URI in MRS's current API V2 overview, parameter table not independently fetched — probe before scripting:

| Operation | Purpose in a migration |
|---|---|
| `ShowSingleJob`, `ShowJobList` | Follow a DistCp/Hive job to actual completion |
| `StopJob`, `BatchDeleteJobs` | Terminate or clean up migration jobs |
| `ShowHdfsFileList` | Confirm files landed at the expected HDFS path |
| `ShowMrsVersionList`, `ShowMrsFlavors` | Version/specification metadata for target sizing |
| `ExpandCluster`, `ShrinkCluster` | Resize the target after migration (out of scope here) |

**Land the target** (`CreateCluster`) — requires EXPLICIT approval:
```bash
hcloud MRS CreateCluster --cli-region=<REGION> --project_id="<PROJECT_ID>" --cli-jsonInput=./mrs-create.json
```
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
The `components` string must reproduce the Step 3 inventory, validated in Step 4. Size `node_groups` against the measured source footprint.

**Load the data** (`CreateExecuteJob`, DistCp) — requires EXPLICIT approval:
```bash
hcloud MRS CreateExecuteJob --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --cli-jsonInput=./mrs-distcp.json
```
```json
{
  "job_name": "distcp-hdfs-load",
  "job_type": "DistCp",
  "arguments": [ "obs://<obs_bucket>/<source_path>/", "/user/<target_path>/" ],
  "properties": { "fs.obs.endpoint": "<obs_endpoint>" }
}
```

**Rebuild metadata** (`CreateExecuteJob`, HiveScript) — requires EXPLICIT approval:
```json
{
  "job_name": "hive-metadata-restore",
  "job_type": "HiveScript",
  "arguments": [ "obs://<obs_bucket>/ddl/create_tables.sql" ]
}
```

**Verify:**
```bash
hcloud MRS ListNodes --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --query_node_detail=true
hcloud MRS ShowSingleJob --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --job_execution_id="<JOB_ID>"
hcloud MRS ShowHdfsFileList --cli-region=<REGION> --project_id="<PROJECT_ID>" --cluster_id="<CLUSTER_ID>" --path="<HDFS_PATH>"
```

### OMS (service name: `OMS`)

Object Storage Migration Service — moves object data from another provider into OBS. This is the cross-provider half of the migration.

Confirmed operation (full parameter table verified):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| `CreateTask` | `POST /v2/{project_id}/tasks` | task_type (object/prefix/list/url_list), src_node (cloud_type, region, bucket, ak/sk or connection_string or json_auth_file, object_key, list_file), dst_node (region, bucket, ak, sk, save_prefix), enable_metadata_migration, enable_failed_object_recording, consistency_check, object_overwrite_mode, dst_storage_policy, bandwidth_policy, migrate_since, smn_config, task_priority |

Confirmed by name/URI in OMS's own API Reference index, parameter table not independently fetched — probe before scripting: `ListTasks`, `ShowTask`, `StartTask`, `StopTask`, `DeleteTask`, `UpdateBandwidthPolicy`, `BatchUpdateTasks`, and the migration task group and synchronization task operations.

**Migrate objects** (`CreateTask`) — requires EXPLICIT approval:
```bash
hcloud OMS CreateTask --cli-region=<REGION> --project_id="<PROJECT_ID>" --cli-jsonInput=./oms-task.json
```
```json
{
  "task_type": "prefix",
  "src_node": {
    "cloud_type": "AWS",
    "region": "<source_region>",
    "bucket": "<source_bucket>",
    "ak": "<source_ak>",
    "sk": "<source_sk>",
    "object_key": [ "" ]
  },
  "dst_node": {
    "region": "<region>",
    "bucket": "<obs_bucket>",
    "ak": "<dst_ak>",
    "sk": "<dst_sk>"
  },
  "enable_metadata_migration": true,
  "enable_failed_object_recording": true,
  "consistency_check": "size_last_modified",
  "bandwidth_policy": [ { "start": "00:00", "end": "23:59", "max_bandwidth": 50000000 } ]
}
```

Per-platform authentication: `AWS` uses `ak`/`sk`; `Azure` uses `connection_string`; `Google` uses `json_auth_file`. `object_key: [""]` migrates an entire bucket. For the pre-cutover delta pass, set `migrate_since` to the timestamp of the full copy.

**Track:**
```bash
hcloud OMS ShowTask --cli-region=<REGION> --project_id="<PROJECT_ID>" --task_id="<TASK_ID>"
```

Then read the failed-object list written into the destination bucket and re-run only those objects.

### MgC (Migration Center) — console only

Source metadata collection and post-migration consistency verification. The MgC Agent is installed on a server inside the source network and connects to Hive Metastore, HBase, Doris, ClickHouse, Delta Lake, or Hudi. MgC's big-data verification compares migrated data against the source. No confirmed hcloud operation surface exists (`GAP-MRS-MIG-102`) — drive it from the MgC console and record its output as an artifact.

# Capability gap handling

When a capability required for a migration operation is not available or not confirmed:

1. Document the gap with Gap ID and impact
2. Classify the gap: critical path (blocks the requested action) or optional
3. Evaluate alternatives:
   - Can the step be performed via hcloud CLI after a live `--help` probe? → PROBE_HELP_BEFORE_USE (preferred)
   - Can it only be done in the MRS/OMS/MgC console? → USE_MANUAL_CONSOLE_FALLBACK
   - Can it only be done on the source side? → SOURCE_SIDE_COLLECTION (read-only, outside this skill)
4. Never auto-activate a generated MCP or invent an undocumented command as a workaround
5. Never substitute a V1.1 operation for a missing V2 one on an MRS 3.x cluster
6. Never work around a missing capability by writing to the source platform
7. Update `# Known limitations` if critical gaps remain

Known capability gaps:

- **GAP-MRS-MIG-101** (critical path for cluster-level list/show/delete): `ListClusters`, `ShowClusterDetails`, and `DeleteCluster` exist in MRS's own API Reference but only under the V1.1 namespace, which MRS's documentation states MRS 3.x does not support. No V2 equivalent was found. Consequence for a migration: a target cluster created in error cannot be torn down programmatically. → USE_MANUAL_CONSOLE_FALLBACK
- **GAP-MRS-MIG-102**: MgC's big-data inventory and consistency-verification features are console- and Agent-driven; no confirmed hcloud operation surface exists. Steps 3 and 9 therefore have a manual component. → USE_MANUAL_CONSOLE_FALLBACK
- **GAP-MRS-MIG-103**: No Huawei Cloud API can read the source cluster (on-prem, EMR, HDInsight, Dataproc). The inventory that drives the entire migration must be collected on the source side. → SOURCE_SIDE_COLLECTION
- **GAP-MRS-MIG-104**: DistCp against an `hdfs://` source requires network reachability (Direct Connect or VPN) between the source network and the target VPC. This skill does not create that path and cannot verify it. → OUT_OF_SCOPE_PREREQUISITE
- **GAP-MRS-MIG-105**: HBase table migration mechanics (snapshot/export/import) run inside the cluster, not through the MRS management API. → USE_COMPONENT_TOOLING
- **GAP-MRS-MIG-106**: Every operation beyond CreateCluster/CreateExecuteJob/AddComponent/ListNodes (MRS) and CreateTask (OMS) is confirmed by name/URI only, not parameter-verified. → PROBE_HELP_BEFORE_USE
- **GAP-MRS-MIG-000**: No dedicated MCP exists for MRS or OMS; all operations via hcloud CLI. [VERIFIED_FROM_PUBLIC_API_DOCS]
- **GAP-MRS-MIG-999**: This skill has not been executed against a live hcloud CLI, a live tenant, or a real migration. [NOT_LIVE_TESTED]

# Output artifacts

- artifacts/mrs-mig-intent.json — Parsed intent (action, source platform, target parameters)
- artifacts/mrs-mig-auth-discovery.json — Authentication and hcloud version/profile check
- artifacts/mrs-mig-project-network-resolution.json — Resolved project_id, vpc_name, subnet_id, subnet_name, OBS staging bucket
- artifacts/mrs-mig-source-inventory.json — Source component list, versions, data footprint, table/partition counts
- artifacts/mrs-mig-service-capability-probe.json — MRS and OMS reachability and operation-name confirmation
- artifacts/mrs-mig-component-mapping.json — Source component → target MRS component mapping, with any unmapped components flagged
- artifacts/mrs-mig-cluster-landing.json — CreateCluster result and recorded cluster_id
- artifacts/mrs-mig-cluster-verification.json — ListNodes read-back for the landed cluster
- artifacts/mrs-mig-oms-tasks.json — OMS task IDs, parameters, and final states
- artifacts/mrs-mig-failed-objects.json — Failed-object list read back from the destination bucket
- artifacts/mrs-mig-distcp-jobs.json — DistCp job IDs and execution results
- artifacts/mrs-mig-metadata-jobs.json — Hive metadata job IDs and results, plus partition registration outcome
- artifacts/mrs-mig-verification.json — Per-dataset row count and checksum comparison
- artifacts/mrs-mig-reconciliation-report.md — Discrepancy list and cutover-readiness statement
- artifacts/mrs-mig-final-report.md — Closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| `hcloud: command not found` | KooCLI not installed or not in PATH | `hcloud version` | Install KooCLI; add `/usr/local/bin` to PATH |
| Authentication failure | hcloud profile misconfigured | `hcloud configure show --cli-profile=default` | Re-run `hcloud configure init`. Note source credentials are separate from the Huawei Cloud AK/SK |
| `CreateCluster` returns `MRS.0002` | A component name isn't supported by the target version, or a network/node field is invalid | Re-check components against Step 4 | Correct the components list or node/network parameters and retry |
| A source component has no MRS equivalent | Version mismatch or a component MRS doesn't offer | Compare Step 3 inventory to Step 4 mapping | STOP; escalate to the approval owner — do not drop it silently |
| OMS task rejected on the destination bucket | Destination OBS bucket is not in the OMS endpoint's region | Compare bucket region to `--cli-region` | Use a bucket in the same region; OMS does not migrate cross-region on the destination side |
| OMS task completes but objects are missing | Some objects failed individually | Read the failed-object list in the destination bucket | Re-run only the failed objects; never assume completion means totality |
| OMS task creation refused | Tenant hit the 1,500-tasks-per-24h limit, or 1,500 tasks are already Waiting | Count recent tasks | Wait, or consolidate into a migration task group |
| Very large bucket migrates slowly | Single task used for >3 TB or >5M objects | Check bucket size/object count | Use a migration task group for concurrent transfer |
| Transfer saturates the source network | No bandwidth policy set | Check `bandwidth_policy` in the task body | Add up to five non-overlapping periods (1 MB/s–200 MB/s) |
| DistCp job returns `state: COMPLETE` but no data in HDFS | `COMPLETE` means submitted, not finished | `ShowSingleJob` for the execution result | Poll to actual completion; read the job log for the real failure |
| Migrated Hive table exists but returns no rows | Partitions never registered after the DDL ran | Compare partition count to the Step 3 inventory | Repair the table's partition metadata before concluding data is missing |
| Credentials appear in job details or logs | AK/SK passed in `arguments` or `properties` | Review the job body | Use an agency or cluster-side credential configuration; rotate the exposed key |
| `AddComponent` fails | Cluster isn't CUSTOM, or is earlier than MRS 3.1.2 / 3.1.2-LTS.2 | Check cluster_type and cluster_version | Use a supported CUSTOM cluster, or include the component at CreateCluster time |
| A node stays non-`started`, or a component's `running_status` stays non-`GOOD` | Normal provisioning time, or a provisioning failure | Poll `ListNodes` with `query_node_detail=true`; check the console | Wait; escalate if status never advances. Do not start copying data |
| `hcloud MRS --help` lists a `v1.1`-style operation that misbehaves on a 3.x cluster | The documented V1.1/V2 split (`GAP-MRS-MIG-101`) | Compare the operation's URI | Use the console instead for an MRS 3.x cluster |
| Lost track of the target `cluster_id` | No confirmed V2 list-clusters operation | N/A | MRS console → Active Clusters → Dashboard, or the original CreateCluster response |
| Write operation rejected (403) | Tenant lacks the specific MRS or OMS permission | Error message from the call | Request the specific permission from an administrator |

# Failure handling

- Authentication failure: verify hcloud config, region, IAM permissions. Do not retry with different credentials without operator confirmation.
- Networking/project/staging-bucket prerequisites not resolved: STOP; this skill does not create VPCs, subnets, buckets, or interconnects.
- Source inventory incomplete or unverified: STOP before Step 5. Landing a cluster on a guessed inventory produces a failed cutover.
- A source component with no target equivalent: STOP; escalate. Never silently drop a component.
- Service unreachable / operation missing: cross-check `# Per-service operations` before assuming a transient error; if genuinely missing, use the console fallback, never an invented command, and never a V1.1 substitute.
- OMS task failure: read the failed-object list, re-run only the failures. Do not restart the whole transfer blindly.
- DistCp or Hive job failure: read the job log via `ShowSingleJob`. Do not re-copy before understanding whether the cause was data, path, or permission.
- Verification failure (row counts or checksums mismatch): report the discrepancy per dataset. Do NOT declare cutover readiness. The source keeps running.
- Any write rejection for a permission reason: report; do not retry with different credentials without operator confirmation.
- Any failure at all: the source platform remains untouched and running. That is the invariant.

# Recovery procedure

1. Failure during discovery (Steps 2-4): no resource created, no data moved. Fix and retry from Step 2.
2. Failure during inventory (Step 3): nothing was created. Complete the inventory before proceeding — do not compensate by guessing.
3. Failure during landing (Step 5): if authorization-related, request the specific permission with a new approval. If a parameter/component/network error, correct and retry with fresh approval if the cluster shape changed. A cluster created in error cannot be deleted by this skill (`GAP-MRS-MIG-101`) — report the `cluster_id` for console termination.
4. Failure during bulk migration (Step 6): re-run only the failed objects from the recorded failed-object list. Use `StopTask`/`StartTask` to pause and resume rather than recreating tasks.
5. Failure during load or metadata (Steps 7-8): jobs are re-runnable. Confirm the target path state first so a retry does not duplicate or half-overwrite data.
6. Failure during verification (Step 9): do not cut over, do not delete anything, do not "fix" by re-copying blindly. Report the discrepancy and await a decision.
7. Never expand recovery into a V1.1 operation, a networking change, or any write to the source platform.

# Rollback

The rollback path for this skill is **the source platform**, which remains untouched and running throughout. Nothing in this workflow modifies, reconfigures, or decommissions the source, and cutover is a separate human decision outside this skill — so until cutover, rolling back means simply continuing to use the source.

On the target side, because `GAP-MRS-MIG-101` means no confirmed V2 delete-cluster operation exists for MRS 3.x, this skill has **no automated rollback mechanism** for a target cluster created in error. The only corrective actions within scope are:

- `AddComponent` — to correct an inventory miss on an existing CUSTOM cluster rather than rebuilding and re-copying
- OMS `StopTask` / `DeleteTask` — to halt an in-flight object migration
- MRS `StopJob` — to terminate a running DistCp or Hive job
- Reporting the `cluster_id` to the approval owner so the cluster can be terminated from the MRS console

Never invent a `DeleteCluster`-style V2 call. Never call the V1.1 `DeleteCluster` against an MRS 3.x cluster without first confirming live that it functions for that cluster generation. Do NOT delete or recreate a target cluster automatically after a downstream failure. Do NOT touch networking resources, and above all do NOT write to the source platform, as part of any rollback.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- project_id, vpc_name, subnet_id, subnet_name, cluster_id, OMS task_ids, MRS job_execution_ids, and the exact components list recorded in artifacts
- Source inventory recorded with its collection method and date, so the component mapping is auditable
- Per-dataset verification results (row counts, checksums) recorded alongside the source values they were compared against
- Failed-object lists retained, not just summarised
- Approval decisions recorded with approver identity and timestamp
- Explicit record that the source platform was accessed read-only
- Capability probe results recorded and reusable across runs against the same tenant/CLI version (re-probe if either changes, and always re-check whether `GAP-MRS-MIG-101` has been resolved)
- No secrets (AK/SK, cluster passwords, source credentials) in any artifact

# Known limitations

- No dedicated MCP exists for MRS or OMS [VERIFIED_FROM_PUBLIC_API_DOCS]
- No confirmed V2 operation exists to list clusters, show full cluster details, or delete a cluster for MRS 3.x [GAP-MRS-MIG-101] — no automated rollback/delete for a target cluster
- Source inventory and post-migration consistency verification have a manual, console-driven component via MgC [GAP-MRS-MIG-102, GAP-MRS-MIG-103]
- Direct `hdfs://` DistCp depends on a private network path this skill neither creates nor verifies [GAP-MRS-MIG-104]
- HBase table migration uses in-cluster component tooling, outside the management API [GAP-MRS-MIG-105]
- Operations beyond the five parameter-verified ones are name/URI-confirmed only [GAP-MRS-MIG-106]
- This skill's scope excludes VPC/subnet creation, network interconnects, source-side changes, cutover execution, and post-migration workload management
- No live hcloud CLI, tenant test, or real migration was performed during authoring

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- MRS (`MRS`): `CreateCluster`, `AddComponent`, `ListNodes`, and `CreateExecuteJob` each confirmed with a full request/response parameter table from their own current (V2) public API Reference page. `ListNodes` is additionally confirmed via its own API Explorer CLI Examples link (`api=ListNodes`). Critically, `CreateExecuteJob`'s documented `job_type` value range explicitly includes `DistCp`, described as a Hadoop tool for importing and exporting data between distributed file systems — so the core data-movement mechanism of this skill rests on a documented, first-party job type rather than an assumption. [VERIFIED_FROM_PUBLIC_API_DOCS]
- OMS (`OMS`): `CreateTask` confirmed with a full request/response parameter table, including the `cloud_type` value range that covers `AWS`, `Azure`, and `Google` — the three cloud sources this skill claims to support — and their differing authentication fields. The service name is confirmed via the page's own API Explorer CLI Examples link (`openapi/oms/cli?api=CreateTask`). [VERIFIED_FROM_PUBLIC_API_DOCS]
- The V1.1 cluster-management namespace, containing the only confirmed `ListClusters`/`ShowClusterDetails`/`DeleteCluster` operations, is explicitly stated by MRS's own documentation to be unsupported for MRS 3.x. This is a genuine, critical-path gap (`GAP-MRS-MIG-101`), not a documentation shortfall. [VERIFIED_FROM_PUBLIC_API_DOCS]
- The source side of the migration is a documented capability gap, not a hidden assumption: no Huawei Cloud API reads a source cluster, and MgC's collection and verification features are console/Agent-driven. Steps 3 and 9 are marked MANUAL/ASSISTED accordingly rather than being papered over with invented commands. [GAP-MRS-MIG-102, GAP-MRS-MIG-103]
- Operations beyond the five parameter-verified ones are confirmed to exist by name/URI only. [PARTIAL]
- All landing, data-migration, metadata, and add-component operations require explicit approval [INFERRED]
- No cloud-side or CLI-side live test was executed, and no real migration was performed; this authoring environment had web-search/fetch access to public documentation only [NOT_LIVE_TESTED]
- Because of the above, this skill mandates a live `hcloud MRS --help` and `hcloud OMS --help` probe before any workflow instance relies on an operation name exactly as documented here, mandates a fresh probe plus approval before using any operation beyond the confirmed set, and enforces the invariant that the source platform stays read-only and running — which is the only rollback path available given `GAP-MRS-MIG-101`
