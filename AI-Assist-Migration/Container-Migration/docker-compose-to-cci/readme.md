# Docker Compose to CCI Migration

Migrate Docker Compose applications to Huawei Cloud CCI (Cloud Container Instance) using the v2 API.

## Overview

This skill translates `docker-compose.yaml` services into CCI v2 API Deployments and deploys them entirely from the terminal. It builds on the `cci-cli-deploy` skill for base CCI operations.

## Key Features

- **Automated translation** — parse Compose, generate CCI v2 API payloads
- **Full migration** — namespace + network + deployments in one command
- **Field mapping** — complete Docker Compose to CCI translation table
- **Worked examples** — nginx+redis, GitLab runner, multi-service with health checks

## Files

- `SKILL.md` — Complete 10-step migration workflow
- `scripts/cci_api_helper.py` — Python CCI client (from cci-cli-deploy)
- `scripts/compose-to-cci.py` — Docker Compose to CCI translation script
- `references/translation-table.md` — Complete field-by-field mapping
- `references/compose-examples.md` — Worked examples
- `references/cci-networking.md` — CCI networking via v2 API
- `references/cci-storage-sfs-turbo.md` — SFS Turbo persistent storage
- `references/docker-compose-to-cci.md` — Additional migration notes

## Quick Start

```bash
# Parse and summarize
python3 scripts/compose-to-cci.py parse docker-compose.yaml

# Full migration
python3 scripts/compose-to-cci.py migrate docker-compose.yaml \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --namespace my-app \
  --domain-id <DID> --subnet-id <SID> --sg-id <SGID>
```

## Dependencies

- `cci-cli-deploy` skill (CCI v2 API, signing, base deployment)
- Python 3.6+ with PyYAML (`pip install pyyaml`)
