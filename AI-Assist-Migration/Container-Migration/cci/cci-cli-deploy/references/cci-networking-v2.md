# CCI Networking via v2 API

## Overview

CCI requires a dedicated Network resource for pod networking. The network connects CCI pods to a VPC subnet and applies security group rules. This resource MUST be created via the `yangtse/v2` API — the v1beta1 API strips `securityGroups`.

## Creating a Network

```python
POST /apis/yangtse/v2/namespaces/<namespace>/networks

{
  "apiVersion": "yangtse/v2",
  "kind": "Network",
  "metadata": {
    "name": "<network-name>",
    "annotations": {
      "yangtse.io/domain-id": "<domain-id>",
      "yangtse.io/project-id": "<project-id>"
    }
  },
  "spec": {
    "networkType": "underlay_neutron",
    "securityGroups": ["<security-group-id>"],
    "subnets": [{"subnetID": "<neutron-subnet-id>"}]
  }
}
```

## Required Fields

| Field | Value | Notes |
|-------|-------|-------|
| `apiVersion` | `yangtse/v2` | Must be v2, not v1beta1 |
| `kind` | `Network` | - |
| `metadata.name` | string | Network name (e.g. `my-network`) |
| `metadata.annotations.yangtse.io/domain-id` | string | Domain ID from IAM |
| `metadata.annotations.yangtse.io/project-id` | string | Project ID for the region |
| `spec.networkType` | `underlay_neutron` | **Underscore**, not dash |
| `spec.securityGroups` | array&lt;string&gt; | Security Group IDs |
| `spec.subnets[].subnetID` | string | Neutron subnet ID (not VPC subnet ID) |

## networkType Values

| Value | Description |
|-------|-------------|
| `underlay_neutron` | Standard neutron-backed network (underscore!) |
| `underlay-neutron` | **INVALID** — returns 403 "not supported" |

## Subnet ID: Neutron vs VPC

The `subnetID` field requires the **neutron subnet ID**, which may differ from the VPC subnet ID. Discover both:

```python
# List subnets via hcloud MCP
hcloud_list_subnets(region, vpc_id)

# Each subnet has:
# - id: VPC subnet ID (e.g. "509f190d-1b5d-4ce3-b641-c08d6245d55b")
# - neutron_subnet_id: Neutron subnet ID (may be same or different)
```

In practice, the VPC subnet ID and neutron subnet ID are often the same. Use the `neutron_subnet_id` field from the subnet discovery response.

## Network Status

```python
GET /apis/yangtse/v2/namespaces/<namespace>/networks/<network-name>
```

Response:

```json
{
  "status": {
    "status": "Ready",
    "subnetAttrs": [{
      "subnetV4ID": "a550f6e0-...",
      "networkID": "509f190d-..."
    }],
    "conditions": [
      {"type": "NetworkExternalDependenciesSynced", "status": "True"},
      {"type": "NetworkSynced", "status": "True"}
    ]
  }
}
```

Wait for `status.status` = `Ready` before deploying workloads.

## NAT Gateway for Internet Access

CCI pods cannot reach external services (Docker Hub, public APIs) without a NAT gateway. The SWR internal endpoint (100.125.x.x) may also be unreachable.

### Setup (pay-per-use)

```bash
# 1. Create EIP
hcloud EIP CreatePublicip --cli-region=<region> \
  --bandwidth.size=5 --bandwidth.share_type=PER \
  --bandwidth.name=cci-nat-bw --publicip.type=5_bgp

# 2. Create NAT gateway
hcloud NAT CreateNatGateway --cli-region=<region> \
  --nat_gateway.name=cci-nat-gw \
  --nat_gateway.router_id=<vpc-id> \
  --nat_gateway.internal_network_id=<subnet-id> \
  --nat_gateway.spec=1

# 3. Create SNAT rule
hcloud NAT CreateNatGatewaySnatRule --cli-region=<region> \
  --snat_rule.nat_gateway_id=<nat-gw-id> \
  --snat_rule.floating_ip_id=<eip-id> \
  --snat_rule.source_type=0 \
  --snat_rule.cidr=<vpc-cidr>
```

### NAT Gateway Specs

| Spec | Size | Max SNAT Connections |
|------|------|---------------------|
| 1 | small | 10,000 |
| 2 | medium | 50,000 |
| 3 | large | 200,000 |
| 4 | extra-large | 1,000,000 |
| 5 | enterprise | 10,000,000 |

Use `spec=1` (small) for most CCI workloads.

## Pod Network Information

After a pod is running, its network details are in annotations:

```json
{
  "cni.yangtse.io/network-status": "[{
    \"macAddress\": \"fa:16:8e:e8:4a:28\",
    \"ipv4Info\": {
      \"subnet\": \"192.168.10.0/24\",
      \"ipAddress\": \"192.168.10.232\",
      \"gateway\": \"192.168.10.1\"
    },
    \"name\": \"<network-name>\",
    \"ips\": [\"192.168.10.232\"]
  }]"
}
```

## Limitations

- One Network per namespace
- Cannot change network spec after creation
- No VPC peering directly — use VPC peering on the underlying VPC
- SWR internal endpoint (100.125.x.x) may not be reachable — use Docker Hub or VPC endpoint
- No ClusterIP or NodePort services — only LoadBalancer (with ELB) and ExternalName
