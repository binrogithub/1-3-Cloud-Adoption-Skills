---
name: kind-to-cce-migration
description: Migrate a Kubernetes application from a local Kind cluster to Huawei Cloud CCE. Covers CCE cluster creation, node pool provisioning, public API access via EIP, ELB setup for Ingress, SWR image push, Nginx Ingress Controller installation, application deployment with CCE-specific values, and post-migration validation. Based on a verified end-to-end migration of an nginx-demo Helm chart.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: kind-to-cce-migration
---

# Kind to Huawei Cloud CCE Migration

Migrate a Kubernetes application from a local **Kind** cluster to **Huawei Cloud CCE** (Cloud Container Engine). This skill documents the exact steps, pitfalls, and solutions discovered during a verified end-to-end migration.

## Rules

1. **ALWAYS create the CCE cluster first, then the node pool** — Cluster creation returns an ID needed for all subsequent operations. Poll `CCE ShowCluster` until `status.phase=Available` before proceeding.
2. **NEVER use Ubuntu with overlay_l2** — CCE rejects Ubuntu 22.04 on overlay_l2 clusters with `"Not support Ubuntu 22.04 in overlay_l2 cluster"`. Use **EulerOS 2.9** instead.
3. **ALWAYS validate flavor availability per AZ** — Flavors like `c3.large.2` may not exist in all AZs. Use `hcloud_hcloud_list_flavors` with `availability_zone` filter before creating the node pool. Prefer small flavors (ac8.large.2 = 2 vCPU / 4 GB) for dev/test.
4. **ALWAYS bind an EIP to the API server ELB** — The internal endpoint (172.31.x.x:5443) is unreachable from outside the VPC. Create an EIP first, then bind with `CCE UpdateClusterEip --spec.action=bind --spec.spec.id=<eip_id>`. Re-generate kubeconfig afterward.
5. **ALWAYS use L4+L7 ELB for nginx-ingress** — An L7-only ELB cannot create TCP listeners (ports 80/443). The error: `"Loadbalancer has only flavor of type l7 and cannot create listeners of type l4"`. Create the ELB with both `l4_flavor_id` and `l7_flavor_id`.
6. **ALWAYS push images to SWR before deploying** — CCE nodes cannot reliably pull from Docker Hub or registry.k8s.io (timeouts). Push all application images to `swr.<region>.myhuaweicloud.com/<namespace>`. Use `SWR CreateAuthorizationToken` for temporary credentials.
7. **ALWAYS create an imagePullSecret for private SWR namespaces** — CCE nodes can pull from `hwofficial` (public SWR namespace), but custom namespaces require authentication. Create a `docker-registry` secret with **decoded** SWR credentials and patch the service account: `kubectl patch serviceaccount default -p '{"imagePullSecrets":[{"name":"swr-secret"}]}'`.
8. **NEVER use RWO PVC with multi-node Deployments on CCE** — EVS (csi-disk) volumes with `ReadWriteOnce` cannot be attached to multiple nodes simultaneously (`Multi-Attach error`). Options: (a) disable PVC if content comes from ConfigMap, (b) use `ReadWriteMany` with SFS/SFS Turbo, (c) use StatefulSet with `volumeClaimTemplates`.
9. **ALWAYS disable admission webhooks on ingress** — The admission webhook job pulls images from registry.k8s.io which times out on CCE. Set `controller.admissionWebhooks.enabled=false`.
10. **ALWAYS use SWR images for ingress controller** — Set `controller.image.registry=swr.<region>.myhuaweicloud.com`, `controller.image.image=hwofficial/nginx-ingress`. Get the compatible tag from the CCE add-on template: `CCE ListAddonTemplates --addon_template_name=nginx-ingress`, find the version supporting your cluster K8s version.
11. **NEVER trust hcloud CLI for nested addon values** — `CCE CreateAddonInstance --spec.values` only accepts `{}` or `[]`. For add-ons requiring nested JSON (like nginx-ingress with ELB ID), install via **Helm** with `kubernetes.io/elb.id` service annotation instead.
12. **ALWAYS decode SWR auth before creating secrets** — `SWR CreateAuthorizationToken` returns base64-encoded `auth` field. Decode with `echo "$AUTH" | base64 -d`, then split into `username:password` for `kubectl create secret docker-registry`.
13. **Kubeconfig re-generation may need retries** — After binding EIP, `CCE CreateKubernetesClusterCert` may fail transiently with EOF error. Retry after 15-30 seconds.
14. **ALWAYS verify each step before proceeding** — After cluster creation, node pool, EIP bind, ELB create, Helm install, and app deploy — run the corresponding verification command. Never assume success.

