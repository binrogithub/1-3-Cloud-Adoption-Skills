---
name: LiteLLM-Huawei-MaaS-Proxy
description: Deploy, configure, validate, troubleshoot, or extend an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1). TRIGGER when the task involves LiteLLM proxy deployment, Docker Compose stack with litellm_config.yaml, Huawei MaaS model routing, virtual key or budget management, Prometheus/Grafana observability for LLM traffic, custom_callbacks.py TTFT/TPOT/ITL metrics, or any reference to `LITELLM_MASTER_KEY`, `HUAWEI_MAAS_API_KEY`, or `docker compose` with this stack.
---

# LiteLLM Huawei MaaS Proxy

Deploy an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1).

This repo ships runtime stack files for deterministic clone-and-run deployment. The file templates below serve as reference for understanding each file or building from scratch when git is not available.

## When to Use

| Situation | Route |
|---|---|
| Deploy the full stack from scratch | Follow **Deployment Workflow** |
| Add or modify a model in the proxy | Follow **Adding a new model** |
| Troubleshoot a broken deployment | Follow **Repair Playbook**, then **Common failure modes** |
| Validate an existing deployment | Follow **Validation Sequence** |
| Manage virtual keys, budgets, or teams | Follow **Virtual key management** |
| Extend observability (custom metrics, dashboards) | Read **Metrics** and **Grafana Dashboard** sections |
| Backup, restore, or reset data | Follow **Operations** |

**When NOT to use:**
- Direct MaaS API calls without proxy (no spend tracking, no rate limiting)
- Non-Huawei LLM providers (this stack is MaaS-specific)
- Multi-host / Kubernetes deployment (this is a single-host Docker Compose stack)

## Required Inputs

Confirm before making changes:

- **Huawei MaaS API key** — from [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/).
- **Huawei MaaS API base** — `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` (ap-southeast-1 / CN-Hong Kong). Do not swap regions without re-validating models and quotas.
- **Explicit MaaS model IDs** to expose (e.g. `glm-5.1`, `deepseek-v4-flash`). Verify in MaaS console — do not guess. If the user only gives one model, prefer explicit routing for that model instead of adding all five.
- **LiteLLM listen port** — default `4000`. Override in `docker-compose.yml` ports section if colliding with an existing service.
- **Prometheus listen port** — default `9090`.
- **Grafana listen port** — default `3000`.
- **Prometheus retention** — default `15d`. Adjust for disk capacity.
- **Whether virtual keys already exist** — if yes, `LITELLM_SALT_KEY` is immutable and cannot be changed.
- **Docker 20.10+ with Compose V2** on the target host.

All of these are collected by `./scripts/init_env.sh` (interactive, `--auto`, or `--ci` mode). The user can always choose manual `.env` editing instead.

## Core Rules

- **Never commit `.env`, real API keys, virtual keys, or bearer tokens.** Secrets live in `.env` (gitignored) with `0600` permissions.
- **Never change `LITELLM_SALT_KEY` after virtual keys exist.** Recovery requires `docker compose down -v` and fresh start.
- **Model names are case-sensitive.** Must match MaaS console exactly.
- **MaaS is region-locked** to `ap-southeast-1`.
- **LiteLLM config is read-only at startup.** Changes require `docker compose restart litellm`.
- **Every model must have non-zero `input_cost_per_token` and `output_cost_per_token`** for budget enforcement to work.
- **Keep master key admin-only.** Mint child virtual keys per team/service/environment.
- **Make proxy the only egress path** for MaaS traffic so budgets, rate limits, and spend logs stay centralized.
- **`STORE_MODEL_IN_DB: True`** — DB models take precedence over config file models.
- **`drop_params: True`** — unsupported parameters silently dropped rather than causing errors.
- **TTFT and ITL custom metrics are streaming-only.**

## Architecture

```
Client → LiteLLM (:4000) → Huawei MaaS (ap-southeast-1)
               │
               ├── PostgreSQL (:5432)  — keys, usage, spend
               ├── Prometheus (:9090)  — /metrics scrape every 15s
               └── Grafana   (:3000)  — pre-built dashboard
```

Startup chain: PostgreSQL (`pg_isready`) → LiteLLM (`/health/liveliness`) → Prometheus (scrape) → Grafana.

