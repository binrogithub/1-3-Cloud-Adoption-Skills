# Kind to Huawei Cloud CCE Migration

Migrate your Kubernetes application from a local Kind cluster to Huawei Cloud CCE in 10 steps, with all common errors already solved.

## What you'll achieve

```
Kind (local)                       Huawei Cloud CCE
┌──────────────────┐              ┌──────────────────────────┐
│  nginx-demo      │              │  nginx-demo on CCE       │
│  2 pods          │  ──migrate─► │  2 pods + ELB + SWR      │
│  PVC local-path  │              │  PVC csi-disk (EVS)      │
│  Docker images   │              │  SWR images              │
│  ingress local   │              │  ingress via public ELB  │
└──────────────────┘              └──────────────────────────┘
```

When finished, your app responds on a Huawei Cloud public IP, with the same pods, HPA, ConfigMap, and Secret you had locally.

## Before you begin

### Required tools

| Tool | Purpose | How to verify |
|------|---------|---------------|
| hcloud (KooCLI) | Call Huawei Cloud APIs | `hcloud --version` |
| kubectl | Manage the K8s cluster | `kubectl version --client` |
| Helm 3.x | Deploy the application | `helm version` |
| Docker | Push images to SWR | `docker version` |

### What you need in Huawei Cloud

- **VPC and subnet** already created in the target region
- **IAM permissions** for CCE, EIP, ELB, SWR, and ECS
- **Region** chosen (e.g. `la-north-2`)
- **AZ** chosen (e.g. `la-north-2a`)

### What you need from the local cluster

- **Helm chart** for your application
- **Kubeconfig** of the working Kind cluster
- **Images** used by your app (nginx, etc.)

---

## The 10 steps

### Step 1: Create the CCE cluster

**What:** Create a managed Kubernetes cluster on Huawei Cloud.

**Why:** CCE manages the control plane for you. You only need to define the network and Kubernetes version.

```bash
hcloud CCE CreateCluster --cli-region=<REGION> \
  --metadata.name=cce-migrated \
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

**Verify:** Wait until the cluster is `Available`:
```bash
hcloud CCE ShowCluster --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
# status.phase must be "Available"
```

---

### Step 2: Create SSH keypair

**What:** Create an SSH key pair to access the cluster nodes.

**Why:** CCE requires a keypair for worker nodes. You'll use it for SSH access if you need to debug.

```bash
hcloud ECS CreateKeypair --cli-region=<REGION> --keypair.name=cce-node-key
# Save the private_key output to a secure file
```

**Verify:** `hcloud ECS ListKeypairs --cli-region=<REGION>` should show `cce-node-key`.

---

### Step 3: Create the node pool

**What:** Create the worker nodes where your pods will run.

**Why:** A CCE cluster without nodes can't run anything. The node pool defines the machine type, OS, and autoscaling.

**Before creating, validate the flavor** (machine type) available in your AZ:
```bash
hcloud_hcloud_list_flavors(region="<REGION>", availability_zone="<AZ>")
# Find a small flavor with status "normal", e.g. ac8.large.2 (2 vCPU / 4 GB)
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
  --spec.nodeTemplate.flavor=ac8.large.2 \
  --spec.nodeTemplate.os="EulerOS 2.9" \
  --spec.nodeTemplate.billingMode=0 \
  --spec.nodeTemplate.login.sshKey=cce-node-key \
  --spec.nodeTemplate.rootVolume.size=40 \
  --spec.nodeTemplate.rootVolume.volumetype=SAS \
  --spec.nodeTemplate.dataVolumes.1.size=100 \
  --spec.nodeTemplate.dataVolumes.1.volumetype=SAS \
  --spec.nodeTemplate.runtime.name=containerd
```

**Verify:** Wait until `activeNode == 2`:
```bash
hcloud CCE ShowNodePool --cli-region=<REGION> --cluster_id=<CLUSTER_ID> --nodepool_id=<NODEPOOL_ID>
```

> **Pitfall:** Don't use Ubuntu 22.04 with overlay_l2 — CCE rejects it. Use **EulerOS 2.9**.
>
> **Pitfall:** Don't assume a flavor exists in your AZ. Always validate with `list_flavors` first.

---

### Step 4: Enable public API server access

**What:** Assign a public IP (EIP) to the cluster's API server so you can use kubectl from your machine.

**Why:** By default, the API server is only accessible from inside the VPC (IP 172.31.x.x). From outside, you can't connect.

Create the EIP:
```bash
hcloud EIP CreatePublicip --cli-region=<REGION> \
  --publicip.type=5_bgp \
  --publicip.alias=cce-api-eip \
  --bandwidth.share_type=PER \
  --bandwidth.name=cce-api-eip \
  --bandwidth.size=5 \
  --bandwidth.charge_mode=traffic
