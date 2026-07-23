# Local Container Environment to Huawei Cloud CCE Migration

Migrate containerized workloads from a local Kubernetes environment (Kind) to Huawei Cloud CCE. This guide uses Helm charts to simplify deployment and is designed to be executed with a single prompt to the AI agent.

---

## Overview

```
Kind (local)                           Huawei Cloud CCE
+------------------+                  +----------------------------+
|  3-node cluster  |                  |  CCE cluster + node pool    |
|  nginx-demo app  |  --- migrate --> |  nginx-demo on CCE          |
|  PVC local-path  |                  |  PVC csi-disk (EVS)         |
|  Docker images   |                  |  SWR images                 |
|  ingress local   |                  |  ingress via public ELB     |
+------------------+                  +----------------------------+
```

When finished, your app responds on a Huawei Cloud public IP, with the same pods, HPA, ConfigMap, and Secret you had locally.

---

## Skills Used

| Skill | Role | When |
|-------|------|------|
| [cce-local-kind-setup](./cce-local-kind-setup/SKILL.md) | Set up local K8s cluster compatible with CCE | Step 1: Source environment |
| [kind-to-cce-migration](./kind-to-cce-migration/SKILL.md) | 10-step migration from Kind to CCE | Steps 2-10: Migration |
| [huaweicloud-cce-deploy-terraform](../CCE-Deployment/huaweicloud-cce-deploy-terraform/SKILL.md) | Deploy CCE via Terraform MCP (shared) | Step 3: Destination environment |
| [huaweicloud-cce-deployment](../CCE-Deployment/huaweicloud-cce-deployment/SKILL.md) | Deploy CCE via KooCLI (shared) | Step 3: Destination environment (alternative) |

---

## Prerequisites

| Tool | Purpose | How to verify |
|------|---------|---------------|
| OpenCode | AI agent with MCP support | `opencode --version` |
| Huawei Cloud MCP | Call Huawei Cloud APIs | Configured in opencode |
| Terraform MCP | Infrastructure as Code | Configured in opencode |
| KooCLI (hcloud) | Huawei Cloud CLI | `hcloud --version` |
| Docker | Kind cluster + SWR push | `docker version` |
| kubectl | Cluster management | `kubectl version --client` |
| Helm 3.x | Application deployment | `helm version` |
| Kind | Local K8s cluster | `kind version` |

### What you need in Huawei Cloud

- **VPC and subnet** already created in the target region
- **IAM permissions** for CCE, EIP, ELB, SWR, and ECS
- **Region** chosen (e.g. `la-north-2`)
- **AZ** chosen (e.g. `la-north-2a`)

---

## Migration Workflow

### Phase 1: Source Environment (Local)

Set up a CCE-compatible local Kubernetes cluster using Kind:

```
cce-local-kind-setup
|
|-- Create 3-node Kind cluster (1 control-plane + 2 workers)
|-- Install NGINX Ingress Controller (DaemonSet, hostNetwork)
|-- Install local-path provisioner (dynamic PVCs)
|-- Deploy nginx-demo Helm chart (sample app)
+-- Verify: pods running, ingress accessible
```

**Infrastructure topology:**

```
Your machine (Docker)
|-- cce-local-control-plane  <- K8s API, port 80/443 mapped to host
|-- cce-local-worker         <- Ingress controller runs here
+-- cce-local-worker2        <- Application pods
```

### Phase 2: Destination Environment (CCE)

Deploy the CCE cluster and node pool using the shared deployment skills:

```
CCE-Deployment
|
|-- Create CCE cluster (EulerOS 2.9, containerd, ipvs)
|-- Create SSH keypair
|-- Create node pool (worker nodes)
|-- Bind EIP to API server
+-- Generate kubeconfig
```

### Phase 3: Image Migration (SWR)

Push local Docker images to Huawei Cloud SWR:

```
|-- Login to SWR (swr.<region>.myhuaweicloud.com)
|-- Tag images for SWR namespace
|-- Push images
+-- Create imagePullSecret for private namespace
```

### Phase 4: Ingress Setup (ELB)

Create ELB and install NGINX Ingress Controller on CCE:

```
|-- Create ELB with L4 + L7 flavors
|-- Get nginx-ingress add-on template from CCE
|-- Install ingress controller via Helm (SWR images)
+-- Verify: ELB listeners on 80/443
```