Request flow: Client → LiteLLM:4000 → Huawei MaaS. LiteLLM logs usage/spend to PostgreSQL, exposes `/metrics` for Prometheus, returns response.

## Codebase

```
.
├── README.md                                       human-facing overview
├── SKILL.md                                        agent-facing workflow (this file)
├── docker-compose.yml                              4-service orchestrator (references assets/config/)
├── agents/
│   ├── openai.yaml                                 skill interface (OpenAI agent format)
│   └── opencode.md                                 skill interface (OpenCode agent format)
├── assets/config/
│   ├── litellm_config.yaml                         model catalog, tpm/rpm, pricing, callbacks
│   ├── custom_callbacks.py                         TTFT/TPOT/ITL Prometheus histograms
│   ├── prometheus.yml                              15s scrape → litellm:4000
│   ├── .env.example                                environment template
│   └── grafana/
│       └── provisioning/
│           ├── datasources/prometheus.yml           auto-linked Prometheus datasource
│           └── dashboards/
│               ├── dashboards.yml                   file-based provider, 30s refresh
│               └── litellm_overview.json            pre-built overview dashboard
├── references/
│   ├── architecture.md                              topology, services, volumes, environment
│   ├── metrics-and-dashboards.md                    PromQL, custom metrics, Grafana panel config
│   ├── operations.md                                health checks, backup, restart, usage, endpoints
│   └── troubleshooting.md                           repair playbook, failure modes, common mistakes
├── scripts/
│   ├── init_env.sh                                  interactive .env setup (manual or agent-guided)
│   ├── validate_e2e.sh                              12-step end-to-end validation
│   └── generate_secrets.sh                          generate MASTER_KEY, SALT_KEY, passwords
├── .env                                             actual secrets (gitignored)
└── .gitignore                                       only .env
```

### File-by-file reference

| File | Role | Key details |
|---|---|---|
| `docker-compose.yml` | Service orchestration | YAML anchor, 4 services with healthcheck chain, named volumes, mounts from `./assets/config/` |
| `assets/config/litellm_config.yaml` | Model catalog + proxy settings | `openai/` prefix + MaaS endpoint, `tpm`/`rpm` per model, per-token pricing, built-in `prometheus` + custom callback |
| `assets/config/custom_callbacks.py` | Custom Prometheus metrics | `PrometheusTTFTTPOTITL(CustomLogger)`, 3 histograms labeled by `model`, `model_group`, `api_provider` |
| `assets/config/prometheus.yml` | Scrape config | Single job `litellm` at 15s interval |
| `assets/config/grafana/provisioning/datasources/prometheus.yml` | Datasource | Prometheus type, proxy access, `http://prometheus:9090` |
| `assets/config/grafana/provisioning/dashboards/dashboards.yml` | Dashboard provider | File-based, org 1, 30s update interval |
| `assets/config/grafana/provisioning/dashboards/litellm_overview.json` | Pre-built dashboard | UID `litellm-overview`, 10s auto-refresh, template variables: `model`, `datasource` |

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

## Deployment Workflow

Follow in order. Do not skip validation steps.

### 0. Preflight

```bash
docker --version          # expect 20.10+
docker compose version    # expect v2
```

### 1. Install from monorepo

```bash
MONOREPO="https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git"
TEMP_DIR="/home/1-3-Cloud-Adoption-Skills"
LITELLM_DIR="/home/LiteLLM-Huawei-MaaS-Proxy"

git clone --depth 1 "$MONOREPO" "$TEMP_DIR"
cp -r "$TEMP_DIR/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy" "$LITELLM_DIR"
rm -rf "$TEMP_DIR"
cd "$LITELLM_DIR"
```

### 2. Configure `.env`

Two paths — choose one:

**Guided (recommended for agents and first-time deployers):**

```bash
./scripts/init_env.sh              # interactive — prompt for each secret, offer generated defaults
./scripts/init_env.sh --auto       # agent mode — auto-generate all, prompt only for HUAWEI_MAAS_API_KEY
./scripts/init_env.sh --ci         # CI mode — all from env vars, no prompts
```

The script writes `.env` with `0600` permissions, validates required values, and refuses to proceed if `HUAWEI_MAAS_API_KEY` is missing or placeholder.

**Manual (full control over every value):**

