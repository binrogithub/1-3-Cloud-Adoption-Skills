# huawei-mrs-migration-operations

## Purpose

Migrate a complete big-data system — components **and** internal data — from an on-premises Hadoop distribution (Apache Hadoop, CDH, Hortonworks, FusionInsight), AWS (EMR/S3), Azure (HDInsight/Blob Storage), or Google Cloud (Dataproc/Cloud Storage) into a Huawei Cloud MapReduce Service (MRS) CUSTOM cluster, using hcloud CLI (KooCLI).

The target is always a CUSTOM cluster, because it is the only MRS cluster type that lets you enable any combination of components in a single cluster — which is what makes it possible to *reproduce a source cluster's inventory* rather than accept a fixed component set. CUSTOM is supported only by MRS 3.x.

This skill is migration-only: it never writes to the source platform, does not create the VPC/subnet or the network interconnect a migration may need, does not execute cutover, and does not manage the workload afterwards. It ends at an evidence-backed statement of cutover readiness.

## The three planes of the migration

| Plane | Mechanism | What moves |
|---|---|---|
| Bulk object | OMS `CreateTask` | S3 / Blob Storage / Cloud Storage → OBS |
| Cluster data | MRS `CreateExecuteJob` with `job_type: DistCp` | OBS (or a reachable `hdfs://` source) → target HDFS |
| Metadata | MRS `CreateExecuteJob` with `job_type: HiveSql` / `HiveScript` | Table definitions, so the copied files become queryable |

## Services covered

| Service | `hcloud` service name | API generation used |
|---|---|---|
| MapReduce Service (MRS) | `MRS` | API V2 only — MRS's own documentation states MRS 3.x does not support API V1.1 |
| Object Storage Migration Service (OMS) | `OMS` | APIs V2 (`/v2/{project_id}/tasks`) |
| Migration Center (MgC) | — (console + Agent) | Source inventory and consistency verification; no confirmed hcloud surface |

## Source platform support

| Source | Compute inventoried | OMS `cloud_type` | Authentication field |
|---|---|---|---|
| On-premises | Apache Hadoop, CDH, Hortonworks, FusionInsight | n/a (private-network DistCp, or `URLSource`) | — |
| AWS | EMR | `AWS` | `ak` / `sk` |
| Azure | HDInsight | `Azure` | `connection_string` |
| Google Cloud | Dataproc | `Google` | `json_auth_file` |

## Confirmed vs. unconfirmed operations

| Operation | Status |
|---|---|
| `MRS CreateCluster` (`POST /v2/{project_id}/clusters`) | Full parameter table confirmed; `components` reproduces the source inventory on the target |
| `MRS CreateExecuteJob` (`POST /v2/{project_id}/clusters/{cluster_id}/job-executions`) | Full parameter table confirmed; `job_type` value range **explicitly includes `DistCp`**, documented as a Hadoop tool for importing/exporting between distributed file systems — the core data-movement mechanism of this skill |
| `MRS AddComponent` (`POST /v2/{project_id}/clusters/{cluster_id}/components`) | Full parameter table confirmed; the cheap remedy for an inventory miss (MRS 3.1.2+) |
| `MRS ListNodes` (`GET /v2/{project_id}/clusters/{cluster_id}/nodes`) | Full parameter table confirmed, AND independently confirmed via its own API Explorer CLI Examples link (`api=ListNodes`) |
| `OMS CreateTask` (`POST /v2/{project_id}/tasks`) | Full parameter table confirmed, including the `cloud_type` value range covering AWS, Azure, and Google; service name confirmed via `openapi/oms/cli?api=CreateTask` |
| `MRS ShowSingleJob`, `ShowJobList`, `StopJob`, `ShowHdfsFileList`, `ShowMrsVersionList` | Confirmed by name/URI only — probe before use |
| `OMS ListTasks`, `ShowTask`, `StartTask`, `StopTask`, `DeleteTask`, `UpdateBandwidthPolicy` | Confirmed by name/URI in OMS's own API Reference index — probe before use |
| `MRS ListClusters`, `ShowClusterDetails`, `DeleteCluster` | Confirmed to exist, but **only under V1.1**, which MRS's own docs state is unsupported for MRS 3.x — critical, confirmed gap |
| MgC inventory + big-data consistency verification | Console/Agent-driven; no confirmed hcloud operation surface |