## Prerequisites

| Tool | Purpose |
|------|---------|
| hcloud (KooCLI) | Huawei Cloud API calls |
| kubectl | Kubernetes CLI |
| Helm 3.x | Application deployment |
| Docker | Image tag/push to SWR |

**Huawei Cloud requirements:**
- VPC and subnet already exist in the target region
- IAM permissions for CCE, EIP, ELB, SWR, ECS
- SSH keypair (create via `ECS CreateKeypair` or import)

## Workflow

### Step 1: Create CCE Cluster

```bash
hcloud CCE CreateCluster --cli-region=<REGION> \
  --metadata.name=<CLUSTER_NAME> \
  --spec.type=VirtualMachine \
  --spec.flavor=cce.s1.small \
  --spec.version=v1.30 \
  --spec.hostNetwork.vpc=<VPC_ID> \
  --spec.hostNetwork.subnet=<SUBNET_ID> \
  --spec.containerNetwork.mode=overlay_l2 \
  --spec.containerNetwork.cidr=10.244.0.0/16 \
  --spec.authentication.mode=rbac \
  --spec.billingMode=0
```

Poll until Available:
```bash
hcloud CCE ShowCluster --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
# Wait until status.phase == "Available"
```

### Step 2: Create SSH Keypair (if not existing)

```bash
hcloud ECS CreateKeypair --cli-region=<REGION> --keypair.name=<KEYPAIR_NAME> --keypair.public_key="<SSH_PUBLIC_KEY>"
```

Or create and save the private key:
```bash
hcloud ECS CreateKeypair --cli-region=<REGION> --keypair.name=<KEYPAIR_NAME>
# Save the private_key output to a file
```

### Step 3: Create Node Pool

**IMPORTANT:** Validate flavor availability first:
```bash
hcloud_hcloud_list_flavors(region="<REGION>", availability_zone="<AZ>")
# Pick a flavor with status "normal" in your AZ (e.g., ac8.large.2)
```

```bash
hcloud CCE CreateNodePool --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --apiVersion=v3 --kind=NodePool \
  --metadata.name=worker-pool \
  --spec.initialNodeCount=2 \
  --spec.autoscaling.enable=true \
  --spec.autoscaling.minNodeCount=2 \
  --spec.autoscaling.maxNodeCount=5 \
  --spec.nodeTemplate.az=<AZ> \
  --spec.nodeTemplate.flavor=<FLAVOR> \
  --spec.nodeTemplate.os="EulerOS 2.9" \
  --spec.nodeTemplate.billingMode=0 \
  --spec.nodeTemplate.login.sshKey=<KEYPAIR_NAME> \
  --spec.nodeTemplate.rootVolume.size=40 \
  --spec.nodeTemplate.rootVolume.volumetype=SAS \
  --spec.nodeTemplate.dataVolumes.1.size=100 \
  --spec.nodeTemplate.dataVolumes.1.volumetype=SAS \
  --spec.nodeTemplate.runtime.name=containerd
```

Poll until `activeNode == initialNodeCount`.

### Step 4: Enable Public API Access

Create EIP:
```bash
hcloud EIP CreatePublicip --cli-region=<REGION> \
  --publicip.type=5_bgp \
  --publicip.alias=cce-api-eip \
  --bandwidth.share_type=PER \
  --bandwidth.name=cce-api-eip \
  --bandwidth.size=5 \
  --bandwidth.charge_mode=traffic
```

