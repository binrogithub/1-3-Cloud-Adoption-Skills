---
name: huaweicloud-cce-deploy-terraform
description: Deploy Huawei Cloud CCE (Cloud Container Engine) clusters with node pools using Terraform MCP and Huawei Cloud MCP. Covers provider schema discovery, data source references for existing VPC/subnet, cluster and node pool resource creation, keypair management, kubeconfig extraction, and post-deployment validation.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: cce-deployment-terraform-huaweicloud
---

# Huawei Cloud CCE Deployment via Terraform MCP + Huawei Cloud MCP

Deploy CCE clusters declaratively using Terraform with the `huaweicloud` provider. Always get the latest provider schema from Terraform MCP — the provider evolves fast and training data is stale. Use `data` blocks for existing resources, never hardcode IDs. The Terraform provider handles many CCE API quirks internally (ENI subnets, password salting, OS quoting) that require manual workarounds in KooCLI.

## Rules

1. **ALWAYS get schema from Terraform MCP** — call `terraform_get_latest_provider_version` and `terraform_search_providers` + `terraform_get_provider_details` for every resource type (`cce_cluster`, `cce_node_pool`, `compute_keypair`, `vpc`, `vpc_subnet`). Your training data is stale.
2. **ALWAYS get the latest provider version** — call `terraform_get_latest_provider_version(namespace="huaweicloud", name="huaweicloud")` before writing any code.
3. **NEVER hardcode resource IDs** — use `data` blocks for existing resources (VPCs, subnets, security groups) and resource references for created resources. See Data Block Map below.
4. **Terraform handles `eniNetwork.subnets` internally** — unlike KooCLI where you must pass `neutron_subnet_id` explicitly, the Terraform provider sends it automatically. Do NOT add `eni_subnet_id` unless creating a CCE Turbo cluster.
5. **Terraform handles password salting automatically** — the `password` parameter in `huaweicloud_cce_node_pool` accepts plain text. No manual `Base64(Salt + SHA256(Salt + Password))` needed. However, `key_pair` is still recommended over `password`.
6. **Container CIDR must not overlap VPC CIDR** — if the VPC is `192.168.0.0/16`, use `172.16.0.0/16` or `10.0.0.0/16` for `container_network_cidr`.
7. **Match cluster flavor to node count** — `cce.s1.small` = 1 control + max 50 workers. `cce.s1.medium` = 1 control + max 200. Choose the `flavor_id` that supports your maximum node count.
8. **Recommend `containerd` + `ipvs`** — for clusters v1.25+, use `runtime = "containerd"` (docker is deprecated) and `kube_proxy_mode = "ipvs"` (better performance with many services).
9. **Use `kube_config_raw` for kubeconfig** — the `huaweicloud_cce_cluster` resource exposes `kube_config_raw` as an attribute. No separate API call or JSON-to-YAML conversion needed (unlike KooCLI).
10. **Provider timeouts handle waiting** — the provider has built-in timeouts (30 min for cluster, 20 min for node pool). No manual polling or sleep loops needed.

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
- **EIP** — bind an EIP to the cluster for external API access? Default: no.

**Gaps** — any required value the user did NOT specify. Discover and ask about these.

### Step 2: SCHEMA (always, no exceptions)

For **every** resource type:

1. `terraform_get_latest_provider_version(namespace="huaweicloud", name="huaweicloud")` → latest version (e.g. `1.92.0`)
2. `terraform_search_providers(provider_name="huaweicloud", provider_namespace="huaweicloud", service_slug="cce", provider_document_type="resources")` → find `cce_cluster` and `cce_node_pool` doc IDs
3. `terraform_get_provider_details(provider_doc_id="<id>")` → full schema with required + optional params
4. `terraform_search_providers(provider_name="huaweicloud", provider_namespace="huaweicloud", service_slug="vpc", provider_document_type="data-sources")` → find `vpc` and `vpc_subnet` data source doc IDs
5. `terraform_get_provider_details(provider_doc_id="<id>")` → data source schemas

This is mandatory even for resources you think you know. The provider changes between versions — params get renamed, deprecated, or added.

### Step 3: DISCOVER

Call HCloud MCP tools to find real values for anything the user did NOT specify. Batch independent calls in parallel.

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
| Subnet | `hcloud_list_subnets` | Show name + CIDR + available IPs. |
| Keypair | `hcloud_list_keypairs` | If none exist, Terraform will create one via `huaweicloud_compute_keypair`. |
| Image | `hcloud_list_images` | Filter by `__os_version` matching the requested OS. |