## Architecture

```
Source system (on-prem / EMR / HDInsight / Dataproc)
                │  (read-only)
      Inventory: components, versions, TB, table + partition counts
                │            [MgC Agent — console-driven]
                ▼
      Resolve project_id / VPC / subnet / OBS staging bucket
                │
      hcloud MRS --help   +   hcloud OMS --help
                │
      Map every source component → target MRS version's supported set
                │
        ┌───────┴────────┐
        │                │
   unmapped found    all mapped
        │                │
   STOP + escalate   Explicit approval
                          │
              MRS CreateCluster (CUSTOM) ──► ListNodes until GOOD
                          │
              OMS CreateTask ──► ShowTask ──► read failed-object list
                          │
              MRS CreateExecuteJob (DistCp) ──► ShowSingleJob to completion
                          │
              MRS CreateExecuteJob (HiveScript) ──► register partitions
                          │
              ShowHdfsFileList  +  row counts / checksums (MgC)
                          │
                 Cutover readiness  →  human decision (outside this skill)

   Throughout: the source platform stays untouched and running.
```

## Known capability gaps

| Gap ID | Decision |
|---|---|
| GAP-MRS-MIG-101 | USE_MANUAL_CONSOLE_FALLBACK — no confirmed V2 list/show/delete-cluster for MRS 3.x; a target cluster created in error cannot be torn down programmatically |
| GAP-MRS-MIG-102 | USE_MANUAL_CONSOLE_FALLBACK — MgC inventory and verification are console/Agent-driven |
| GAP-MRS-MIG-103 | SOURCE_SIDE_COLLECTION — no Huawei Cloud API reads a source cluster |
| GAP-MRS-MIG-104 | OUT_OF_SCOPE_PREREQUISITE — direct `hdfs://` DistCp needs a Direct Connect/VPN path this skill neither creates nor verifies |
| GAP-MRS-MIG-105 | USE_COMPONENT_TOOLING — HBase snapshot/export runs inside the cluster |
| GAP-MRS-MIG-106 | PROBE_HELP_BEFORE_USE — everything beyond the five parameter-verified operations is name/URI-only |
| GAP-MRS-MIG-000 | No dedicated MCP; hcloud CLI only |
| GAP-MRS-MIG-999 | Not live tested; no real migration performed |

`GAP-MRS-MIG-101` carries over from `huawei-mrs-deploy-operations` and matters more here: in a deployment it means you cannot delete a cluster, but in a migration it means the target has **no automated rollback at all**. That is why this skill's actual rollback path is the source platform, and why keeping the source read-only and running is treated as an invariant rather than a recommendation.

`GAP-MRS-MIG-103` is the gap most likely to be papered over by a careless implementation. There is no API that will tell you what your source cluster runs. The inventory is a required human/Agent-collected input, and every downstream decision — component list, node sizing, verification targets — depends on it.

## Rules summary

