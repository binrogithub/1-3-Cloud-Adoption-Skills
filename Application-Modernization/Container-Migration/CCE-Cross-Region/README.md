# CCE Cross-Region Migration with Velero

Migrate Huawei Cloud CCE (Cloud Container Engine) workloads between clusters across different regions using Velero backup and restore, with obsutil for PersistentVolume data migration.

---

## Overview

```
CCE Region A (source)                    CCE Region B (destination)
+-----------------------+               +-----------------------+
|  Workloads running    |               |  Empty CCE cluster    |
|  PVC data             |   --- migrate -->  |  (pre-deployed)  |
|  SWR images (region A)|               |  SWR images (region B)|
+-----------------------+               +-----------------------+
         |                                         ^
         v                                         |
  +--------------+                          +--------------+
  |  OBS bucket  |  -- Velero backup -->   |  OBS bucket  |
  |  (region A)  |  -- Velero restore -->  |  (region A)  |
  +--------------+                          +--------------+
```

The migration is divided into two main parts:
1. **Destination environment deployment** — Create an equivalent CCE cluster in the target region
2. **Migration between CCE clusters** — Velero backup on source, restore on destination, SWR reconfiguration

---

## Skills Used

| Skill | Role | When |
|-------|------|------|
| [huaweicloud-velero-cce-migration-planner](./huaweicloud-velero-cce-migration-planner/SKILL.md) | Velero backup and restore between CCE clusters | Steps 2-6: Migration |
| [pv-migration-planner](./pv-migration-planner/SKILL.md) | PVC data migration via obsutil | Step 7: PVC data (if needed) |
| [huaweicloud-cce-deploy-terraform](../CCE-Deployment/huaweicloud-cce-deploy-terraform/SKILL.md) | Deploy destination CCE via Terraform MCP | Step 1: Destination environment |
| [huaweicloud-cce-deployment](../CCE-Deployment/huaweicloud-cce-deployment/SKILL.md) | Deploy destination CCE via KooCLI | Step 1: Destination environment (alternative) |

---

## Prerequisites

| Tool | Purpose | How to verify |
|------|---------|---------------|
| OpenCode | AI agent with MCP support | `opencode --version` |
| Huawei Cloud MCP | Call Huawei Cloud APIs | Configured in opencode |
| Terraform MCP | Infrastructure as Code | Configured in opencode |
| Playwright MCP | Web UI verification (optional) | Configured in opencode |
| kubectl | Cluster management | `kubectl version --client` |
| Velero CLI | Backup and restore | `velero version` |
| obsutil | PVC data migration | `obsutil version` |
| Docker | SWR image management | `docker version` |

### What you need

- **Source CCE cluster** with at least 1 working workload (with or without PVC)
- **Source region** (e.g. `la-north-2`) and **destination region** (e.g. `na-mexico-1`)
- **OBS bucket** in the source region for Velero backup storage
- **AK/SK** with permissions for CCE, OBS, SWR, EIP, ELB
- **kubeconfig** for source cluster (`~/.kube/config`)
- **kubeconfig** for destination cluster (`~/.kube/config-destination`)

---

## Migration Workflow

### Step 1: Deploy Destination Environment

Create an equivalent CCE cluster in the destination region using the shared deployment skills:

```
CCE-Deployment
|
|-- Plan equivalent environment (same flavors, node count, K8s version)
|-- Create CCE cluster in destination region
|-- Create node pool
|-- Bind EIPs to worker nodes (required for Velero image pulls)
+-- Generate kubeconfig (~/.kube/config-destination)
```

**Key decision:** Divide the migration into two parts — deploy destination first, then migrate. This avoids deployment failures blocking the migration.

### Step 2: Install Velero on Both Clusters

```
|-- Source cluster: velero install with OBS bucket
|-- Destination cluster: velero install with same OBS bucket
|-- Verify: velero version, backupstoragelocation available
+-- Assign EIPs to destination worker nodes if Velero install fails
```

**Critical:** CCE nodes without EIPs cannot pull Velero images from Docker Hub. Always verify and assign EIPs before running `velero install`.

### Step 3: Create Velero Backup (Source)

```
|-- Switch to source kubeconfig: export KUBECONFIG=~/.kube/config
|-- velero backup create <backup-name> --include-namespaces <ns>
|-- Wait for backup completion
+-- Verify: velero backup get <backup-name> (status=Completed)
```

### Step 4: Restore on Destination

```
|-- Switch to destination kubeconfig: export KUBECONFIG=~/.kube/config-destination
|-- velero restore create --from-backup <backup-name>
|-- Wait for restore completion
+-- Verify: velero restore get (status=Completed)
```

### Step 5: SWR Reconfiguration (Cross-Region)

