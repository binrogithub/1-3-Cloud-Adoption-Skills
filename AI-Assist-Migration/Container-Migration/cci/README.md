# Huawei Cloud CCI — Docker Compose to Serverless Container Migration

Migrate Docker Compose applications to Huawei Cloud CCI (Cloud Container Instance) serverless containers. The migration is **fully AI-assisted** — the AI does practically everything, from parsing the Compose file to deploying workloads on CCI.

## What is Docker Compose?

Docker Compose is a tool for defining and running multi-container applications locally via a YAML file (`docker-compose.yaml`). It lets you declare services (containers), volumes, networks, environment variables, ports, and inter-service dependencies in a single file. Ideal for local development and testing, but not designed for scalable production.

## What is Huawei Cloud CCI?

CCI (Cloud Container Instance) is Huawei Cloud's **serverless** container service. Unlike CCE (which manages full Kubernetes clusters), CCI lets you run containers without managing servers or clusters. Pods are billed **per second** and can scale to zero when idle. Managed via the v2 API (`cci/v2` for workloads, `yangtse/v2` for networks).

## Why Migrate?

| Aspect | Docker Compose (local) | CCI (cloud) |
|--------|------------------------|-------------|
| Hosting | Single machine | Serverless (Huawei manages) |
| Idle cost | Server always on | $0 (scale to zero) |
| Scalability | None | Configurable replicas |
| High availability | No | Yes (managed infra) |
| Billing | Fixed server cost | Per second of active pod |

## How the Migration Works

The migration follows these steps, all executed by the AI:

```
Client: "migrate my docker-compose.yaml to CCI"
  |
  |  Step 0: SOURCE DISCOVERY
  |  AI asks: do you have docker-compose? where? any .env? any data?
  |
  |  Step 1: PARSE
  |  AI parses YAML with yaml.safe_load (correct parsing, no errors)
  |
  |  Step 2: DISCOVER HUAWEI CLOUD
  |  AI discovers VPC, subnet, security groups, project ID, domain ID
  |
  |  Step 3: TRANSLATE
  |  AI translates each Compose service to CCI v2 API resources:
  |    services.web  -> Deployment (cci/v2)
  |    .ports        -> Service LoadBalancer + ELB
  |    .volumes      -> PVC SFS Turbo
  |    .environment  -> ConfigMap
  |    .secrets      -> Secret (base64)
  |    .depends_on   -> init containers
  |    .cpu/.mem     -> resources.limits (mandatory in CCI)
  |
  |  Step 4: PREPARE INFRA
  |  AI creates: NAT Gateway + EIP + SNAT (internet), ELB (load balancer)
  |  If build: -> docker build + push to SWR
  |  If volume data -> obsutil upload to OBS -> SFS Turbo
  |
  |  Step 5: DEPLOY
  |  AI deploys: namespace -> network -> configmaps -> secrets
  |    -> deployments -> services
  |
  |  Step 6: VALIDATE
  |  AI verifies: pods Running, network Ready, ELB responds
  |
  v
Result: app running on CCI, public ELB URL
```

## Architecture: Parser + AI

This scenario uses a **Parser + AI** approach instead of a rigid translation script:

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

The parser handles YAML mechanics (anchors, merge keys, multi-line strings). The AI handles all translation logic, intelligent decisions (e.g., suggesting RDS for databases), and edge cases.

## What Gets Translated vs What Cannot

### Automatically translated:

| Docker Compose | CCI v2 API |
|----------------|-----------|
| `services.<name>` | Deployment |
| `.image` | container.image |
| `.ports` | Service LoadBalancer + ELB |
| `.environment` | ConfigMap + env[] |
| `.volumes` (named) | PVC SFS Turbo |
| `.secrets` | Secret (base64) |
| `.depends_on` | init containers |
| `.healthcheck` | livenessProbe |
| `.cpu` / `.mem` | resources.limits (mandatory) |
| `.command` / `.entrypoint` | command / args |
| `.restart: always` | replicas: 1 |
| `.restart: "no"` | replicas: 0 (scale to zero) |