Bind to cluster:
```bash
hcloud CCE UpdateClusterEip --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --spec.action=bind \
  --spec.spec.id=<EIP_ID>
```

Re-generate kubeconfig (may need retry):
```bash
hcloud CCE CreateKubernetesClusterCert --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> --duration=1827
# Save output as ~/.kube/config-<CLUSTER_NAME>
```

Verify:
```bash
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get nodes
```

### Step 5: Create ELB for Ingress Controller

**IMPORTANT:** Must have both L4 and L7 flavors. Get flavor IDs:
```bash
hcloud_hcloud_list_elb_flavors(region="<REGION>")
# L4: L4_flavor.elb.s1.small (e.g., 6b03c99b-...)
# L7: L7_flavor.elb.s1.small (e.g., 19c6da96-...)
```

```bash
hcloud ELB CreateLoadBalancer --cli-region=<REGION> \
  --loadbalancer.name=cce-ingress-elb \
  --loadbalancer.vpc_id=<VPC_ID> \
  --loadbalancer.vip_subnet_cidr_id=<NEUTRON_SUBNET_ID> \
  --loadbalancer.availability_zone_list.1=<AZ> \
  --loadbalancer.l4_flavor_id=<L4_FLAVOR_ID> \
  --loadbalancer.l7_flavor_id=<L7_FLAVOR_ID> \
  --loadbalancer.publicip.bandwidth.share_type=PER \
  --loadbalancer.publicip.bandwidth.name=cce-ingress-elb \
  --loadbalancer.publicip.bandwidth.size=5 \
  --loadbalancer.publicip.bandwidth.charge_mode=traffic \
  --loadbalancer.publicip.network_type=5_bgp
```

Record: `ELB_ID` and `publicip_address` (the public IP for ingress traffic).

### Step 6: Push Images to SWR

Login to SWR:
```bash
# Get temporary credentials
hcloud SWR CreateAuthorizationToken --cli-region=<REGION>
# Decode auth: echo "<AUTH_BASE64>" | base64 -d → username:password
docker login swr.<REGION>.myhuaweicloud.com -u "<USER>" --password-stdin
```

Create namespace:
```bash
hcloud SWR CreateNamespace --cli-region=<REGION> --namespace=<SWR_NAMESPACE>
```

Tag and push each image:
```bash
docker pull <SOURCE_IMAGE>
docker tag <SOURCE_IMAGE> swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/<IMAGE_NAME>:<TAG>
docker push swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/<IMAGE_NAME>:<TAG>
```

### Step 7: Install Nginx Ingress Controller

Get the compatible SWR image tag from CCE add-on templates:
```bash
hcloud CCE ListAddonTemplates --cli-region=<REGION> --addon_template_name=nginx-ingress
# Find version supporting your K8s version (e.g., 6.0.2 for v1.30)
# Note the tag (e.g., v1.14.3_6.0.2)
```

Create ingress values file (see `templates/ingress-values-cce.yaml`):
```yaml
controller:
  kind: DaemonSet
  hostNetwork: false
  service:
    type: LoadBalancer
    annotations:
      kubernetes.io/elb.id: "<ELB_ID>"
  ingressClassResource:
    default: true
  metrics:
    enabled: false
  admissionWebhooks:
    enabled: false
defaultBackend:
  enabled: false
```

Install via Helm:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

KUBECONFIG=~/.kube/config-<CLUSTER_NAME> helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  -f ingress-values-cce.yaml \
  --version <CHART_VERSION> \
  --set controller.image.registry=swr.<REGION>.myhuaweicloud.com \
  --set controller.image.image=hwofficial/nginx-ingress \
  --set controller.image.tag=<SWR_INGRESS_TAG> \
  --set controller.image.digest="" \
  --timeout 5m
