---
name: hcloud-cce-setup
description: Create a CCE (Kubernetes) cluster on Huawei Cloud with node pools, add-ons, and kubectl access. Use when setting up CCE, creating node pools, installing add-ons, or troubleshooting CCE cluster creation.
---

# CCE Cluster Setup on Huawei Cloud

Create a CCE (Cloud Container Engine) Kubernetes cluster with node pools, add-ons, and kubectl access on Huawei Cloud.

## Prerequisites

- **hcloud CLI** configured with AK/SK (see `hcloud-cli-setup` skill)
- **kubectl** installed
- A **VPC** and **subnet** exist in the target region

Verify:
```bash
hcloud VPC ListVpcs --cli-region=la-north-2
kubectl version --client
```

## EKS ↔ CCE Mapping

| AWS EKS | Huawei Cloud CCE |
|---|---|
| EKS Cluster | CCE Cluster |
| Node Group | Node Pool |
| Fargate | Volcano (batch scheduling add-on) |
| EBS gp3 | EVS (ESSD/GPSSD/SSD) |
| ECR | SWR (SoftWare Repository) |
| ALB/NLB | ELB (L7/L4) |
| IRSA (IAM Roles for SA) | IAM Agency |
| CloudWatch | CES + AOM |
| VPC CNI | ENI network mode (CCE Turbo) |

## Step 1: Gather Network Info

```bash
# List VPCs and subnets
hcloud VPC ListVpcs --cli-region=la-north-2
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=<VPC_ID>

# Or via MCP tools
# hcloud_list_vpcs(region="la-north-2")
# hcloud_list_subnets(region="la-north-2", vpc_id="<VPC_ID>")
```

Save the VPC ID and subnet ID (the `neutron_subnet_id` field).

## Step 2: Create the Cluster

CCE creates an **empty cluster** (master nodes only). Worker nodes are added separately via node pools.

### Cluster Flavors

| Flavor | Master Nodes | Max Worker Nodes | Use Case |
|---|---|---|---|
| `cce.s1.small` | 1 | 50 | Dev/test |
| `cce.s1.medium` | 1 | 200 | Small prod |
| `cce.s1.large` | 1 | 1000 | Single-AZ prod |
| `cce.s2.small` | 3 (HA) | 50 | HA dev/test |
| `cce.s2.medium` | 3 (HA) | 200 | HA small prod |
| `cce.s2.large` | 3 (HA) | 1000 | HA prod |
| `cce.s2.xlarge` | 3 (HA) | 2000 | HA large prod |

### Container Network Modes

| Mode | Description | Use Case |
|---|---|---|
| `overlay_l2` | Tunnel network (OVS) | Default, simple |
| `vpc-router` | Underlay (IPVLAN + VPC routes) | Better performance |
| `eni` | Cloud Native 2.0 (passthrough) | CCE Turbo only, best perf |

### Create cluster

```bash
hcloud CCE CreateCluster --cli-region=la-north-2 \
  --apiVersion=v3 \
  --kind=Cluster \
  --metadata.name=my-cce-cluster \
  --spec.hostNetwork.vpc=<VPC_ID> \
  --spec.hostNetwork.subnet=<SUBNET_ID> \
  --spec.containerNetwork.mode=overlay_l2 \
  --spec.flavor=cce.s2.small \
  --spec.version=v1.30 \
  --spec.type=VirtualMachine \
  --spec.billingMode=0 \
  --spec.kubeProxyMode=ipvs \
  --metadata.annotations.cluster.install.addons.external/install='[{"addonTemplateName":"icagent"}]'
```

Key parameters:
- `--spec.flavor`: `cce.s2.small` = HA (3 masters), max 50 workers
- `--spec.version`: Kubernetes version (e.g. `v1.30`). Omit for latest.
- `--spec.type`: `VirtualMachine` (x86) or `ARM64` (Kunpeng)
- `--spec.category`: `CCE` (standard) or `Turbo` (ENI network, requires `--spec.containerNetwork.mode=eni`)
- `--spec.billingMode`: `0` (pay-per-use) or `1` (yearly/monthly)
- `--spec.kubeProxyMode`: `ipvs` (recommended for large clusters), `iptables`, `nftables` (v1.35+)
- `--spec.publicAccess.cidrs.1=0.0.0.0/0`: Enable public API access (configure CIDR whitelist)
- ICAgent annotation: installs APM agent for observability

### Monitor cluster creation

```bash
# Via CLI
hcloud CCE ListClusters --cli-region=la-north-2

# Via MCP
# hcloud_list_cce_clusters(region="la-north-2")
# hcloud_show_cce_cluster(region="la-north-2", cluster_id="<CLUSTER_ID>")
```

