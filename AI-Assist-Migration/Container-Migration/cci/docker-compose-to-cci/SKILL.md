---
name: huaweicloud-docker-compose-to-cci
description: Migrate Docker Compose applications to Huawei Cloud CCI (Cloud Container Instance). Parses docker-compose.yaml, translates services to CCI v2 API Deployments, handles images (SWR or Docker Hub), volumes (SFS Turbo), env/secrets (ConfigMaps/Secrets), networking (yangtse/v2 with securityGroups), and services (LoadBalancer with ELB). Builds on the huaweicloud-cci-cli-deploy skill.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: docker-compose-to-cci-migration
  depends_on: huaweicloud-cci-cli-deploy
---

# Docker Compose to CCI Migration (Parser + AI)

Migrate containerized applications from local `docker-compose.yaml` to Huawei Cloud CCI serverless containers. The AI performs the entire translation — no rigid translation script needed. A minimal YAML parser ensures correct parsing; the AI handles all translation logic, intelligent decisions, and edge cases.

**Prerequisite skill**: `huaweicloud-cci-cli-deploy` — covers CCI v2 API, signing, and base deployment flow.

## Architecture: Parser + AI

```
docker-compose.yaml
      |
      |  Parser (yaml.safe_load — deterministic, correct)
      v
  JSON dict (validated)
      |
      |  AI (translation logic — intelligent, adaptive)
      v
  CCI v2 API payloads (JSON)
      |
      |  cci_api_helper.py (deploy)
      v
  CCI namespace + network + workloads
```

The parser handles YAML mechanics (anchors, merge keys, multi-line). The AI handles translation logic (field mapping, resource limits, service types, intelligent decisions like DB→RDS).

## Rules

1. **Parse before translating** — use `compose_parser.py` to get a validated JSON dict. Never parse YAML manually.
2. **One Deployment per Compose service** — each `services.<name>` becomes a CCI Deployment in the same namespace.
3. **Resource limits are mandatory** — map Compose `cpu`/`mem` to CCI `resources.limits`. If not specified, use defaults: `250m` CPU, `512Mi` memory. CCI rejects pods without limits (403).
4. **Images: Docker Hub or SWR** — if `build:` is present, the AI should build the image and push to SWR. If using Docker Hub, ensure NAT gateway is configured.
5. **Volumes → SFS Turbo PVC** — named volumes become PersistentVolumeClaims with `storageClassName: sfs-turbo`. Bind mounts become ConfigMaps or PVCs.
6. **No ClusterIP/NodePort** — Compose `ports` map to CCI LoadBalancer services (require ELB ID).
7. **All pay-per-use** — CCI pods billed per-second, NAT gateway per-hour, EIP per-bandwidth.
8. **Ask the user first** — before deploying, confirm the translation plan with the user. Show what will be created.
9. **Warn on impossible features** — if the Compose uses privileged, host network, devices, etc., warn the user and suggest alternatives. See `references/cci-limitations.md`.

## Prerequisites

### From `huaweicloud-cci-cli-deploy` skill:

1. CCI agency authorized for the region (one-time console step)
2. AK/SK with CCI permissions
3. VPC, Subnet (neutron subnet ID), Security Group discovered
4. NAT gateway + EIP + SNAT rule created (for internet access)
5. `cci_api_helper.py` available in `scripts/`

### Additional for migration:

- Docker installed locally (only if `build:` is present in the Compose file)
- `docker-compose.yaml` file (v2 or v3 format)
- `obsutil` installed (only if migrating volume data)

## Workflow

### Step 0: SOURCE DISCOVERY (ask the user)

Before touching anything, understand the source environment.

**0a. Ask the user:**

```
- "Do you have a docker-compose.yaml?"
  - YES: "What is the path?"
  - NO:  "Would you like to deploy a sample app locally to try the migration?"
         (suggest the docker-compose-local-demo skill)

- "Are there .env files or secrets files?"
- "Are there Dockerfiles (build contexts) in the project?"
- "Is there data in volumes that needs to be migrated to the cloud?"
- "What Huawei Cloud region will you deploy to?"
- "Are your AK/SK credentials configured? (hcloud CLI or environment)"
```

**0b. Inspect the source environment:**

