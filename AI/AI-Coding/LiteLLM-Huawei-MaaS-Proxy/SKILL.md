---
name: litellm-huawei-maas
description: Build, validate, troubleshoot, or extend a single-host LiteLLM proxy for Huawei ModelArts MaaS using Docker Compose, PostgreSQL, Prometheus, and Grafana. This is a from-scratch workflow: create the stack files locally from the templates below, then deploy and verify them against the ap-southeast-1 MaaS OpenAI-compatible endpoint.
---

# LiteLLM Huawei MaaS Proxy

Create a single-host OpenAI-compatible LiteLLM proxy in front of Huawei ModelArts MaaS with PostgreSQL persistence, Prometheus metrics, and Grafana.

This skill is intentionally **from scratch**. The repository does not bundle `docker-compose.yml`, `litellm_config.yaml`, or the Grafana and Prometheus files for this stack. You create them locally from the templates in this document.

## When to Use

| Situation | Route |
|---|---|
| Build the stack on a new host | Follow **Deployment Workflow** |
| Validate a running stack | Follow **Validation Sequence** |
| Add or change models | Follow **Adding a model** |
| Troubleshoot health, auth, or metrics | Follow **Repair Playbook** |
| Set up virtual keys and budgets | Follow **Virtual key management** |

**When NOT to use:**

- direct MaaS API calling without a proxy
- non-Huawei model providers
- Kubernetes or multi-host deployments

## Required Inputs

Confirm these before making changes:

- Huawei MaaS API key from the ModelArts MaaS console
- MaaS OpenAI-compatible base URL:
  `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
- Docker 20.10+ with Compose V2
- exact model IDs to expose
- whether virtual keys already exist, because `LITELLM_SALT_KEY` becomes immutable after first use

The endpoint uses the `ap-southeast-1` hostname but Huawei documents it as the **CN-Hong Kong** availability for MaaS. Do not swap in a different region URL without re-validating the models and quotas there.

## Core Rules

- Never commit `.env`, API keys, virtual keys, or database passwords.
- Treat `LITELLM_SALT_KEY` as immutable after creating the first virtual key.
- Copy MaaS model IDs exactly; they are case-sensitive.
- Keep non-zero `input_cost_per_token` and `output_cost_per_token` on every exposed model if budgets matter.
- Restart LiteLLM after changing `litellm_config.yaml`.
- Keep `LITELLM_MASTER_KEY` admin-only; issue child virtual keys to users and services.
- Make the proxy the only egress path for MaaS traffic if you need reliable spend and budget enforcement.
- TTFT and ITL metrics are meaningful only for streaming responses.

## Target Layout

Create a fresh working directory such as `~/litellm-huawei-maas/` with this layout:

```text
litellm-huawei-maas/
├── .env.example
├── .gitignore
├── custom_callbacks.py
├── docker-compose.yml
├── litellm_config.yaml
├── prometheus.yml
└── grafana/
    └── provisioning/
        ├── dashboards/
        │   └── dashboards.yml
        └── datasources/
            └── prometheus.yml
```

Create the directories first:

```bash
mkdir -p ~/litellm-huawei-maas/grafana/provisioning/datasources
mkdir -p ~/litellm-huawei-maas/grafana/provisioning/dashboards
cd ~/litellm-huawei-maas
```

## File Templates

### `.gitignore`

```gitignore
.env
```

### `.env.example`

```dotenv
LITELLM_MASTER_KEY="sk-change-me"
LITELLM_SALT_KEY="change-me"
DB_PASSWORD="change-me"
HUAWEI_MAAS_API_KEY="change-me"
HUAWEI_MAAS_API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
PROMETHEUS_RETENTION="15d"
GRAFANA_PASSWORD="change-me"
```

### `docker-compose.yml`

```yaml
x-default: &default
  restart: unless-stopped
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"

services:
  db:
    <<: *default
    image: postgres:16-alpine
    container_name: litellm_pg_db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U llmproxy"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - litellm_postgres_data:/var/lib/postgresql/data

  litellm:
    <<: *default
    image: ghcr.io/berriai/litellm:v1.83.14-stable.patch.3
    container_name: litellm_proxy
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://llmproxy:${DB_PASSWORD}@db:5432/litellm
      STORE_MODEL_IN_DB: "True"
    command: ["--config=/app/config.yaml"]
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "4000:4000"
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness').read()",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    volumes:
      - ./litellm_config.yaml:/app/config.yaml:ro
      - ./custom_callbacks.py:/app/custom_callbacks.py:ro

  prometheus:
    <<: *default
    image: prom/prometheus:v3.3.1
    container_name: litellm_prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=${PROMETHEUS_RETENTION:-15d}
    depends_on:
      litellm:
        condition: service_healthy
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - litellm_prometheus_data:/prometheus

  grafana:
    <<: *default
    image: grafana/grafana:11.5.2
    container_name: litellm_grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
    depends_on:
      - prometheus
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - litellm_grafana_data:/var/lib/grafana