Wait until `status.phase` = `Available`. Creation takes 5-10 minutes.

## Step 3: Create a Node Pool

Worker nodes are added via node pools. You need an **OS image ID** and a **flavor**.

### Find available images

```bash
# List public Linux images (use for node OS)
hcloud IMS ListImages --cli-region=la-north-2 --imagetype=gold --os_type=Linux
```

Common CCE node images: EulerOS 2.0, Ubuntu 22.04.

### Common node flavors (la-north-2)

| Flavor | vCPU | RAM | Generation |
|---|---|---|---|
| `ac8.large.2` | 2 | 4GB | ac8 (AMD) |
| `ac8.large.4` | 2 | 8GB | ac8 |
| `ac8.xlarge.2` | 4 | 8GB | ac8 |
| `ac8.xlarge.4` | 4 | 16GB | ac8 |
| `ac8.2xlarge.2` | 8 | 16GB | ac8 |
| `ac9.large.2` | 2 | 4GB | ac9 (newer) |
| `ac9.xlarge.2` | 4 | 8GB | ac9 |
| `c6.2xlarge.2` | 8 | 16GB | c6 (Intel) |

### Create node pool

```bash
hcloud CCE CreateNodePool --cli-region=la-north-2 \
  --cluster_id=<CLUSTER_ID> \
  --apiVersion=v3 \
  --kind=NodePool \
  --metadata.name=my-nodepool \
  --spec.nodeFlavor=ac8.xlarge.2 \
  --spec.initialNodeCount=2 \
  --spec.autoscaling.enable=true \
  --spec.autoscaling.minNodeCount=2 \
  --spec.autoscaling.maxNodeCount=5 \
  --spec.osImage=<IMAGE_ID> \
  --spec.rootVolume.size=50 \
  --spec.rootVolume.volumetype=GPSSD \
  --spec.dataVolumes.1.size=100 \
  --spec.dataVolumes.1.volumetype=GPSSD \
  --spec.keyPair=<KEYPAIR_NAME>
```

Key parameters:
- `--spec.nodeFlavor`: ECS flavor ID for worker nodes
- `--spec.initialNodeCount`: Initial number of worker nodes
- `--spec.autoscaling.enable=true`: Enable cluster autoscaler
- `--spec.autoscaling.minNodeCount` / `maxNodeCount`: Scaling bounds
- `--spec.rootVolume.volumetype`: `GPSSD`, `SSD`, `ESSD`, `SAS`
- `--spec.keyPair`: SSH key pair name (create one first if needed)

### Create SSH key pair (if needed)

```bash
hcloud ECS CreateKeypair --cli-region=la-north-2 \
  --keypair.name=my-keypair \
  --public_key="$(cat ~/.ssh/id_rsa.pub)"
```

### Monitor node pool

```bash
# Via CLI
hcloud CCE ShowNodePool --cli-region=la-north-2 --cluster_id=<CLUSTER_ID> --nodepool_id=<NODEPOOL_ID>

# Via MCP
# hcloud_list_node_pools(region="la-north-2", cluster_id="<CLUSTER_ID>")
# hcloud_show_node_pool(region="la-north-2", cluster_id="<CLUSTER_ID>", nodepool_id="<NODEPOOL_ID>")
```

## Step 4: Configure kubectl

Use the special `update-kubeconfig` CLI command (not an API operation):

```bash
# Internal access (from within VPC)
hcloud CCE update-kubeconfig \
  --region=la-north-2 \
  --cluster_id=<CLUSTER_ID> \
  --context-name=my-cce-cluster

# External access (from anywhere)
hcloud CCE update-kubeconfig \
  --region=la-north-2 \
  --cluster_id=<CLUSTER_ID> \
  --context-name=my-cce-cluster \
  --external

# Custom output path
hcloud CCE update-kubeconfig \
  --region=la-north-2 \
  --cluster_id=<CLUSTER_ID> \
  --output=/tmp/my-kubeconfig
```

Flags:
- `--region`: Region (required)
- `--cluster_id`: Cluster ID (required)
- `--external`: Use external API endpoint (for access outside VPC)
- `--output`: Output file path (default: `~/.kube/config`)
- `--context-name`: kubeconfig context name
- `--ak` / `--sk` / `--security-token`: Override credentials
- `--project-id`: Override project ID
- `--user-name`: User name in kubeconfig

Verify:
```bash
kubectl get nodes
kubectl get pods -A
```

