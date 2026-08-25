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

# Docker Compose to CCI Migration

Migrate containerized applications from local `docker-compose.yaml` to Huawei Cloud CCI serverless containers. This skill translates Compose services into CCI v2 API resources and deploys them entirely from the terminal.

**Prerequisite skill**: `huaweicloud-cci-cli-deploy` — covers CCI v2 API, signing, and base deployment flow.

## Rules

1. **Parse before translating** — read the entire `docker-compose.yaml` to understand all services, volumes, networks, and dependencies before generating any CCI resources.
2. **One Deployment per Compose service** — each `services.<name>` becomes a CCI Deployment in the same namespace.
3. **Resource limits are mandatory** — map Compose `cpu`/`mem` to CCI `resources.limits`. If not specified, use defaults: `250m` CPU, `512Mi` memory.
4. **Images: Docker Hub or SWR** — if using SWR, create an imagePullSecret. If using Docker Hub, ensure NAT gateway is configured (see `huaweicloud-cci-cli-deploy`).
5. **Volumes → SFS Turbo PVC** — named volumes become PersistentVolumeClaims with `storageClassName: sfs-turbo`. Bind mounts become ConfigMaps or PVCs.
6. **No ClusterIP/NodePort** — Compose `ports` map to CCI LoadBalancer services (require ELB ID).
7. **All pay-per-use** — CCI pods billed per-second, NAT gateway per-hour, EIP per-bandwidth.

## Prerequisites

### From `huaweicloud-cci-cli-deploy` skill:

1. CCI agency authorized for the region (one-time console step)
2. AK/SK with CCI permissions
3. VPC, Subnet (neutron subnet ID), Security Group discovered
4. NAT gateway + EIP + SNAT rule created (for internet access)
5. `cci_api_helper.py` available in `assets/`

### Additional for migration:

- Docker installed locally with images built or pulled
- `docker-compose.yaml` file (v2 or v3 format)
- `yq` or Python `yaml` module for parsing

## Workflow

### Step 1: PARSE DOCKER COMPOSE

Read and analyze the `docker-compose.yaml`:

```bash
# Extract all service names
yq '.services | keys' docker-compose.yaml

# For each service, extract:
yq '.services.<name>.image' docker-compose.yaml      # Image
yq '.services.<name>.ports[]' docker-compose.yaml     # Ports
yq '.services.<name>.volumes[]' docker-compose.yaml   # Volumes
yq '.services.<name>.environment' docker-compose.yaml  # Environment
yq '.services.<name>.depends_on' docker-compose.yaml   # Dependencies
yq '.services.<name>.healthcheck' docker-compose.yaml  # Health check
yq '.services.<name>.restart' docker-compose.yaml      # Restart policy
```

Or use the helper script:

```bash
python3 assets/compose-to-cci.py parse docker-compose.yaml
```

### Step 2: PREPARE IMAGES

**Option A: Docker Hub (simplest, works with NAT gateway)**

No preparation needed — use the image directly in the Deployment spec.

**Option B: SWR (for private images or faster pulls)**

```bash
# Get SWR login credentials
hcloud SWR CreateSecret --cli-region=<region> --expire=1000

# Login to SWR
docker login -u <region>@<AK> -p <SK> swr.<region>.myhuaweicloud.com

# Tag and push each image
docker tag <original-image> swr.<region>.myhuaweicloud.com/<org>/<app>:<tag>
docker push swr.<region>.myhuaweicloud.com/<org>/<app>:<tag>
```

Note: SWR internal endpoint (100.125.x.x) may not be reachable from CCI pods. If image pulls timeout, use Docker Hub instead.

### Step 3: CREATE CCI NAMESPACE + NETWORK

Follow `huaweicloud-cci-cli-deploy` Steps 2-3:

```python
from cci_api_helper import CCIClient

client = CCIClient(ak, sk, project_id, region)
client.create_namespace("my-app", domain_id)
client.create_network("my-app", "my-net", domain_id, neutron_subnet_id, [sg_id])
```

### Step 4: TRANSLATE SERVICES TO CCI DEPLOYMENTS

For each Compose service, generate a CCI Deployment:

```bash
python3 assets/compose-to-cci.py translate docker-compose.yaml --namespace my-app
```

This outputs CCI v2 API JSON payloads for each service. See `references/translation-table.md` for the complete field mapping.

