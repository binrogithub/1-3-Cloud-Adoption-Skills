# CCI Networking Configuration (v2 API)

## CCI Network via yangtse/v2

CCI requires a dedicated Network resource for pod networking. **Must use the v2 API** — v1beta1 strips `securityGroups`.

## Creating a CCI Network

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
| `apiVersion` | `yangtse/v2` | NOT v1beta1 |
| `spec.networkType` | `underlay_neutron` | Underscore, not dash |
| `spec.securityGroups` | array of SG IDs | Only in v2 API |
| `spec.subnets[].subnetID` | neutron subnet ID | From hcloud_list_subnets |

## NAT Gateway (for internet access)

CCI pods need a NAT gateway + EIP + SNAT rule to reach external services:

```bash
# EIP (pay-per-use)
hcloud EIP CreatePublicip --cli-region=<region> \
  --bandwidth.size=5 --bandwidth.share_type=PER \
  --bandwidth.name=cci-nat-bw --publicip.type=5_bgp

# NAT gateway (small, pay-per-use)
hcloud NAT CreateNatGateway --cli-region=<region> \
  --nat_gateway.name=cci-nat-gw \
  --nat_gateway.router_id=<vpc-id> \
  --nat_gateway.internal_network_id=<subnet-id> \
  --nat_gateway.spec=1

# SNAT rule
hcloud NAT CreateNatGatewaySnatRule --cli-region=<region> \
  --snat_rule.nat_gateway_id=<nat-gw-id> \
  --snat_rule.floating_ip_id=<eip-id> \
  --snat_rule.source_type=0 \
  --snat_rule.cidr=<vpc-cidr>
```

## Service Networking

CCI does NOT support ClusterIP or NodePort services.

- `LoadBalancer`: Requires ELB ID annotation (`kubernetes.io/elb.id`)
- `ExternalName`: DNS alias only

## DNS

CCI provides internal DNS resolution:
- Services: `<service-name>.<namespace>.svc.cluster.local`
- Pods: `<pod-ip>.<namespace>.pod.cluster.local`

## Limitations

- One CCI Network per namespace
- Cannot change network spec after creation
- SWR internal endpoint (100.125.x.x) may not be reachable — use Docker Hub or VPC endpoint
- No ClusterIP or NodePort services
