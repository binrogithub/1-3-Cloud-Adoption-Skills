---
name: huaweicloud-cci-cli-deploy
description: Deploy Huawei Cloud CCI (Cloud Container Instance) workloads entirely from the CLI using the v2 API with AK/SK signing. Covers prerequisites, SDK-HMAC-SHA256 signing, namespace creation via cci/v2, network creation via yangtse/v2 with securityGroups, NAT gateway for internet access, deployments with resource limits, services, and validation — all in pay-per-use mode.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: cci-cli-deploy-huaweicloud
---

# Huawei Cloud CCI Deployment via CLI (v2 API)

Deploy CCI serverless containers **entirely from the terminal** using the CCI v2 API with AK/SK request signing. No console access needed (except one-time agency authorization per region). All resources use pay-per-use billing.

## Rules

1. **ALWAYS use the v2 API** — v1beta1 strips `securityGroups` from Network spec (not in CRD schema), causing `400 securitygroup can not be empty`. Use `cci/v2` for namespaces/workloads and `yangtse/v2` for networks.
2. **Namespaces MUST be created via `cci/v2`** — namespaces created via `api/v1` are NOT visible to v2 APIs. They use separate namespace stores.
3. **`networkType` uses underscore** — value must be `underlay_neutron` (underscore), NOT `underlay-neutron` (dash). The dash form returns 403.
4. **Resource limits are REQUIRED** — CCI rejects pods without CPU/memory requests. Minimum: `250m` CPU, `512Mi` memory.
5. **No ClusterIP or NodePort services** — CCI only supports `LoadBalancer` (with ELB ID annotation) and `ExternalName`.
6. **NAT gateway needed for internet** — CCI pods cannot reach external registries without SNAT. SWR internal endpoint (100.125.x.x) may also be unreachable — use Docker Hub or VPC endpoint.
7. **All pay-per-use** — EIP with `share_type=PER`, NAT with `spec=1`, CCI pods billed per-second.
8. **Signing is SDK-HMAC-SHA256** — single HMAC with SK as key, NOT AWS-style derived keys. See `references/huaweicloud-signing.md`.

## Prerequisites

### One-time: CCI Agency Authorization (per region)

This is the ONLY manual console step. Everything else is from the terminal.

1. Go to: `https://console-intl.huaweicloud.com/cci/?region=<region>`
2. Click "Authorize CCI"
3. This creates `cci_admin_trust` and `cci_instance_trust` IAM agencies

### Credentials and Infrastructure

- **AK/SK** — create via IAM (`CreatePermanentAccessKey`) or use existing KooCLI credentials
- **Project ID** — from `hcloud_list_projects` for the target region
- **Domain ID** — from `hcloud_list_domains`
- **VPC, Subnet, Security Group** — discover via hcloud MCP tools

## Workflow

### Step 1: DISCOVER

Use hcloud MCP tools to find existing infrastructure. Batch parallel calls.

```
hcloud_list_vpcs(region)
hcloud_list_subnets(region, vpc_id)
hcloud_list_security_groups(region)
```

Extract:
- VPC ID (e.g. `d277896b-83c8-4690-9f0b-48dc17d20a40`)
- Subnet neutron subnet ID (e.g. `a550f6e0-d391-40f2-a185-7b25c95f993e`)
- Security Group ID (e.g. `e7078087-631f-4a54-b493-1aaccc12080c`)
- VPC CIDR (e.g. `192.168.0.0/16`)

### Step 2: CREATE NAMESPACE (cci/v2)

```python
POST https://cci.<region>.myhuaweicloud.com/apis/cci/v2/namespaces

{
  "apiVersion": "cci/v2",
  "kind": "Namespace",
  "metadata": {
    "name": "<namespace>",
    "annotations": {
      "yangtse.io/domain-id": "<domain-id>",
      "yangtse.io/project-id": "<project-id>"
    }
  }
}
```

**Verify**: `GET /apis/cci/v2/namespaces/<namespace>` — status.phase should be `Active`.

### Step 3: CREATE NETWORK (yangtse/v2)