volumes:
  litellm_postgres_data:
  litellm_prometheus_data:
  litellm_grafana_data:
```

### `litellm_config.yaml`

```yaml
model_list:
  - model_name: glm-5.1
    litellm_params:
      model: openai/glm-5.1
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      rpm: 30
      tpm: 500000
    model_info:
      max_tokens: 192000
      max_input_tokens: 192000
      max_output_tokens: 128000
      input_cost_per_token: 0.000001078
      output_cost_per_token: 0.000003774

  - model_name: glm-5
    litellm_params:
      model: openai/glm-5
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      rpm: 30
      tpm: 500000
    model_info:
      max_tokens: 192000
      max_input_tokens: 192000
      max_output_tokens: 64000
      input_cost_per_token: 0.000000809
      output_cost_per_token: 0.000002965

  - model_name: deepseek-v4-pro
    litellm_params:
      model: openai/deepseek-v4-pro
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      rpm: 3
      tpm: 30000
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
      rpm: 3
      tpm: 30000
    model_info:
      max_tokens: 1000000
      max_input_tokens: 1000000
      max_output_tokens: 128000
      input_cost_per_token: 0.000000135
      output_cost_per_token: 0.000000270

  - model_name: deepseek-v3.2
    litellm_params:
      model: openai/deepseek-v3.2
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      rpm: 700
      tpm: 500000
    model_info:
      max_tokens: 128000
      max_input_tokens: 128000
      max_output_tokens: 32000
      input_cost_per_token: 0.000000270
      output_cost_per_token: 0.000000404

litellm_settings:
  num_retries: 3
  request_timeout: 10
  drop_params: true
  set_verbose: false
  callbacks:
    - prometheus
    - custom_callbacks.my_prometheus_logger

general_settings:
  database_connection_pool_limit: 10
  database_connection_timeout: 60
```

### `custom_callbacks.py`

```python
from prometheus_client import Histogram
from litellm.integrations.custom_logger import CustomLogger