### CCI limitations (cannot be migrated):

| Docker Compose Feature | Reason |
|------------------------|-------|
| `privileged: true` | CCI does not allow privileged pods |
| `network_mode: host` | Serverless, no host namespace |
| `devices` | No device access |
| `cap_add` / `cap_drop` | No Linux capabilities |
| `pid: host` | No host PID namespace |
| DaemonSets | CCI does not support |
| ClusterIP / NodePort | Only LoadBalancer + ExternalName |
| Multiple isolated networks | 1 network per namespace in CCI |

The AI detects these cases, explains why they are impossible, and suggests alternatives (CCE, ECS, RDS, etc.). See [`docker-compose-to-cci/references/cci-limitations.md`](./docker-compose-to-cci/references/cci-limitations.md) for the complete list.

## Skills in This Repository

| Skill | Path | Purpose |
|-------|------|---------|
| `cci-cli-deploy` | [`cci/cci-cli-deploy/`](./cci-cli-deploy) | Deploy CCI workloads from CLI using v2 API with AK/SK signing |
| `docker-compose-to-cci` | [`cci/docker-compose-to-cci/`](./docker-compose-to-cci) | Migrate Docker Compose to CCI (Parser + AI approach) |
| `docker-compose-local-demo` | [`cci/docker-compose-local-demo/`](./docker-compose-local-demo) | **(Optional)** Deploy a sample app locally to try the full migration flow |

**Relationship**: `docker-compose-to-cci` depends on `cci-cli-deploy`. The `docker-compose-local-demo` skill is optional — it deploys a 3-service sample app (nginx + node + postgres) locally so clients without an existing Compose file can experience the migration end-to-end.

---

## Prerequisites

### Required

1. **Huawei Cloud AK/SK** with CCI permissions
2. **docker-compose.yaml** — your application
3. **CCI Agency Authorization** (one-time, per region)
   - Go to: `https://console-intl.huaweicloud.com/cci/?region=<region>`
   - Click "Authorize CCI"
   - This creates IAM agencies `cci_admin_trust` and `cci_instance_trust`

### Optional

- **Docker installed** — needed if `build:` is present (to build and push images to SWR)
- **obsutil** — needed if migrating volume data (upload to OBS -> SFS Turbo)
- **`docker-compose-local-demo` skill** — only if you want to create a demo app from scratch

---

## Quick Start

### Scenario A: You already have docker-compose.yaml

```bash
# 1. Open opencode
opencode

# 2. Request the migration
> migrate my docker-compose.yaml to CCI in sa-brazil-1
```

The AI will ask for:
- Path to docker-compose.yaml
- Whether there are .env files or secrets
- Whether there is volume data to migrate
- AK/SK credentials (if not configured)

### Scenario B: Full demo (no docker-compose.yaml)

```bash
# 1. Open opencode
opencode

# 2. Request a demo
> I want to try the migration to CCI
```

The AI will:
1. Deploy a sample app locally (nginx + node + postgres)
2. Verify it works on localhost
3. Migrate the app to CCI
4. Provide the public URL of the result

### Scenario C: Database migration to RDS

If the AI detects a database container (postgres, mysql, etc.), it will suggest migrating to **RDS** (managed database) using **DRS** (Data Replication Service) instead of running it as a container in CCI. This provides automatic backup, high availability, and scaling.

---

## Example Workload

The `docker-compose-local-demo` skill includes a 3-service sample application:

| Service | Image | Port | CCI Translation |
|---------|-------|------|-----------------|
| web | nginx:1.25-alpine | 8080 | Deployment + Service LoadBalancer + ELB |
| api | node:18-alpine | 3000 | Deployment (internal) |
| db | postgres:15-alpine | 5432 | Deployment + PVC SFS Turbo (or RDS suggestion) |

This sample covers: ports, environment, depends_on, volumes, restart, cpu/mem limits, healthchecks — the most common migration cases.