```bash
cp assets/config/.env.example .env
./scripts/generate_secrets.sh      # prints secrets to stdout — copy into .env
$EDITOR .env                       # fill HUAWEI_MAAS_API_KEY from ModelArts console
chmod 600 .env
```

Or generate secrets individually:

```bash
python3 -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"   # MASTER_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"            # SALT_KEY, passwords
```

### 3. Pre-deploy validation

Before starting the stack, verify `.env` is complete:

```bash
source .env
for VAR in LITELLM_MASTER_KEY LITELLM_SALT_KEY DB_PASSWORD HUAWEI_MAAS_API_KEY; do
  VAL="${!VAR:-}"
  [ -z "$VAL" ] && echo "MISSING: $VAR" || echo "OK: $VAR (len=${#VAL})"
done
```

If any variable is missing or contains a placeholder, **halt and fix before proceeding.** The stack will fail at runtime with incomplete secrets.

### 4. Start the stack

```bash
docker compose up -d
```

### 5. Wait for healthy services

```bash
docker compose ps
```

All four services must show `healthy` or `running`. LiteLLM has a 40s start period.

### 6. Validate direct MaaS connectivity

```bash
curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" | jq '.data[].id'
```

Expect a list of model IDs. If 403, key is wrong or expired.

### 7. Validate LiteLLM health

```bash
curl -s http://localhost:4000/health/liveliness
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.healthy_count, .unhealthy_count'
```

Expect `unhealthy_count: 0`.

### 8. Validate proxied chat completion

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-5.1", "messages": [{"role": "user", "content": "Reply with OK only."}]}' | jq '.choices[0].message.content'
```

### 9. Validate streaming

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Count to 3."}], "stream": true}' | head -5
```

Expect SSE chunks (`data: {...}`).

### 10. Validate Prometheus metrics

```bash
curl -s http://localhost:4000/metrics | grep -c "litellm_"
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

Expect metric count > 0 and Prometheus target health = `up`.

### 11. Validate Grafana dashboard

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```

Expect `200`.

### 12. Validate virtual key minting

```bash
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models": ["glm-5.1"], "max_budget": 1.0, "duration": "1d"}' | jq '.key'
```

Expect a virtual key starting with `sk-`.

## Validation Sequence

For an existing deployment, run in order:

1. `docker compose ps` — all services healthy
2. `curl http://localhost:4000/health/liveliness` — LiteLLM process up
3. `curl http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"` — upstream reachable per model
4. Chat completion with master key on `glm-5.1` — sync path
5. Streaming completion — SSE path
6. `/key/generate` — mints a virtual key
7. Chat completion with virtual key — multi-user path and budget hooks
8. `/metrics | grep -c litellm_` — metrics flowing
9. Prometheus targets — scraping
10. `http://localhost:3000` — Grafana reachable

## Environment Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | Yes | — | Admin key, must start with `sk-` |
| `LITELLM_SALT_KEY` | Yes | — | Key encryption salt — **immutable after first virtual key** |
| `DB_PASSWORD` | Yes | — | PostgreSQL password for `llmproxy` user |
| `HUAWEI_MAAS_API_KEY` | Yes | — | From ModelArts MaaS console (CN-Hong Kong) |
| `HUAWEI_MAAS_API_BASE` | Yes | — | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| `PROMETHEUS_RETENTION` | No | `15d` | Prometheus TSDB retention period |
| `GRAFANA_PASSWORD` | No | `admin` | Grafana admin password |

## Endpoints

| Service | URL | Auth |
|---|---|---|
| LiteLLM API | `http://localhost:4000` | `Authorization: Bearer <key>` |
| LiteLLM Admin UI | `http://localhost:4000/ui` | Login with `LITELLM_MASTER_KEY` |
| Prometheus | `http://localhost:9090` | None |
| Grafana | `http://localhost:3000` | admin / `GRAFANA_PASSWORD` |

### LiteLLM API routes

| Route | Method | Description |
|---|---|---|
| `/v1/chat/completions` | POST | OpenAI-compatible chat completions |
| `/v1/models` | GET | List available models |
| `/health/liveliness` | GET | Liveness probe (used by healthcheck) |
| `/health` | GET | Per-model health (auth required) |
| `/metrics` | GET | Prometheus metrics endpoint |
| `/key/generate` | POST | Generate scoped virtual key |
| `/key/info` | POST | Get key info |
| `/key/update` | POST | Update key settings |
| `/key/delete` | POST | Delete a key |
| `/model/info` | GET | Model details including pricing (auth required) |
| `/ui` | GET | Admin UI |

