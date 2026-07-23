# CCE-Compatible Local Kubernetes Cluster

A local Kubernetes environment that replicates Huawei Cloud CCE topology,
designed for local development and as a cloud migration exercise.

## What it is

A 3-node Kubernetes cluster running on your machine with Docker,
using Kind (Kubernetes in Docker). It includes everything you need to
develop and test applications that you'll later migrate to CCE:

- **Kind cluster** (1 control-plane + 2 workers) — same API as CCE
- **NGINX Ingress Controller** — same ingress type used by CCE
- **local-path provisioner** — dynamic volumes (local equivalent of EVS)
- **Helm chart nginx-demo** — sample app with all common K8s resources

## Quick Start

```bash
# 1. Create the cluster + ingress + provisioner
~/.opencode/skills/cce-local-kind-setup/scripts/setup.sh

# 2. Deploy the sample app
~/.opencode/skills/cce-local-kind-setup/scripts/deploy.sh

# 3. Test
kubectl port-forward svc/nginx-demo 8080:80
curl http://localhost:8080

# 4. When done
~/.opencode/skills/cce-local-kind-setup/scripts/teardown.sh
```

## Topology

```
Your machine (Docker)
├── cce-local-control-plane  ← K8s API, port 80/443 mapped to host
├── cce-local-worker         ← Ingress controller runs here
└── cce-local-worker2        ← Application pods
```

## Files

| File | What it does |
|------|--------------|
| `kind-cluster.yaml` | Defines the cluster: 3 nodes, K8s v1.30, ports 80/443 |
| `ingress-values.yaml` | Ingress controller config: version, no SHA digests, DaemonSet |
| `helm/nginx-demo/` | Sample app: Deployment, Service, Ingress, ConfigMap, Secret, HPA, PVC |
| `scripts/setup.sh` | Creates everything from scratch (idempotent, safe to re-run) |
| `scripts/deploy.sh` | Deploys the nginx-demo app via Helm |
| `scripts/teardown.sh` | Removes the app and the cluster |

## How the setup works

The setup process has 5 steps, and one of them is critical
because it's where most people get stuck:

### The problem with Ingress images

The Ingress Controller uses images from `registry.k8s.io`, which is
**extremely slow** to download from inside Kind nodes
(5-10+ minutes per image). Additionally, the official manifests include
hardcoded SHA digests that don't match the images you have.

**The solution that works:**

1. Download the images with Docker (which is fast)
2. Copy them into each Kind node with `docker save | ctr import`
3. Install the Ingress Controller with Helm, **without SHA digests**
   (`digest: ""`), so containerd finds images by tag

This avoids the common problems:
- `kind load docker-image` → fails with digest error
- `kubectl apply -f <manifest URL>` → uses SHA that don't match
- Waiting 10+ minutes for `registry.k8s.io` to respond

### Why Helm instead of raw manifests

Helm allows you to:
- Reference images by tag (no hardcoded SHA)
- Parameterize everything so migrating to CCE only requires changing `values.yaml`
- Manage lifecycle (`helm upgrade`, `helm uninstall`)

### Why the Ingress runs on a worker, not the control-plane

The control-plane has a `NoSchedule` taint that prevents normal pods
from being scheduled there. The Ingress DaemonSet has no tolerations
for that taint, so we label a worker with `ingress-ready=true` instead.

## The nginx-demo app

A Helm chart that demonstrates all common resources you'd use in CCE:

| Resource | What it demonstrates |
|----------|---------------------|
| Deployment | Replicas, probes, resource limits, volumeMounts |
| Service | ClusterIP (internal) |
| Ingress | HTTP routing with NGINX |
| ConfigMap | Injected configuration (custom HTML) |
| Secret | Credentials (API key in base64) |
| HPA | CPU-based autoscaling (2-5 replicas) |
| PVC | Persistent volume with configurable StorageClass |

## Migration to CCE

When you want to move this to Huawei Cloud, you only need to change
`values.yaml`:

| Component | Local | CCE | Change |
|-----------|-------|-----|--------|
| Images | Docker Hub | SWR | `docker tag` + `docker push` to SWR |
| Ingress | NGINX Ingress | CCE Ingress (ELB) | Automatic with annotation |
| PVC StorageClass | `local-path` | `csi-disk` | Change in values |
| PVC size | 1Gi | 10Gi (EVS minimum) | Change in values |
| HPA | `autoscaling/v2` | Same | No change |
| ConfigMap/Secret | Same | Same | No change |

Example `values-cce.yaml`:

```yaml
image:
  repository: swr.la-north-2.myhuaweicloud.com/my-org/nginx
persistence:
  storageClass: csi-disk
  size: 10Gi
```

## Troubleshooting (real issues encountered)

| Symptom | Cause | Solution |
|---------|-------|----------|
| Ingress pods in `ContainerCreating` forever | `registry.k8s.io` very slow | Pre-load images with Docker + `docker save \| ctr import` |
| `ctr: content digest ... not found` | Using `kind load docker-image` | Use `docker save \| docker exec -i ctr import -` |
| Ingress DaemonSet with 0 pods | Missing `ingress-ready=true` label | `kubectl label nodes cce-local-worker ingress-ready=true` |
| Helm fails with "invalid ownership metadata" | Orphaned resources from previous install | `helm delete` before reinstalling |
| Namespace stuck in `Terminating` | Finalizers blocking deletion | Force-delete pods + patch finalizers |
| `--set ingress-ready=true` fails | Helm parses `true` as boolean | Use values file with `"true"` (string) |

## Prerequisites

- Docker 20.x+ (running)
- Kind 0.27+
- kubectl 1.28+
- Helm 3.14+
- Minimum: 4 GB RAM, 2 CPUs, 20 GB free disk
