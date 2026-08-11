# huawei-mrs-deploy-operations

## Purpose

Deploy and operate Huawei Cloud MapReduce Service (MRS) CUSTOM clusters using hcloud CLI (KooCLI), enabling any combination of MRS components (Hadoop, Spark, HBase, Hive, Kafka, Flink, ZooKeeper, ClickHouse, Ranger, and more) supported by the target cluster version. Uses only the current MRS API V2, since MRS's own documentation states MRS 3.x does not support the older V1.1 API — including the confirmed gap that V2 has no list/show/delete-cluster operation, documented explicitly rather than substituted with an unconfirmed V1.1 call.

This skill is deployment-only: it does not submit or manage MRS jobs, does not manage data inside HDFS/Hive/HBase, does not configure auto scaling, and does not create the VPC/subnet a cluster uses.

## Service covered

| Service | `hcloud` service name | API generation used |
|---|---|---|
| MapReduce Service (MRS) | `MRS` | API V2 only — MRS's own documentation states MRS 3.x does not support API V1.1 |

## Confirmed vs. unconfirmed operations

| Operation | Status |
|---|---|
| `CreateCluster` (`POST /v2/{project_id}/clusters`) | Full parameter table confirmed; `components` field enables any combination the target version supports |
| `AddComponent` (`POST /v2/{project_id}/clusters/{cluster_id}/components`) | Full parameter table confirmed; adds components to an existing CUSTOM cluster (MRS 3.1.2+) |
| `ListNodes` (`GET /v2/{project_id}/clusters/{cluster_id}/nodes`) | Full parameter table confirmed, AND independently confirmed via its own API Explorer CLI Examples link (`api=ListNodes`) — the strongest confirmation of any operation across this skill family |
| `ListClusters`, `ShowClusterDetails`, `DeleteCluster` | Confirmed to exist, but **only under V1.1**, which MRS's own docs state is unsupported for MRS 3.x — critical, confirmed gap |
| Rename/scale/submit-and-run, version/flavor metadata, job management, auto scaling, HDFS listing, SQL execution, agency management, data connections, IAM sync, tag management | Confirmed to exist by name/URI only — not parameter-verified; probe before use |

## Architecture

```
Operation Intent (action, region, cluster_version, components, node_groups)
                │
      Resolve project_id (hcloud IAM KeystoneListProjects)
                │
      Resolve vpc_name / subnet_id / subnet_name (hcloud VPC List...)
                │
      hcloud MRS --help   (confirm operations available)
                │
      Confirm target cluster_version's supported components (ShowMrsVersionList)
                │
        ┌───────┴────────┐
        │                │
  Read-only request   Create requested
        │                │
   (stop here)      Explicit approval
                          │
              Build nested JSON body → --cli-jsonInput
                          │
                    Execute CreateCluster
                          │
           Verify: poll ListNodes until all nodes started
                          │
              (optional) AddComponent for further services
```

## Known capability gaps

| Gap ID | Decision |
|---|---|
| GAP-MRS-OPS-101 | USE_MANUAL_CONSOLE_FALLBACK — no confirmed V2 list/show/delete-cluster operation for MRS 3.x; V1.1 equivalents exist but are explicitly unsupported for 3.x |
| GAP-MRS-OPS-102 | PROBE_HELP_BEFORE_USE — every operation beyond the 3 core ones is name/URI-only |
| GAP-MRS-OPS-000 | No dedicated MCP; hcloud CLI only |
| GAP-MRS-OPS-999 | Not live tested |

GAP-MRS-OPS-101 is this skill's most significant capability gap, directly analogous to the CodeArts Build gap in `huawei-codearts-devops-operations` and the GaussDB gap in `huawei-database-deploy-operations` — except here the gap is not "unconfirmed," it is a **confirmed absence**: MRS's own documentation states in plain language that the API generation containing these operations (V1.1) does not work for the cluster generation (3.x) this skill targets. Because of this, the skill also has **no automated rollback/delete capability** — see `SKILL.md` → "Rollback".

## Rules summary