```bash
# Check if Docker is available
docker --version 2>/dev/null && docker compose version 2>/dev/null

# Check if compose is running
docker compose ps 2>/dev/null

# Resolve variables in the compose file
docker compose config 2>/dev/null

# List local images (to know what needs to be pushed to SWR)
docker images

# Check for .env files
ls -la .env .env.* 2>/dev/null

# Check for volume data directories
ls -la ./data/ ./volumes/ 2>/dev/null
```

**0c. Summarize findings to the user before proceeding:**

```
"I found:
 - 3 services: web (nginx), api (node), db (postgres)
 - 1 named volume: db-data (with data to migrate)
 - 2 environment variables, 1 secret
 - 1 build context: ./api/Dockerfile
 - Docker is installed and running
 - Region: sa-brazil-1

 Proceed with migration?"
```

### Step 1: PARSE (deterministic)

Use the parser to get a validated JSON dict:

```bash
python3 scripts/compose_parser.py docker-compose.yaml
```

This outputs a JSON dict with all YAML features resolved (anchors, merge keys, multi-line strings). It also validates:
- Every service has either `image` or `build`
- No duplicate service names
- Warns about features that are impossible in CCI (privileged, host network, etc.)

### Step 2: DISCOVER HUAWEI CLOUD INFRASTRUCTURE

Use hcloud MCP tools to find existing infrastructure:

```
hcloud_list_vpcs(region)
hcloud_list_subnets(region, vpc_id)
hcloud_list_security_groups(region)
hcloud_list_projects()        → project_id
hcloud_list_domains()         → domain_id
```

Extract:
- VPC ID
- Subnet neutron subnet ID
- Security Group ID
- VPC CIDR
- Project ID
- Domain ID

### Step 3: TRANSLATE (AI does the translation)

The AI reads the parsed JSON dict from Step 1 and generates CCI v2 API payloads for each service. Use `references/translation-table.md` as the field mapping guide.

**Translation rules the AI must follow:**

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `services.<name>` | `Deployment` | One per service, apiVersion: cci/v2 |
| `.image` | `containers[].image` | SWR URL or Docker Hub |
| `.ports` | `Service` type=LoadBalancer | Requires ELB ID annotation |
| `.volumes` (named) | `PVC` | `storageClassName: sfs-turbo`, `accessModes: [ReadWriteMany]` |
| `.volumes` (bind mount) | `ConfigMap` or `PVC` | Depends on content |
| `.environment` (dict) | `ConfigMap` + `env[]` | ConfigMap for shared, env for inline |
| `.environment` (list) | `env[]` | Parse KEY=value |
| `.secrets` | `Secret` type=Opaque | Base64 encode values |
| `.env_file` | `ConfigMap` or `Secret` | Parse file, split by sensitivity |
| `.depends_on` | init containers | Wait for dependency readiness |
| `.healthcheck.test [CMD,...]` | `livenessProbe.exec.command` | Remove "CMD" prefix |
| `.healthcheck.interval 30s` | `livenessProbe.periodSeconds: 30` | Strip "s" |
| `.healthcheck.timeout 10s` | `livenessProbe.timeoutSeconds: 10` | Strip "s" |
| `.healthcheck.start_period 40s` | `livenessProbe.initialDelaySeconds: 40` | Strip "s" |
| `.restart: always` | `replicas: 1` | Pod always running |
| `.restart: "no"` | `replicas: 0` | Scale to zero |
| `.restart: on-failure` | `replicas: 1` | CCI doesn't distinguish |
| `.cpus: "0.25"` | `resources.requests.cpu: 250m` | float * 1000, default 250m |
| `.mem_limit: 512m` | `resources.requests.memory: 512Mi` | Normalize: m→Mi, g→Gi |
| `.deploy.resources.limits.cpus` | `resources.limits.cpu` | Compose v3 deploy section |
| `.deploy.resources.limits.memory` | `resources.limits.memory` | Compose v3 deploy section |
| `.command` | `containers[].command` | Direct or split if string |
| `.entrypoint` | `containers[].args` | Direct or wrap in list |
| `networks:` | CCI Network (yangtse/v2) | One per namespace |
| `.build: ./dir` | (build + push to SWR) | AI generates docker build + push commands |