1. MRS and OMS each have one `hcloud` service name (`MRS`, `OMS`), both confirmed via their own API Explorer CLI Examples links
2. Only the current MRS V2 API is ever used for MRS 3.x; the V1.1 namespace is confirmed unsupported for 3.x and must never be called for a 3.x cluster
3. CreateCluster, CreateTask, and CreateExecuteJob all take nested JSON bodies — always pass them via `--cli-jsonInput=<file>`, never as flattened `--param` flags
4. Any operation beyond the five parameter-verified ones must be probed live before use
5. INVENTORY BEFORE LAND: the target component list is derived from the source, never guessed. An unmappable component is a STOP, not a silent drop
6. VERIFY AFTER EVERY WRITE: ListNodes after CreateCluster (before any data moves), ShowTask plus the failed-object list after CreateTask, ShowSingleJob to completion after every job
7. `state: COMPLETE` from CreateExecuteJob means *submitted*, not finished — never report a step done on a submission response
8. FILE PRESENCE IS NOT EQUIVALENCE: row counts and checksums per table are required before cutover readiness
9. The source platform is read-only and stays running — it is the only rollback path
10. Never put credentials in job `arguments` or `properties`; sensitive parameters surface in job details and logs
11. Every landing, data-migration, metadata, and add-component action requires explicit approval
12. Cutover is a separate human decision; this skill stops at verified readiness

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI (KooCLI) | All MRS and OMS operations |
| Huawei Cloud auth (AK/SK) | API access |
| Source-platform read-only credentials | Inventory and object-storage read |
| An existing VPC and subnet | Required by CreateCluster |
| An OBS bucket in the target region | Staging landing zone; must match the OMS endpoint region |
| MgC Agent + console | Source inventory and consistency verification (manual component) |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region/Project/Network → 3. **Inventory the Source System** → 4. Confirm Reachability and Map Components → 5. Land the Target Cluster → 6. Migrate Bulk Object Data (OMS) → 7. Load Data into the Cluster (DistCp) → 8. Rebuild Metadata (Hive) → 9. Verify and Reconcile → 10. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery (auth/region/project/network) | ASSISTED | hcloud CLI read-only |
| Source inventory | MANUAL / ASSISTED | MgC Agent + console, or source-side tooling |
| Component mapping + reachability probe | ASSISTED | hcloud CLI read-only (`--help`, ShowMrsVersionList) |
| Cluster landing | ASSISTED | hcloud CLI + approval |
| Landing verification | ASSISTED | hcloud CLI read-only, polled (ListNodes) |
| Bulk object migration | ASSISTED | hcloud CLI + approval (OMS CreateTask/ShowTask) |
| Cluster data load | ASSISTED | hcloud CLI + approval (CreateExecuteJob, DistCp) |
| Metadata rebuild | ASSISTED | hcloud CLI + approval (CreateExecuteJob, HiveScript) |
| Verification and reconciliation | ASSISTED / MANUAL | ShowHdfsFileList + MgC consistency verification |
| Closure | AUTOMATED | Logic |

## hcloud / verification status

- Verified from: MRS's own official public "API V2" API Reference pages for CreateCluster, AddComponent, ListNodes, and CreateExecuteJob, and OMS's "APIs V2" page for CreateTask — each with a full parameter table independently fetched and read. ListNodes and CreateTask additionally confirmed via their own API Explorer CLI Examples links
- Live CLI test performed: **No** (authoring environment had web-search/fetch access to public documentation only)
- Real migration performed: **No**

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-ticket | No | Support escalation if a capability gap blocks a requested action |

No dedicated MCP exists for MRS or OMS. All operations via hcloud CLI.

## Approval gates

- Landing the target cluster
- Any OMS bulk data migration
- Any DistCp data load
- Any Hive metadata rebuild
- Any add-component action
- Reuse of an existing target cluster instead of creating a new one
- Choice of `safe_mode` (SIMPLE vs KERBEROS) — it determines who can use the platform after migration
- Declaring cutover readiness
- Any operation beyond the confirmed set (requires a fresh probe too)

## Outputs

- artifacts/mrs-mig-intent.json
- artifacts/mrs-mig-auth-discovery.json
- artifacts/mrs-mig-project-network-resolution.json
- artifacts/mrs-mig-source-inventory.json
- artifacts/mrs-mig-service-capability-probe.json
- artifacts/mrs-mig-component-mapping.json
- artifacts/mrs-mig-cluster-landing.json
- artifacts/mrs-mig-cluster-verification.json
- artifacts/mrs-mig-oms-tasks.json
- artifacts/mrs-mig-failed-objects.json
- artifacts/mrs-mig-distcp-jobs.json
- artifacts/mrs-mig-metadata-jobs.json
- artifacts/mrs-mig-verification.json
- artifacts/mrs-mig-reconciliation-report.md
- artifacts/mrs-mig-final-report.md

## Known limitations

- No confirmed V2 operation exists to list clusters, show cluster details, or delete a cluster for MRS 3.x (`GAP-MRS-MIG-101`) — no automated rollback for the target
- Source inventory and consistency verification have a manual, console-driven component (`GAP-MRS-MIG-102`, `GAP-MRS-MIG-103`)
- Direct `hdfs://` DistCp depends on a network path outside this skill's scope (`GAP-MRS-MIG-104`)
- HBase migration uses in-cluster component tooling (`GAP-MRS-MIG-105`)
- Operations beyond the five parameter-verified ones are name/URI-confirmed only (`GAP-MRS-MIG-106`)
- Scope excludes VPC/subnet creation, network interconnects, source-side changes, cutover execution, and post-migration workload management
- No live hcloud CLI, tenant test, or real migration was performed during authoring