After restore, pods will be in `ImagePullBackOff` because SWR images from the source region are not available in the destination region:

```
|-- Login to destination SWR (swr.<dest-region>.myhuaweicloud.com)
|-- Pull image from source SWR
|-- Tag for destination SWR
|-- Push to destination SWR
|-- Update deployment to reference destination SWR image
|-- Create/update swr-secret in destination cluster
+-- Verify: pods running (not in ImagePullBackOff)
```

### Step 6: PVC Data Migration (If Needed)

If the source CCE has persistent data (PVCs), Velero's file-level backup (restic/kopia) will fail due to Huawei Cloud OBS S3 API incompatibility (virtual-hosted-style requirement). Use the pv-migration-planner skill instead:

```
pv-migration-planner
|
|-- Deploy helper pod on source CCE (with obsutil)
|-- Upload PVC data to OBS bucket
|-- Deploy helper pod on destination CCE (with obsutil)
|-- Download data from OBS to destination PVC
|-- Fix permissions and symlinks
+-- Verify data integrity
```

### Step 7: Validation

```
|-- Compare source vs destination workloads
|-- Verify all pods running
|-- Test application endpoints
|-- Verify PVC data (if applicable)
+-- Check Velero backup/restore logs for warnings
```

---

## How to Use with an AI Agent

### Deployment Phase

```
Planning prompt:
"Plan a CCE deployment over na-mexico-1 creating an equivalent environment
 in comparison with the current CCE in la-north-2. Use Huawei MCP and Terraform MCP."

Building prompt:
"Execute"
```

### Migration Phase

```
Planning prompt:
"Plan a CCE migration from la-north-2 to na-mexico-1 using Velero.
 Follow the steps of the huaweicloud-velero-cce-migration-planner skill.
 Remember to use the OBS of the first region (where the backup will be pushed
 and pulled), configure Velero in each CCE following the steps in the skill
 document. Do not forget to change the pointing SWR at the end in order to
 let the pods pull the workload image from the SWR of the second region.
 Do not forget switching between kube config and config-destination in the
 related steps. You can use the Huawei MCP, Playwright MCP and Terraform MCP
 if you need tools. The source CCE is the one related to openwebui and the
 destination is the empty CCE that you just created. The method of configuring
 Velero must be the method presented in the skill planner (with a command),
 you do not need to pull or push Velero, do not forget to verify (and bound)
 EIP to install correctly Velero."

Building prompt:
"Execute"
```

### EIP Fix (If Velero Install Fails)

```
Planning prompt:
"You need to add EIP to each worker node in order to execute the Velero
 installing command over the destination cluster."

Building prompt:
"Execute"
```

### PVC Migration (If Persistent Data Exists)

```
Planning prompt:
"Verify if the source CCE environment has persistent data in a PV.
 If you already migrated PV data from source region to destination, just verify.
 In case of not, plan a migration of PV data using obsutil skill,
 use the pv-migration-planner skill."

Building prompt:
"Execute"
```

---

## Key Decisions and Lessons Learned

1. **Divide deployment and migration** — Deploy the destination CCE first in a separate step, then migrate. Trying to do both in one step causes failures.
2. **EIPs are mandatory for Velero** — CCE nodes without EIPs cannot pull Velero images. Always assign EIPs before `velero install`.
3. **Kubeconfig switching** — Use `~/.kube/config` for source and `~/.kube/config-destination` for destination. Switch explicitly at each step.
4. **SWR must be reconfigured** — After Velero restore, images point to source region SWR. Must push to destination SWR and update deployments.
5. **PVC data needs obsutil** — Velero's restic/kopia cannot backup PVC data on Huawei Cloud OBS (virtual-hosted-style requirement). Use pv-migration-planner instead.
6. **Be specific in prompts** — Each step needs explicit instructions about which skill to use, which kubeconfig, and which region.

---

## Appendix: Why Velero File-Level Backup Fails on Huawei Cloud OBS

Huawei Cloud OBS's S3-compatible API only supports virtual-hosted-style access:

```
# Virtual-hosted-style (OBS accepts this):
https://<bucket>.obs.<region>.myhuaweicloud.com/<key>

# Path-style (OBS rejects this):
https://obs.<region>.myhuaweicloud.com/<bucket>/<key>
```

Velero's file-level backup tools (restic and kopia) use path-style S3 access, which OBS rejects with:
```
Virtual host domain is required while accessing a specific bucket.
```

The pv-migration-planner skill works around this by using obsutil (Huawei's native tool) inside helper pods to transfer data via OBS.

---

*Version: 1.0 -- July 2026*
*Skills: huaweicloud-velero-cce-migration-planner, pv-migration-planner*
*Strategy: Backup and restore (Velero + obsutil)*
*Target: Huawei Cloud CCE (cross-region)*