---

## Cost Comparison

| Scenario | Docker Compose (local) | CCI (pay-per-use) |
|----------|------------------------|-------------------|
| Web app idle 20h/day | Server always on ($50/mo) | $0 (scale to zero) |
| Web app active 4h/day | Same cost | Pay only 4h x vCPU-seconds |
| CI/CD runner idle 22h/day | Server always on | $0 (scale to zero) |
| Batch job 10 min/day | Server always on | Pay only 10 min/day |

All CCI resources are pay-per-use:

| Resource | Configuration | Billing |
|----------|--------------|---------|
| CCI Pods | CPU + memory requests | Per second |
| EIP | 5_bgp, per-bandwidth | Per hour |
| NAT Gateway | spec=1 (small) | Per hour |
| SFS Turbo | PVC storage | Per GB/hour |
| ELB | Load balancer | Per hour |
| ConfigMap / Secret | - | Free |

---

## File Structure

```
cci/
  README.md                                    <- this file
  cci-cli-deploy/                              <- base CCI deployment skill
    SKILL.md
    scripts/cci_api_helper.py
    references/...
    readme.md
  docker-compose-to-cci/                       <- migration skill (Parser + AI)
    SKILL.md
    scripts/
      cci_api_helper.py                        <- shared CCI API client
      compose_parser.py                        <- YAML parser + validator
    references/
      translation-table.md                     <- field-by-field mapping
      compose-examples.md                      <- worked examples
      cci-limitations.md                       <- impossible features + alternatives
      cci-networking.md                        <- networking via v2 API
      cci-storage-sfs-turbo.md                 <- SFS Turbo storage
      docker-compose-to-cci.md                 <- additional notes
    readme.md
  docker-compose-local-demo/                   <- optional demo skill
    SKILL.md
    readme.md
    assets/
      sample-compose.yaml                      <- 3-service sample app
```

---

## AI Agent Usage

Both skills can be used as tools by an AI agent (e.g., OpenCode, Claude Code):

```
User: "Migrate my Docker Compose app to Huawei Cloud CCI"

AI Agent:
  1. Step 0: Asks user about source environment
  2. Step 1: Parses docker-compose.yaml with compose_parser.py
  3. Step 2: Discovers VPC/subnet/SG via hcloud MCP tools
  4. Step 3: Translates services to CCI v2 API payloads (AI does this)
  5. Step 4: Creates NAT gateway + EIP + ELB via hcloud CLI
  6. Step 5: Deploys via cci_api_helper.py (CCI v2 API)
  7. Step 6: Validates pods are Running, network is Ready
  8. Reports: "Migration complete. N pods running on CCI. URL: http://<elb-ip>"
```

### Skill Installation

```bash
# Copy skills to opencode skills directory
cp -r cci/cci-cli-deploy ~/.opencode/skills/huaweicloud-cci-cli-deploy
cp -r cci/docker-compose-to-cci ~/.opencode/skills/huaweicloud-docker-compose-to-cci
cp -r cci/docker-compose-local-demo ~/.opencode/skills/docker-compose-local-demo
```

---

## References

- [CCI Product Page](https://www.huaweicloud.com/intl/en-us/product/cci.html)
- [CCI Documentation](https://support.huaweicloud.com/intl/en-us/cci/index.html)
- [`cci-cli-deploy/SKILL.md`](./cci-cli-deploy/SKILL.md) — CCI deployment workflow
- [`docker-compose-to-cci/SKILL.md`](./docker-compose-to-cci/SKILL.md) — Migration workflow (Parser + AI)
- [`docker-compose-to-cci/references/cci-limitations.md`](./docker-compose-to-cci/references/cci-limitations.md) — CCI limitations and alternatives
- [`docker-compose-to-cci/references/translation-table.md`](./docker-compose-to-cci/references/translation-table.md) — Complete field mapping
- [`docker-compose-local-demo/SKILL.md`](./docker-compose-local-demo/SKILL.md) — Optional demo skill