## Models

| Name | in / out | RPM | TPM | Cost (in/out per token) |
|---|---|---|---|---|
| `glm-5.1` | 192K / 128K | 30 | 500K | $1.078 / $3.774 × 10⁻⁶ |
| `glm-5` | 192K / 64K | 30 | 500K | $0.809 / $2.965 × 10⁻⁶ |
| `deepseek-v4-pro` | 1M / 128K | 3 | 30K | $1.617 / $3.235 × 10⁻⁶ |
| `deepseek-v4-flash` | 1M / 128K | 3 | 30K | $0.135 / $0.270 × 10⁻⁶ |
| `deepseek-v3.2` | 128K / 32K | 700 | 500K | $0.270 / $0.404 × 10⁻⁶ |

### Model configuration structure

```yaml
- model_name: <public-name>
  litellm_params:
    model: openai/<maas-model-name>
    api_base: os.environ/HUAWEI_MAAS_API_BASE
    api_key: os.environ/HUAWEI_MAAS_API_KEY
    tpm: <tokens-per-minute>
    rpm: <requests-per-minute>
  model_info:
    max_tokens: <total>
    max_input_tokens: <input>
    max_output_tokens: <output>
    input_cost_per_token: <price>
    output_cost_per_token: <price>
```

### Adding a new model

1. Find model name and rate/price info in [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/)
2. Add entry to `model_list` in `assets/config/litellm_config.yaml` following the structure above
3. Ensure `model_name` matches MaaS exactly (case-sensitive)
4. Set `tpm`/`rpm` from MaaS console quotas
5. Set non-zero `input_cost_per_token` and `output_cost_per_token` (per-token, not per-1K)
6. Restart: `docker compose restart litellm`
7. Verify: `curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[].id'`
8. Confirm pricing: `curl -s http://localhost:4000/model/info -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[] | {model: .model_name, input_cost: .input_cost_per_token, output_cost: .output_cost_per_token}'`

### Proxy settings

Configured in `assets/config/litellm_config.yaml` under `litellm_settings`:

| Setting | Value | Meaning |
|---|---|---|
| `num_retries` | 3 | Retry failed calls 3 times per model |
| `request_timeout` | 10 | Raise TimeoutError after 10s |
| `drop_params` | True | Drop unsupported params instead of erroring |
| `set_verbose` | False | Suppress debug logging |
| `callbacks` | `["prometheus", "custom_callbacks.my_prometheus_logger"]` | Built-in Prometheus + custom TTFT/TPOT/ITL |

Under `general_settings`:

| Setting | Value | Meaning |
|---|---|---|
| `database_connection_pool_limit` | 10 | Max DB connections |
| `database_connection_timeout` | 60 | DB connection timeout in seconds |

## Usage

### Chat completion

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-5.1", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Streaming

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Count to 5."}], "stream": true}'
```

### Thinking mode (DeepSeek)

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "Solve step by step."}], "extra_body": {"thinking": {"type": "enabled"}}}'
```

