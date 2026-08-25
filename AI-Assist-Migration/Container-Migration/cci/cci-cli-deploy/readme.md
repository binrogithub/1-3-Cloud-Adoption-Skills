# CCI CLI Deploy

Deploy Huawei Cloud CCI (Cloud Container Instance) workloads entirely from the terminal using the v2 API with AK/SK signing.

## Overview

This skill provides a complete workflow for deploying serverless containers to CCI without console access (except one-time agency authorization). It uses the CCI v2 API (`cci/v2` for namespaces/workloads, `yangtse/v2` for networks) with SDK-HMAC-SHA256 request signing.

## Key Features

- **No console needed** — all operations via CLI and API calls
- **v2 API** — bypasses v1beta1 `securityGroups` stripping bug
- **Pay-per-use** — all resources billed per-second/per-hour
- **Python helper** — reusable `CCIClient` class with signing built-in

## Files

- `SKILL.md` — Complete 10-step deployment workflow
- `scripts/cci_api_helper.py` — Python CCI client with AK/SK signing
- `references/cci-v2-api-discovery.md` — Why v1beta1 fails, v2 API mapping
- `references/huaweicloud-signing.md` — SDK-HMAC-SHA256 algorithm details
- `references/cci-networking-v2.md` — Network creation via yangtse/v2

## Quick Start

```bash
python3 scripts/cci_api_helper.py --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action setup \
  --namespace my-app --domain-id <DID> \
  --subnet-id <SID> --sg-id <SGID>

python3 scripts/cci_api_helper.py --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --action deploy \
  --namespace my-app --image nginx:1.25-alpine
```

## Requirements

- Huawei Cloud AK/SK with CCI permissions
- CCI agency authorized for the target region (one-time console step)
- Python 3.6+
- KooCLI (`hcloud`) for NAT gateway/EIP creation
