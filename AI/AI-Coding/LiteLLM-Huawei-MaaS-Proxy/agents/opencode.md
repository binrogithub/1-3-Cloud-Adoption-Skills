---
name: LiteLLM-Huawei-MaaS-Proxy
description: Deploy, configure, validate, troubleshoot, or extend an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1). TRIGGER when the task involves LiteLLM proxy deployment, Docker Compose stack with litellm_config.yaml, Huawei MaaS model routing, virtual key or budget management, Prometheus/Grafana observability for LLM traffic, custom_callbacks.py TTFT/TPOT/ITL metrics, or any reference to `LITELLM_MASTER_KEY`, `HUAWEI_MAAS_API_KEY`, or `docker compose` with this stack.
version: "1.0"
triggers:
  - litellm
  - huawei-maas
  - docker-compose
  - prometheus
  - grafana
  - virtual-key
  - ttft
  - tpot
  - itl
commands:
  deploy:
    description: "Deploy the full LiteLLM proxy stack from scratch"
    steps:
      - "Run scripts/init_env.sh --auto to configure .env (prompts for MaaS API key)"
      - "Run docker compose up -d"
      - "Run scripts/validate_e2e.sh to verify"
  validate:
    description: "Validate an existing deployment"
    command: "scripts/validate_e2e.sh"
  add-model:
    description: "Add a new model to the proxy"
    steps:
      - "Verify exact model ID in MaaS console"
      - "Add entry to litellm_config.yaml with non-zero pricing"
      - "Run docker compose restart litellm"
      - "Verify with /v1/models endpoint"
  troubleshoot:
    description: "Diagnose and fix a broken deployment"
    reference: "references/troubleshooting.md"
  manage-keys:
    description: "Create, inspect, update, or delete virtual keys"
    reference: "SKILL.md Virtual key management section"
---

# LiteLLM Huawei MaaS Proxy

Deploy an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1).

## Quick Start

```bash
./scripts/init_env.sh --auto       # auto-generate secrets, prompt for MaaS API key
docker compose up -d
./scripts/validate_e2e.sh
```

Or full manual control:

```bash
cp assets/config/.env.example .env
./scripts/generate_secrets.sh
$EDITOR .env
docker compose up -d
./scripts/validate_e2e.sh
```

## Key Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | 4-service Docker stack |
| `assets/config/litellm_config.yaml` | Model catalog + proxy settings |
| `assets/config/custom_callbacks.py` | TTFT/TPOT/ITL Prometheus metrics |
| `scripts/init_env.sh` | Interactive .env setup (manual, agent, or CI) |
| `scripts/validate_e2e.sh` | 12-step end-to-end validation |
| `scripts/generate_secrets.sh` | Secret generation |

## References

- [Architecture](references/architecture.md) — topology, services, volumes
- [Metrics & Dashboards](references/metrics-and-dashboards.md) — PromQL, custom metrics, Grafana
- [Operations](references/operations.md) — health checks, backup, restart, usage
- [Troubleshooting](references/troubleshooting.md) — repair playbook, failure modes
