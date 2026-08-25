# Huawei Cloud CCI — Serverless Container Migration

Migrate Docker Compose applications to Huawei Cloud CCI (Cloud Container Instance) serverless containers using the v2 API. This guide walks through the complete end-to-end flow: local deployment, destination setup, and migration.

## What is CCI?

CCI (Cloud Container Instance) is Huawei Cloud's serverless container service — similar to AWS Fargate and Azure Container Instances. Key characteristics:

- **Serverless** — no cluster nodes to manage (unlike CCE which requires node pools)
- **Per-second billing** — pay only for the seconds your container is running
- **Scale-to-zero** — containers can scale to zero when idle, cost goes to $0
- **Kubernetes API compatible** — uses standard K8s resource models (Deployments, Services, ConfigMaps, Secrets)
- **v2 API required** — the v1beta1 API strips `securityGroups` from Network spec; must use `cci/v2` for namespaces/workloads and `yangtse/v2` for networks

## Architecture

```
Source (Local)                          Destination (Huawei Cloud CCI)
host:~/app$ docker compose up           CCI Namespace (cci/v2)
  |- nginx (web)          ---------->     |- Deployment: web (nginx:1.25-alpine)
  '- redis (cache)        ---------->     '- Deployment: redis (redis:7-alpine)
                                           Network (yangtse/v2) + NAT Gateway + EIP
```

## Prerequisites

### One-time: CCI Agency Authorization (per region)

This is the ONLY manual console step:

1. Go to `https://console-intl.huaweicloud.com/cci/?region=<region>`
2. Click "Authorize CCI"
3. This creates `cci_admin_trust` and `cci_instance_trust` IAM agencies

### Tools and Credentials

- **Huawei Cloud AK/SK** with CCI permissions
- **Project ID** and **Domain ID** for the target region
- **KooCLI** (`hcloud`) installed and configured
- **Python 3.6+** with PyYAML (`pip install pyyaml`)
- **Docker** + Docker Compose (for the source workload)
- **Existing VPC, Subnet, Security Group** in the target region

## Skills in This Repository

| Skill | Path | Purpose |
|-------|------|---------|
| `cci-cli-deploy` | [`cci/cci-cli-deploy/`](./cci-cli-deploy) | Deploy CCI workloads from the CLI using v2 API with AK/SK signing |
| `docker-compose-to-cci` | [`cci/docker-compose-to-cci/`](./docker-compose-to-cci) | Translate Docker Compose to CCI Deployments and migrate |

**Relationship**: `docker-compose-to-cci` depends on `cci-cli-deploy`. The migration skill uses the same `cci_api_helper.py` for CCI API access. You can also use `cci-cli-deploy` standalone to deploy any container to CCI.

---

## Example Workload (Source)

Let's migrate a simple web application running locally with Docker Compose.

### docker-compose.yaml

```yaml
version: "3.8"

services:
  web:
    image: nginx:1.25-alpine
    ports:
      - "8090:80"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
    restart: always
    cpus: "0.25"
    mem_limit: 512m

  redis:
    image: redis:7-alpine
    restart: always
    cpus: "0.25"
    mem_limit: 256m
```

### Run locally

```bash
docker compose up -d
```

Verify:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090
# -> 200

docker exec <redis-container> redis-cli ping
# -> PONG
```

Both services are running locally. Now let's migrate them to CCI.

---

## Step 1: Discover Infrastructure

Use KooCLI to find existing VPC, subnet, and security group:

```bash
hcloud VPC ListVpcs --cli-region=sa-brazil-1
hcloud VPC ListSubnets --cli-region=sa-brazil-1 --vpc_id=<vpc-id>
hcloud VPC ListSecurityGroups --cli-region=sa-brazil-1
```

Extract these values (needed for all subsequent steps):

| Value | Example | Source |
|-------|---------|---------|
| VPC ID | `d277896b-...` | `ListVpcs` |
| Neutron Subnet ID | `a550f6e0-...` | `ListSubnets` (neutron_subnet_id field) |
| Security Group ID | `e7078087-...` | `ListSecurityGroups` |
| VPC CIDR | `192.168.0.0/16` | `ListVpcs` |
| Project ID | `522793ebec...` | `IAM ListProjects` |
| Domain ID | `248d91ce30...` | `IAM ListDomains` |

---

## Step 2: Setup CCI Destination

Using the **`cci-cli-deploy`** skill to create the destination infrastructure.

### 2a. Create Namespace + Network

```bash
python3 cci-cli-deploy/scripts/cci_api_helper.py \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action setup \
  --namespace my-app \
  --network my-app-net \
  --domain-id <DID> \
  --subnet-id <neutron-subnet-id> \
  --sg-id <sg-id>