### Python SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="sk-...")
response = client.chat.completions.create(
    model="glm-5.1",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### Virtual key management

```bash
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models": ["glm-5.1", "deepseek-v4-flash"], "max_budget": 10.0, "duration": "30d"}'

curl -s -X POST http://localhost:4000/key/info \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-..."}'

curl -s -X POST http://localhost:4000/key/update \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-...", "max_budget": 50.0}'

curl -s -X POST http://localhost:4000/key/delete \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["sk-..."]}'
```

## Metrics

### Built-in LiteLLM metrics (on `/metrics`)

| Metric | Type | Description |
|---|---|---|
| `litellm_proxy_total_requests_metric` | counter | Total requests |
| `litellm_request_total_latency_metric` | histogram | End-to-end latency |
| `litellm_llm_api_latency_metric` | histogram | Upstream API latency only |
| `litellm_spend_metric` | counter | Cumulative spend (USD) |
| `litellm_input_tokens_metric` | counter | Input tokens |
| `litellm_output_tokens_metric` | counter | Output tokens |
| `litellm_deployment_state` | gauge | 0=healthy, 1=partial, 2=outage |

### Custom metrics (`custom_callbacks.py`)

| Metric | Type | When | Bucket range |
|---|---|---|---|
| `litellm_custom_ttft_seconds` | histogram | Streaming only | 0.01s → 30s |
| `litellm_custom_tpot_seconds` | histogram | Always | 0.001s → 5s |
| `litellm_custom_itl_seconds` | histogram | Streaming only | 0.001s → 5s |

All custom metrics labeled: `model`, `model_group`, `api_provider`.

### Custom callback internals

`PrometheusTTFTTPOTITL(CustomLogger)`:

- **TTFT** = `completion_start_time - api_call_start_time` (streaming only, when > 0)
- **TPOT** = `(end_time - start_time) / output_tokens` (always, when output_tokens > 0)
- **ITL** = `(end_time - completion_start_time) / (output_tokens - 1)` (streaming only, when output_tokens > 1)

### Useful PromQL

```promql
rate(litellm_proxy_total_requests_metric[5m]) * 60
histogram_quantile(0.99, rate(litellm_request_total_latency_metric_bucket[5m]))
rate(litellm_spend_metric[1d])
rate(litellm_input_tokens_metric[5m])*60 + rate(litellm_output_tokens_metric[5m])*60
litellm_deployment_state == 2
histogram_quantile(0.95, rate(litellm_custom_ttft_seconds_bucket[5m]))
rate(litellm_custom_tpot_seconds_sum[5m]) / rate(litellm_custom_tpot_seconds_count[5m])
```

## Grafana Dashboard

Pre-built dashboard (`litellm_overview.json`):

- **Auto-refresh**: 10s
- **Default time range**: Last 1 hour
- **Template variables**: `model` (multi-select), `datasource` (Prometheus selector)
- **Panel sections**: Request Rates, Latency Percentiles, Spend, Token Rates, Deployment State, Custom TTFT/TPOT/ITL

Access at `http://localhost:3000`, login with admin / `GRAFANA_PASSWORD`.

## Operations

### Health checks

```bash
docker compose ps
curl -s http://localhost:4000/health/liveliness
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.healthy_count, .unhealthy_count'
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY"
```

### Backup & restore

```bash
docker compose exec db pg_dump -U llmproxy litellm > backup_$(date +%Y%m%d).sql
cat backup_20260516.sql | docker compose exec -T db psql -U llmproxy litellm
```

### Restart & reset

```bash
docker compose restart litellm
docker compose down && docker compose up -d
docker compose down -v && docker compose up -d
```

### Troubleshooting commands

```bash
docker compose logs litellm
docker compose logs -f litellm
docker compose logs db
docker compose exec db pg_isready -d litellm -U llmproxy
docker compose logs prometheus
docker compose logs grafana
docker volume ls | grep litellm
docker compose exec litellm env | grep -E '^(LITELLM|DB_|HUAWEI|STORE_)'
```

## Repair Playbook

1. **Inspect state** — `docker compose ps` and `docker compose logs litellm --tail 50`
2. **Inspect config** — read `assets/config/litellm_config.yaml` and `.env` before editing
3. **Confirm environment** — verify `.env` contains real MaaS key (not placeholder)
4. **Check DB** — `docker compose exec db pg_isready -d litellm -U llmproxy`
5. **Check LiteLLM health** — `curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"`
6. **Fix the issue** — see Common failure modes below
7. **Restart if config changed** — `docker compose restart litellm`
8. **Re-validate** — run `scripts/validate_e2e.sh` or Validation Sequence

### Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `litellm` keeps restarting | DB not ready or wrong `DB_PASSWORD` | Check `docker compose logs db`, verify `.env` |
| 401 from `/v1/chat/completions` | Wrong or missing API key | Verify `Authorization: Bearer sk-...` header |
| 404 model not found | Model name mismatch | Names are case-sensitive, must match MaaS console |
| No metrics in Prometheus | LiteLLM healthcheck failing | Check `docker compose ps`, ensure litellm healthy |
| `LITELLM_SALT_KEY` error | Salt changed after keys created | Use original salt; if lost, `docker compose down -v` |
| MaaS 403 | Wrong region or expired key | Verify key in [ModelArts console](https://console.huaweicloud.com/modelarts/), region must be `ap-southeast-1` |
| Callback import error | `custom_callbacks.py` not mounted | Check volume mount in `docker-compose.yml` |
| `unhealthy_count > 0` in `/health` | Upstream model unreachable | Check MaaS key, model ID, region; do not add wildcards |
| Budget not consumed | Zero `input_cost_per_token` / `output_cost_per_token` | Set non-zero pricing; verify with `/model/info` |
| Prometheus target down | LiteLLM not healthy or not started | Check healthcheck chain: `db` → `litellm` → `prometheus` |
| Grafana shows no data | Prometheus not scraping or wrong datasource | Check targets; verify datasource URL is `http://prometheus:9090` |
| Virtual key 403 | Key expired, over budget, or model not in allow-list | Check key with `/key/info` |

## Sanitization Rules

- **Never write real secrets into committed files.** Use `.env` (gitignored) with `0600` permissions.
- **In output or documentation**, use placeholders: `sk-<master-key>`, `<maas-api-key>`, `<db-password>`.
- **In configuration demos**, read secrets from env vars (`os.environ/...`) or `$VAR_NAME` placeholders.
- **Mask discovered keys** as `<prefix>...<suffix> (len=N)` or `***redacted***`.
- **LiteLLM may print `api_key` values in startup logs.** Scan after troubleshooting: `docker compose logs litellm 2>&1 | grep -i 'api_key\|sk-'`; set `set_verbose: False` if keys appear.

## Common Mistakes

| Mistake | Why it's wrong | Correct approach |
|---|---|---|
| Committing `.env` to git | Leaks all secrets | `.env` is gitignored; never `git add .env` |
| Changing `LITELLM_SALT_KEY` after creating virtual keys | All existing keys unreadable | Keep original salt; if lost, full reset |
| Giving clients the raw `HUAWEI_MAAS_API_KEY` | Bypasses spend tracking, rate limiting, audit | Mint virtual keys via `/key/generate` |
| Using per-1K-token pricing in `model_info` | LiteLLM expects per-token pricing | Use `input_cost_per_token` (e.g. `0.000001078`, not `0.001078`) |
| Adding a model with zero pricing | Budgets don't consume spend | Set non-zero `input_cost_per_token` and `output_cost_per_token` |
| Guessing model names | MaaS model IDs are case-sensitive | Verify exact name in MaaS console |
| Editing config without restarting | Config is read at startup only | `docker compose restart litellm` after changes |
| Running `docker compose down` expecting data loss | Volumes survive `down` | Use `docker compose down -v` to destroy data |
| Checking `/health/liveliness` instead of `/health` for model status | Liveliness only checks process | Use `/health` with auth for model-level diagnostics |

## Reference: File Templates

Templates for reference — to understand each file's structure or build from scratch when git is not available. When cloning this repo, the actual files take precedence.

### `.gitignore`

```gitignore
.env
```

### `.env.example`

```dotenv
# ── Proxy Auth ───────────────────────────────────
LITELLM_MASTER_KEY="sk-change-me"
LITELLM_SALT_KEY="change-me-to-a-long-random-string"

# ── Database ─────────────────────────────────────
DB_PASSWORD="change-me-to-a-strong-password"

# ── Huawei MaaS ──────────────────────────────────
HUAWEI_MAAS_API_KEY="change-me-to-your-maas-api-key"
HUAWEI_MAAS_API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"

# ── Prometheus ───────────────────────────────────
PROMETHEUS_RETENTION="15d"

# ── Grafana ──────────────────────────────────────
GRAFANA_PASSWORD="change-me-to-a-strong-password"
```

### `docker-compose.yml`

```yaml
x-default: &default
  restart: unless-stopped
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"

services:
  litellm:
    <<: *default
    container_name: litellm_proxy
    image: ghcr.io/berriai/litellm:v1.83.14-stable.patch.3
    ports:
      - "4000:4000"
    volumes:
      - ./assets/config/litellm_config.yaml:/app/config.yaml:ro
      - ./assets/config/custom_callbacks.py:/app/custom_callbacks.py:ro
    environment:
      DATABASE_URL: "postgresql://llmproxy:${DB_PASSWORD}@db:5432/litellm"
      STORE_MODEL_IN_DB: "True"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness')\""]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    command:
      - "--config=/app/config.yaml"

  db:
    <<: *default
    image: postgres:16-alpine
    container_name: litellm_pg_db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U llmproxy"]
      interval: 5s
      timeout: 5s
      retries: 10

  prometheus:
    <<: *default
    image: prom/prometheus:v3.3.1
    container_name: litellm_prometheus
    volumes:
      - ./assets/config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=${PROMETHEUS_RETENTION:-15d}"
    depends_on:
      litellm:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget --spider -q http://localhost:9090/-/healthy || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s

  grafana:
    <<: *default
    image: grafana/grafana:11.5.2
    container_name: litellm_grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./assets/config/grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      prometheus:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget --spider -q http://localhost:3000/api/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 15s

volumes:
  postgres_data:
    name: litellm_postgres_data
  prometheus_data:
    name: litellm_prometheus_data
  grafana_data:
    name: litellm_grafana_data
```

### `litellm_config.yaml`

```yaml
model_list:

  # ───────── Huawei MaaS Models ───────────

  - model_name: glm-5.1
    litellm_params:
      model: openai/glm-5.1
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      tpm: 500000
      rpm: 30
    model_info:
      max_tokens: 198000
      max_input_tokens: 192000
      max_output_tokens: 128000
      input_cost_per_token: 0.000001078
      output_cost_per_token: 0.000003774

  - model_name: glm-5
    litellm_params:
      model: openai/glm-5
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      tpm: 500000
      rpm: 30
    model_info:
      max_tokens: 198000
      max_input_tokens: 192000
      max_output_tokens: 64000
      input_cost_per_token: 0.000000809
      output_cost_per_token: 0.000002965

  - model_name: deepseek-v4-pro
    litellm_params:
      model: openai/deepseek-v4-pro
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      tpm: 30000
      rpm: 3
    model_info:
      max_tokens: 1000000
      max_input_tokens: 1000000
      max_output_tokens: 128000
      input_cost_per_token: 0.000001617
      output_cost_per_token: 0.000003235

  - model_name: deepseek-v4-flash
    litellm_params:
      model: openai/deepseek-v4-flash
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      tpm: 30000
      rpm: 3
    model_info:
      max_tokens: 1000000
      max_input_tokens: 1000000
      max_output_tokens: 128000
      input_cost_per_token: 0.000000135
      output_cost_per_token: 0.00000027

  - model_name: deepseek-v3.2
    litellm_params:
      model: openai/deepseek-v3.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      tpm: 500000
      rpm: 700
    model_info:
      max_tokens: 160000
      max_input_tokens: 128000
      max_output_tokens: 32000
      input_cost_per_token: 0.00000027
      output_cost_per_token: 0.000000404


litellm_settings:
  num_retries: 3
  request_timeout: 10
  drop_params: True
  set_verbose: False
  callbacks:
    - "prometheus"
    - custom_callbacks.my_prometheus_logger
  ui_theme_config:
    logo_url: "https://upload.wikimedia.org/wikipedia/en/thumb/0/04/Huawei_Standard_logo.svg/3840px-Huawei_Standard_logo.svg.png"
    favicon_url: "https://upload.wikimedia.org/wikipedia/en/thumb/0/04/Huawei_Standard_logo.svg/3840px-Huawei_Standard_logo.svg.png"

general_settings:
  database_connection_pool_limit: 10
  database_connection_timeout: 60
```

### `custom_callbacks.py`

```python
"""
Custom LiteLLM callback that emits TTFT, TPOT, and ITL as Prometheus histograms.

TTFT  = completion_start_time - api_call_start_time  (streaming only)
TPOT  = total_latency / output_tokens
ITL   = (end_time - completion_start_time) / max(output_tokens - 1, 1)  (streaming only)
"""

from datetime import datetime
from litellm.integrations.custom_logger import CustomLogger
from prometheus_client import Histogram


def _to_timestamp(val):
    """Convert datetime or numeric to a float unix timestamp."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "timestamp"):
        return val.timestamp()
    return None


class PrometheusTTFTTPOTITL(CustomLogger):
    """Custom callback that emits TTFT, TPOT, and ITL as Prometheus histograms."""

    def __init__(self):
        super().__init__()

        self.ttft = Histogram(
            "litellm_custom_ttft_seconds",
            "Time to first token in seconds (streaming only)",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )

        self.tpot = Histogram(
            "litellm_custom_tpot_seconds",
            "Time per output token in seconds",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
        )

        self.itl = Histogram(
            "litellm_custom_itl_seconds",
            "Inter-token latency in seconds (average between successive tokens, streaming only)",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
        )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            stream = kwargs.get("stream", False)
            completion_start_time = kwargs.get("completion_start_time")
            api_call_start_time = kwargs.get("api_call_start_time")

            slo = kwargs.get("standard_logging_object") or {}
            model = slo.get("model") or kwargs.get("model", "unknown")
            model_group = slo.get("model_group") or model
            api_provider = slo.get("custom_llm_provider") or "unknown"

            labels = {"model": model, "model_group": model_group, "api_provider": api_provider}

            output_tokens = 0
            if response_obj is not None:
                usage = None
                if hasattr(response_obj, "get"):
                    usage = response_obj.get("usage")
                elif hasattr(response_obj, "usage"):
                    usage = response_obj.usage
                if usage is not None:
                    if isinstance(usage, dict):
                        output_tokens = usage.get("completion_tokens", 0) or 0
                    elif hasattr(usage, "completion_tokens"):
                        output_tokens = usage.completion_tokens or 0

            start_ts = _to_timestamp(start_time)
            end_ts = _to_timestamp(end_time)
            api_start_ts = _to_timestamp(api_call_start_time)
            comp_start_ts = _to_timestamp(completion_start_time)

            if stream and api_start_ts and comp_start_ts:
                ttft_seconds = comp_start_ts - api_start_ts
                if ttft_seconds > 0:
                    self.ttft.labels(**labels).observe(ttft_seconds)

            if output_tokens > 0 and start_ts and end_ts:
                total_latency = end_ts - start_ts
                tpot_seconds = total_latency / output_tokens
                self.tpot.labels(**labels).observe(tpot_seconds)

                if stream and comp_start_ts:
                    streaming_duration = end_ts - comp_start_ts
                    if streaming_duration > 0 and output_tokens > 1:
                        itl_seconds = streaming_duration / (output_tokens - 1)
                        self.itl.labels(**labels).observe(itl_seconds)

        except Exception as e:
            print(f"[PrometheusTTFTTPOTITL] Error: {e}")


my_prometheus_logger = PrometheusTTFTTPOTITL()
```

### `prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "litellm"
    static_configs:
      - targets: ["litellm:4000"]
```

### `grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### `grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: LiteLLM
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: false
```

The pre-built `litellm_overview.json` dashboard is at `assets/config/grafana/provisioning/dashboards/litellm_overview.json`.

## Bundled Resources

- [references/architecture.md](references/architecture.md) — topology, services, volumes
- [references/metrics-and-dashboards.md](references/metrics-and-dashboards.md) — PromQL, custom metrics, Grafana
- [references/operations.md](references/operations.md) — health checks, backup, restart, usage
- [references/troubleshooting.md](references/troubleshooting.md) — repair playbook, failure modes
- [scripts/init_env.sh](scripts/init_env.sh) — interactive .env setup (manual, agent-guided, or CI)
- [scripts/validate_e2e.sh](scripts/validate_e2e.sh) — 12-step end-to-end validation
- [scripts/generate_secrets.sh](scripts/generate_secrets.sh) — generate all required secrets
- [agents/openai.yaml](agents/openai.yaml) — skill interface (OpenAI agent format)
- [agents/opencode.md](agents/opencode.md) — skill interface (OpenCode agent format)

## Output Expectations

On completion, leave behind:

- `docker compose ps` with all four services healthy
- `.env` populated with real secrets, `chmod 600`, no placeholders
- Validated: direct MaaS request, proxied request, streaming, metrics, Grafana, virtual key
- Operator note listing: endpoints, file paths, master key location, MaaS region, virtual keys created

## Verification Exit Criteria

- [ ] `.env` exists with all required variables set (no placeholders)
- [ ] `.env` has `0600` permissions
- [ ] `docker compose ps` shows all 4 services healthy
- [ ] `curl http://localhost:4000/health/liveliness` returns 200
- [ ] `/health` with master key returns `unhealthy_count: 0`
- [ ] Chat completion with master key on `glm-5.1` succeeds
- [ ] Streaming completion succeeds
- [ ] `/metrics` returns LiteLLM metrics (count > 0)
- [ ] Prometheus target `litellm` is `up`
- [ ] Grafana returns 200 on port 3000
- [ ] Virtual key generation succeeds
- [ ] No real secrets appear in `git diff`