TTFT_SECONDS = Histogram(
    "litellm_custom_ttft_seconds",
    "Time to first token for streaming responses",
    ["model", "model_group", "api_provider"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

TPOT_SECONDS = Histogram(
    "litellm_custom_tpot_seconds",
    "Time per output token",
    ["model", "model_group", "api_provider"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

ITL_SECONDS = Histogram(
    "litellm_custom_itl_seconds",
    "Inter-token latency for streaming responses",
    ["model", "model_group", "api_provider"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


class PrometheusTTFTTPOTITL(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        slog = kwargs.get("standard_logging_object") or {}
        model = slog.get("model", kwargs.get("model", "unknown"))
        model_group = slog.get("model_group", model)
        api_provider = slog.get("api_provider", "openai")
        labels = (model, model_group, api_provider)

        usage = getattr(response_obj, "usage", None)
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        completion_start_time = kwargs.get("completion_start_time")
        if completion_start_time is not None:
            ttft = completion_start_time - start_time
            if ttft > 0:
                TTFT_SECONDS.labels(*labels).observe(ttft)

        total_duration = end_time - start_time
        if output_tokens > 0 and total_duration > 0:
            TPOT_SECONDS.labels(*labels).observe(total_duration / output_tokens)

        if completion_start_time is not None and output_tokens > 1:
            streaming_duration = end_time - completion_start_time
            if streaming_duration > 0:
                ITL_SECONDS.labels(*labels).observe(streaming_duration / (output_tokens - 1))


my_prometheus_logger = PrometheusTTFTTPOTITL()
```

### `prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: litellm
    static_configs:
      - targets:
          - litellm:4000
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
    editable: true
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

This minimal dashboard provider is enough for Grafana to start. If you want a prebuilt dashboard, import one manually after the stack is running or add a checked-in JSON file in your own local deployment directory.

## Deployment Workflow

### 1. Create the working directory and files

Create the directories shown above, then write each template exactly as provided.

### 2. Generate secrets

```bash
python3 -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use the first value for `LITELLM_MASTER_KEY`. Use additional generated values for `LITELLM_SALT_KEY`, `DB_PASSWORD`, and `GRAFANA_PASSWORD`.

### 3. Create `.env`

```bash
cp .env.example .env
```

Replace every `change-me` value with a real secret, then:

```bash
chmod 600 .env
```

### 4. Start the stack

```bash
docker compose up -d
docker compose ps
```

Expected service chain:

- `db` becomes healthy first
- `litellm` becomes healthy after DB
- `prometheus` starts after LiteLLM
- `grafana` starts after Prometheus

### 5. Validate direct MaaS connectivity

```bash
set -a
source .env
set +a

curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" | jq '.data[].id'
```

If this fails with 403, fix the MaaS key or region before debugging LiteLLM.

### 6. Validate LiteLLM health

```bash
curl -s http://localhost:4000/health/liveliness

curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq
```

Expected:

- liveliness returns success
- `/health` shows `unhealthy_count` equal to `0`

### 7. Validate sync completion

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5.1","messages":[{"role":"user","content":"Reply with OK only."}]}' \
  | jq -r '.choices[0].message.content'
```

### 8. Validate streaming

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"Count to 3."}],"stream":true}' \
  | head -5
```

Expect server-sent event lines beginning with `data:`.

### 9. Validate metrics

```bash
curl -s http://localhost:4000/metrics | grep -c 'litellm_'
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

Expected:

- metric count greater than zero
- Prometheus target health is `up`

### 10. Validate Grafana

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```

Expected: `200`

### 11. Validate virtual key generation

```bash
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models":["glm-5.1"],"max_budget":1.0,"duration":"1d"}' \
  | jq -r '.key'
```

Expected: a child key beginning with `sk-`

## Validation Sequence

For an existing deployment, run these in order:

1. `docker compose ps`
2. `curl -s http://localhost:4000/health/liveliness`
3. `curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"`
4. sync completion test
5. streaming completion test
6. `/metrics` count check
7. Prometheus target check
8. Grafana HTTP 200 check
9. virtual key generation

## Adding a Model

1. Verify the exact model ID in the MaaS console.
2. Add a new `model_list` entry in `litellm_config.yaml`.
3. Set non-zero `input_cost_per_token` and `output_cost_per_token`.
4. Set `rpm` and `tpm` according to the quota you actually have.
5. Restart LiteLLM:

```bash
docker compose restart litellm
```

6. Verify:

```bash
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.data[].id'
```

## Virtual Key Management

Create a scoped key:

```bash
curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models":["glm-5.1","deepseek-v4-flash"],"max_budget":10.0,"duration":"30d"}'
```

Inspect a key:

```bash
curl -s -X POST http://localhost:4000/key/info \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key":"sk-..."}'
```

## Repair Playbook

1. Inspect current state:

```bash
docker compose ps
docker compose logs litellm --tail 100
docker compose logs db --tail 50
```

2. Re-load the real environment before testing:

```bash
set -a
source .env
set +a
```

3. Check DB readiness:

```bash
docker compose exec db pg_isready -d litellm -U llmproxy
```

4. Check MaaS direct access:

```bash
curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" | jq '.data[].id'
```

5. Check LiteLLM health:

```bash
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq
```

6. Fix the specific issue, then restart LiteLLM if `litellm_config.yaml` changed.

## Common Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `litellm` keeps restarting | DB not ready or wrong DB password | Check DB logs and `.env` |
| 401 from proxy | Wrong master key or child key | Re-check `Authorization` header |
| 404 model not found | Wrong MaaS model ID | Copy exact model name from MaaS console |
| `/health` shows unhealthy models | Wrong MaaS key, model ID, or region | Fix upstream config, not client prompts |
| No metrics in Prometheus | LiteLLM unhealthy or scrape misconfigured | Check `/metrics` and target health |
| Virtual key generation fails after salt change | `LITELLM_SALT_KEY` changed | Restore old salt or rebuild from scratch |
| Budgets do not decrement | Model pricing is zero | Set non-zero token pricing |

## Sanitization Rules

- Keep secrets in `.env`, not in committed files.
- Use placeholders like `sk-...` or `<maas-api-key>` in examples.
- If logs expose secrets during debugging, redact them before sharing.

## Verification Exit Criteria

- [ ] `.env` exists and contains real values
- [ ] `.env` is `0600`
- [ ] all four services are up
- [ ] LiteLLM liveliness succeeds
- [ ] `/health` shows zero unhealthy models
- [ ] sync completion succeeds
- [ ] streaming completion succeeds
- [ ] LiteLLM metrics are exposed
- [ ] Prometheus target is up
- [ ] Grafana returns HTTP 200
- [ ] virtual key generation succeeds
- [ ] no secrets are shown in shared diffs or notes
