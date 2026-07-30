---
name: cce-local-kind-setup
description: Set up a local Kubernetes cluster using Kind that is compatible with Huawei Cloud CCE for development and migration exercises. Covers prerequisites check, cluster creation, NGINX Ingress Controller installation with pre-loaded images, local-path provisioner, and CCE-compatible Helm chart deployment.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: local-k8s-cce-compatible
---

# CCE-Compatible Local Kubernetes Cluster (Kind)

Set up a local Kubernetes cluster using **Kind** (Kubernetes in Docker) that mirrors Huawei Cloud CCE topology and is ready for migration. The cluster uses standard K8s APIs identical to CCE, with NGINX Ingress Controller and dynamic PVC provisioning.

## Rules

1. **ALWAYS pre-load images into Kind nodes** — `registry.k8s.io` is extremely slow inside Kind nodes (5-10+ min per image). Pull via Docker first, then pipe into each node using `docker save | docker exec -i <node> ctr --namespace=k8s.io images import -`. Do NOT use `kind load docker-image` or `kind load image-archive` — they fail with `ctr: content digest ... not found`.
2. **NEVER use raw manifest URL for ingress-nginx** — `kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/...` hardcodes SHA digests and uses whatever version is on `main`. SHA mismatches cause containerd to re-pull from the slow registry. Instead, use **Helm install** with `digest: ""` to reference images by tag only.
3. **Label a WORKER node with `ingress-ready=true`** — The Kind-specific ingress DaemonSet requires `nodeSelector: ingress-ready=true`. Do NOT label the control-plane — it has a `NoSchedule` taint and the DaemonSet has no tolerations for it.
4. **Use a values file for Helm, not `--set`** — `--set controller.nodeSelector.ingress-ready=true` parses `true` as boolean, but nodeSelector values must be strings. Use a YAML values file with `ingress-ready: "true"` (quoted string).
5. **Clean up before reinstalling** — If a previous Helm install failed or left orphan ClusterRole/ClusterRoleBinding/ValidatingWebhookConfiguration, they block the next install with "invalid ownership metadata" errors. Run `helm delete` first. If a namespace is stuck in `Terminating`, force-delete all resources inside it and patch finalizers.
6. **Set `controller.kind=DaemonSet` and `controller.hostNetwork=true`** — For Kind clusters, a DaemonSet with hostNetwork gives the ingress controller direct access to node ports 80/443, matching CCE's ELB-based ingress behavior.
7. **Match K8s version to target CCE** — Use `kindest/node:v1.30.0` (or whatever CCE version you target). Kind images are at https://github.com/kubernetes-sigs/kind/releases — check the supported node image tags.

## Prerequisites

| Tool | Min Version | Install |
|------|-------------|---------|
| Docker | 20.x+ | https://docs.docker.com/get-docker/ |
| Kind | 0.27+ | `sudo curl -Lo /usr/local/bin/kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64 && sudo chmod +x /usr/local/bin/kind` |
| kubectl | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| Helm | 3.14+ | `curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` |

**Minimum resources:** 4 GB RAM, 2 CPUs, 20 GB disk free (for 3-node cluster).

## Workflow

### Step 1: CHECK PREREQUISITES

Verify all tools are installed and Docker daemon is running:

```bash
docker info >/dev/null 2>&1 || { echo "Docker not running"; exit 1; }
kind version || { echo "Kind not installed"; exit 1; }
kubectl version --client || { echo "kubectl not installed"; exit 1; }
helm version || { echo "Helm not installed"; exit 1; }
```

### Step 2: CREATE KIND CLUSTER

Create a multi-node cluster that mirrors CCE topology (1 control-plane + 2 workers):

```yaml
# kind-cluster.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: cce-local
nodes:
  - role: control-plane
    image: kindest/node:v1.30.0
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
  - role: worker
    image: kindest/node:v1.30.0
  - role: worker
    image: kindest/node:v1.30.0
```

```bash
kind create cluster --config kind-cluster.yaml --wait 180s
```

**Why extraPortMappings:** Maps host ports 80/443 to the control-plane, enabling Ingress access via `localhost` or `127.0.0.1`.

**Why v1.30.0:** Matches commonly available CCE cluster versions. Adjust to your target CCE version.

### Step 3: INSTALL LOCAL-PATH PROVISIONER

Required for dynamic PVC provisioning (CCE uses `csi-disk`/EVS; locally we use `local-path`):

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.28/deploy/local-path-storage.yaml
kubectl wait --namespace local-path-storage \
  --for=condition=ready pod \
  --selector=app=local-path-provisioner \
  --timeout=60s
