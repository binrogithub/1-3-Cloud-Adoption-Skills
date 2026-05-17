---
name: litellm-huawei-maas
description: Deploy, configure, validate, troubleshoot, or extend an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1). TRIGGER when the task involves LiteLLM proxy deployment, Docker Compose stack with litellm_config.yaml, Huawei MaaS model routing, virtual key or budget management, Prometheus/Grafana observability for LLM traffic, custom_callbacks.py TTFT/TPOT/ITL metrics, or any reference to `LITELLM_MASTER_KEY`, `HUAWEI_MAAS_API_KEY`, or `docker compose` with this stack.
---

# LiteLLM Huawei MaaS Proxy

Deploy an OpenAI-compatible API proxy backed by PostgreSQL, Prometheus, and Grafana, routing through Huawei ModelArts MaaS (ap-southeast-1).

> **5 models included arbitrarily.** Huawei MaaS supports many more — browse the [ModelArts console](https://console.huaweicloud.com/modelarts/) and add them to `litellm_config.yaml`.

## When to Use

| Situation | Route |
|---|---|
| Deploy the full stack from scratch | Follow the **Deployment Workflow** below |
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

- **Huawei MaaS API key** — from [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/), CN-Hong Kong region (`ap-southeast-1`).
- **Huawei MaaS API base URL** — `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`.
- **Docker 20.10+ with Compose V2** on the target host.
- **Explicit model IDs** to expose (e.g. `glm-5.1`, `deepseek-v4-flash`). Do not guess — verify in the MaaS console.
- **Whether virtual keys already exist** — if yes, `LITELLM_SALT_KEY` is immutable and cannot be changed.

If the user only gives one model, prefer explicit routing for that model instead of adding all five.

## Core Rules

- **Never commit `.env`, real API keys, virtual keys, or bearer tokens into version control.** Secrets live in `.env` (gitignored) with `0600` permissions. Config files use `os.environ/...` placeholders.
- **Never change `LITELLM_SALT_KEY` after virtual keys exist.** All keys become unreadable. If lost, the only recovery is `docker compose down -v` and start fresh.
- **Model names are case-sensitive.** Must match MaaS console exactly. A typo in `model_name` causes 404 at runtime.
- **MaaS is region-locked** to `ap-southeast-1`. The `HUAWEI_MAAS_API_BASE` URL must use the correct region endpoint.
- **LiteLLM config is read-only at startup.** Changes to `litellm_config.yaml` require `docker compose restart litellm`.
- **For budget enforcement, every exposed model must have non-zero `input_cost_per_token` and `output_cost_per_token`.** Otherwise successful calls do not consume spend and budgets do not bite.
- **For multi-user proxying, keep the master key admin-only** and mint child virtual keys per team, service, or environment.
- **Make the proxy the only egress path for MaaS traffic** so budgets, rate limits, and spend logs stay centralized. Do not hand out the raw `HUAWEI_MAAS_API_KEY` to clients.
- **`STORE_MODEL_IN_DB: True`** — models are also stored in PostgreSQL, allowing runtime model management via the Admin UI. DB models take precedence over config file models.
- **`drop_params: True`** — unsupported parameters are silently dropped rather than causing errors. This avoids failures when clients send params not supported by MaaS models.
- **TTFT and ITL custom metrics are streaming-only** — non-streaming requests will not emit these histograms.

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
├── docker-compose.yml            4 services, healthchecks, named volumes, YAML anchor for shared config
├── litellm_config.yaml           Model catalog (openai/ prefix + MaaS endpoint), tpm/rpm, pricing, callbacks, Huawei branding
├── custom_callbacks.py           PrometheusTTFTTPOTITL — emits ttft/tpot/itl histograms on /metrics
├── prometheus.yml                15s scrape → litellm:4000
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml    Auto-linked Prometheus datasource (proxy mode, non-editable)
│       └── dashboards/
│           ├── dashboards.yml    File-based provider, 30s refresh, watches /etc/grafana/provisioning/dashboards/
│           └── litellm_overview.json  Pre-built: latency percentiles, spend, token rates, per-minute metrics
├── .env.example                  Template — copy to .env and fill
├── .env                          Actual secrets (gitignored)
└── .gitignore                    Only .env
```

### File-by-file reference

| File | Role | Key details |
|---|---|---|
| `docker-compose.yml` | Service orchestration | YAML anchor `x-default` sets `restart: unless-stopped` + json-file logging (10m max, 3 files). 4 services with healthcheck dependency chain. Named volumes for persistence. |
| `litellm_config.yaml` | Model catalog + proxy settings | Maps public `model_name` → `openai/` provider prefix + MaaS endpoint. Sets `tpm`/`rpm` per model. `model_info` carries token limits and per-token pricing. Callbacks: built-in `prometheus` + `custom_callbacks.my_prometheus_logger`. Huawei logo branding. |
| `custom_callbacks.py` | Custom Prometheus metrics | `PrometheusTTFTTPOTITL` extends `litellm.integrations.custom_logger.CustomLogger`. Module-level instance `my_prometheus_logger` picked up by LiteLLM's `get_instance_fn()`. Emits 3 histograms labeled by `model`, `model_group`, `api_provider`. |
| `prometheus.yml` | Scrape config | Single job `litellm` targeting `litellm:4000` at 15s interval. |
| `grafana/provisioning/datasources/prometheus.yml` | Datasource | Prometheus type, proxy access, `http://prometheus:9090`, default, non-editable. |
| `grafana/provisioning/dashboards/dashboards.yml` | Dashboard provider | File-based, org 1, 30s update interval, watches `/etc/grafana/provisioning/dashboards/`. |
| `grafana/provisioning/dashboards/litellm_overview.json` | Pre-built dashboard | UID `litellm-overview`, 10s auto-refresh, 1h default time range. Template variables: `model` (multi-select, regex `.*` for all), `datasource` (Prometheus). Panels: request rates, latency percentiles, spend, token rates, deployment state, custom TTFT/TPOT/ITL histograms. |

## Docker Compose Services

| Service | Image | Container name | Port | Healthcheck | Depends on |
|---|---|---|---|---|---|
| `litellm` | `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3` | `litellm_proxy` | `4000:4000` | `GET /health/liveliness` every 30s, 10s timeout, 3 retries, 40s start period | `db` (healthy) |
| `db` | `postgres:16-alpine` | `litellm_pg_db` | (internal 5432) | `pg_isready` every 5s, 5s timeout, 10 retries | — |
| `prometheus` | `prom/prometheus:v3.3.1` | `litellm_prometheus` | `9090:9090` | — | `litellm` (healthy) |
| `grafana` | `grafana/grafana:11.5.2` | `litellm_grafana` | `3000:3000` | — | `prometheus` |

### Volume mounts

| Service | Host path | Container path | Mode |
|---|---|---|---|
| `litellm` | `./litellm_config.yaml` | `/app/config.yaml` | ro |
| `litellm` | `./custom_callbacks.py` | `/app/custom_callbacks.py` | ro |
| `db` | `postgres_data` volume | `/var/lib/postgresql/data` | rw |
| `prometheus` | `./prometheus.yml` | `/etc/prometheus/prometheus.yml` | ro |
| `prometheus` | `prometheus_data` volume | `/prometheus` | rw |
| `grafana` | `./grafana/provisioning` | `/etc/grafana/provisioning` | ro |
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

Follow these steps in order. Do not skip validation steps.

### 0. Preflight

Confirm the host has Docker 20.10+ with Compose V2:

```bash
docker --version          # expect 20.10+
docker compose version    # expect v2
```

Confirm you have a Huawei MaaS API key from the [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/) (CN-Hong Kong region).

### 1. Clone and prepare

```bash
git clone <repo-url> && cd litellm-huawei-maas
cp .env.example .env
```

### 2. Generate secrets

```bash
# MASTER_KEY (must start with sk-)
python3 -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"

# SALT_KEY and passwords
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Write `.env`

Fill all required values. Never leave placeholder values in production:

```bash
# ── Proxy Auth ───────────────────────────────────
LITELLM_MASTER_KEY="sk-<generated>"
LITELLM_SALT_KEY="<generated>"

# ── Database ─────────────────────────────────────
DB_PASSWORD="<generated>"

# ── Huawei MaaS ──────────────────────────────────
HUAWEI_MAAS_API_KEY="<from-maas-console>"
HUAWEI_MAAS_API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"

# ── Prometheus ───────────────────────────────────
PROMETHEUS_RETENTION="15d"

# ── Grafana ──────────────────────────────────────
GRAFANA_PASSWORD="<generated>"
```

Set file permissions: `chmod 600 .env`

### 4. Start the stack

```bash
docker compose up -d
```

### 5. Wait for healthy services

```bash
docker compose ps
```

All four services (`litellm`, `db`, `prometheus`, `grafana`) must show `healthy` or `running`. LiteLLM has a 40s start period; wait if still starting.

If `litellm` keeps restarting, check `docker compose logs db` for DB errors and verify `DB_PASSWORD` matches in `.env`.

### 6. Validate direct MaaS connectivity

Confirm the MaaS API key works before blaming LiteLLM:

```bash
curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" | jq '.data[].id'
```

Expect a list of model IDs. If 403, the key is wrong or expired. If connection refused, check outbound network.

### 7. Validate LiteLLM health

```bash
# Liveness (no auth required)
curl -s http://localhost:4000/health/liveliness

# Per-model health (auth required)
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.healthy_count, .unhealthy_count'
```

Expect `unhealthy_count: 0`. If > 0, the MaaS key or model ID is wrong; do not patch around it with wildcards.

### 8. Validate a proxied chat completion

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-5.1", "messages": [{"role": "user", "content": "Reply with OK only."}]}' | jq '.choices[0].message.content'
```

Expect a valid response. If 401, the master key is wrong. If 404, the model name doesn't match.

### 9. Validate streaming

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Count to 3."}], "stream": true}' | head -5
```

Expect SSE chunks (`data: {...}`). This also validates that TTFT and ITL custom metrics will be emitted.

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

Expect `200`. Login at `http://localhost:3000` with admin / `GRAFANA_PASSWORD`. The `LiteLLM Proxy Overview` dashboard should be visible.

### 12. Validate virtual key minting

```bash
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models": ["glm-5.1"], "max_budget": 1.0, "duration": "1d"}' | jq '.key'
```

Expect a virtual key starting with `sk-`. This proves the DB, salt, and budget hooks all work.

## Validation Sequence

When validating an existing deployment (not a fresh install), run these checks in order. Do not skip steps:

1. `docker compose ps` — all services healthy
2. `curl -s http://localhost:4000/health/liveliness` — LiteLLM process up
3. `curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"` — upstream reachable per model
4. `curl -s http://localhost:4000/v1/chat/completions ...` with master key on `glm-5.1` — sync path
5. `curl -s http://localhost:4000/v1/chat/completions ... stream:true` — SSE path
6. `curl -s http://localhost:4000/key/generate ...` — mints a virtual key
7. `curl -s http://localhost:4000/v1/chat/completions ...` with the virtual key — multi-user path and budget hooks
8. `curl -s http://localhost:4000/metrics | grep -c litellm_` — metrics flowing
9. `curl -s http://localhost:9090/api/v1/targets` — Prometheus scraping
10. `curl -s http://localhost:3000` — Grafana reachable

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

### How models are configured

Each model in `litellm_config.yaml` follows this structure:

```yaml
- model_name: <public-name>           # Name exposed to clients
  litellm_params:
    model: openai/<maas-model-name>    # openai/ prefix tells LiteLLM to use OpenAI-compatible provider
    api_base: os.environ/HUAWEI_MAAS_API_BASE  # Resolved from env at runtime
    api_key: os.environ/HUAWEI_MAAS_API_KEY     # Resolved from env at runtime
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

1. Browse the [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/) to find the model name and its rate/price info
2. Add a new entry to the `model_list` array in `litellm_config.yaml` following the structure above
3. Ensure `model_name` matches exactly what MaaS expects (case-sensitive)
4. Set `tpm`/`rpm` from the MaaS console quotas
5. Set `input_cost_per_token` and `output_cost_per_token` (price per token, not per 1K tokens) — **must be non-zero for budget enforcement to work**
6. Restart: `docker compose restart litellm`
7. Verify: `curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[].id'`
8. Confirm pricing: `curl -s http://localhost:4000/model/info -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[] | {model: .model_name, input_cost: .input_cost_per_token, output_cost: .output_cost_per_token}'` — both costs must be > 0

### LiteLLM proxy settings

Configured in `litellm_config.yaml` under `litellm_settings`:

| Setting | Value | Meaning |
|---|---|---|
| `num_retries` | 3 | Retry failed calls 3 times per model |
| `request_timeout` | 10 | Raise TimeoutError after 10s |
| `drop_params` | True | Drop unsupported params instead of erroring |
| `set_verbose` | False | Suppress debug logging |
| `callbacks` | `["prometheus", "custom_callbacks.my_prometheus_logger"]` | Built-in Prometheus + custom TTFT/TPOT/ITL |

Configured under `general_settings`:

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

For multi-user proxying, keep the master key admin-only and mint child keys per team or service:

```bash
# Create a key limited to specific models and budget
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models": ["glm-5.1", "deepseek-v4-flash"], "max_budget": 10.0, "duration": "30d"}'

# Check key info
curl -s -X POST http://localhost:4000/key/info \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-..."}'

# Update key (e.g., increase budget)
curl -s -X POST http://localhost:4000/key/update \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-...", "max_budget": 50.0}'

# Delete a key
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

`custom_callbacks.py` defines `PrometheusTTFTTPOTITL(CustomLogger)`:

- **TTFT** = `completion_start_time - api_call_start_time` (streaming only, observed when > 0)
- **TPOT** = `(end_time - start_time) / output_tokens` (always, when output_tokens > 0)
- **ITL** = `(end_time - completion_start_time) / (output_tokens - 1)` (streaming only, when output_tokens > 1)

Labels are extracted from `kwargs["standard_logging_object"]` with fallbacks to `kwargs` directly. The module-level instance `my_prometheus_logger` is registered in `litellm_config.yaml` as `custom_callbacks.my_prometheus_logger`.

### Useful PromQL

```promql
# Requests per minute
rate(litellm_proxy_total_requests_metric[5m]) * 60

# P99 latency
histogram_quantile(0.99, rate(litellm_request_total_latency_metric_bucket[5m]))

# Daily spend rate
rate(litellm_spend_metric[1d])

# Tokens per minute
rate(litellm_input_tokens_metric[5m])*60 + rate(litellm_output_tokens_metric[5m])*60

# Models in outage
litellm_deployment_state == 2

# P95 TTFT by model
histogram_quantile(0.95, rate(litellm_custom_ttft_seconds_bucket[5m]))

# Average TPOT
rate(litellm_custom_tpot_seconds_sum[5m]) / rate(litellm_custom_tpot_seconds_count[5m])
```

## Grafana Dashboard

The pre-built dashboard (`litellm_overview.json`) provides:

- **Auto-refresh**: 10s
- **Default time range**: Last 1 hour
- **Template variables**: `model` (multi-select, all models by default), `datasource` (Prometheus selector)
- **Panel sections**: Request Rates, Latency Percentiles, Spend, Token Rates, Deployment State, Custom TTFT/TPOT/ITL

Access at `http://localhost:3000`, login with admin / `GRAFANA_PASSWORD`.

## Operations

### Health checks

```bash
# Verify all services healthy
docker compose ps

# Check LiteLLM health directly
curl -s http://localhost:4000/health/liveliness

# Per-model health (auth required)
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.healthy_count, .unhealthy_count'

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Verify MaaS API key works
curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY"
```

### Backup & restore

```bash
# Backup PostgreSQL
docker compose exec db pg_dump -U llmproxy litellm > backup_$(date +%Y%m%d).sql

# Restore PostgreSQL
cat backup_20260516.sql | docker compose exec -T db psql -U llmproxy litellm
```

### Restart & reset

```bash
# Restart just LiteLLM (e.g., after config change)
docker compose restart litellm

# Full restart preserving data
docker compose down && docker compose up -d

# Full reset (destroys ALL data — volumes, DB, metrics, dashboards)
docker compose down -v && docker compose up -d
```

### Troubleshooting commands

```bash
# LiteLLM logs
docker compose logs litellm

# Follow logs in real-time
docker compose logs -f litellm

# Database logs
docker compose logs db

# Check if DB is ready
docker compose exec db pg_isready -d litellm -U llmproxy

# Prometheus logs
docker compose logs prometheus

# Grafana logs
docker compose logs grafana

# List all volumes
docker volume ls | grep litellm

# Inspect a container's env (redacted)
docker compose exec litellm env | grep -E '^(LITELLM|DB_|HUAWEI|STORE_)'
```

## Repair Playbook

When fixing an existing deployment, follow this sequence:

1. **Inspect current state** — `docker compose ps` and `docker compose logs litellm --tail 50`
2. **Inspect current config** — read `litellm_config.yaml` and `.env` before editing; preserve working explicit models
3. **Confirm environment** — verify `.env` still contains the real MaaS key (not a placeholder)
4. **Check DB connectivity** — `docker compose exec db pg_isready -d litellm -U llmproxy`
5. **Check LiteLLM health** — `curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"`
6. **Fix the specific issue** — see Common failure modes below
7. **Restart if config changed** — `docker compose restart litellm`
8. **Re-validate** — run the Validation Sequence

### Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `litellm` keeps restarting | DB not ready or wrong `DB_PASSWORD` | Check `docker compose logs db`, verify `.env` `DB_PASSWORD` matches |
| 401 from `/v1/chat/completions` | Wrong or missing API key | Verify `Authorization: Bearer sk-...` header; check key starts with `sk-` |
| 404 model not found | Model name mismatch | Names are case-sensitive, must match MaaS console exactly |
| No metrics in Prometheus | LiteLLM healthcheck failing | Check `docker compose ps`, ensure litellm is healthy before Prometheus starts |
| `LITELLM_SALT_KEY` error | Salt changed after keys created | Must use original salt; if lost, `docker compose down -v` and start fresh |
| MaaS 403 | Wrong region or expired key | Verify key in [ModelArts console](https://console.huaweicloud.com/modelarts/), region must be `ap-southeast-1` |
| Callback import error | `custom_callbacks.py` not mounted | Check volume mount in `docker-compose.yml` — should be `./custom_callbacks.py:/app/custom_callbacks.py:ro` |
| `unhealthy_count > 0` in `/health` | Upstream model unreachable | Check MaaS key, model ID, and region; do not add wildcards to work around |
| Budget not consumed on successful calls | Model has zero `input_cost_per_token` / `output_cost_per_token` | Set non-zero pricing in `model_info`; verify with `/model/info` |
| Prometheus target down | LiteLLM not healthy or not started | Check healthcheck chain: `db` → `litellm` → `prometheus` |
| Grafana shows no data | Prometheus not scraping or wrong datasource | Check Prometheus targets; verify datasource URL is `http://prometheus:9090` |
| Virtual key 403 | Key expired, over budget, or model not in allow-list | Check key with `/key/info`; verify `models` and `max_budget` |

## Sanitization Rules

- **Never write real API keys, virtual keys, bearer tokens, or database passwords into committed files.** Use `.env` (gitignored) with `0600` permissions.
- **In generated output or documentation**, use placeholders: `sk-<master-key>`, `<maas-api-key>`, `<db-password>`.
- **When demonstrating configuration**, read secrets from environment variables (`os.environ/...`) or `$VAR_NAME` placeholders, never hardcode.
- **Mask discovered keys** as `<prefix>...<suffix> (len=N)` or `***redacted***` in logs and debug output.
- **LiteLLM may print custom `api_key` values in startup logs.** After troubleshooting, scan and scrub: `docker compose logs litellm 2>&1 | grep -i 'api_key\|sk-'` — if keys appear, this is a log-level issue; set `set_verbose: False`.

## Common Mistakes

| Mistake | Why it's wrong | Correct approach |
|---|---|---|
| Committing `.env` to git | Leaks all secrets | `.env` is gitignored; never `git add .env` |
| Changing `LITELLM_SALT_KEY` after creating virtual keys | All existing keys become unreadable | Keep the original salt; if lost, full reset is the only option |
| Giving clients the raw `HUAWEI_MAAS_API_KEY` | Bypasses spend tracking, rate limiting, and audit | Mint virtual keys via `/key/generate` |
| Using per-1K-token pricing in `model_info` | LiteLLM expects per-token pricing | Use `input_cost_per_token` (e.g. `0.000001078`, not `0.001078`) |
| Adding a model with zero pricing | Budgets don't consume spend on successful calls | Always set non-zero `input_cost_per_token` and `output_cost_per_token` |
| Guessing model names | MaaS model IDs are case-sensitive and non-obvious | Verify exact name in MaaS console before adding |
| Editing `litellm_config.yaml` without restarting | Config is read at startup only | `docker compose restart litellm` after any config change |
| Running `docker compose down` and expecting data loss | Volumes survive `down` | Use `docker compose down -v` to destroy data |
| Checking `/health/liveliness` instead of `/health` for model status | Liveliness only checks process; `/health` checks upstream per model | Use `/health` with auth for model-level diagnostics |

## Output Expectations

When completing a deployment task, leave behind:

- A working `docker compose ps` with all four services healthy.
- `.env` populated with real secrets, `chmod 600`, no placeholder values.
- Validated direct MaaS request (step 6 of Deployment Workflow).
- Validated proxied LiteLLM request (step 8).
- Validated streaming request (step 9).
- Validated Prometheus metrics flowing (step 10).
- Validated Grafana dashboard reachable (step 11).
- Validated virtual key minting (step 12).
- A short operator note listing: endpoints, file paths, master key location, MaaS region, and any virtual keys created.

## Verification Exit Criteria

A deployment is complete when all of the following are true:

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
