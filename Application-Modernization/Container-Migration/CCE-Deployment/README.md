# CCE Deployment Skills (Shared)

Foundational skills for deploying Huawei Cloud CCE (Cloud Container Engine) clusters with node pools. These skills are shared by both migration scenarios: [Local-to-CCE](../Local-to-CCE/README.md) and [CCE-Cross-Region](../CCE-Cross-Region/README.md).

---

## Two Deployment Options

### Option A: Terraform MCP (Declarative)

**Skill:** [huaweicloud-cce-deploy-terraform](./huaweicloud-cce-deploy-terraform/SKILL.md)

Deploy CCE clusters declaratively using Terraform with the `huaweicloud` provider. The Terraform provider handles many CCE API quirks internally:

- ENI subnets sent automatically (no manual `neutron_subnet_id`)
- Password salting handled automatically (no manual `Base64(Salt + SHA256(Salt + Password))`)
- Built-in timeouts (30 min cluster, 20 min node pool)
- `kube_config_raw` attribute for direct kubeconfig extraction

**When to use:**
- Repeatable Infrastructure as Code deployments
- When Terraform MCP is available
- For production environments where declarative config is preferred
- When you want automatic dependency management and state tracking

**Workflow:**
```
1. Get latest provider schema from Terraform MCP
2. Discover existing resources (VPC, subnet) via data blocks
3. Write Terraform config for cce_cluster + cce_node_pool
4. terraform init && terraform apply
5. Extract kubeconfig from kube_config_raw
6. Validate cluster status
```

### Option B: KooCLI + Huawei Cloud MCP (Imperative)

**Skill:** [huaweicloud-cce-deployment](./huaweicloud-cce-deployment/SKILL.md)

Deploy CCE clusters imperatively using `hcloud` KooCLI and Huawei Cloud MCP tools. Discovery-first approach: always find real values from the live cloud before creating resources.

**When to use:**
- Quick one-off deployments
- When Terraform MCP is not available
- For scenarios requiring imperative step-by-step control
- When you need to discover and adapt to existing cloud resources dynamically

**Workflow:**
```
1. Discover AZs, flavors, VPCs, subnets, keypairs, images (parallel)
2. Create CCE cluster (hcloud CCE CreateCluster)
3. Poll until cluster status=Available
4. Create SSH keypair
5. Create node pool (hcloud CCE CreateNodePool)
6. Poll until node pool activeNode=initialNodeCount
7. Bind EIP to API server
8. Generate kubeconfig
9. Validate cluster
```

---

## Comparison

| Feature | Terraform MCP | KooCLI |
|---------|--------------|--------|
| Approach | Declarative (IaC) | Imperative (step-by-step) |
| ENI subnets | Handled automatically | Must pass `neutron_subnet_id` explicitly |
| Password salting | Handled automatically | Must salt manually or use keypair |
| Kubeconfig | `kube_config_raw` attribute | Separate API call + JSON-to-YAML |
| Timeouts/polling | Built-in provider timeouts | Manual polling required |
| State management | Terraform state file | None (imperative) |
| Repeatable | Yes (idempotent) | No (manual cleanup needed) |
| Speed | Slower (init + plan + apply) | Faster (direct API calls) |
| Best for | Production, repeatable | Quick deploy, discovery |

---

## Common Requirements (Both Options)

| Requirement | Details |
|-------------|---------|
| OS | EulerOS 2.9 (Ubuntu 22.04 rejected on overlay_l2 clusters) |
| Container runtime | containerd (docker is deprecated for K8s v1.25+) |
| kube-proxy mode | ipvs (better performance with many services) |
| Container CIDR | Must not overlap VPC CIDR (e.g. use 172.16.0.0/16 if VPC is 192.168.0.0/16) |
| Cluster flavor | cce.s1.small (max 50 workers) or cce.s1.medium (max 200 workers) |
| SSH access | Prefer keypair over password (password salting is complex in KooCLI) |
| EIP | Required for API server access from outside VPC |

---

## How to Use with an AI Agent

### Using Terraform MCP

```
"Plan a CCE deployment over <region> using the huaweicloud-cce-deploy-terraform skill.
 Use Terraform MCP to get the latest provider schema. Create a cluster with
 <node-count> worker nodes, EulerOS 2.9, containerd runtime."
```

### Using KooCLI

```
"Plan a CCE deployment over <region> using the huaweicloud-cce-deployment skill.
 Discover available AZs, flavors, and existing VPC/subnet first.
 Create a cluster with <node-count> worker nodes, EulerOS 2.9, containerd runtime."
```

---

*Version: 1.0 -- July 2026*
*Skills: huaweicloud-cce-deploy-terraform, huaweicloud-cce-deployment*
*Target: Huawei Cloud CCE (Cloud Container Engine)*