**Translation summary:**

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `services.<name>` | `Deployment` | One per service |
| `.image` | `containers[].image` | SWR URL or Docker Hub |
| `.ports` | `Service` (LoadBalancer) | Requires ELB ID |
| `.volumes` (named) | `PVC` (SFS Turbo) | `storageClassName: sfs-turbo` |
| `.volumes` (bind mount) | `ConfigMap` or `PVC` | Depends on content |
| `.environment` | `ConfigMap` or `env[]` | ConfigMap for shared, env for simple |
| `.secrets` / `.env` | `Secret` | Base64 encode values |
| `.depends_on` | init containers | Or startup ordering |
| `.healthcheck` | `livenessProbe` | Map test/interval/timeout |
| `.restart: always` | `replicas: 1` | Pod always running |
| `.restart: "no"` | `replicas: 0` | Scale to zero |
| `.cpu` | `resources.limits.cpu` | Required, default `250m` |
| `.mem` | `resources.limits.memory` | Required, default `512Mi` |
| `.command` | `containers[].command` | Direct mapping |
| `.entrypoint` | `containers[].args` | Direct mapping |
| `networks:` | CCI Network (yangtse/v2) | One per namespace |

### Step 5: CREATE CONFIGMAPS AND SECRETS

For each service's environment variables and secrets:

```python
# ConfigMap for non-sensitive env vars
client.create_configmap("my-app", "web-config", {
    "ENV": "production",
    "LOG_LEVEL": "info"
})

# Secret for sensitive values
import base64
client.create_secret("my-app", "web-secrets", "Opaque", {
    "API_KEY": base64.b64encode(b"secret-value").decode()
})
```

### Step 6: CREATE IMAGE PULL SECRET (if using SWR)

```python
client.create_image_pull_secret(
    "my-app", "swr-pull-secret",
    "swr.<region>.myhuaweicloud.com",
    ak, sk
)
```

### Step 7: DEPLOY

For each translated service:

```python
client.create_deployment(
    namespace="my-app",
    name="web",
    image="nginx:1.25-alpine",
    replicas=1,
    container_port=80,
    cpu_req="250m", mem_req="512Mi",
    cpu_lim="500m", mem_lim="1024Mi",
    image_pull_secret="swr-pull-secret"  # or None for Docker Hub
)
```

### Step 8: CREATE SERVICES (for exposed ports)

```python
# LoadBalancer (requires existing ELB)
client.create_service(
    namespace="my-app",
    name="web-svc",
    selector={"app": "web"},
    port=80, target_port=80,
    elb_id="<elb-id>"
)
```

### Step 9: VALIDATE

```python
# Wait for all pods to be ready
ok, pod = client.wait_for_pod_ready("my-app")
if ok:
    print(f"Running! podIP={pod['status']['podIP']}")
else:
    print("TIMEOUT")

# List all pods
s, r = client.list_pods("my-app")
for p in r.get("items", []):
    print(f"  {p['metadata']['name']}: {p['status']['phase']}")
```

### Step 10: CLEANUP

```python
# Delete in reverse order
client.delete_deployment("my-app", "web")
# Delete services, configmaps, secrets...
# Delete network, namespace...
```

Then delete NAT gateway and EIP via hcloud CLI.

## Using the Translation Script

```bash
# Parse and show summary
python3 assets/compose-to-cci.py parse docker-compose.yaml

# Generate CCI v2 API payloads
python3 assets/compose-to-cci.py translate docker-compose.yaml \
  --namespace my-app --output cci-payloads/

# Full migration (requires AK/SK)
python3 assets/compose-to-cci.py migrate docker-compose.yaml \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --namespace my-app \
  --domain-id <DID> --subnet-id <SID> --sg-id <SGID>
```

## Cost Comparison

| Scenario | Docker Compose (local) | CCI (pay-per-use) |
|----------|----------------------|-------------------|
| Web app idle 20h/day | Server always on | $0 (scale to zero) |
| Web app active 4h/day | Same cost | Pay only 4h x vCPU-seconds |
| CI/CD runner idle 22h/day | Server always on | $0 (scale to zero) |
| Batch job 10 min/day | Server always on | Pay only 10 min/day |

## Limitations

- **Storage**: Only SFS Turbo for persistent volumes (no EVS, no OBS)
- **Workload types**: Deployments, StatefulSets, Jobs (no DaemonSets)
- **Services**: Only LoadBalancer (with ELB) and ExternalName — no ClusterIP/NodePort
- **SWR access**: Internal endpoint may not be reachable — use Docker Hub or VPC endpoint
- **Resource limits**: Required on all containers (minimum 250m CPU, 512Mi memory)
- **API**: Must use v2 API (`cci/v2` + `yangtse/v2`) — see `huaweicloud-cci-cli-deploy`

## References

- `references/translation-table.md` — Complete field-by-field Docker Compose to CCI mapping
- `references/compose-examples.md` — Worked examples (nginx+redis, GitLab runner)
- `references/cci-networking.md` — CCI networking via v2 API
- `references/cci-storage-sfs-turbo.md` — SFS Turbo persistent storage
- `references/docker-compose-to-cci.md` — Additional migration notes
- `assets/cci_api_helper.py` — Reusable Python CCI client
- `assets/compose-to-cci.py` — Docker Compose to CCI translation script
- Depends on: `huaweicloud-cci-cli-deploy` skill