```

Verify:
```bash
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get pods -n ingress-nginx
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get svc -n ingress-nginx
# svc should show EXTERNAL-IP = ELB internal IP
```

### Step 8: Create SWR Image Pull Secret

**Required if using a private SWR namespace** (not `hwofficial`):

```bash
# Get SWR credentials (decode the base64 auth)
SWR_AUTH=$(hcloud SWR CreateAuthorizationToken --cli-region=<REGION> | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['auths']['swr.<REGION>.myhuaweicloud.com']['auth'])")
DECODED=$(echo "$SWR_AUTH" | base64 -d)
SWR_USER=$(echo "$DECODED" | cut -d: -f1)
SWR_PASS=$(echo "$DECODED" | cut -d: -f2)

KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl create secret docker-registry swr-secret \
  --docker-server=swr.<REGION>.myhuaweicloud.com \
  --docker-username="$SWR_USER" \
  --docker-password="$SWR_PASS" \
  -n <APP_NAMESPACE>

KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl patch serviceaccount default \
  -n <APP_NAMESPACE> \
  -p '{"imagePullSecrets":[{"name":"swr-secret"}]}'
```

### Step 9: Deploy Application

Create CCE-specific values (see `templates/values-cce.yaml`):
```yaml
image:
  repository: swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/<IMAGE_NAME>
  tag: "<TAG>"

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: <HOSTNAME>
      paths:
        - path: /
          pathType: Prefix

persistence:
  enabled: false  # Or true with csi-disk + ReadWriteOnce (single replica only)
  # storageClass: csi-disk
  # size: 10Gi
```

```bash
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> helm install <RELEASE> <CHART_PATH> \
  -f values-cce.yaml \
  --timeout 5m
```

### Step 10: Validate Migration

Run the full verification checklist:

```bash
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get pods -l app.kubernetes.io/name=<APP>
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get ingress
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get hpa
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get configmap <APP>-config -o yaml
KUBECONFIG=~/.kube/config-<CLUSTER_NAME> kubectl get secret <APP>-secret -o yaml

# Test via ELB public IP
curl -s -H "Host: <HOSTNAME>" http://<ELB_PUBLIC_IP>/
```

**Verification checklist:**

| Check | Command | Expected |
|-------|---------|----------|
| Pods Running | `kubectl get pods` | All 1/1 Running |
| Ingress has address | `kubectl get ingress` | ADDRESS column populated |
| HPA configured | `kubectl get hpa` | Min/Max/Target match source |
| ConfigMap matches | `kubectl get cm -o yaml` | Data matches source (or intentionally updated) |
| Secret matches | `kubectl get secret -o yaml` | Data matches source |
| App responds | `curl -H "Host: ..." http://<ELB_IP>/` | Expected HTML/response |
| CCE add-ons healthy | `CCE ListAddonInstances` | coreddns=running, everest=running |

## CCE Compatibility Mapping

| Component | Local (Kind) | CCE | Migration Change |
|-----------|-------------|-----|-----------------|
| Container images | Docker Hub / registry.k8s.io | SWR registry | `docker tag` + `docker push` to SWR |
| Image pull auth | None (public) | imagePullSecret (private SWR) | Create `swr-secret`, patch ServiceAccount |
| Node OS | Kind (Debian-based) | EulerOS 2.9 | Automatic (node pool config) |
| Ingress Controller | Helm from community | Helm with SWR images + ELB annotation | Change image registry, add `kubernetes.io/elb.id` |
| Ingress LoadBalancer | NodePort / hostNetwork | ELB (L4+L7) | Create ELB, annotate Service |
| PVC StorageClass | `local-path` | `csi-disk` (EVS) | Change `storageClassName` in values |
| PVC accessMode | ReadWriteOnce (single node) | ReadWriteOnce (single node, Multi-Attach error if multi-replica) | Disable PVC or use ReadWriteMany (SFS) |
| PVC size | 1Gi (local) | 10Gi (EVS minimum) | Adjust `size` in values |
| HPA | `autoscaling/v2` | Same | No change |
| ConfigMap/Secret | Same | Same | No change |
| K8s version | v1.30.0 (Kind) | v1.30.x-rXX (CCE) | Compatible within same minor version |

## Cost Reference