### Step 4: WRITE

Write complete Terraform code with:

1. **Provider block** — with the latest version from Step 2
2. **Data blocks** — for all existing resources being referenced (VPCs, subnets). See Data Block Map below.
3. **Resource blocks** — for resources being created (keypair, cluster, node pool). Reference data blocks or other resources, never hardcode IDs.
4. **Outputs** — useful outputs (cluster ID, status, category, node pool ID, kubeconfig)

**Critical: Data blocks vs hardcoded IDs**

NEVER hardcode an ID like `vpc_id = "2bb03951-5698-47a4-bbeb-d2b558a7afd4"`.

Instead, write a data block and reference it:
```hcl
data "huaweicloud_vpc" "hce" {
  name = "vpc-hce"
}

resource "huaweicloud_cce_cluster" "cluster" {
  vpc_id = data.huaweicloud_vpc.hce.id
  # ...
}
```

For resources being CREATED (not referenced), use resource references:
```hcl
resource "huaweicloud_compute_keypair" "cce" {
  name = "cce-tf-key"
}

resource "huaweicloud_cce_node_pool" "workers" {
  cluster_id = huaweicloud_cce_cluster.cluster.id
  key_pair   = huaweicloud_compute_keypair.cce.name
  # ...
}
```

### Step 5: APPLY

Execute the Terraform workflow:

```bash
terraform init
terraform plan
terraform apply -auto-approve
```

**`terraform init`** — downloads the `huaweicloud/huaweicloud` provider.

**`terraform plan`** — previews changes. Should show:
- `data.huaweicloud_vpc.*` — read (resolves VPC ID)
- `data.huaweicloud_vpc_subnet.*` — read (resolves subnet ID)
- `huaweicloud_compute_keypair.*` — create
- `huaweicloud_cce_cluster.*` — create
- `huaweicloud_cce_node_pool.*` — create

**`terraform apply`** — creates resources. The provider handles waiting automatically:
- Keypair: ~2s
- Cluster: ~3-5 min (provider timeout: 30 min)
- Node pool: ~2-3 min (provider timeout: 20 min)

No manual polling or sleep loops needed.

### Step 6: VALIDATE

**6.1 Check Terraform outputs:**

```bash
terraform output
```

Confirm:
- `cluster_status` = `Available`
- `cluster_category` = `CCE`
- `cluster_id` and `node_pool_id` are populated

**6.2 Save kubeconfig:**

```bash
terraform output -raw kubeconfig > ~/.kube/config-<CLUSTER_NAME>
```

**6.3 Use the cluster:**

```bash
export KUBECONFIG=~/.kube/config-<CLUSTER_NAME>
kubectl get nodes
```

**6.4 Verify via Huawei Cloud MCP (optional):**

```
hcloud CCE ShowCluster --cluster_id=<CLUSTER_ID>
hcloud CCE ListNodes --cluster_id=<CLUSTER_ID>
```

## Data Block Map

When referencing existing resources, always use data blocks. When creating resources, use resource references. Never hardcode IDs.

| What | Data Block | How to reference | Example |
|------|-----------|-----------------|---------|
| VPC | `data "huaweicloud_vpc"` | `data.huaweicloud_vpc.<name>.id` | `name = "vpc-hce"` |
| Subnet | `data "huaweicloud_vpc_subnet"` | `data.huaweicloud_vpc_subnet.<name>.id` | `name = "subnet-hce", vpc_id = data.huaweicloud_vpc.hce.id` |
| Availability Zones | `data "huaweicloud_availability_zones"` | `data.huaweicloud_availability_zones.<name>.names[0]` | `state = "available"` |
| Key Pair (existing) | **No data block** — use string directly | `"my-key"` | Key pair names are stable strings |
| ECS Flavor | **No data block** — use string directly | `"c3.xlarge.2"` | Flavor names are stable strings |
| CCE Cluster Flavor | **No data block** — use string directly | `"cce.s1.small"` | Flavor names are stable strings |

**How to decide:**
- If a `data` source exists in the provider → use it
- If the value is a stable string name (flavor, key pair name) → use it directly
- If the resource is being created in the same config → use resource reference (`huaweicloud_cce_cluster.cluster.id`)
- If the resource already exists outside this config → use data block

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

| Mode | `container_network_type` | Description | Cluster Type |
|------|-------------------------|-------------|-------------|
| Tunnel (overlay) | `overlay_l2` | OVS-based overlay network. Container traffic is encapsulated. | CCE standard |
| VPC-router (underlay) | `vpc-router` | IPVLAN + VPC routes. Containers share VPC CIDR. | CCE standard |
| Cloud Native 2.0 | `eni` | Deep ENI integration, VPC CIDR for containers, passthrough. | CCE Turbo only |

