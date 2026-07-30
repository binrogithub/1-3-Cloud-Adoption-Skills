---
name: huaweicloud-cce-deployment
description: Deploy Huawei Cloud CCE (Cloud Container Engine) clusters with node pools using KooCLI and Huawei Cloud MCP. Covers environment discovery, cluster creation, node pool provisioning, SSH keypair setup, kubeconfig generation, and post-deployment validation.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: cce-deployment-huaweicloud
---

# Huawei Cloud CCE Deployment via KooCLI + MCP

Deploy CCE clusters imperatively using `hcloud` KooCLI and Huawei Cloud MCP tools. Always discover real values from the live cloud first — never guess AZs, flavors, or subnet IDs. Validate after every step. Stop on failure.

## Rules

1. **ALWAYS discover before creating** — call HCloud MCP tools to find AZs, flavors, VPCs, subnets, keypairs, and images before issuing any `hcloud CCE` command. Your training data is stale.
2. **Batch parallel discoveries** — AZs, flavors, VPCs, keypairs, and images are independent. Call them all at once. Only serialize when there's a dependency (subnets need VPC ID).
3. **NEVER hardcode resource IDs** — discover them via MCP tools and pass the returned values into KooCLI commands.
4. **Validate after every step** — after `CreateCluster`, poll `ShowCluster` until `phase=Available`. After `CreateNodePool`, poll `ShowNodePool` until `activeNode` matches `initialNodeCount`. Stop and present logs if anything fails.
5. **Prefer SSH keypair over password** — CCE node password requires a non-trivial salting format (`Base64(Salt + SHA256(Salt + Password))`) that KooCLI does not handle automatically. Create a keypair with `hcloud ECS NovaCreateKeypair` and use `--spec.nodeTemplate.login.sshKey` instead.
6. **`eniNetwork.subnets` is required** — even for standard (non-Turbo) CCE clusters, the API rejects `CreateCluster` without `--spec.eniNetwork.subnets.1.subnetID`. Use the `neutron_subnet_id` from the subnet discovery response.
7. **Quote OS strings with spaces** — values like `EulerOS 2.9` contain spaces and must be quoted in KooCLI: `"--spec.nodeTemplate.os=EulerOS 2.9"`. Unquoted values cause parse errors.
8. **Container CIDR must not overlap VPC CIDR** — if the VPC is `192.168.0.0/16`, use `172.16.0.0/16` or `10.0.0.0/16` for the container network. The API will reject overlapping ranges.
9. **Match cluster flavor to node count** — `cce.s1.small` = 1 control + max 50 workers. `cce.s1.medium` = 1 control + max 200. Choose the flavor that supports your maximum node count.
10. **Recommend `containerd` + `ipvs`** — for clusters v1.25+, use `--spec.nodeTemplate.runtime.name=containerd` (docker is deprecated) and `--spec.kubeProxyMode=ipvs` (better performance with many services).

## Workflow

### Step 1: PARSE INTENT

Extract from the user's request:

- **Region** — required. Ask if not specified.
- **Cluster name** — required. 4-128 chars, lowercase start, no trailing hyphen.
- **Kubernetes version** — e.g. `v1.32`. If not specified, use latest.
- **Cluster type** — `CCE` (standard) or `Turbo`. Default: `CCE`.
- **Cluster flavor** — derived from control node count + max worker count. See Cluster Flavor Reference below.
- **Control node count** — 1 (s1) or 3 (s2). Default: 1.
- **Max worker nodes** — determines flavor suffix (small=50, medium=200, large=1000, xlarge=2000).
- **Worker node flavor** — e.g. 4 vCPU / 8 GB RAM. Discover matching flavors.
- **Worker node count** — initial number of worker nodes.
- **Container network mode** — `overlay_l2` (tunnel), `vpc-router` (underlay), `eni` (Turbo only). Default: `overlay_l2`.
- **Container CIDR** — must not overlap with VPC CIDR. Default: `172.16.0.0/16`.
- **Node OS** — e.g. `EulerOS 2.9`, `Ubuntu 22.04`. Default: `EulerOS 2.9`.
- **VPC strategy** — use existing or create new. Default: use existing.
- **Auth method** — SSH keypair (recommended) or password.
- **Autoscaling** — enabled? min/max node counts.
- **Disk sizes** — root volume (default 40 GB SAS) and data volume (default 100 GB SAS).