1. MRS has one `hcloud` service name (`MRS`), confirmed directly via the `ListNodes` operation's own API Explorer CLI Examples link
2. Only the current V2 API (`/v2/{project_id}/clusters...`) is ever used for MRS 3.x; the V1.1 namespace is confirmed unsupported for 3.x and must never be called for a 3.x cluster
3. CreateCluster's and AddComponent's request bodies are nested JSON objects — always pass them via `--cli-jsonInput=<file>`, never as flattened `--param` flags
4. Any operation beyond CreateCluster/AddComponent/ListNodes must be probed live (`hcloud MRS <OPERATION> --help`) before use
5. DISCOVER BEFORE CREATE: resolve project_id/vpc_name/subnet_id/subnet_name via read operations, and validate every requested component against the target cluster_version's supported list, never assume
6. VERIFY AFTER EVERY CREATE OR ADD-COMPONENT, polling `ListNodes` until every node is `started` and every component's `running_status` is `GOOD`
7. Every create or add-component action requires explicit approval
8. This skill never creates/modifies networking resources, and never touches job or data-plane operations — only the cluster instance itself
9. Passwords are never generated or logged by this skill
10. Never include secrets in commands, examples, or logs

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI (KooCLI) | All MRS operations |
| Huawei Cloud auth (AK/SK) | API access |
| An existing VPC and subnet | Required by CreateCluster |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region/Project/Network Prerequisites → 3. Confirm MRS Reachability and Target Version/Components → 4. Run the MRS Module (Discover → Create → Verify → optional Add-Component, from `SKILL.md` → "Per-service operations") → 5. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery (auth/region/project/network) | ASSISTED | hcloud CLI read-only |
| Service reachability + version/component probe | ASSISTED | hcloud CLI read-only (`--help`, ShowMrsVersionList) |
| Cluster create | ASSISTED | hcloud CLI + approval |
| Cluster verification | ASSISTED | hcloud CLI read-only, polled (ListNodes) |
| Add component (optional) | ASSISTED | hcloud CLI + approval |
| Closure | AUTOMATED | Logic |

## hcloud / verification status

- Verified from: MRS's own official public "API V2" API Reference pages for CreateCluster, AddComponent, and ListNodes — each with a full parameter table independently fetched and read; ListNodes additionally confirmed via its own API Explorer CLI Examples link
- Live CLI test performed: **No** (authoring environment had web-search/fetch access to public documentation only)

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-ticket | No | Support escalation if a capability gap blocks a requested action and manual escalation is desired |

No dedicated MCP exists for MRS. All operations via hcloud CLI.

## Approval gates

- Any create action
- Any add-component action
- Reuse of an existing cluster instead of creating a new one
- Choice of safe_mode (SIMPLE vs KERBEROS)
- Any operation beyond CreateCluster/AddComponent/ListNodes (requires a fresh probe too)

## Outputs

- artifacts/mrs-ops-intent.json
- artifacts/mrs-ops-auth-discovery.json
- artifacts/mrs-ops-project-network-resolution.json
- artifacts/mrs-ops-service-capability-probe.json
- artifacts/mrs-ops-execution-result.json
- artifacts/mrs-ops-verification.json
- artifacts/mrs-ops-final-report.md

## Known limitations

- No confirmed V2 operation exists to list clusters, show cluster details, or delete a cluster for MRS 3.x (`GAP-MRS-OPS-101`) — this also means no automated rollback/delete capability
- Every MRS operation beyond CreateCluster/AddComponent/ListNodes is unverified at the parameter level (`GAP-MRS-OPS-102`)
- This skill's scope excludes VPC/subnet creation, job submission/management, in-cluster data operations, and scaling/auto-scaling configuration
- No live hcloud CLI or tenant test was performed during authoring

## Troubleshooting

See `SKILL.md` → "Troubleshooting" for the full table.

| Symptom | Action |
|---|---|
| An operation only appears under a `/v1.1/...` URI | Use the console; never call it against an MRS 3.x cluster |
| `CreateCluster` rejected with `MRS.0002` | Re-check components against the target cluster_version's supported list, and node/network parameters |
| Lost track of a cluster_id | Check the MRS console (`GAP-MRS-OPS-101` means no reliable programmatic list exists) |
| `AddComponent` fails | Confirm the cluster is CUSTOM and on MRS 3.1.2+ (normal) / 3.1.2-LTS.2+ (LTS) |
| A node or component stuck in a non-ready state | Poll `ListNodes`; escalate to console if it never advances |

## Maturity status

**READY_WITH_WARNINGS**

All three operations this skill relies on for its core deploy/verify/add-component flow — CreateCluster, AddComponent, and ListNodes — have a full parameter table independently confirmed from MRS's own current (V2) API Reference, with ListNodes additionally confirmed live via its API Explorer CLI Examples link. The skill's one significant, confirmed gap is that MRS 3.x has no working list/show/delete-cluster capability at the V2 level (the only such operations are V1.1, explicitly unsupported for 3.x) — this is documented plainly rather than worked around, and it means the skill has no automated rollback path. All create/add-component operations require approval.

## Evidence

| Evidence | Type |
|---|---|
| `CreateCluster`, `AddComponent`, `ListNodes` confirmed via their own current API Reference parameter tables | VERIFIED_FROM_PUBLIC_API_DOCS |
| `ListNodes` operation name additionally confirmed via its own API Explorer CLI Examples link (`api=ListNodes`) | VERIFIED_FROM_PUBLIC_API_DOCS |
| MRS 3.x does not support the V1.1 API generation (which is the only generation containing ListClusters/ShowClusterDetails/DeleteCluster) | VERIFIED_FROM_PUBLIC_API_DOCS |
| Operations beyond the 3 core ones (rename/scale/job/auto-scaling/etc.) | PARTIAL (name/URI only) |
| No dedicated MCP exists for MRS | VERIFIED_FROM_PUBLIC_API_DOCS |
| Live hcloud CLI / tenant execution | NOT_LIVE_TESTED |
