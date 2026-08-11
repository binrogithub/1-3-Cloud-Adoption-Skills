# MRS Deployment

Deploy and operate Huawei Cloud MapReduce Service (MRS) CUSTOM clusters using hcloud CLI (KooCLI), enabling any combination of MRS components (Hadoop, Spark, HBase, Hive, Kafka, Flink, ZooKeeper, ClickHouse, Ranger, and more) supported by the target cluster version.

---

## Overview

```
Operation Intent (action, region, cluster_version, components, node_groups)
                |
      Resolve project_id (IAM KeystoneListProjects)
                |
      Validate inputs (region, version, components, flavors)
                |
      Create cluster (MRS CreateCluster V2)
                |
      Add components (MRS AddComponent V2, if needed)
                |
      List nodes (MRS ListNodes V2)
```

This scenario covers deployment-only operations: creating CUSTOM clusters with any component combination, adding components to existing clusters, and listing cluster nodes. It does not submit or manage MRS jobs, manage data inside HDFS/Hive/HBase, configure auto scaling, or create the VPC/subnet.

---

## Skills Used

| Skill | Role | When |
|-------|------|------|
| [huawei-mrs-deploy-operations](./huawei-mrs-deploy-operations/SKILL.md) | Deploy and operate MRS CUSTOM clusters | All steps |

---

## Prerequisites

| Tool | Purpose | How to verify |
|------|---------|---------------|
| OpenCode | AI agent with MCP support | `opencode --version` |
| Huawei Cloud MCP | Call Huawei Cloud APIs | Configured in opencode |
| hcloud CLI (KooCLI) | Direct API calls | `hcloud --version` |

### What you need

- **Huawei Cloud account** with MRS enabled
- **AK/SK** with permissions for MRS and IAM
- **VPC and subnet** pre-created in the target region
- **Region** where MRS is available (e.g. `cn-north-4`, `la-north-2`)
- **Cluster version** (e.g. MRS 3.x) and desired components

---

## Workflow

1. Resolve project ID (`IAM KeystoneListProjects`)
2. Validate cluster parameters (region, version, components, node flavors)
3. Create CUSTOM cluster (`MRS CreateCluster` V2)
4. Add components if needed (`MRS AddComponent` V2, MRS 3.1.2+)
5. List cluster nodes (`MRS ListNodes` V2)

---

## Important Notes

- Uses **MRS API V2 only** — MRS's own documentation states MRS 3.x does not support the older V1.1 API
- `ListClusters`, `ShowClusterDetails`, and `DeleteCluster` exist only under V1.1, which is unsupported for MRS 3.x — this is a confirmed gap, documented explicitly in the skill
- This skill is **deployment-only**: no job submission, no data management, no auto scaling

---

## Internal Documentation

| Document | Description |
|----------|-------------|
| [Deploying_MRS_Custom_Clusters_with_KooCLI.docx](./huawei-mrs-deploy-operations/assets/Deploying_MRS_Custom_Clusters_with_KooCLI.docx) | Word guide for MRS cluster deployment |