## Provider Authentication

The Terraform provider needs AK/SK credentials. Three methods:

### Method 1: Provider block (simplest for single-region)

```hcl
provider "huaweicloud" {
  region     = "na-mexico-1"
  access_key = "YOUR_AK"
  secret_key = "YOUR_SK"
}
```

> **Warning:** Do not commit AK/SK to version control. Use this only for local testing.

### Method 2: Environment variables (recommended)

```bash
export HUAWEICLOUD_ACCESS_KEY="YOUR_AK"
export HUAWEICLOUD_SECRET_KEY="YOUR_SK"
```

Then the provider block only needs:
```hcl
provider "huaweicloud" {
  region = "na-mexico-1"
}
```

### Method 3: Terraform Cloud/Enterprise variable set

Set `HUAWEICLOUD_ACCESS_KEY` and `HUAWEICLOUD_SECRET_KEY` as sensitive environment variables in a TFC/TFE variable set, then attach it to the workspace.

## KooCLI vs Terraform Comparison

| Issue | KooCLI Approach | Terraform Approach |
|-------|----------------|-------------------|
| `eniNetwork.subnets` required | Must pass `neutron_subnet_id` manually via `--spec.eniNetwork.subnets.1.subnetID` | Provider handles internally — **not needed** for standard CCE |
| Password salting | Manual `Base64(Salt+SHA256(Salt+Pwd))` — KooCLI does not auto-salt | Provider handles automatically — `password` accepts plain text |
| OS string quoting | Must quote `"--spec.nodeTemplate.os=EulerOS 2.9"` (space breaks KooCLI parse) | Normal HCL string — no quoting issue |
| Keypair creation | `hcloud ECS NovaCreateKeypair` (not `CreateKeypair` — different API) | `huaweicloud_compute_keypair` resource |
| Kubeconfig | Separate `CreateKubernetesClusterCert` API call + JSON→YAML conversion | `kube_config_raw` attribute on cluster resource — one command |
| Wait/polling | Manual 60-90s sleep loops + `ShowCluster`/`ShowNodePool` polling | Provider timeouts (30 min cluster, 20 min node pool) — automatic |
| State management | Manual tracking of cluster ID, node pool ID via copy-paste | `terraform state` — automatic, inspectable |
| Idempotency | None — re-running creates duplicates | `terraform apply` = no-op if resources unchanged |
| Destroy | Manual `DeleteCluster` + `DeleteNodePool` in correct order | `terraform destroy` — correct dependency order automatic |
| Drift detection | None | `terraform plan` detects drift from expected state |

## Examples

### Example 1: CCE Standard — Single Control, 2 Workers, Tunnel Network

**User:** "Deploy a CCE standard cluster with 1 control node, 2 worker nodes of 4 vCPU / 8 GB RAM, v1.32, max 50 nodes, tunnel network, in na-mexico-1 using existing vpc-hce"

**Agent execution:**

1. **PARSE:** Region=na-mexico-1, cluster=cce-cluster-tf, K8s=v1.32, type=CCE, flavor=cce.s1.small, workers=2, max=50, flavor_spec=4vCPU/8GB, network=overlay_l2, VPC=vpc-hce. **Gaps: AZ, exact flavor, subnet.**

2. **SCHEMA:** Get `huaweicloud_cce_cluster` (doc ID 12401431), `huaweicloud_cce_node_pool` (doc ID 12401440), `huaweicloud_vpc` data source (doc ID 12404871), `huaweicloud_vpc_subnet` data source (doc ID 12404901). Latest provider: 1.92.0.

3. **DISCOVER:** Batch: `hcloud_list_availability_zones`, `hcloud_list_flavors`, `hcloud_list_vpcs`, `hcloud_list_subnets`. Resolve: AZ=`na-mexico-1a`, flavor=`c3.xlarge.2`, VPC=`vpc-hce`, subnet=`subnet-hce`, container CIDR=`172.16.0.0/16`.

4. **WRITE:**

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.92.0"
    }
  }
}

provider "huaweicloud" {
  region = "na-mexico-1"
}

data "huaweicloud_vpc" "hce" {
  name = "vpc-hce"
}

data "huaweicloud_vpc_subnet" "hce" {
  name   = "subnet-hce"
  vpc_id = data.huaweicloud_vpc.hce.id
}

resource "huaweicloud_compute_keypair" "cce" {
  name = "cce-tf-key"
}