```

Bind to the cluster:
```bash
hcloud CCE UpdateClusterEip --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --spec.action=bind \
  --spec.spec.id=<EIP_ID>
```

Generate the kubeconfig:
```bash
hcloud CCE CreateKubernetesClusterCert --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> --duration=1827
# Save the output as ~/.kube/config-cce-migrated
```

**Verify:**
```bash
KUBECONFIG=~/.kube/config-cce-migrated kubectl get nodes
# Should show 2 nodes Ready
```

> **Pitfall:** If kubeconfig generation fails with an EOF error, wait 15-30 seconds and retry. This is a transient issue after binding the EIP.

---

### Step 5: Create ELB for the Ingress Controller

**What:** Create a load balancer (ELB) that receives internet traffic and distributes it to the pods.

**Why:** In Kind, the ingress uses node ports directly. In CCE, you need an ELB with a public IP that listens on ports 80 and 443 and forwards to the ingress controller.

Get the ELB flavor IDs:
```bash
hcloud_hcloud_list_elb_flavors(region="<REGION>")
# L4: L4_flavor.elb.s1.small
# L7: L7_flavor.elb.s1.small
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

**Verify:** The ELB should have `provisioning_status=ACTIVE` and a `publicip_address`.

> **Pitfall:** The ELB needs **both L4 and L7** flavors. If you create it with L7 only, it will fail to create TCP listeners on ports 80/443. The error is: *"cannot create listeners of type l4"*.

---

### Step 6: Push images to SWR

**What:** Push your app's Docker images to Huawei Cloud's private registry (SWR).

**Why:** CCE nodes cannot reliably pull images from Docker Hub or registry.k8s.io (timeout). SWR is in the same region and is fast.

Get temporary credentials:
```bash
hcloud SWR CreateAuthorizationToken --cli-region=<REGION>
# The "auth" field is base64-encoded. Decode it:
echo "<AUTH_BASE64>" | base64 -d    # → username:password
docker login swr.<REGION>.myhuaweicloud.com -u "<USER>" --password-stdin
```

Create namespace and push images:
```bash
hcloud SWR CreateNamespace --cli-region=<REGION> --namespace=<SWR_NAMESPACE>

docker pull nginx:1.27-alpine
docker tag nginx:1.27-alpine swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/nginx:1.27-alpine
docker push swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/nginx:1.27-alpine
```

**Verify:** `docker push` should complete with a SHA digest.

> **Pitfall:** The SWR namespace is private by default. Pods need an imagePullSecret to pull images from it (see Step 8).

---

### Step 7: Install Nginx Ingress Controller

**What:** Install the ingress controller that processes Ingress rules and routes traffic to pods.

**Why:** Without an ingress controller, Ingress resources don't work. In CCE, the controller connects to the ELB created in Step 5.

First, get the SWR image tag compatible with your K8s version:
```bash
hcloud CCE ListAddonTemplates --cli-region=<REGION> --addon_template_name=nginx-ingress
# Find the version supporting v1.30, e.g. 6.0.2 with tag v1.14.3_6.0.2
```

Create the values file (`ingress-values-cce.yaml`):
```yaml
controller:
  kind: DaemonSet
  hostNetwork: false
  service:
    type: LoadBalancer
    annotations:
      kubernetes.io/elb.id: "<ELB_ID>"    # ← ELB ID from Step 5
  ingressClassResource:
    default: true
  metrics:
    enabled: false
  admissionWebhooks:
    enabled: false                        # ← Webhooks disabled
defaultBackend:
  enabled: false                          # ← Default backend disabled
```

Install:
```bash
KUBECONFIG=~/.kube/config-cce-migrated helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  -f ingress-values-cce.yaml \
  --version 4.12.1 \
  --set controller.image.registry=swr.<REGION>.myhuaweicloud.com \
  --set controller.image.image=hwofficial/nginx-ingress \
  --set controller.image.tag=v1.14.3_6.0.2 \
  --set controller.image.digest="" \
  --timeout 5m
```

**Verify:**
```bash
KUBECONFIG=~/.kube/config-cce-migrated kubectl get pods -n ingress-nginx
# 2 pods Running

KUBECONFIG=~/.kube/config-cce-migrated kubectl get svc -n ingress-nginx
# EXTERNAL-IP should show the ELB's internal IP
```

> **Pitfall:** Admission webhooks use images from registry.k8s.io which can't be pulled. Disable with `admissionWebhooks.enabled=false`.
>
> **Pitfall:** The default backend also uses registry.k8s.io images. Disable with `defaultBackend.enabled=false`.
>
> **Pitfall:** Use the official SWR images (`hwofficial/nginx-ingress`) instead of community registry images. They're faster and pre-cached in the region.

---

### Step 8: Create SWR image pull secret

**What:** Give pods permission to pull images from your private SWR namespace.