**Gaps** — any required value the user did NOT specify. Discover and ask about these.

### Step 2: DISCOVER

Call HCloud MCP tools to find real values. Batch independent calls in parallel.

**Parallel (no dependencies):**

```
hcloud_list_availability_zones(region)
hcloud_list_flavors(region)
hcloud_list_vpcs(region)
hcloud_list_keypairs(region)
hcloud_list_images(region, os_type="Linux", platform="EulerOS")
```

**Sequential (after VPC chosen):**

```
hcloud_list_subnets(region, vpc_id)
```

**From the results, resolve:**

| Need | Source | Notes |
|------|--------|-------|
| AZ | `hcloud_list_availability_zones` | Use zones with `available: true`. If only 1 AZ, use it without asking. |
| Worker flavor | `hcloud_list_flavors` | Filter by vCPU/RAM. Prefer flavors with `cond:operation:az` containing `(normal)`. Avoid `(sellout)`. |
| VPC | `hcloud_list_vpcs` | Show name + CIDR. If user said "use existing", list them. |
| Subnet | `hcloud_list_subnets` | Show name + CIDR + available IPs. Note `neutron_subnet_id` (needed for `eniNetwork`). |
| Keypair | `hcloud_list_keypairs` | If none exist, create one (see Keypair Setup below). |
| Image | `hcloud_list_images` | Filter by `__os_version` matching the requested OS. |

### Step 3: CREATE CLUSTER

Create an empty CCE cluster (master nodes only, no workers). Workers are added in Step 4 via a node pool.

**KooCLI command:**

```bash
hcloud CCE CreateCluster \
  --cli-region=<REGION> \
  --apiVersion=v3 \
  --kind=Cluster \
  --metadata.name=<CLUSTER_NAME> \
  --spec.category=CCE \
  --spec.flavor=<CLUSTER_FLAVOR> \
  --spec.version=<K8S_VERSION> \
  --spec.type=VirtualMachine \
  --spec.hostNetwork.vpc=<VPC_ID> \
  --spec.hostNetwork.subnet=<SUBNET_ID> \
  --spec.containerNetwork.mode=<NETWORK_MODE> \
  --spec.containerNetwork.cidr=<CONTAINER_CIDR> \
  --spec.eniNetwork.subnets.1.subnetID=<NEUTRON_SUBNET_ID> \
  --spec.billingMode=0 \
  --spec.kubeProxyMode=ipvs \
  --spec.masters.1.availabilityZone=<AZ>
```

**Required parameters explained:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `--spec.hostNetwork.subnet` | Subnet `id` (network ID) | From `hcloud_list_subnets` → `id` field |
| `--spec.eniNetwork.subnets.1.subnetID` | Subnet `neutron_subnet_id` | **Different from above!** Uses the neutron subnet ID. Required even for standard CCE. |
| `--spec.flavor` | e.g. `cce.s1.small` | See Cluster Flavor Reference |
| `--spec.masters.1.availabilityZone` | e.g. `na-mexico-1a` | Must be a valid CCE AZ |

**For HA clusters (3 control nodes), add:**

```bash
  --spec.masters.1.availabilityZone=<AZ_1> \
  --spec.masters.2.availabilityZone=<AZ_2> \
  --spec.masters.3.availabilityZone=<AZ_3>
```

**Validation:**

```bash
# Poll until status.phase == "Available"
hcloud CCE ShowCluster --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
```

CCE cluster creation typically takes 3-5 minutes. Check every 60 seconds. Do NOT proceed to node pool creation until `phase=Available`.

**Capture from response:**

- `metadata.uid` → cluster ID (needed for all subsequent commands)
- `status.endpoints` → internal API URL
- `spec.hostNetwork.SecurityGroup` → worker security group ID
- `spec.hostNetwork.controlPlaneSecurityGroup` → control plane security group ID