```

Kind includes a built-in `local-path` StorageClass, but the Rancher provisioner is more reliable for dynamic provisioning.

### Step 4: INSTALL NGINX INGRESS CONTROLLER

This is the most error-prone step. Follow the exact procedure below.

#### 4.1 Pre-pull images via Docker

```bash
docker pull registry.k8s.io/ingress-nginx/controller:v1.12.1
docker pull registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9
```

#### 4.2 Load images into Kind nodes

**This is the ONLY method that works.** Do NOT use `kind load docker-image` or `kind load image-archive`:

```bash
for node in cce-local-control-plane cce-local-worker cce-local-worker2; do
  docker save registry.k8s.io/ingress-nginx/controller:v1.12.1 | \
    docker exec -i "$node" ctr --namespace=k8s.io images import -
  docker save registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9 | \
    docker exec -i "$node" ctr --namespace=k8s.io images import -
done
```

> **Critical:** Do NOT add `--all-platforms --digests` flags to `ctr images import`. Those flags cause `ctr: content digest ... not found` errors.

#### 4.3 Label worker node for ingress scheduling

```bash
kubectl label nodes cce-local-worker ingress-ready=true --overwrite
```

> **Why the worker, not control-plane:** The control-plane has a `node-role.kubernetes.io/control-plane:NoSchedule` taint. The ingress DaemonSet has no tolerations for it. The worker has no taints.

#### 4.4 Install via Helm (NOT raw manifest)

```yaml
# ingress-values.yaml
controller:
  image:
    tag: v1.12.1
    digest: ""
  admissionWebhooks:
    patch:
      image:
        tag: v1.6.9
        digest: ""
  nodeSelector:
    ingress-ready: "true"
  hostNetwork: true
  kind: DaemonSet
```

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  -f ingress-values.yaml \
  --wait --timeout 5m
```

> **Why `digest: ""` :** Without this, Helm uses the default SHA digest from the chart. If the pre-loaded image doesn't match that SHA, containerd ignores it and tries to pull from `registry.k8s.io` (which is very slow). Setting `digest: ""` forces image resolution by tag only, which matches the pre-loaded images.

> **Why `kind: DaemonSet` :** A DaemonSet ensures one ingress controller pod per eligible node, similar to how CCE's ELB distributes traffic to node ports.

> **Why `hostNetwork: true` :** Gives the controller direct access to ports 80/443 on the node, enabling traffic from `localhost` via the Kind extraPortMappings.

### Step 5: VALIDATE

```bash
kubectl get nodes
kubectl get pods -n ingress-nginx
kubectl get storageclass local-path
```

Expected:
- 3 nodes (1 control-plane + 2 workers), all `Ready`
- 1 ingress-nginx-controller pod `Running`
- StorageClass `local-path` available

## Sample Helm Chart: nginx-demo

The skill includes a complete CCE-compatible Helm chart at `helm/nginx-demo/` that demonstrates all common K8s resource types needed for CCE migration.

### Chart structure

```
helm/nginx-demo/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl      # Name/label helpers
    ├── deployment.yaml   # Deployment with probes, volumes, resource limits
    ├── service.yaml      # ClusterIP service
    ├── ingress.yaml      # Ingress with className + annotations
    ├── configmap.yaml    # Custom HTML content
    ├── secret.yaml       # Opaque secret (API key)
    ├── hpa.yaml          # HorizontalPodAutoscaler (autoscaling/v2)
    └── pvc.yaml          # PersistentVolumeClaim with configurable StorageClass
```

### Default values (local Kind)

| Key | Default | Purpose |
|-----|---------|---------|
| `replicaCount` | 2 | Matches CCE typical minimum |
| `image.repository` | `nginx` | Docker Hub image |
| `image.tag` | `1.27-alpine` | Lightweight nginx |
| `service.type` | `ClusterIP` | Standard internal service |
| `ingress.className` | `nginx` | NGINX Ingress Controller |
| `ingress.hosts[0].host` | `demo.local` | Local dev hostname |
| `persistence.enabled` | `true` | PVC for volume migration practice |
| `persistence.storageClass` | `local-path` | Kind dynamic provisioning |
| `persistence.size` | `1Gi` | Small local volume |
| `hpa.minReplicas` | 2 | Minimum pods |
| `hpa.maxReplicas` | 5 | Maximum pods |
| `hpa.targetCPUUtilizationPercentage` | 70 | Scale trigger |
| `resources.requests` | 100m CPU / 128Mi | Guaranteed resources |
| `resources.limits` | 250m CPU / 256Mi | Maximum resources |