**Why:** The `hwofficial` namespace is public, but your custom namespace (e.g. `cce-migrated`) requires authentication. Without this secret, pods get stuck in `ImagePullBackOff`.

```bash
# Get SWR credentials and decode
SWR_AUTH=$(hcloud SWR CreateAuthorizationToken --cli-region=<REGION> 2>/dev/null | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['auths']['swr.<REGION>.myhuaweicloud.com']['auth'])")
DECODED=$(echo "$SWR_AUTH" | base64 -d)
SWR_USER=$(echo "$DECODED" | cut -d: -f1)
SWR_PASS=$(echo "$DECODED" | cut -d: -f2)

# Create the secret in Kubernetes
KUBECONFIG=~/.kube/config-cce-migrated kubectl create secret docker-registry swr-secret \
  --docker-server=swr.<REGION>.myhuaweicloud.com \
  --docker-username="$SWR_USER" \
  --docker-password="$SWR_PASS" \
  -n default

# Associate the secret with the default ServiceAccount
KUBECONFIG=~/.kube/config-cce-migrated kubectl patch serviceaccount default \
  -n default -p '{"imagePullSecrets":[{"name":"swr-secret"}]}'
```

**Verify:** New pods should be able to pull images from SWR without `ImagePullBackOff`.

> **Pitfall:** The SWR `auth` field is **base64-encoded**. If you don't decode it before creating the secret, the username stays encoded and authentication fails.

---

### Step 9: Deploy the application

**What:** Install your Helm chart on the CCE cluster with adapted values.

**Why:** Kind values (DockerHub, local-path, demo.local) don't work on CCE. You need SWR, csi-disk, and a real hostname.

Create `values-cce.yaml`:
```yaml
image:
  repository: swr.<REGION>.myhuaweicloud.com/<SWR_NAMESPACE>/nginx
  tag: "1.27-alpine"

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: demo.cce-migrated.local
      paths:
        - path: /
          pathType: Prefix

persistence:
  enabled: false    # See note below
```

Install:
```bash
KUBECONFIG=~/.kube/config-cce-migrated helm install nginx-demo <CHART_PATH> \
  -f values-cce.yaml --timeout 5m
```

**Verify:**
```bash
KUBECONFIG=~/.kube/config-cce-migrated kubectl get pods -l app.kubernetes.io/name=nginx-demo
# All Running
```

> **Pitfall — PVC Multi-Attach:** If your Deployment has 2+ replicas and a PVC with `ReadWriteOnce`, only one pod can mount the volume. The second pod fails with `"Multi-Attach error"`. Solutions:
> - Disable PVC if content comes from a ConfigMap
> - Use `ReadWriteMany` with SFS (Scalable File Service)
> - Use StatefulSet with `volumeClaimTemplates` (each pod gets its own PVC)

---

### Step 10: Validate the migration

**What:** Verify everything works the same as in the local cluster.

```bash
# Pods
KUBECONFIG=~/.kube/config-cce-migrated kubectl get pods
# → All Running, same count as Kind

# Ingress
KUBECONFIG=~/.kube/config-cce-migrated kubectl get ingress
# → ADDRESS should show the ELB IP

# HPA
KUBECONFIG=~/.kube/config-cce-migrated kubectl get hpa
# → Same min/max/target as Kind

# ConfigMap
KUBECONFIG=~/.kube/config-cce-migrated kubectl get configmap nginx-demo-config -o yaml
# → Data should match (or be intentionally updated)

# Secret
KUBECONFIG=~/.kube/config-cce-migrated kubectl get secret nginx-demo-secret -o yaml
# → Data should match the local cluster

# Connectivity test
curl -s -H "Host: demo.cce-migrated.local" http://<ELB_PUBLIC_IP>/
# → Should return your app's HTML
```

**Full checklist:**

| Check | Command | Expected |
|---|---|---|
| Pods running | `kubectl get pods` | All 1/1 Running |
| Ingress has IP | `kubectl get ingress` | ADDRESS column populated |
| HPA configured | `kubectl get hpa` | Min/Max/Target correct |
| ConfigMap OK | `kubectl get cm -o yaml` | Data correct |
| Secret OK | `kubectl get secret -o yaml` | Data correct |
| App responds | `curl -H "Host: ..." http://<ELB_IP>/` | Expected HTML |
| CCE add-ons | `CCE ListAddonInstances` | coredns=running, everest=running |

---

## Lessons learned

The 7 most common errors, in order of frequency:

### 1. ImagePullBackOff from registry.k8s.io
**Symptom:** Pods stuck in `ContainerCreating` or `ErrImagePull`.
**Cause:** CCE nodes can't reach registry.k8s.io (timeout).
**Fix:** Push all images to SWR before deploying.