```python
POST https://cci.<region>.myhuaweicloud.com/apis/yangtse/v2/namespaces/<namespace>/networks

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

**Verify**: `GET /apis/yangtse/v2/namespaces/<namespace>/networks/<network-name>` — status.status should be `Ready`.

See `references/cci-networking-v2.md` for details.

### Step 4: CREATE NAT GATEWAY (pay-per-use, for internet access)

```bash
# 4a. Create EIP (5_bgp, per-bandwidth)
hcloud EIP CreatePublicip --cli-region=<region> \
  --bandwidth.size=5 --bandwidth.share_type=PER \
  --bandwidth.name=cci-nat-bw --publicip.type=5_bgp

# 4b. Create NAT gateway (spec=1 = small)
hcloud NAT CreateNatGateway --cli-region=<region> \
  --nat_gateway.name=cci-nat-gw \
  --nat_gateway.router_id=<vpc-id> \
  --nat_gateway.internal_network_id=<subnet-id> \
  --nat_gateway.spec=1

# 4c. Create SNAT rule (allows VPC CIDR to access internet)
hcloud NAT CreateNatGatewaySnatRule --cli-region=<region> \
  --snat_rule.nat_gateway_id=<nat-gw-id> \
  --snat_rule.floating_ip_id=<eip-id> \
  --snat_rule.source_type=0 \
  --snat_rule.cidr=<vpc-cidr>
```

### Step 5: CREATE IMAGE PULL SECRET (optional, for private registries)

```python
POST /apis/cci/v2/namespaces/<namespace>/secrets

{
  "apiVersion": "cci/v2",
  "kind": "Secret",
  "metadata": {"name": "swr-pull-secret"},
  "type": "kubernetes.io/dockerconfigjson",
  "data": {
    ".dockerconfigjson": "<base64(json({\"auths\": {\"<registry>\": {\"auth\": \"<base64(ak:sk)>\"}}}))>"
  }
}
```

For SWR, use AK as username and SK as password.

### Step 6: CREATE DEPLOYMENT (cci/v2)

```python
POST /apis/cci/v2/namespaces/<namespace>/deployments

{
  "apiVersion": "cci/v2",
  "kind": "Deployment",
  "metadata": {"name": "<app-name>"},
  "spec": {
    "replicas": 1,
    "selector": {"matchLabels": {"app": "<app-name>"}},
    "template": {
      "metadata": {"labels": {"app": "<app-name>"}},
      "spec": {
        "imagePullSecrets": [{"name": "swr-pull-secret"}],
        "containers": [{
          "name": "<container-name>",
          "image": "<image>",
          "ports": [{"containerPort": 80}],
          "resources": {
            "requests": {"cpu": "250m", "memory": "512Mi"},
            "limits": {"cpu": "500m", "memory": "1024Mi"}
          }
        }]
      }
    }
  }
}
```

**Resource limits are mandatory.** Omitting them returns 403.

### Step 7: CREATE SERVICE (cci/v2)

**Option A: LoadBalancer (requires existing ELB)**

```python
POST /apis/cci/v2/namespaces/<namespace>/services

{
  "apiVersion": "cci/v2",
  "kind": "Service",
  "metadata": {
    "name": "<svc-name>",
    "annotations": {"kubernetes.io/elb.id": "<elb-id>"}
  },
  "spec": {
    "type": "LoadBalancer",
    "selector": {"app": "<app-name>"},
    "ports": [{"port": 80, "targetPort": 80, "protocol": "TCP"}]
  }
}
```

**Option B: ExternalName (DNS alias only)**

```python
{
  "apiVersion": "cci/v2",
  "kind": "Service",
  "metadata": {"name": "<svc-name>"},
  "spec": {
    "type": "ExternalName",
    "externalName": "example.com"
  }
}
```

**NOT supported**: `ClusterIP`, `NodePort`.

### Step 8: CREATE CONFIGMAP AND SECRET (cci/v2)

```python
# ConfigMap
POST /apis/cci/v2/namespaces/<namespace>/configmaps
{
  "apiVersion": "cci/v2",
  "kind": "ConfigMap",
  "metadata": {"name": "app-config"},
  "data": {"KEY": "value"}
}

# Secret (Opaque)
POST /apis/cci/v2/namespaces/<namespace>/secrets
{
  "apiVersion": "cci/v2",
  "kind": "Secret",
  "metadata": {"name": "app-secret"},
  "type": "Opaque",
  "data": {"KEY": "<base64-value>"}
}
```

### Step 9: VALIDATE

```python
# List pods
GET /apis/cci/v2/namespaces/<namespace>/pods

