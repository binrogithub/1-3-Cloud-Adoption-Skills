# Docker Compose Local Demo (Optional Skill)

## What is this?

This is an **optional** skill that deploys a sample 3-service application locally using Docker Compose. It exists so clients who don't have a `docker-compose.yaml` can experience the full migration flow end-to-end: create a local app → verify it works → migrate to Huawei Cloud CCI.

## When to use

- You want to try the CCI migration but don't have a Docker Compose file
- You want to demo the full migration flow to someone
- You're learning how the migration works

## When NOT to use

- You already have a `docker-compose.yaml` — go directly to the migration skill
- You want to migrate a real application

## Prerequisites

- Docker installed and running
- Port 8080 available on localhost

## What it deploys

A 3-service application:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| web | nginx:1.25-alpine | 8080 | Reverse proxy (exposed to host) |
| api | node:18-alpine | 3000 | Node.js API (internal) |
| db | postgres:15-alpine | 5432 | PostgreSQL database (internal) |

This sample covers the most common migration cases:
- Exposed ports (web:8080) → LoadBalancer + ELB in CCI
- Internal ports (api:3000, db:5432) → no Service in CCI
- Named volume (db-data) → SFS Turbo PVC in CCI
- Environment variables → ConfigMaps in CCI
- depends_on → init containers in CCI
- Health checks → livenessProbes in CCI
- CPU/memory limits → resources.limits in CCI (mandatory)

## How to use

```bash
# In opencode:
> I want to try the migration to CCI

# The AI will:
# 1. Deploy this sample locally
# 2. Verify it works (curl localhost:8080)
# 3. Ask if you're ready to migrate
# 4. Hand off to the migration skill (huaweicloud-docker-compose-to-cci)
```

## After migration

Once the migration to CCI is complete, you can clean up the local demo:

```bash
docker compose down -v
rm docker-compose.yaml
```

## Files

- `assets/sample-compose.yaml` — the 3-service demo application
- `SKILL.md` — instructions for the AI

## Related skills

- `huaweicloud-docker-compose-to-cci` — the migration skill (handoff target)
- `huaweicloud-cci-cli-deploy` — base CCI deployment skill