### Step 4: CREATE NODE POOL

Add worker nodes to the cluster via a node pool.

**Keypair Setup (if no existing keypair):**

```bash
# Generate SSH keypair locally
ssh-keygen -t rsa -b 2048 -f /tmp/cce-node-key -N "" -q

# Register in Huawei Cloud
PUBKEY=$(cat /tmp/cce-node-key.pub)
hcloud ECS NovaCreateKeypair \
  --cli-region=<REGION> \
  --keypair.name=cce-node-key \
  "--keypair.public_key=$PUBKEY"
```

> **Important:** The `CreateKeypair` operation is NOT available on the ECS service. Use `NovaCreateKeypair` instead. The public key contains `+` and `/` characters that break KooCLI parsing — always pass it via a shell variable with quoting: `"--keypair.public_key=$PUBKEY"`.

**KooCLI command:**

```bash
hcloud CCE CreateNodePool \
  --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --apiVersion=v3 \
  --kind=NodePool \
  --metadata.name=<NODE_POOL_NAME> \
  --spec.initialNodeCount=<INITIAL_NODE_COUNT> \
  --spec.autoscaling.enable=<true|false> \
  --spec.autoscaling.minNodeCount=<MIN_NODES> \
  --spec.autoscaling.maxNodeCount=<MAX_NODES> \
  --spec.nodeTemplate.az=<AZ> \
  --spec.nodeTemplate.flavor=<FLAVOR> \
  "--spec.nodeTemplate.os=<OS>" \
  --spec.nodeTemplate.billingMode=0 \
  --spec.nodeTemplate.login.sshKey=<KEYPAIR_NAME> \
  --spec.nodeTemplate.rootVolume.size=40 \
  --spec.nodeTemplate.rootVolume.volumetype=SAS \
  --spec.nodeTemplate.dataVolumes.1.size=100 \
  --spec.nodeTemplate.dataVolumes.1.volumetype=SAS \
  --spec.nodeTemplate.runtime.name=containerd
```

> **Important:** The `--spec.nodeTemplate.os` value contains a space (e.g. `EulerOS 2.9`). You MUST quote the entire parameter: `"--spec.nodeTemplate.os=EulerOS 2.9"`. Unquoted values cause KooCLI parse errors.

**Node pool parameters explained:**

| Parameter | Typical Value | Notes |
|-----------|---------------|-------|
| `--spec.initialNodeCount` | 2 | Number of nodes to create immediately |
| `--spec.autoscaling.minNodeCount` | 2 | Minimum nodes when autoscaling |
| `--spec.autoscaling.maxNodeCount` | 50 | Must not exceed cluster flavor max |
| `--spec.nodeTemplate.flavor` | `c3.xlarge.2` | 4 vCPU / 8 GB. Use discovered flavor ID. |
| `--spec.nodeTemplate.rootVolume.size` | 40 | System disk in GB (min 40) |
| `--spec.nodeTemplate.dataVolumes.1.size` | 100 | Data disk in GB (min 20 for first data disk) |
| `--spec.nodeTemplate.runtime.name` | `containerd` | Use `containerd` for v1.25+. `docker` is deprecated. |

**Validation:**

```bash
# Poll until activeNode == initialNodeCount and creatingNode == 0
hcloud CCE ShowNodePool --cli-region=<REGION> --cluster_id=<CLUSTER_ID> --nodepool_id=<NODEPOOL_ID>
```

Node provisioning typically takes 3-5 minutes. Check every 60-90 seconds.

**Capture from response:**

- `metadata.uid` → node pool ID
- `status.activeNode` → count of healthy nodes
- `status.creatingNode` → count of nodes still being provisioned

### Step 5: VALIDATE AND GENERATE KUBECONFIG

**5.1 Verify cluster and nodes:**

```bash
hcloud CCE ShowCluster --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
hcloud CCE ListNodes --cli-region=<REGION> --cluster_id=<CLUSTER_ID>
```