# Get deployment
GET /apis/cci/v2/namespaces/<namespace>/deployments/<app-name>

# Get network status
GET /apis/yangtse/v2/namespaces/<namespace>/networks/<network-name>

# Pod logs
GET /apis/cci/v2/namespaces/<namespace>/pods/<pod-name>/log
```

Check:
- Pod `status.phase` = `Running`
- Pod `status.containerStatuses[0].ready` = `true`
- Deployment `status.readyReplicas` = `spec.replicas`
- Network `status.status` = `Ready`

### Step 10: CLEANUP

Delete in reverse order:

```python
DELETE /apis/cci/v2/namespaces/<namespace>/deployments/<app-name>
DELETE /apis/cci/v2/namespaces/<namespace>/services/<svc-name>
DELETE /apis/cci/v2/namespaces/<namespace>/configmaps/<cm-name>
DELETE /apis/cci/v2/namespaces/<namespace>/secrets/<secret-name>
DELETE /apis/yangtse/v2/namespaces/<namespace>/networks/<network-name>
DELETE /apis/cci/v2/namespaces/<namespace>
```

Then delete NAT gateway and EIP via hcloud CLI:

```bash
hcloud NAT DeleteNatGateway --cli-region=<region> --nat_gateway_id=<nat-gw-id>
hcloud EIP DeletePublicip --cli-region=<region> --publicip_id=<eip-id>
```

## Using the Helper Script

`assets/cci_api_helper.py` provides a reusable `CCIClient` class:

```python
from cci_api_helper import CCIClient

client = CCIClient(ak, sk, project_id, region)

# Setup namespace + network
client.create_namespace("my-app", domain_id)
client.create_network("my-app", "my-net", domain_id, subnet_id, [sg_id])

# Deploy
client.create_deployment("my-app", "web", "nginx:1.25-alpine")
ok, pod = client.wait_for_pod_ready("my-app")
```

CLI usage:

```bash
python3 cci_api_helper.py --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action setup \
  --namespace my-app --domain-id <DID> \
  --subnet-id <SID> --sg-id <SGID>

python3 cci_api_helper.py --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action deploy \
  --namespace my-app --image nginx:1.25-alpine

python3 cci_api_helper.py --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action status --namespace my-app
```

## Pay-Per-Use Billing

All resources are pay-per-use (no period subscription):

| Resource | Configuration | Billing |
|----------|--------------|---------|
| EIP | `share_type=PER`, `type=5_bgp` | Per-bandwidth, per-hour |
| NAT Gateway | `spec=1` (small) | Per-hour, 10K SNAT connections |
| CCI Pods | Resource requests (cpu/memory) | **Per-second** billing |
| SWR | Storage + traffic | Pay-per-use |
| ConfigMap/Secret | - | Free |

## Limitations

- **Storage**: Only SFS Turbo for persistent volumes (no EVS, no OBS)
- **Workload types**: Deployments, StatefulSets, Jobs, Volcano Jobs (no DaemonSets)
- **Services**: Only LoadBalancer (with ELB) and ExternalName — no ClusterIP/NodePort
- **SWR access**: Internal endpoint (100.125.x.x) may not be reachable from CCI — use Docker Hub or VPC endpoint
- **Resource limits**: Required on all containers (minimum 250m CPU, 512Mi memory)
- **API version**: Must use v2 API (`cci/v2` + `yangtse/v2`) — v1beta1 strips `securityGroups`
- **Namespace store**: v1 (`api/v1`) and v2 (`cci/v2`) namespaces are separate — v2 APIs cannot see v1 namespaces

## References

- `references/cci-v2-api-discovery.md` — Why v1beta1 fails, v2 API endpoint mapping
- `references/huaweicloud-signing.md` — SDK-HMAC-SHA256 signing algorithm details
- `references/cci-networking-v2.md` — Network creation via yangtse/v2 with securityGroups
- `assets/cci_api_helper.py` — Reusable Python CCI client with AK/SK signing
- [CCI Product Page](https://www.huaweicloud.com/intl/en-us/product/cci.html)
- [CCI Documentation](https://support.huaweicloud.com/intl/en-us/cci/index.html)