## Troubleshooting

See `SKILL.md` → "Troubleshooting" for the full table.

| Symptom | Action |
|---|---|
| A source component has no MRS equivalent | STOP and escalate; never drop it silently |
| OMS task rejected on the destination bucket | The destination OBS bucket must be in the OMS endpoint's region |
| OMS task completes but objects are missing | Read the failed-object list in the destination bucket; re-run only those |
| Bucket over 3 TB or 5M objects migrates slowly | Use a migration task group, not a single task |
| DistCp job returns `COMPLETE` but no data in HDFS | `COMPLETE` means submitted; poll `ShowSingleJob` for the real result |
| Migrated Hive table exists but returns no rows | Partitions were never registered after the DDL ran |
| An operation only appears under a `/v1.1/...` URI | Use the console; never call it against an MRS 3.x cluster |
| Lost track of the target `cluster_id` | MRS console (`GAP-MRS-MIG-101` means no reliable programmatic list) |
| Credentials visible in job details | Rotate the key; use an agency or cluster-side credential configuration |

## Maturity status

**READY_WITH_WARNINGS**

The five operations this skill relies on for its core land → migrate → load → rebuild → verify flow — MRS `CreateCluster`, `CreateExecuteJob`, `AddComponent`, `ListNodes`, and OMS `CreateTask` — each have a full parameter table independently confirmed from their own current API Reference pages, with `ListNodes` and `CreateTask` additionally confirmed via live API Explorer CLI Examples links. Crucially, the data-movement mechanism is not an assumption: `DistCp` is a documented `job_type` value of `CreateExecuteJob`, and `AWS`, `Azure`, and `Google` are documented `cloud_type` values of `CreateTask`.

The skill's significant gaps are documented plainly rather than worked around: MRS 3.x has no working list/show/delete-cluster capability at V2, and no Huawei Cloud API can read the source cluster. The first means the target has no automated rollback; the second means the inventory driving the whole migration is a human/Agent-collected input. Both are why the source platform is kept read-only and running as an enforced invariant, and why cutover remains a human decision outside this skill.

## Evidence

| Evidence | Type |
|---|---|
| `CreateCluster`, `AddComponent`, `ListNodes`, `CreateExecuteJob` confirmed via their own current MRS V2 API Reference parameter tables | VERIFIED_FROM_PUBLIC_API_DOCS |
| `CreateExecuteJob`'s `job_type` value range explicitly includes `DistCp`, documented as a Hadoop tool for importing/exporting between distributed file systems | VERIFIED_FROM_PUBLIC_API_DOCS |
| `OMS CreateTask` confirmed via its own APIs V2 parameter table, including `cloud_type` values `AWS`, `Azure`, `Google` and their differing authentication fields | VERIFIED_FROM_PUBLIC_API_DOCS |
| `ListNodes` and `CreateTask` operation names additionally confirmed via their own API Explorer CLI Examples links | VERIFIED_FROM_PUBLIC_API_DOCS |
| MRS 3.x does not support the V1.1 API generation (the only generation containing ListClusters/ShowClusterDetails/DeleteCluster) | VERIFIED_FROM_PUBLIC_API_DOCS |
| OMS constraints: 1,500 tasks/24h, task group recommended above 3 TB or 5M objects, destination bucket must match the endpoint region, failed-object recording | VERIFIED_FROM_PUBLIC_API_DOCS |
| MgC big-data migration and consistency verification for Hive, HBase, Doris, ClickHouse, Delta Lake, Hudi | VERIFIED_FROM_PUBLIC_API_DOCS |
| Operations beyond the five parameter-verified ones | PARTIAL (name/URI only) |
| No dedicated MCP exists for MRS or OMS | VERIFIED_FROM_PUBLIC_API_DOCS |
| Live hcloud CLI / tenant execution / real migration | NOT_LIVE_TESTED |