Confirm:
- `status.phase` = `Available`
- All nodes have `status.phase` = `Active`
- Node count matches `initialNodeCount`

**5.2 Generate kubeconfig:**

```bash
hcloud CCE CreateKubernetesClusterCert \
  --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --duration=1827
```

> **Note:** `duration` is in days. Max is 1827 (5 years). The response is a full kubeconfig JSON object.

**5.3 Save kubeconfig to disk:**

```bash
# Save the JSON response and convert to YAML
mkdir -p ~/.kube
hcloud CCE CreateKubernetesClusterCert \
  --cli-region=<REGION> \
  --cluster_id=<CLUSTER_ID> \
  --duration=1827 > /tmp/kubeconfig_raw.json

python3 -c "
import json, yaml
with open('/tmp/kubeconfig_raw.json') as f:
    data = json.load(f)
with open('/home/ubuntu-user/.kube/config-<CLUSTER_NAME>', 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
"
```

**5.4 Use the cluster:**

```bash
export KUBECONFIG=/home/ubuntu-user/.kube/config-<CLUSTER_NAME>
kubectl get nodes
```

## Discovery Map

| Need | HCloud MCP Tool | Dependencies |
|------|-----------------|-------------|
| Availability Zones | `hcloud_list_availability_zones` | — |
| ECS Flavors | `hcloud_list_flavors` | — |
| VPCs | `hcloud_list_vpcs` | — |
| Subnets | `hcloud_list_subnets` | `vpc_id` (after VPC chosen) |
| Keypairs | `hcloud_list_keypairs` | — |
| Images | `hcloud_list_images` | — |
| Security Groups | `hcloud_list_security_groups` | — |
| Server Quotas | `hcloud_show_server_limits` | — |
| Volume Types | `hcloud_list_volume_types` | — |

## Cluster Flavor Reference

| Flavor | Control Nodes | Max Worker Nodes | Use Case |
|--------|--------------|-----------------|----------|
| `cce.s1.small` | 1 | 50 | Small dev/test, single control plane |
| `cce.s1.medium` | 1 | 200 | Medium workload, single control plane |
| `cce.s1.large` | 1 | 1,000 | Large workload, single control plane |
| `cce.s2.small` | 3 | 50 | Small HA cluster |
| `cce.s2.medium` | 3 | 200 | Medium HA cluster |
| `cce.s2.large` | 3 | 1,000 | Large HA cluster |
| `cce.s2.xlarge` | 3 | 2,000 | Ultra-large HA cluster |

> **s1 = single control node.** If the control node fails, the cluster becomes unavailable (but running workloads are unaffected). **s2 = 3 control nodes (HA).** One control node can fail without cluster impact.

## Container Network Modes

| Mode | Flag | Description | Cluster Type |
|------|------|-------------|-------------|
| Tunnel (overlay) | `overlay_l2` | OVS-based overlay network. Container traffic is encapsulated. | CCE standard |
| VPC-router (underlay) | `vpc-router` | IPVLAN + VPC routes. Containers share VPC CIDR. | CCE standard |
| Cloud Native 2.0 | `eni` | Deep ENI integration, VPC CIDR for containers, passthrough. | CCE Turbo only |

## Password vs Keypair for Node Authentication

**Problem:** CCE requires password values to be salted as `Base64(Salt + SHA256(Salt + Password))`. KooCLI does NOT handle this automatically. Passing a raw password results in `"Unexpected initial node password format"` errors.

**Solution:** Use SSH keypair authentication instead:

1. Generate a keypair: `ssh-keygen -t rsa -b 2048 -f /tmp/cce-node-key -N "" -q`
2. Register it: `hcloud ECS NovaCreateKeypair --keypair.name=cce-node-key "--keypair.public_key=$(cat /tmp/cce-node-key.pub)"`
3. Reference it in node pool: `--spec.nodeTemplate.login.sshKey=cce-node-key`

If password auth is strictly required, the salting formula is:

```bash
SALT="random8ch"
HASH=$(echo -n "${SALT}${PASSWORD}" | sha256sum | awk '{print $1}')
SALTED=$(echo -n "${SALT}${HASH}" | base64 -w 0)
# Pass $SALTED as --spec.nodeTemplate.login.userPassword.password
```

