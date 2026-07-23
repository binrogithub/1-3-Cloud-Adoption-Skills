# Container Migration to Huawei Cloud CCE

Complete toolkit for migrating containerized workloads to and between Huawei Cloud CCE (Cloud Container Engine) using AI agents. Covers two migration scenarios with ready-to-use skills for OpenCode, Hermes, Claude Code, and Codex.

---

## What These Skills Do and Why They Are Useful

### The Problem

Migrating Kubernetes workloads to or between Huawei Cloud CCE involves many error-prone steps:

- CCE has specific requirements (EulerOS, ENI subnets, ELB flavors) that differ from standard K8s
- Container images must be pushed to SWR (Docker Hub and registry.k8s.io time out on CCE nodes)
- Ingress Controller needs an ELB with both L4 and L7 flavors
- Cross-region migrations require Velero + OBS + SWR reconfiguration
- PersistentVolume data cannot be migrated with Velero alone (OBS S3 API incompatibility)

### The Solution: 6 Skills Covering 2 Migration Scenarios

```
  SCENARIO 1: Local to CCE                    SCENARIO 2: CCE Cross-Region

  Kind (local)                                CCE Region A (source)
    |                                           |
    v                                           v
  cce-local-kind-setup                        huaweicloud-velero-cce-migration-planner
  (set up compatible local env)              (Velero backup + restore)
    |                                           |
    v                                           v
  kind-to-cce-migration                       pv-migration-planner
  (10-step migration to CCE)                 (PVC data via obsutil)
    |                                           |
    +---> CCE-Deployment (shared) <---+         +---> CCE-Deployment (shared) <---+
          huaweicloud-cce-deploy-terraform            huaweicloud-cce-deploy-terraform
          huaweicloud-cce-deployment                  huaweicloud-cce-deployment
```

#### Shared: CCE Deployment Skills

Both scenarios need to deploy CCE clusters. Two options are provided:

- **huaweicloud-cce-deploy-terraform** — Declarative deployment via Terraform MCP (handles ENI subnets, password salting, and other API quirks automatically)
- **huaweicloud-cce-deployment** — Imperative deployment via KooCLI + Huawei Cloud MCP (discovery-first approach, no Terraform required)

---

## What This Package Includes

```
Container-Migration/
|
|-- Local-to-CCE/                            Scenario 1: Local Kind to CCE
|   |-- cce-local-kind-setup/                Skill: local K8s cluster (Kind) compatible with CCE
|   |   |-- SKILL.md
|   |   |-- README.md
|   |   |-- kind-cluster.yaml                Kind cluster definition (3 nodes, K8s v1.30)
|   |   |-- ingress-values.yaml              NGINX Ingress Controller config
|   |   |-- helm/nginx-demo/                 Sample app (Deployment, Service, Ingress, ConfigMap, Secret, HPA, PVC)
|   |   +-- scripts/                         setup.sh, deploy.sh, teardown.sh
|   |-- kind-to-cce-migration/               Skill: 10-step migration from Kind to CCE
|   |   |-- SKILL.md
|   |   |-- README.md
|   |   |-- infra_migration.md               Infrastructure migration reference
|   |   |-- scripts/migrate.sh               Migration automation script
|   |   +-- templates/                       CCE-specific Helm values (values-cce.yaml, ingress-values-cce.yaml)
|   +-- README.md                            Scenario 1 guide
|
|-- CCE-Cross-Region/                        Scenario 2: CCE to CCE across regions
|   |-- huaweicloud-velero-cce-migration-planner/  Skill: Velero-based CCE migration
|   |   +-- SKILL.md
|   |-- pv-migration-planner/               Skill: PVC data migration via obsutil
|   |   +-- SKILL.md
|   +-- README.md                            Scenario 2 guide
|
|-- CCE-Deployment/                          Shared: CCE cluster deployment
|   |-- huaweicloud-cce-deploy-terraform/    Skill: CCE deployment via Terraform MCP
|   |   +-- SKILL.md
|   |-- huaweicloud-cce-deployment/          Skill: CCE deployment via KooCLI
|   |   +-- SKILL.md
|   +-- README.md                            Deployment skills guide
|
+-- README.md                                (this file)
```

---

## Installation

The skills are markdown documents (SKILL.md) with YAML frontmatter + instructions. Each AI agent loads them from its own path. The scripts accompany each skill in its directory.

### Option A: OpenCode

```bash
# Copy all skills to the OpenCode skills directory
cp -r Local-to-CCE/cce-local-kind-setup ~/.opencode/skills/
cp -r Local-to-CCE/kind-to-cce-migration ~/.opencode/skills/
cp -r CCE-Cross-Region/huaweicloud-velero-cce-migration-planner ~/.opencode/skills/
cp -r CCE-Cross-Region/pv-migration-planner ~/.opencode/skills/
cp -r CCE-Deployment/huaweicloud-cce-deploy-terraform ~/.opencode/skills/
cp -r CCE-Deployment/huaweicloud-cce-deployment ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r Local-to-CCE/cce-local-kind-setup ~/.hermes/skills/infrastructure/
cp -r Local-to-CCE/kind-to-cce-migration ~/.hermes/skills/infrastructure/
cp -r CCE-Cross-Region/huaweicloud-velero-cce-migration-planner ~/.hermes/skills/infrastructure/
cp -r CCE-Cross-Region/pv-migration-planner ~/.hermes/skills/infrastructure/
cp -r CCE-Deployment/huaweicloud-cce-deploy-terraform ~/.hermes/skills/infrastructure/
cp -r CCE-Deployment/huaweicloud-cce-deployment ~/.hermes/skills/infrastructure/
```