## Step 5: Install Add-ons

CCE add-ons extend cluster functionality. Common add-ons:

| Add-on | Description |
|---|---|
| `icagent` | APM observability agent (install during cluster creation) |
| `dashboard` | Kubernetes Dashboard web UI |
| `autoscaler` | Cluster autoscaler (if not enabled in node pool) |
| `volcano` | Batch scheduling (Volcano) |
| `nginx-ingress` | NGINX Ingress Controller |
| `coredns` | CoreDNS (installed by default) |
| `everest` | CSI driver for OBS/EVS/SFS (installed by default) |
| `gpu-beta` | GPU support |
| `nvidia-vgpu` | vGPU support |

### List available add-on templates

```bash
hcloud CCE ListAddonTemplates --cli-region=la-north-2 --cluster_id=<CLUSTER_ID>
```

### Install an add-on

```bash
hcloud CCE'CreateAddonInstance --cli-region=la-north-2 \
  --cluster_id=<CLUSTER_ID> \
  --apiVersion=v3 \
  --kind=AddonInstance \
  --metadata.addonTemplateName=nginx-ingress \
  --spec.version=1.3.0 \
  --spec.values.1.key=controller.service.external.enabled \
  --spec.values.1.value=true
```

### List installed add-ons

```bash
# Via CLI
hcloud CCE ListAddonInstances --cli-region=la-north-2 --cluster_id=<CLUSTER_ID>

# Via MCP
# hcloud_list_addon_instances(region="la-north-2", cluster_id="<CLUSTER_ID>")
```

## Step 6: Deploy a Test Workload

```bash
# Deploy nginx
kubectl create deployment nginx --image=nginx:latest --replicas=2

# Expose as LoadBalancer (uses ELB)
kubectl expose deployment nginx --port=80 --type=LoadBalancer

# Get external IP
kubectl get svc nginx

# Clean up
kubectl delete svc nginx
kubectl delete deployment nginx
```

## CCE Cluster Lifecycle

### List clusters
```bash
hcloud CCE ListClusters --cli-region=la-north-2
```

### Get cluster details
```bash
hcloud CCE ShowCluster --cli-region=la-north-2 --cluster_id=<CLUSTER_ID> --detail=true
```

### List nodes
```bash
hcloud CCE ListNodes --cli-region=la-north-2 --cluster_id=<CLUSTER_ID>
```

### Delete a node pool
```bash
hcloud CCE DeleteNodePool --cli-region=la-north-2 --cluster_id=<CLUSTER_ID> --nodepool_id=<NODEPOOL_ID>
```

### Delete a cluster
```bash
hcloud CCE DeleteCluster --cli-region=la-north-2 --cluster_id=<CLUSTER_ID>
```

## MCP Tools Reference

| MCP Tool | Description |
|---|---|
| `hcloud_list_cce_clusters` | List CCE clusters |
| `hcloud_show_cce_cluster` | Get cluster details |
| `hcloud_list_cce_nodes` | List nodes in a cluster |
| `hcloud_list_node_pools` | List node pools |
| `hcloud_show_node_pool` | Get node pool details |
| `hcloud_list_addon_instances` | List installed add-ons |

For any operation not covered by MCP tools, use `hcloud_cli` with the appropriate CCE command.

## Troubleshooting

### Cluster stuck in Creating
- Check VPC/subnet exist and are in the same region
- Verify sufficient quota for master nodes (ECS quota)
- Check `status.message` and `status.reason` via `ShowCluster`

### Node pool stuck in Scaling
- Verify flavor is available in the AZ
- Check ECS quota and resource limits
- Ensure key pair exists
- Check image ID is valid and active

### kubectl connection refused
- Use `--external` flag with `update-kubeconfig` for access outside VPC
- Verify `publicAccess.cidrs` includes your IP range
- Check security group rules allow port 5443

### Add-on installation fails
- Check add-on version compatibility with cluster version
- View add-on status: `hcloud CCE ShowAddonInstance --cli-region=<region> --cluster_id=<id> --addon_id=<addon_id>`
- Some add-ons require specific network modes (e.g., `everest` needs OBS access)

## Current Environment (la-north-2)

- VPCs: `vpc-default-smb` (172.31.0.0/16), `vpc-openwebui` (192.168.0.0/16)
- Subnets: `subnet-default-smb` (172.31.0.0/20), `subnet-openwebui` (192.168.0.0/24)
- AZs: `la-north-2a`, `la-north-2b`, `la-north-2c`
- Project ID: `87c1f98546014799bef9d5a56db6dc60`
- No existing CCE clusters