## Common Flavor Patterns

| Spec | Flavor ID | vCPU | RAM | Notes |
|------|-----------|------|-----|-------|
| 2 vCPU / 4 GB | `c3.large.2` | 2 | 4 GB | Small worker |
| 4 vCPU / 8 GB | `c3.xlarge.2` | 4 | 8 GB | Medium worker |
| 8 vCPU / 16 GB | `c3.2xlarge.2` | 8 | 16 GB | Large worker |
| 16 vCPU / 32 GB | `c3.4xlarge.2` | 16 | 32 GB | XL worker |

> **Important:** Always verify flavor availability in your AZ. Flavors marked `sellout` in `cond:operation:az` are unavailable. Only use flavors with `normal` status.

## Examples

### Example 1: CCE Standard — Single Control, 2 Workers, Tunnel Network

**User:** "Deploy a CCE standard cluster with 1 control node, 2 worker nodes of 4 vCPU / 8 GB RAM, v1.32, max 50 nodes, tunnel network, in na-mexico-1 using existing vpc-hce"

**Agent execution:**

1. **PARSE:** Region=na-mexico-1, cluster=cce-cluster, K8s=v1.32, type=CCE, flavor=cce.s1.small, workers=2, max=50, flavor_spec=4vCPU/8GB, network=overlay_l2, VPC=vpc-hce. **Gaps: AZ, exact flavor, subnet, keypair.**

2. **DISCOVER:** Batch: `hcloud_list_availability_zones`, `hcloud_list_flavors`, `hcloud_list_vpcs`, `hcloud_list_keypairs`, `hcloud_list_images`. Then: `hcloud_list_subnets(vpc_id)`.

3. **RESOLVE:**
   - AZ: `na-mexico-1a` (only AZ available)
   - Flavor: `c3.xlarge.2` (4 vCPU, 8 GB, status=normal)
   - VPC: `vpc-hce` → `2bb03951-5698-47a4-bbeb-d2b558a7afd4`
   - Subnet: `subnet-hce` → `59971e21-c177-46dc-9558-774c8dc91676`, neutron: `c621bd52-fa67-45f8-9861-216021db9ab2`
   - Keypair: none → create `cce-node-key`
   - Container CIDR: `172.16.0.0/16` (no overlap with VPC `192.168.0.0/16`)

4. **CREATE CLUSTER:**

```bash
hcloud CCE CreateCluster \
  --cli-region=na-mexico-1 \
  --apiVersion=v3 \
  --kind=Cluster \
  --metadata.name=cce-cluster \
  --spec.category=CCE \
  --spec.flavor=cce.s1.small \
  --spec.version=v1.32 \
  --spec.type=VirtualMachine \
  --spec.hostNetwork.vpc=2bb03951-5698-47a4-bbeb-d2b558a7afd4 \
  --spec.hostNetwork.subnet=59971e21-c177-46dc-9558-774c8dc91676 \
  --spec.containerNetwork.mode=overlay_l2 \
  --spec.containerNetwork.cidr=172.16.0.0/16 \
  --spec.eniNetwork.subnets.1.subnetID=c621bd52-fa67-45f8-9861-216021db9ab2 \
  --spec.billingMode=0 \
  --spec.kubeProxyMode=ipvs \
  --spec.masters.1.availabilityZone=na-mexico-1a
```

5. **WAIT** for `phase=Available` (poll `ShowCluster` every 60s, ~3-5 min).

6. **CREATE NODE POOL:**