### Phase 5: Application Deployment

Deploy the Helm chart on CCE with adapted values:

```
|-- Adapt values: SWR images, csi-disk PVC, real hostname
|-- Helm install with CCE-specific values
+-- Verify: pods running, HPA active, ingress routing
```

### Phase 6: Validation

```
|-- Compare source vs destination (pods, services, ingress)
|-- Test HTTP response on public ELB IP
+-- Verify HPA, ConfigMap, Secret parity
```

---

## The 10 Migration Steps (kind-to-cce-migration)

| Step | Action | Key Consideration |
|------|--------|-------------------|
| 1 | Create the CCE cluster | Poll until status=Available |
| 2 | Create SSH keypair | Required for worker node access |
| 3 | Create the node pool | Validate flavor availability per AZ |
| 4 | Enable public API server access | Bind EIP to API server ELB |
| 5 | Create ELB for Ingress | Use both L4 and L7 flavors |
| 6 | Push images to SWR | CCE nodes cannot pull from Docker Hub |
| 7 | Install NGINX Ingress Controller | Use SWR images, disable admission webhooks |
| 8 | Create SWR image pull secret | Decode SWR auth before creating secret |
| 9 | Deploy the application | Adapt Helm values for CCE |
| 10 | Validate the migration | Verify pods, ingress, HPA, ConfigMap |

---

## How to Use with an AI Agent

### Single-Prompt Migration

```
"Based on the skills cce-local-kind-setup and kind-to-cce-migration,
 and using Huawei and Terraform MCPs, plan a migration plan, design the
 local containerized environment (compatible with CCE), plan the migration.
 Bound the necessary EIP (use them with traffic of 5), select node flavor
 with 4 CPU and 4GB of RAM, use always pay per use, configure by yourself
 the SSH keys. The exercise is from this local machine to the Huawei Cloud
 (la-north-2)."
```

The agent will:
1. Load the cce-local-kind-setup skill and create the local cluster
2. Deploy the sample nginx-demo app
3. Load the kind-to-cce-migration skill and execute the 10 steps
4. Use CCE-Deployment skills for cluster creation
5. Validate the migration end-to-end

### Step-by-Step (Manual)

```bash
# Phase 1: Set up local environment
~/.opencode/skills/cce-local-kind-setup/scripts/setup.sh
~/.opencode/skills/cce-local-kind-setup/scripts/deploy.sh

# Phase 2-6: Migrate to CCE (via AI agent or manually following SKILL.md)
# The kind-to-cce-migration SKILL.md documents all 10 steps with exact commands
```

---

## File Description

### cce-local-kind-setup

| File | What it does |
|------|--------------|
| `kind-cluster.yaml` | Defines the cluster: 3 nodes, K8s v1.30, ports 80/443 |
| `ingress-values.yaml` | Ingress controller config: version, no SHA digests, DaemonSet |
| `helm/nginx-demo/` | Sample app: Deployment, Service, Ingress, ConfigMap, Secret, HPA, PVC |
| `scripts/setup.sh` | Creates everything from scratch (idempotent, safe to re-run) |
| `scripts/deploy.sh` | Deploys the nginx-demo app via Helm |
| `scripts/teardown.sh` | Removes the app and the cluster (rollback/cleanup) |

### kind-to-cce-migration

| File | What it does |
|------|--------------|
| `SKILL.md` | Complete 10-step migration guide with all pitfalls solved |
| `README.md` | User-friendly migration guide with diagrams |
| `infra_migration.md` | Infrastructure migration reference |
| `scripts/migrate.sh` | Migration automation script |
| `templates/values-cce.yaml` | CCE-specific Helm values (SWR, csi-disk, real hostname) |
| `templates/ingress-values-cce.yaml` | CCE-specific ingress controller values |

---

## Results

This migration has been verified end-to-end:

- Local Kind cluster deployed successfully with nginx-demo app
- CCE cluster created in la-north-2 with node pool
- Images pushed to SWR
- NGINX Ingress Controller installed with ELB
- Application deployed on CCE with adapted values
- Migration validated: pods running, ingress accessible on public IP

---

*Version: 1.0 -- July 2026*
*Skills: cce-local-kind-setup, kind-to-cce-migration*
*Strategy: Re-deploy (local to cloud)*
*Target: Huawei Cloud CCE*