```

This creates:
- **Namespace** `my-app` via `POST /apis/cci/v2/namespaces`
- **Network** `my-app-net` via `POST /apis/yangtse/v2/namespaces/my-app/networks` with `securityGroups` and `networkType: "underlay_neutron"`

### 2b. Create NAT Gateway + EIP (for internet access)

CCI pods need a NAT gateway to pull images from Docker Hub:

```bash
# EIP (pay-per-use)
hcloud EIP CreatePublicip --cli-region=sa-brazil-1 \
  --bandwidth.size=5 --bandwidth.share_type=PER \
  --bandwidth.name=cci-nat-bw --publicip.type=5_bgp

# NAT gateway (small, pay-per-use)
hcloud NAT CreateNatGateway --cli-region=sa-brazil-1 \
  --nat_gateway.name=cci-nat-gw \
  --nat_gateway.router_id=<vpc-id> \
  --nat_gateway.internal_network_id=<subnet-id> \
  --nat_gateway.spec=1

# SNAT rule (allows VPC CIDR to access internet)
hcloud NAT CreateNatGatewaySnatRule --cli-region=sa-brazil-1 \
  --snat_rule.nat_gateway_id=<nat-gw-id> \
  --snat_rule.floating_ip_id=<eip-id> \
  --snat_rule.source_type=0 \
  --snat_rule.cidr=192.168.0.0/16
```

---

## Step 3: Migrate

Using the **`docker-compose-to-cci`** skill to translate and deploy all services.

### 3a. Parse (verify the Compose file is understood)

```bash
python3 docker-compose-to-cci/scripts/compose-to-cci.py \
  parse docker-compose.yaml
```

Output:

```
Services: 2
  web: image=nginx:1.25-alpine ports=['8090:80'] env=2
  redis: image=redis:7-alpine ports=[] env=0
```

### 3b. Translate (generate CCI v2 API payloads)

```bash
python3 docker-compose-to-cci/scripts/compose-to-cci.py \
  translate docker-compose.yaml \
  --namespace my-app \
  --output cci-payloads/
```

This generates JSON payloads for each service: Deployment, Service (if ports exposed), and ConfigMap (if environment variables).

### 3c. Full Migration (deploy to CCI)

```bash
python3 docker-compose-to-cci/scripts/compose-to-cci.py \
  migrate docker-compose.yaml \
  --namespace my-app \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 \
  --domain-id <DID> \
  --subnet-id <neutron-subnet-id> \
  --sg-id <sg-id>
```

Output:

```
Creating namespace my-app...
  Namespace: 201 - my-app
Creating network...
  Network: 201 - my-app-net

Translating service: web
  Deployment: 201
  Waiting for pod...
  RUNNING! podIP=192.168.10.102

Translating service: redis
  Deployment: 201
  Waiting for pod...
  RUNNING! podIP=192.168.10.125
```

---

## Step 4: Validate

Verify all pods are running in CCI:

```bash
python3 cci-cli-deploy/scripts/cci_api_helper.py \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action status \
  --namespace my-app
```

Output:

```
  redis-6779d664b6-r8cv5: Running ip=192.168.10.125
  web-66dcfbc98f-sspbs: Running ip=192.168.10.102
```

Both pods are Running with distinct pod IPs. The `web` pod can reach `redis` via internal DNS: `redis.my-app.svc.cluster.local`.

---

## Step 5: Cleanup

### Clean up CCI (destination)

```bash
python3 cci-cli-deploy/scripts/cci_api_helper.py \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action cleanup \
  --namespace my-app