### Deploy the chart

```bash
# From the skill directory
helm install nginx-demo ./helm/nginx-demo --namespace default --wait --timeout 180s
```

Or use the deploy script:

```bash
./scripts/deploy.sh
```

### CCE migration: values override

Create `values-cce.yaml` to adapt the chart for Huawei Cloud CCE:

```yaml
image:
  repository: swr.<region>.myhuaweicloud.com/<org>/nginx
ingress:
  className: nginx
  hosts:
    - host: demo.<your-domain>.com
      paths:
        - path: /
          pathType: Prefix
persistence:
  storageClass: csi-disk
  size: 10Gi
```

```bash
helm install nginx-demo ./helm/nginx-demo -f values-cce.yaml
```

### CCE compatibility mapping

| Component | Local (Kind) | CCE | Migration Change |
|-----------|-------------|-----|-----------------|
| Container images | Docker Hub / local | SWR registry | `docker tag` + `docker push` to SWR |
| Ingress | NGINX Ingress Controller | CCE Ingress (ELB backend) | Change `ingressClassName` / annotations if needed |
| PVC StorageClass | `local-path` | `csi-disk` (EVS) | Change `storageClassName` in values |
| PVC size | 1Gi (local) | 10Gi (EVS minimum) | Adjust `size` in values |
| HPA | `autoscaling/v2` | Same | No change |
| ConfigMap/Secret | Same | Same | No change |

### Verify deployment

```bash
kubectl get pods -l app.kubernetes.io/name=nginx-demo
kubectl get pvc
kubectl get ingress
kubectl get hpa
kubectl port-forward svc/nginx-demo 8080:80
curl http://localhost:8080
```

## Idempotent Setup Script

The scripts in this skill's `scripts/` directory are idempotent — safe to re-run:

- **`setup.sh`** — Full cluster setup (prereqs, cluster, provisioner, ingress)
- **`deploy.sh`** — Deploy the nginx-demo Helm chart
- **`teardown.sh`** — Uninstall release + delete Kind cluster

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ctr: content digest ... not found` | Using `kind load docker-image` or `kind load image-archive` | Use `docker save \| docker exec -i <node> ctr --namespace=k8s.io images import -` (no extra flags) |
| Ingress pods `ContainerCreating` forever | `registry.k8s.io` image pull extremely slow | Pre-pull via Docker + pipe into Kind nodes (Step 4.1-4.2) |
| Ingress DaemonSet `0/0` pods, no scheduling | Missing `ingress-ready=true` label on nodes | `kubectl label nodes cce-local-worker ingress-ready=true` |
| Ingress pod `Pending` with `node(s) didn't match Pod's node affinity/selector` | DaemonSet nodeSelector doesn't match any node + control-plane has `NoSchedule` taint | Label a worker node, not control-plane |
| Helm install fails: `invalid ownership metadata` | Orphan ClusterRole/CRB from previous failed install | `helm delete <release> -n <ns>` then reinstall |
| Namespace stuck `Terminating` | Finalizers blocking deletion | Force-delete all resources inside, then `kubectl patch ns <name> -p '{"metadata":{"finalizers":[]}}' --type=merge` |
| `--set controller.nodeSelector.ingress-ready=true` error | Helm parses `true` as boolean; nodeSelector requires string values | Use values file: `ingress-ready: "true"` (quoted) |
| Ingress images still pulling despite pre-load | SHA digest mismatch between pre-loaded image and Helm chart default | Set `controller.image.digest: ""` and `controller.admissionWebhooks.patch.image.digest: ""` in values |
| PVC `ProvisioningFailed` timeout | local-path provisioner not running or slow | Wait 2-3 min; if persistent, check `kubectl get pods -n local-path-storage` |

## Image Version Reference

| Component | Version | Image |
|-----------|---------|-------|
| Kind node | v1.30.0 | `kindest/node:v1.30.0` |
| Ingress controller | v1.12.1 | `registry.k8s.io/ingress-nginx/controller:v1.12.1` |
| Ingress certgen | v1.6.9 | `registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9` |
| local-path provisioner | v0.0.28 | `rancher/local-path-provisioner:v0.0.28` |

> **When upgrading ingress-nginx:** Update BOTH the image versions in `ingress-values.yaml` AND the pre-pull commands. The controller and certgen versions must be from the same Helm chart release. Check https://github.com/kubernetes/ingress-nginx/releases for compatible pairs.
