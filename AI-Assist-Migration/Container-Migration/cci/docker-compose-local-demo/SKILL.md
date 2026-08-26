---
name: docker-compose-local-demo
description: Deploy a sample Docker Compose application locally (nginx + node + postgres) for experimenting with migration to Huawei Cloud CCI. Optional skill — only useful when the user does not have an existing docker-compose.yaml and wants to try the full migration flow end-to-end.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: docker-compose-local-demo
  optional: true
  handoff_to: huaweicloud-docker-compose-to-cci
---

# Docker Compose Local Demo (Optional)

Deploy a 3-service sample application (nginx + node + postgres) locally using Docker Compose. This skill is **optional** — it exists so clients without an existing `docker-compose.yaml` can experience the full migration flow end-to-end: create source environment → verify it works → migrate to CCI.

## When to use

- User says "I want to try the migration to CCI" but has no `docker-compose.yaml`
- User says "deploy a demo app locally"
- User wants to see the full flow: local → cloud

## When NOT to use

- User already has a `docker-compose.yaml` — go directly to `huaweicloud-docker-compose-to-cci`
- User wants to migrate an existing app — skip this skill

## Prerequisites

- Docker installed and running (`docker --version` and `docker compose version`)
- Port 8080 available on localhost

## Rules

1. **Always verify Docker is running** before attempting `docker compose up`.
2. **Use the sample compose file** from `assets/sample-compose.yaml` — do not generate a new one.
3. **Verify the app works** before handing off to the migration skill.
4. **Hand off to `huaweicloud-docker-compose-to-cci`** after the demo is running — do not attempt migration from this skill.

## Workflow

### Step 1: VERIFY DOCKER

```bash
docker --version
docker compose version
docker info 2>/dev/null | grep "Server Version"
```

If Docker is not installed or not running:
```
"Docker is not available. Please install Docker Desktop or Docker Engine:
 - Docker Desktop: https://docs.docker.com/desktop/
 - Docker Engine: https://docs.docker.com/engine/install/

 Then run: sudo systemctl start docker (Linux) or open Docker Desktop (Mac/Windows)"
```

Stop and wait for the user.

### Step 2: COPY SAMPLE COMPOSE FILE

Copy the sample to the user's working directory:

```bash
cp <skill-path>/assets/sample-compose.yaml ./docker-compose.yaml
```

The sample contains 3 services:
- **web**: nginx reverse proxy (port 8080:80)
- **api**: Node.js API server (port 3000, internal)
- **db**: PostgreSQL database (with persistent volume)

This covers the most common migration cases: ports, environment, depends_on, volumes, restart, cpu/mem limits.

### Step 3: START THE APPLICATION

```bash
docker compose up -d
```

Wait for all containers to be running:

```bash
docker compose ps
```

Expected output:
```
NAME                STATUS              PORTS
cci-demo-web-1      running             0.0.0.0:8080->80/tcp
cci-demo-api-1      running             3000/tcp
cci-demo-db-1       running             5432/tcp
```

### Step 4: VERIFY THE APP WORKS

```bash
# Check web responds
curl -s http://localhost:8080 | head -5

# Check API responds
docker compose exec api curl -s http://localhost:3000/health

# Check DB is accepting connections
docker compose exec db pg_isready
```

If any check fails, show logs:
```bash
docker compose logs web
docker compose logs api
docker compose logs db
```

### Step 5: SHOW THE USER

```
Your demo app is running locally:

  Service  | Image              | Port  | Status
  ---------|--------------------|-------|--------
  web      | nginx:1.25-alpine  | 8080  | running
  api      | node:18-alpine     | 3000  | running (internal)
  db       | postgres:15-alpine | 5432  | running (internal)

  Open http://localhost:8080 in your browser to see the app.

  This app has:
   - 1 exposed port (web:8080) → will become LoadBalancer + ELB in CCI
   - 1 named volume (db-data) → will become SFS Turbo PVC in CCI
   - 3 environment variables → will become ConfigMaps in CCI
   - depends_on → will become init containers in CCI
   - CPU/memory limits → required by CCI

  Ready to migrate to Huawei Cloud CCI?
```

### Step 6: HANDOFF TO MIGRATION SKILL

When the user confirms, hand off to `huaweicloud-docker-compose-to-cci`:

```
"Great! The migration skill will now take over.
 It will parse your docker-compose.yaml, translate each service to CCI,
 and deploy to Huawei Cloud."

→ Load skill: huaweicloud-docker-compose-to-cci
→ The migration skill starts at Step 0 (Source Discovery)
→ Since we already know the compose file path and Docker is running,
  some discovery questions can be skipped.
```

### Step 7: CLEANUP LOCAL DEMO (optional, after migration)

After successful migration, offer to clean up the local demo:

```bash
docker compose down -v   # stops containers and removes volumes
rm docker-compose.yaml    # removes the sample file
```

## Sample Application Architecture

```
  Browser → localhost:8080
               |
               v
  ┌─────────────────────────┐
  │   Docker Compose (local) │
  │                          │
  │  ┌──────┐  ┌──────┐     │
  │  │ web  │─▶│ api  │     │
  │  │nginx │  │node  │     │
  │  │:8080 │  │:3000 │     │
  │  └──────┘  └──┬───┘     │
  │                │         │
  │                v         │
  │           ┌──────┐      │
  │           │  db  │      │
  │           │postgres│    │
  │           │:5432 │      │
  │           └──┬───┘      │
  │              │          │
  │              v          │
  │           ┌──────┐     │
  │           │volume│     │
  │           │db-data│    │
  │           └──────┘     │
  └─────────────────────────┘
```

## References

- `assets/sample-compose.yaml` — the 3-service demo application
- Handoff to: `huaweicloud-docker-compose-to-cci` skill