| Resource | Specification | Billing |
|----------|--------------|---------|
| CCE cluster | cce.s1.small | Free (control plane managed) |
| Worker nodes | ac8.large.2 (2 vCPU / 4 GB) | Pay-per-use (ECS) |
| API server EIP | 5_bgp, 5 Mbps, traffic | Pay-per-use (EIP + traffic) |
| Ingress ELB | L4+L7 s1.small, 5 Mbps, traffic | Pay-per-use (ELB + EIP + traffic) |
| EVS volumes | SAS, 40GB root + 100GB data | Pay-per-use (EVS) |
| SWR storage | Image storage | Pay-per-use (SWR) |

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `"Not support Ubuntu 22.04 in overlay_l2 cluster"` | Ubuntu incompatible with overlay_l2 network mode | Use `EulerOS 2.9` in node pool config |
| Flavor not found in AZ | Flavor doesn't exist in the selected availability zone | Use `hcloud_hcloud_list_flavors` with AZ filter; pick a flavor with status `normal` |
| Kubeconfig generation: `EOF` error | Transient failure after EIP bind | Retry `CCE CreateKubernetesClusterCert` after 15-30 seconds |
| `kubectl get nodes` timeout via internal IP | Kubeconfig uses internal endpoint (172.31.x.x) | Bind EIP to API server, re-generate kubeconfig |
| ELB: `"cannot create listeners of type l4"` | ELB created with L7 flavor only | Create ELB with both `l4_flavor_id` AND `l7_flavor_id` |
| `ImagePullBackOff` from registry.k8s.io | CCE nodes cannot reach registry.k8s.io | Push images to SWR; use SWR image references |
| `ImagePullBackOff` from private SWR namespace | CCE nodes lack auth for custom SWR namespace | Create `imagePullSecret` with decoded SWR credentials; patch ServiceAccount |
| `Multi-Attach error` for PVC | RWO EVS volume already attached to another node | Disable PVC, use ReadWriteMany (SFS), or use StatefulSet |
| Admission webhook `BackoffLimitExceeded` | Webhook job image from registry.k8s.io unreachable | Set `controller.admissionWebhooks.enabled=false` |
| `hcloud CCE CreateAddonInstance` rejects nested values | `--spec.values` only accepts `{}` or `[]` | Install add-on via Helm with `kubernetes.io/elb.id` annotation instead |
| SWR secret auth fails | Passed base64-encoded username instead of decoded | Decode auth first: `echo "$AUTH" \| base64 -d \| cut -d: -f1` |
| `defaultBackend` ImagePullBackOff | Default backend image from registry.k8s.io | Disable defaultBackend (`defaultBackend.enabled=false`) or push image to SWR |
| Ingress svc EXTERNAL-IP `<pending>` | ELB annotation missing or ELB flavor mismatch | Verify `kubernetes.io/elb.id` annotation on Service; ensure ELB has L4+L7 flavors |

## Key Identifiers Reference

During migration, record these identifiers for reference:

| Identifier | Example | Used In |
|------------|---------|---------|
| Cluster ID | `4a82d04e-69ce-11f1-bdae-0255ac1000c9` | All CCE API calls |
| Node Pool ID | `5bfac81f-69cf-11f1-b50c-0255ac1000c5` | Node pool operations |
| VPC ID | `26aabd48-9677-452c-840a-70504eb1952e` | Cluster, ELB creation |
| Subnet ID | `6a4c031d-8474-48ba-bb51-cdc0c9a84d0d` | Cluster, ELB creation |
| Neutron Subnet ID | `019f4b80-8fe4-45bf-816e-e97ad4f0d46a` | ELB vip_subnet_cidr_id |
| API EIP ID | `204a5ffb-4708-4225-96ee-1fba11a953c6` | ClusterEip bind |
| API EIP Address | `46.250.163.45` | kubectl access |
| ELB ID | `3577ef45-a494-4caf-a134-b79df748e4dc` | Service annotation |
| ELB Public IP | `46.250.162.158` | Ingress traffic |
| Keypair Name | `cce-node-key` | Node pool SSH access |
| SWR Namespace | `cce-migrated` | Image push/pull |
| Kubeconfig Path | `~/.kube/config-cce-migrated` | All kubectl/helm commands |