**Always set resource limits** (CCI rejects pods without them):
```json
"resources": {
  "requests": {"cpu": "250m", "memory": "512Mi"},
  "limits": {"cpu": "500m", "memory": "1024Mi"}
}
```

**Intelligent decisions the AI should make:**

1. **Database detection**: if a service uses postgres/mysql/mariadb/mongodb image, suggest migrating to RDS/GaussDB with DRS instead of running as container in CCI. Ask the user.
2. **Redis detection**: if a service uses redis image, suggest DCS (Distributed Cache Service) instead. Ask the user.
3. **Build handling**: if `build:` is present, generate `docker build` + `docker tag` + `docker push` commands to SWR. Replace the image reference in the Deployment with the SWR URL.
4. **Privileged/host warning**: if `privileged: true`, `network_mode: host`, `devices:`, or `cap_add:` are present, warn the user that these are impossible in CCI. See `references/cci-limitations.md`.
5. **Multiple networks**: if the Compose uses multiple isolated networks, warn that CCI supports only one network per namespace. All services will share the same CCI network.
6. **Volume data migration**: if named volumes have local data, generate obsutil commands to upload to OBS, then download to SFS Turbo after PVC creation.

**Generate these CCI resources:**

For each service, the AI generates:
- `Deployment` (cci/v2) — always
- `Service` (cci/v2, LoadBalancer) — only if ports are exposed
- `ConfigMap` (cci/v2) — if environment variables exist
- `Secret` (cci/v2) — if secrets or sensitive env vars exist
- `PVC` (cci/v2, sfs-turbo) — if named volumes exist

Plus shared resources (once):
- `Namespace` (cci/v2) — with domain-id and project-id annotations
- `Network` (yangtse/v2) — with underlay_neutron, securityGroups, subnets

### Step 4: PREPARE INFRASTRUCTURE

**4a. NAT Gateway + EIP + SNAT** (for internet access):

```bash
# EIP
hcloud EIP CreatePublicip --cli-region=<region> \
  --bandwidth.size=5 --bandwidth.share_type=PER \
  --bandwidth.name=cci-nat-bw --publicip.type=5_bgp

# NAT gateway
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

**4b. SWR image push** (if `build:` is present):

```bash
# Get SWR login
hcloud SWR CreateSecret --cli-region=<region> --expire=1000

# Login, tag, push
docker login -u <region>@<AK> -p <SK> swr.<region>.myhuaweicloud.com
docker build -t <app> ./<build-context>
docker tag <app> swr.<region>.myhuaweicloud.com/<org>/<app>:<tag>
docker push swr.<region>.myhuaweicloud.com/<org>/<app>:<tag>
```

**4c. Volume data upload** (if volumes have local data):

```bash
# Upload to OBS
obsutil cp ./<volume-data>/ obs://<bucket>/<volume-data>/ -r -f

# Download to SFS Turbo after PVC is created (Step 5)
# obsutil cp obs://<bucket>/<volume-data>/ /mnt/sfs-turbo/ -r -f
```

### Step 5: DEPLOY

Use `cci_api_helper.py` to deploy all generated resources:

```python
from cci_api_helper import CCIClient

client = CCIClient(ak, sk, project_id, region)

# 5a. Namespace + Network
client.create_namespace(namespace, domain_id)
client.create_network(namespace, f"{namespace}-net", domain_id, neutron_subnet_id, [sg_id])

# 5b. ConfigMaps + Secrets (for each service)
client.create_configmap(namespace, "web-config", {"KEY": "value"})
client.create_secret(namespace, "web-secrets", "Opaque", {"KEY": base64_value})

# 5c. Image Pull Secret (if using SWR)
client.create_image_pull_secret(namespace, "swr-pull-secret", registry, ak, sk)

# 5d. PVCs (for named volumes)
# POST /apis/cci/v2/namespaces/<ns>/persistentvolumeclaims

# 5e. Deployments (for each service)
client.create_deployment(
    namespace=namespace, name="web", image="nginx:1.25-alpine",
    replicas=1, container_port=80,
    cpu_req="250m", mem_req="512Mi",
    cpu_lim="500m", mem_lim="1024Mi",
    image_pull_secret="swr-pull-secret"  # or None
)