### 2. ImagePullBackOff from private SWR
**Symptom:** Pod shows `Back-off pulling image "swr.../cce-migrated/nginx:..."`.
**Cause:** The SWR namespace is private and nodes lack credentials.
**Fix:** Create `imagePullSecret` with decoded credentials and patch the ServiceAccount.

### 3. Multi-Attach error on PVC
**Symptom:** `"Multi-Attach error for volume ... Volume is already used by pod(s) ..."`.
**Cause:** EVS (csi-disk) with ReadWriteOnce doesn't allow multi-node attach.
**Fix:** Disable PVC, use ReadWriteMany with SFS, or use StatefulSet.

### 4. ELB cannot create TCP listeners
**Symptom:** `"cannot create listeners of type l4"`.
**Cause:** The ELB was created with L7 flavor only.
**Fix:** Create the ELB with both `l4_flavor_id` AND `l7_flavor_id`.

### 5. Ubuntu rejected with overlay_l2
**Symptom:** `"Not support Ubuntu 22.04 in overlay_l2 cluster"`.
**Cause:** Ubuntu is incompatible with the overlay_l2 network mode.
**Fix:** Use EulerOS 2.9 in the node pool.

### 6. Kubeconfig with internal endpoint
**Symptom:** `kubectl get nodes` timeout, trying to connect to 172.31.x.x:5443.
**Cause:** The kubeconfig points to the API server's internal endpoint.
**Fix:** Bind an EIP to the cluster and regenerate the kubeconfig.

### 7. Admission webhook fails
**Symptom:** `job ingress-nginx-admission-create failed: BackoffLimitExceeded`.
**Cause:** The webhook uses images from registry.k8s.io that can't be pulled.
**Fix:** Disable admission webhooks: `admissionWebhooks.enabled=false`.

---

## What changes and what doesn't

| Component | In Kind (local) | In CCE | Changes? |
|---|---|---|---|
| Pods | Same | Same | No |
| HPA | Same min/max/target | Identical | No |
| ConfigMap | Same content | Same content | No |
| Secret | Same data | Same data | No |
| Ingress className | `nginx` | `nginx` | No |
| **Images** | Docker Hub | SWR registry | **Yes** |
| **Ingress traffic** | NodePort / localhost | ELB with public IP | **Yes** |
| **PVC StorageClass** | `local-path` | `csi-disk` (EVS) | **Yes** |
| **Node OS** | Debian (Kind) | EulerOS 2.9 | **Yes** |
| **Control plane** | In Docker | Managed by Huawei | **Yes** |

---

## Estimated costs

| Resource | Specification | Cost |
|---|---|---|
| CCE cluster | cce.s1.small | Free (managed control plane) |
| Worker nodes | ac8.large.2 (2 vCPU / 4 GB) | ~$0.05/hr per node |
| API server EIP | 5 Mbps, traffic billing | ~$0.01/hr + traffic |
| Ingress ELB | L4+L7 s1.small, 5 Mbps, traffic | ~$0.03/hr + EIP + traffic |
| EVS volumes | SAS 40GB + 100GB per node | ~$0.001/hr per GB |
| SWR | Image storage | ~$0.0001/hr per GB |

**Total estimate for 2 nodes:** ~$0.15-0.20/hr (~$110-150/month with 24/7 usage).

---

## Cleanup

If you no longer need the CCE environment, delete resources in this order:

```bash
# 1. Uninstall the app
KUBECONFIG=~/.kube/config-cce-migrated helm uninstall nginx-demo
KUBECONFIG=~/.kube/config-cce-migrated helm uninstall ingress-nginx -n ingress-nginx

# 2. Delete the CCE cluster (removes nodes, EVS, security groups)
hcloud CCE DeleteCluster --cli-region=<REGION> --cluster_id=<CLUSTER_ID>

# 3. Delete the ELB
hcloud ELB DeleteLoadBalancer --cli-region=<REGION> --loadbalancer_id=<ELB_ID>

# 4. Delete EIPs
hcloud EIP DeletePublicip --cli-region=<REGION> --publicip_id=<API_EIP_ID>
hcloud EIP DeletePublicip --cli-region=<REGION> --publicip_id=<ELB_EIP_ID>

# 5. Delete the keypair
hcloud ECS NovaDeleteKeypair --cli-region=<REGION> --keypair_name=cce-node-key

# 6. Delete the SWR namespace
hcloud SWR DeleteNamespaces --cli-region=<REGION> --namespace=<SWR_NAMESPACE>
```

---

## Automated script

For repeatable migrations, use the included script:

```bash
./scripts/migrate.sh <REGION> <CLUSTER_ID> <ELB_ID> <SWR_NAMESPACE> <KUBECONFIG_PATH> <CHART_PATH> <HELM_RELEASE>
```

The script executes steps 6-10 (SWR login, ingress install, secret, deploy, validate) assuming the cluster and ELB already exist.