```bash
hcloud CCE CreateNodePool \
  --cli-region=na-mexico-1 \
  --cluster_id=<CLUSTER_ID> \
  --apiVersion=v3 \
  --kind=NodePool \
  --metadata.name=worker-pool \
  --spec.initialNodeCount=2 \
  --spec.autoscaling.enable=true \
  --spec.autoscaling.minNodeCount=2 \
  --spec.autoscaling.maxNodeCount=50 \
  --spec.nodeTemplate.az=na-mexico-1a \
  --spec.nodeTemplate.flavor=c3.xlarge.2 \
  "--spec.nodeTemplate.os=EulerOS 2.9" \
  --spec.nodeTemplate.billingMode=0 \
  --spec.nodeTemplate.login.sshKey=cce-node-key \
  --spec.nodeTemplate.rootVolume.size=40 \
  --spec.nodeTemplate.rootVolume.volumetype=SAS \
  --spec.nodeTemplate.dataVolumes.1.size=100 \
  --spec.nodeTemplate.dataVolumes.1.volumetype=SAS \
  --spec.nodeTemplate.runtime.name=containerd
```

7. **WAIT** for `activeNode=2` and `creatingNode=0` (poll `ShowNodePool` every 60s, ~3-5 min).

8. **VALIDATE:** `ListNodes` confirms 2 nodes with `phase=Active`. Generate kubeconfig with `CreateKubernetesClusterCert --duration=1827`.

### Example 2: CCE HA — 3 Control Nodes, Autoscaling Workers, VPC Network

**User:** "Create an HA CCE cluster in la-north-2 with 3 control nodes, autoscaling 3-10 workers of 8 vCPU / 16 GB, v1.30, VPC-routed network, use existing prod-vpc"

**Agent execution:**

1. **PARSE:** Region=la-north-2, K8s=v1.30, type=CCE, flavor=cce.s2.small (3 control, max 50), workers=3-10, flavor_spec=8vCPU/16GB, network=vpc-router, VPC=prod-vpc. **Gaps: AZs (need 3 for HA), exact flavor, subnet, keypair.**

2. **DISCOVER:** Same batch pattern. For HA, identify at least 3 AZs (or use `multi_az` if only 1 AZ available).

3. **CREATE CLUSTER:**

```bash
hcloud CCE CreateCluster \
  --cli-region=la-north-2 \
  --apiVersion=v3 \
  --kind=Cluster \
  --metadata.name=cce-ha-cluster \
  --spec.category=CCE \
  --spec.flavor=cce.s2.small \
  --spec.version=v1.30 \
  --spec.type=VirtualMachine \
  --spec.hostNetwork.vpc=<VPC_ID> \
  --spec.hostNetwork.subnet=<SUBNET_ID> \
  --spec.containerNetwork.mode=vpc-router \
  --spec.containerNetwork.cidr=10.0.0.0/16 \
  --spec.eniNetwork.subnets.1.subnetID=<NEUTRON_SUBNET_ID> \
  --spec.billingMode=0 \
  --spec.kubeProxyMode=ipvs \
  --spec.extendParam.clusterAZ=multi_az \
  --spec.masters.1.availabilityZone=la-north-2a \
  --spec.masters.2.availabilityZone=la-north-2b \
  --spec.masters.3.availabilityZone=la-north-2c
```

4. **CREATE NODE POOL** with `--spec.nodeTemplate.flavor=c3.2xlarge.2` (8 vCPU, 16 GB), `--spec.autoscaling.minNodeCount=3`, `--spec.autoscaling.maxNodeCount=10`.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `spec.eniNetwork.subnets.[N].subnetID is required` | Missing ENI subnet parameter | Add `--spec.eniNetwork.subnets.1.subnetID=<NEUTRON_SUBNET_ID>` |
| `Unexpected initial node password format` | Raw password passed without salting | Use SSH keypair instead, or apply the salting formula |
| `The X parameter format must be '--param=value'` | Space in parameter value (e.g. `EulerOS 2.9`) | Quote the entire parameter: `"--spec.nodeTemplate.os=EulerOS 2.9"` |
| `Operation CreateKeypair is not supported` | Wrong ECS API operation | Use `NovaCreateKeypair` instead |
| Flavor AZ shows `(sellout)` | Flavor unavailable in that AZ | Choose a different flavor or AZ with `(normal)` status |
| Container CIDR overlap | Container CIDR overlaps with VPC CIDR | Use a non-overlapping range (e.g. `172.16.0.0/16` if VPC is `192.168.0.0/16`) |