# 5f. Services (for exposed ports — requires ELB ID)
client.create_service(
    namespace=namespace, name="web-svc",
    selector={"app": "web"}, port=80, target_port=80,
    elb_id="<elb-id>"
)
```

### Step 6: VALIDATE

```python
# Wait for all pods to be ready
ok, pod = client.wait_for_pod_ready(namespace)
if ok:
    print(f"Running! podIP={pod['status']['podIP']}")
else:
    print("TIMEOUT — check pod logs")

# List all pods
s, r = client.list_pods(namespace)
for p in r.get("items", []):
    print(f"  {p['metadata']['name']}: {p['status']['phase']}")

# Check network
GET /apis/yangtse/v2/namespaces/<ns>/networks/<net-name>
# status.status should be "Ready"

# Check ELB responds
curl http://<elb-public-ip>:<port>
```

**Report to the user:**
```
Migration complete!
 - Namespace: <ns>
 - Services deployed: web, api, db
 - Public URL: http://<elb-ip>:80
 - Pods: all Running
 - Network: Ready

 Warnings:
 - postgres: consider migrating to RDS with DRS for production
 - Volume db-data: 2.3GB uploaded to OBS, downloaded to SFS Turbo
```

### Step 7: CLEANUP (only if user requests)

Delete in reverse order:

```python
client.delete_deployment(namespace, "web")
# Delete services, configmaps, secrets, PVCs...
# Delete network, namespace...
```

Then delete NAT gateway and EIP via hcloud CLI:

```bash
hcloud NAT DeleteNatGateway --cli-region=<region> --nat_gateway_id=<nat-gw-id>
hcloud EIP DeletePublicip --cli-region=<region> --publicip_id=<eip-id>
```

## Using the Parser

```bash
# Parse and validate
python3 scripts/compose_parser.py docker-compose.yaml

# Parse with warnings about CCI-incompatible features
python3 scripts/compose_parser.py docker-compose.yaml --check-cci

# Output to file
python3 scripts/compose_parser.py docker-compose.yaml --output parsed.json
```

## Cost Comparison

| Scenario | Docker Compose (local) | CCI (pay-per-use) |
|----------|----------------------|-------------------|
| Web app idle 20h/day | Server always on | $0 (scale to zero) |
| Web app active 4h/day | Same cost | Pay only 4h x vCPU-seconds |
| CI/CD runner idle 22h/day | Server always on | $0 (scale to zero) |
| Batch job 10 min/day | Server always on | Pay only 10 min/day |

## Limitations

See `references/cci-limitations.md` for the complete list of Docker Compose features that cannot be migrated to CCI and suggested alternatives.

Key limitations:
- **Storage**: Only SFS Turbo for persistent volumes (no EVS, no OBS)
- **Workload types**: Deployments, StatefulSets, Jobs (no DaemonSets)
- **Services**: Only LoadBalancer (with ELB) and ExternalName — no ClusterIP/NodePort
- **SWR access**: Internal endpoint may not be reachable — use Docker Hub or VPC endpoint
- **Resource limits**: Required on all containers (minimum 250m CPU, 512Mi memory)
- **API**: Must use v2 API (`cci/v2` + `yangtse/v2`) — see `huaweicloud-cci-cli-deploy`
- **Privileged/host**: Impossible in serverless — see `references/cci-limitations.md`

## References

- `references/translation-table.md` — Complete field-by-field Docker Compose to CCI mapping
- `references/cci-limitations.md` — What is impossible in CCI and suggested alternatives
- `references/compose-examples.md` — Worked examples (nginx+redis, GitLab runner)
- `references/cci-networking.md` — CCI networking via v2 API
- `references/cci-storage-sfs-turbo.md` — SFS Turbo persistent storage
- `references/docker-compose-to-cci.md` — Additional migration notes
- `scripts/cci_api_helper.py` — Reusable Python CCI client
- `scripts/compose_parser.py` — YAML parser + validation (replaces rigid translation script)
- Depends on: `huaweicloud-cci-cli-deploy` skill
- Optional: `docker-compose-local-demo` skill (for demos without an existing Compose file)