resource "huaweicloud_cce_cluster" "cluster" {
  name                   = "cce-cluster-tf"
  flavor_id              = "cce.s1.small"
  cluster_version        = "v1.32"
  cluster_type           = "VirtualMachine"
  vpc_id                 = data.huaweicloud_vpc.hce.id
  subnet_id              = data.huaweicloud_vpc_subnet.hce.id
  container_network_type = "overlay_l2"
  container_network_cidr = "172.16.0.0/16"
  authentication_mode    = "rbac"
  kube_proxy_mode        = "ipvs"

  masters {
    availability_zone = "na-mexico-1a"
  }

  tags = {
    managed-by = "terraform"
    env        = "dev"
  }
}

resource "huaweicloud_cce_node_pool" "workers" {
  cluster_id         = huaweicloud_cce_cluster.cluster.id
  name               = "worker-pool"
  os                 = "EulerOS 2.9"
  flavor_id          = "c3.xlarge.2"
  initial_node_count = 2
  availability_zone  = "na-mexico-1a"
  key_pair           = huaweicloud_compute_keypair.cce.name
  runtime            = "containerd"
  type               = "vm"

  scall_enable             = true
  min_node_count           = 2
  max_node_count           = 50
  scale_down_cooldown_time = 0
  priority                 = 0

  root_volume {
    size       = 40
    volumetype = "SAS"
  }

  data_volumes {
    size       = 100
    volumetype = "SAS"
  }
}

output "cluster_id" {
  value = huaweicloud_cce_cluster.cluster.id
}

output "cluster_status" {
  value = huaweicloud_cce_cluster.cluster.status
}

output "kubeconfig" {
  value     = huaweicloud_cce_cluster.cluster.kube_config_raw
  sensitive = true
}
```

5. **APPLY:** `terraform init` → `terraform plan` (3 to add) → `terraform apply -auto-approve` (~8 min total).

6. **VALIDATE:** `terraform output` confirms `cluster_status=Available`. Save kubeconfig: `terraform output -raw kubeconfig > ~/.kube/config-cce-cluster-tf`.

### Example 2: CCE HA — 3 Control Nodes, Autoscaling Workers, VPC Network, with EIP

**User:** "Create an HA CCE cluster in la-north-2 with 3 control nodes, autoscaling 3-10 workers of 8 vCPU / 16 GB, v1.30, VPC-routed network, with an EIP for external access, use existing prod-vpc"

**Agent execution:**

1. **PARSE:** Region=la-north-2, K8s=v1.30, type=CCE, flavor=cce.s2.small (3 control, max 50), workers=3-10, flavor_spec=8vCPU/16GB, network=vpc-router, VPC=prod-vpc, EIP=yes. **Gaps: AZs, exact flavor, subnet.**

2. **SCHEMA:** Same pattern. Latest provider: 1.92.0.

3. **DISCOVER:** Same batch. For HA, identify 3 AZs (or use `multi_az = true`).

4. **WRITE:**

```hcl
data "huaweicloud_vpc" "prod" {
  name = "prod-vpc"
}

data "huaweicloud_vpc_subnet" "prod" {
  name   = "prod-subnet"
  vpc_id = data.huaweicloud_vpc.prod.id
}

resource "huaweicloud_vpc_eip" "cce" {
  publicip {
    type = "5_bgp"
  }
  bandwidth {
    name        = "cce-eip"
    size        = 8
    share_type  = "PER"
    charge_mode = "traffic"
  }
}

resource "huaweicloud_cce_cluster" "cluster" {
  name                   = "cce-ha-cluster"
  flavor_id              = "cce.s2.small"
  cluster_version        = "v1.30"
  vpc_id                 = data.huaweicloud_vpc.prod.id
  subnet_id              = data.huaweicloud_vpc_subnet.prod.id
  container_network_type = "vpc-router"
  container_network_cidr = "10.0.0.0/16"
  kube_proxy_mode        = "ipvs"
  eip                    = huaweicloud_vpc_eip.cce.address

  multi_az = true
}

