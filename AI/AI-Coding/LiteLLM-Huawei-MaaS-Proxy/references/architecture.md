# Architecture

## Topology

```
Client → LiteLLM (:4000) → Huawei MaaS (ap-southeast-1)
               │
               ├── PostgreSQL (:5432)  — keys, usage, spend
               ├── Prometheus (:9090)  — /metrics scrape every 15s
               └── Grafana   (:3000)  — pre-built dashboard
```

**Startup chain:** PostgreSQL (`pg_isready`) → LiteLLM (`/health/liveliness`) → Prometheus (scrape) → Grafana

**Request flow:** Client → LiteLLM:4000 → Huawei MaaS. LiteLLM logs usage/spend to PostgreSQL, exposes `/metrics` for Prometheus, returns response.

## Codebase

```
.
├── docker-compose.yml            4 services, healthchecks, named volumes, YAML anchor (references assets/config/)
├── assets/config/
│   ├── litellm_config.yaml       Model catalog (openai/ prefix + MaaS endpoint), tpm/rpm, pricing
│   ├── custom_callbacks.py       PrometheusTTFTTPOTITL — emits ttft/tpot/itl histograms
│   ├── prometheus.yml            15s scrape → litellm:4000
│   ├── .env.example              Template — copy to .env and fill
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml    Auto-linked Prometheus datasource (proxy mode)
│           └── dashboards/
│               ├── dashboards.yml    File-based provider, 30s refresh
│               └── litellm_overview.json  Pre-built dashboard
├── .env                          Actual secrets (gitignored)
└── .gitignore                    Only .env
```

### File-by-file reference

| File | Role | Key details |
|---|---|---|
| `docker-compose.yml` | Service orchestration | YAML anchor for restart/logging, 4 services with healthcheck chain, named volumes, mounts from `./assets/config/` |
| `assets/config/litellm_config.yaml` | Model catalog + proxy settings | Maps `model_name` → `openai/` prefix + MaaS endpoint, tpm/rpm limits, per-token pricing, prometheus + custom callbacks |
| `assets/config/custom_callbacks.py` | Custom Prometheus metrics | `PrometheusTTFTTPOTITL` extends `CustomLogger`, emits 3 histograms labeled by `model`, `model_group`, `api_provider` |
| `assets/config/prometheus.yml` | Scrape config | Single job `litellm` targeting `litellm:4000` at 15s interval |
| `assets/config/grafana/provisioning/datasources/prometheus.yml` | Datasource | Prometheus type, proxy access, `http://prometheus:9090`, default |
| `assets/config/grafana/provisioning/dashboards/dashboards.yml` | Dashboard provider | File-based, org 1, 30s update interval |
| `assets/config/grafana/provisioning/dashboards/litellm_overview.json` | Pre-built dashboard | UID `litellm-overview`, 10s auto-refresh, 1h default time range, `model` and `datasource` template variables |

## Docker Compose Services

| Service | Image | Container name | Port | Healthcheck | Depends on |
|---|---|---|---|---|---|
| `litellm` | `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3` | `litellm_proxy` | `4000:4000` | `GET /health/liveliness` every 30s, 10s timeout, 3 retries, 40s start period | `db` (healthy) |
| `db` | `postgres:16-alpine` | `litellm_pg_db` | (internal 5432) | `pg_isready` every 5s, 5s timeout, 10 retries | — |
| `prometheus` | `prom/prometheus:v3.3.1` | `litellm_prometheus` | `9090:9090` | `GET /-/healthy` every 15s, 5s timeout, 3 retries, 10s start period | `litellm` (healthy) |
| `grafana` | `grafana/grafana:11.5.2` | `litellm_grafana` | `3000:3000` | `GET /api/health` every 15s, 5s timeout, 3 retries, 15s start period | `prometheus` (healthy) |

### Volume mounts

| Service | Host path | Container path | Mode |
|---|---|---|---|
| `litellm` | `./assets/config/litellm_config.yaml` | `/app/config.yaml` | ro |
| `litellm` | `./assets/config/custom_callbacks.py` | `/app/custom_callbacks.py` | ro |
| `db` | `postgres_data` volume | `/var/lib/postgresql/data` | rw |
| `prometheus` | `./assets/config/prometheus.yml` | `/etc/prometheus/prometheus.yml` | ro |
| `prometheus` | `prometheus_data` volume | `/prometheus` | rw |
| `grafana` | `./assets/config/grafana/provisioning` | `/etc/grafana/provisioning` | ro |
| `grafana` | `grafana_data` volume | `/var/lib/grafana` | rw |

### Named volumes

| Volume name | Survives `down`? | Removed by |
|---|---|---|
| `litellm_postgres_data` | Yes | `docker compose down -v` |
| `litellm_prometheus_data` | Yes | `docker compose down -v` |
| `litellm_grafana_data` | Yes | `docker compose down -v` |

### LiteLLM container environment

Set via `env_file: .env` plus explicit `environment`:

| Variable | Source | Value |
|---|---|---|
| `DATABASE_URL` | docker-compose | `postgresql://llmproxy:${DB_PASSWORD}@db:5432/litellm` |
| `STORE_MODEL_IN_DB` | docker-compose | `True` |
| `LITELLM_MASTER_KEY` | .env | Admin key, must start with `sk-` |
| `LITELLM_SALT_KEY` | .env | Key encryption salt |
| `HUAWEI_MAAS_API_KEY` | .env | Huawei MaaS API key |
| `HUAWEI_MAAS_API_BASE` | .env | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |

LiteLLM command: `--config=/app/config.yaml`