### Option C: Claude Code

```bash
mkdir -p ~/.claude/skills
cp Local-to-CCE/cce-local-kind-setup/SKILL.md ~/.claude/skills/cce-local-kind-setup.md
cp Local-to-CCE/kind-to-cce-migration/SKILL.md ~/.claude/skills/kind-to-cce-migration.md
cp CCE-Cross-Region/huaweicloud-velero-cce-migration-planner/SKILL.md ~/.claude/skills/huaweicloud-velero-cce-migration-planner.md
cp CCE-Cross-Region/pv-migration-planner/SKILL.md ~/.claude/skills/pv-migration-planner.md
cp CCE-Deployment/huaweicloud-cce-deploy-terraform/SKILL.md ~/.claude/skills/huaweicloud-cce-deploy-terraform.md
cp CCE-Deployment/huaweicloud-cce-deployment/SKILL.md ~/.claude/skills/huaweicloud-cce-deployment.md
```

### Option D: OpenAI Codex

```bash
# Codex reads AGENTS.md and executes commands from the working directory
cp -r Container-Migration /path/to/project/
# Codex will read AGENTS.md and can execute the scripts directly
```

---

## How to Use the Skills with an AI Agent

### Scenario 1: Local to CCE Migration

```
"Based on the skills cce-local-kind-setup and kind-to-cce-migration,
 plan a migration from this local machine to Huawei Cloud (la-north-2).
 Set up a CCE-compatible local environment, then migrate to CCE."
```

The agent will:
1. Set up a local Kind cluster (cce-local-kind-setup)
2. Deploy the sample app locally
3. Create CCE cluster + node pool (CCE-Deployment)
4. Push images to SWR
5. Install NGINX Ingress Controller with ELB
6. Deploy the app on CCE with adapted values
7. Validate the migration

See [Local-to-CCE/README.md](./Local-to-CCE/README.md) for the full guide.

### Scenario 2: CCE Cross-Region Migration

```
"Plan a CCE migration from la-north-2 to na-mexico-1 using Velero.
 Follow the huaweicloud-velero-cce-migration-planner skill.
 Deploy the destination CCE first, then migrate using Velero.
 Do not forget to reconfigure SWR for the destination region."
```

The agent will:
1. Deploy destination CCE cluster (CCE-Deployment)
2. Install Velero on both source and destination clusters
3. Create a Velero backup on the source
4. Restore on the destination
5. Reconfigure SWR for the destination region
6. Migrate PVC data if needed (pv-migration-planner)
7. Validate the migration

See [CCE-Cross-Region/README.md](./CCE-Cross-Region/README.md) for the full guide.

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| OpenCode / Hermes / Claude Code / Codex | AI agent with MCP support |
| Huawei Cloud MCP | Configured with AK/SK and region |
| Terraform MCP | For huaweicloud-cce-deploy-terraform skill |
| KooCLI (hcloud) | For huaweicloud-cce-deployment skill |
| Docker | For Kind cluster and SWR image push |
| kubectl | For cluster management |
| Helm 3.x | For application deployment |
| Velero CLI | For cross-region migration (Scenario 2) |
| obsutil | For PVC data migration (Scenario 2) |

---

## Common Pitfalls

1. **Docker Hub timeouts on CCE** — CCE nodes cannot reliably pull from Docker Hub or registry.k8s.io. Always push images to SWR first.
2. **Ubuntu 22.04 rejected on overlay_l2** — Use EulerOS 2.9 for CCE worker nodes.
3. **L7-only ELB cannot create TCP listeners** — Create ELB with both l4_flavor_id and l7_flavor_id for ingress.
4. **Velero PVC backup fails on OBS** — OBS requires virtual-hosted-style S3 access which restic/kopia do not support. Use pv-migration-planner (obsutil) instead.
5. **Cross-region SWR images not available** — After Velero restore, pods will be in ImagePullBackOff. Push images to destination SWR and update deployments.
6. **EIPs required for Velero** — CCE nodes without EIPs cannot pull Velero images. Assign EIPs before running `velero install`.
7. **Kubeconfig switching** — Use `~/.kube/config` for source and `~/.kube/config-destination` for destination. Switch with `export KUBECONFIG=...`.

---

*Version: 1.0 -- July 2026*
*Skills: cce-local-kind-setup, kind-to-cce-migration, huaweicloud-velero-cce-migration-planner, pv-migration-planner, huaweicloud-cce-deploy-terraform, huaweicloud-cce-deployment*
*Target: Huawei Cloud CCE (Cloud Container Engine)*