resource "huaweicloud_cce_node_pool" "workers" {
  cluster_id         = huaweicloud_cce_cluster.cluster.id
  name               = "worker-pool"
  os                 = "EulerOS 2.9"
  flavor_id          = "c3.2xlarge.2"
  initial_node_count = 3
  key_pair           = huaweicloud_compute_keypair.cce.name
  runtime            = "containerd"
  scall_enable       = true
  min_node_count     = 3
  max_node_count     = 10

  root_volume {
    size       = 40
    volumetype = "SAS"
  }

  data_volumes {
    size       = 100
    volumetype = "SAS"
  }
}
```

## Common Flavor Patterns

| Spec | Flavor ID | vCPU | RAM | Notes |
|------|-----------|------|-----|-------|
| 2 vCPU / 4 GB | `c3.large.2` | 2 | 4 GB | Small worker |
| 4 vCPU / 8 GB | `c3.xlarge.2` | 4 | 8 GB | Medium worker |
| 8 vCPU / 16 GB | `c3.2xlarge.2` | 8 | 16 GB | Large worker |
| 16 vCPU / 32 GB | `c3.4xlarge.2` | 16 | 32 GB | XL worker |

> **Important:** Always verify flavor availability in your AZ via `hcloud_list_flavors`. Flavors marked `sellout` in `cond:operation:az` are unavailable. Only use flavors with `normal` status.

## Key Terraform Resource Parameters

### `huaweicloud_cce_cluster` — Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Cluster name (4-128 chars) |
| `flavor_id` | string | Cluster spec (e.g. `cce.s1.small`) |
| `vpc_id` | string | VPC ID (use data block) |
| `subnet_id` | string | Subnet ID (use data block, must have DNS configured) |
| `container_network_type` | string | `overlay_l2`, `vpc-router`, or `eni` |

### `huaweicloud_cce_cluster` — Key Optional

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cluster_version` | latest | Kubernetes version (e.g. `v1.32`) |
| `cluster_type` | `VirtualMachine` | `VirtualMachine` or `ARM64` |
| `container_network_cidr` | auto | Container CIDR (must not overlap VPC) |
| `authentication_mode` | `rbac` | `rbac` or `authenticating_proxy` |
| `kube_proxy_mode` | `iptables` | `iptables` or `ipvs` (prefer `ipvs`) |
| `eip` | none | EIP address for external API access |
| `multi_az` | false | Enable multi-AZ for HA clusters |
| `masters` block | — | Specify AZ for each control node |
| `eni_subnet_id` | — | ENI subnet ID(s) for CCE Turbo only |
| `tags` | — | Key-value tags |

### `huaweicloud_cce_node_pool` — Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `cluster_id` | string | CCE cluster ID (use resource reference) |
| `name` | string | Node pool name |
| `flavor_id` | string | ECS flavor (e.g. `c3.xlarge.2`) |
| `initial_node_count` | int | Initial number of nodes |
| `root_volume` block | list | System disk (`size`, `volumetype`) |

### `huaweicloud_cce_node_pool` — Key Optional

| Parameter | Default | Description |
|-----------|---------|-------------|
| `os` | auto | Node OS (e.g. `EulerOS 2.9`) |
| `key_pair` | — | SSH keypair name (alternative to `password`) |
| `password` | — | Root password (provider handles salting) |
| `availability_zone` | random | AZ for nodes |
| `runtime` | auto | `docker` or `containerd` (prefer `containerd` for v1.25+) |
| `scall_enable` | false | Enable autoscaling |
| `min_node_count` | 0 | Min nodes for autoscaling |
| `max_node_count` | 0 | Max nodes for autoscaling |
| `subnet_id` | cluster subnet | Subnet for node NIC |
| `data_volumes` block | — | Data disks (`size`, `volumetype`) |
| `tags` | — | Key-value tags |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Error fetching Auth credentials from ECS Metadata API` | No AK/SK provided | Set `access_key`/`secret_key` in provider block, or export `HUAWEICLOUD_ACCESS_KEY`/`HUAWEICLOUD_SECRET_KEY` env vars |
| `container network cidr overlaps with vpc cidr` | Container CIDR overlaps VPC CIDR | Use non-overlapping range (e.g. `172.16.0.0/16` if VPC is `192.168.0.0/16`) |
| `flavor cce.s1.small not found` | Invalid flavor_id | Use valid flavor from Cluster Flavor Reference table |
| `subnet does not have DNS configured` | Subnet missing DNS servers | Ensure subnet has `primary_dns` and `secondary_dns` set. Use a subnet that already has DNS, or create one with DNS. |
| `keypair not found` | Keypair name doesn't exist | Create keypair via `huaweicloud_compute_keypair` resource, or reference an existing one by name |
| `terraform plan shows unexpected changes` | Drift from manual console changes | Run `terraform plan` to inspect, then `terraform apply` to reconcile. Use `lifecycle { ignore_changes = [...] }` for attributes you manage manually. |
| Provider version mismatch | Stale `.terraform.lock.hcl` | Run `terraform init -upgrade` to update the provider |