```

Then delete NAT gateway and EIP:

```bash
hcloud NAT DeleteNatGateway --cli-region=sa-brazil-1 --nat_gateway_id=<nat-gw-id>
hcloud EIP DeletePublicip --cli-region=sa-brazil-1 --publicip_id=<eip-id>
```

### Clean up Docker Compose (source)

```bash
docker compose down --remove-orphans
```

---

## Cost Comparison

| Scenario | Docker Compose (local) | CCI (pay-per-use) |
|----------|------------------------|-------------------|
| Web app idle 20h/day | Server always on ($50/mo) | $0 (scale to zero) |
| Web app active 4h/day | Same cost | Pay only 4h x vCPU-seconds |
| CI/CD runner idle 22h/day | Server always on | $0 (scale to zero) |
| Batch job 10 min/day | Server always on | Pay only 10 min/day |

**Key insight**: CCI's per-second billing with scale-to-zero eliminates idle compute costs — the biggest advantage over always-on Docker Compose hosts.

---

## Key Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No ClusterIP or NodePort services | Compose `ports` need LoadBalancer | Create ELB and annotate with `kubernetes.io/elb.id` |
| Only SFS Turbo for persistent storage | No EVS (block) or OBS (object) as PVC | Use SFS Turbo with `storageClassName: sfs-turbo` |
| Resource limits mandatory | Compose files often omit CPU/memory | Script adds defaults: 250m CPU, 512Mi memory |
| SWR internal endpoint may not be reachable | Image pulls from SWR can timeout | Use Docker Hub images with NAT gateway |
| v1beta1 strips securityGroups | Network creation fails with 400 | Always use v2 API (`cci/v2` + `yangtse/v2`) |
| Namespace store separation | v1 namespaces invisible to v2 APIs | Create namespaces via `cci/v2` only |

---

## AI Agent Usage

Both skills can be used as tools by an AI agent (e.g., OpenCode, Claude Code) in a larger migration scenario:

```
User: "Migrate my Docker Compose app to Huawei Cloud CCI"

AI Agent:
  1. Reads docker-compose.yaml
  2. Calls cci-cli-deploy skill:
     - Discovers VPC/subnet/SG via hcloud
     - Creates namespace + network via CCI v2 API
     - Creates NAT gateway + EIP via hcloud
  3. Calls docker-compose-to-cci skill:
     - Parses docker-compose.yaml
     - Translates services to CCI Deployments
     - Deploys via CCI v2 API
     - Waits for pods to be Running
  4. Reports: "Migration complete. 2 pods running on CCI."
```

The skills share `cci_api_helper.py` for CCI API access, so the AI agent can reuse the same authenticated client across both skills.

### Skill Installation

```bash
# Copy skills to opencode skills directory
cp -r cci/cci-cli-deploy ~/.opencode/skills/huaweicloud-cci-cli-deploy
cp -r cci/docker-compose-to-cci ~/.opencode/skills/huaweicloud-docker-compose-to-cci
```

---

## References

- [CCI Product Page](https://www.huaweicloud.com/intl/en-us/product/cci.html)
- [CCI Documentation](https://support.huaweicloud.com/intl/en-us/cci/index.html)
- [`cci-cli-deploy/SKILL.md`](./cci-cli-deploy/SKILL.md) — Complete CCI deployment workflow
- [`docker-compose-to-cci/SKILL.md`](./docker-compose-to-cci/SKILL.md) — Complete migration workflow
- [`cci-cli-deploy/references/cci-v2-api-discovery.md`](./cci-cli-deploy/references/cci-v2-api-discovery.md) — Why v1beta1 fails
- [`cci-cli-deploy/references/huaweicloud-signing.md`](./cci-cli-deploy/references/huaweicloud-signing.md) — SDK-HMAC-SHA256 signing
- [`docker-compose-to-cci/references/translation-table.md`](./docker-compose-to-cci/references/translation-table.md) — Complete field mapping
