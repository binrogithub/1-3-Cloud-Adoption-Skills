# Metrics and Dashboards

## Built-in LiteLLM metrics (on `/metrics`)

| Metric | Type | Description |
|---|---|---|
| `litellm_proxy_total_requests_metric` | counter | Total requests |
| `litellm_request_total_latency_metric` | histogram | End-to-end latency |
| `litellm_llm_api_latency_metric` | histogram | Upstream API latency only |
| `litellm_spend_metric` | counter | Cumulative spend (USD) |
| `litellm_input_tokens_metric` | counter | Input tokens |
| `litellm_output_tokens_metric` | counter | Output tokens |
| `litellm_deployment_state` | gauge | 0=healthy, 1=partial, 2=outage |
| `litellm_deployment_success_responses_total` | counter | Successful responses per deployment (label: `litellm_model_name`) |
| `litellm_deployment_failure_responses_total` | counter | Failed responses per deployment (labels: `litellm_model_name`, `exception_status`, `exception_class`) |

> **Label note:** Deployment metrics use `litellm_model_name` (v2), not `model` (v1). Dashboard queries must use `{litellm_model_name=~"$model"}`.

## Deployment-Level Metrics (Multi-Key)

When multiple MaaS API keys are configured, these metrics provide per-deployment visibility:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `litellm_deployment_success_responses_total` | counter | `litellm_model_name` | Successful responses per deployment |
| `litellm_deployment_failure_responses_total` | counter | `litellm_model_name`, `exception_status`, `exception_class` | Failed responses per deployment |
| `litellm_deployment_cooled_down` | gauge | `litellm_model_name` | 1 if deployment is in cooldown, 0 otherwise |
| `litellm_deployment_latency_per_output_token` | histogram | `litellm_model_name` | Latency per output token by deployment |

> **Deployment naming:** With N keys, each model has N deployments named `<model>--maas-key-<N>`. For example, `glm-5.1--maas-key-0`, `glm-5.1--maas-key-1`, etc.

## Deployment-level metrics (multi-key)

When multiple MaaS API keys are configured, LiteLLM exposes per-deployment metrics:

| Metric | Type | Description |
|---|---|---|
| `litellm_deployment_success_responses_total` | counter | Successful responses per deployment, labeled by `litellm_model_name` |
| `litellm_deployment_failure_responses_total` | counter | Failed responses per deployment |
| `litellm_deployment_state` | gauge | Per-deployment health: 0=healthy, 1=partial, 2=outage |
| `litellm_deployment_cooled_down` | gauge | 1 if deployment is in cooldown (too many failures), 0 otherwise |
| `litellm_deployment_latency_per_output_token` | histogram | Latency per output token per deployment |

These metrics allow monitoring individual API key deployments and detecting degraded keys.

## Custom metrics (`custom_callbacks.py`)

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

The module-level instance `my_prometheus_logger` is registered in `litellm_config.yaml` as `custom_callbacks.my_prometheus_logger`.

## Useful PromQL

### General queries

```promql
rate(litellm_proxy_total_requests_metric[5m]) * 60

histogram_quantile(0.99, rate(litellm_request_total_latency_metric_bucket[5m]))

rate(litellm_spend_metric[1d])

rate(litellm_input_tokens_metric[5m])*60 + rate(litellm_output_tokens_metric[5m])*60

litellm_deployment_state == 2

histogram_quantile(0.95, rate(litellm_custom_ttft_seconds_bucket[5m]))

rate(litellm_custom_tpot_seconds_sum[5m]) / rate(litellm_custom_tpot_seconds_count[5m])

sum(litellm_deployment_failure_responses_total) / (sum(litellm_deployment_success_responses_total) + sum(litellm_deployment_failure_responses_total)) * 100
```

### Deployment-level queries (multi-key)

```promql
# Requests per deployment
sum by (litellm_model_name) (rate(litellm_deployment_success_responses_total[5m]))

# Deployments currently in cooldown
sum by (litellm_model_name) (litellm_deployment_cooled_down)

# Per-deployment error rate
sum by (litellm_model_name) (rate(litellm_deployment_failure_responses_total[5m])) 
  / (sum by (litellm_model_name) (rate(litellm_deployment_success_responses_total[5m])) 
     + sum by (litellm_model_name) (rate(litellm_deployment_failure_responses_total[5m]))) * 100

# Per-deployment latency
histogram_quantile(0.95, sum by (litellm_model_name, le) (rate(litellm_deployment_latency_per_output_token_bucket[5m])))

# Count of deployments per model (should be N for all models)
count by (litellm_model_name) (litellm_deployment_cooled_down)

# Request distribution across deployments for a specific model
sum by (litellm_model_name) (rate(litellm_deployment_success_responses_total[5m])) 
  and on (litellm_model_name) litellm_model_name =~ "glm-5.1.*"
```

### Deployment-level PromQL (multi-key)

```promql
# Deployments per model
count(litellm_deployment_state) by (litellm_model_name)

# Request distribution across deployments
sum(increase(litellm_deployment_success_responses_total[5m])) by (litellm_model_name)

# Deployments in cooldown
sum(litellm_deployment_cooled_down)

# Per-deployment P95 latency
histogram_quantile(0.95, sum(rate(litellm_deployment_latency_per_output_token_bucket[5m])) by (le, litellm_model_name))

# Error rate per deployment
sum(rate(litellm_deployment_failure_responses_total[5m])) by (litellm_model_name)
  / (sum(rate(litellm_deployment_success_responses_total[5m])) by (litellm_model_name)
     + sum(rate(litellm_deployment_failure_responses_total[5m])) by (litellm_model_name))
```

## Grafana Dashboard

The pre-built dashboard (`litellm_overview.json`) provides:

- Auto-refresh: 10s, default time range: Last 1 hour
- Template variables: `model` (multi-select), `datasource` (Prometheus selector)
- Panel sections: Request Rates, Latency Percentiles, Spend, Token Rates, Deployment State, Custom TTFT/TPOT/ITL, Deployment Load Balancing

### Deployment Load Balancing panels (multi-key)

When multiple MaaS API keys are configured, the dashboard includes a "Deployment Load Balancing" row with 5 panels:

| Panel | Type | Description |
|---|---|---|
| **Deployments Per Model** | Bar chart | Shows N deployments per model. Useful to verify multi-key config is applied. |
| **Request Distribution** | Pie chart or bar | Per-deployment request counts. Should show even distribution with `simple-shuffle`. |
| **Cooldown Events** | Time series | Deployments temporarily removed from rotation due to failures. Spikes indicate key issues. |
| **Per-Deployment Latency** | Heatmap or time series | Latency breakdown by deployment. Helps identify slow keys. |
| **Deployment Health** | Stat panel | Current health status per deployment (healthy/cooldown). |

These panels use the `litellm_model_name` label which includes the deployment suffix (e.g., `glm-5.1--maas-key-0`)., **Deployment Load Balancing**

### Deployment Load Balancing panels (multi-key)

| Panel | Type | Description |
|---|---|---|
| Deployments Per Model | stat | Number of active deployments per model (N per model with N keys) |
| Request Distribution Across Deployments | piechart | Shows how requests are distributed across deployments |
| Deployment Cooldown Events | stat | Number of deployments currently in cooldown (should be 0) |
| Per-Deployment Latency (P95) | timeseries | P95 latency per deployment to identify slow keys |

### Panel configuration

| Panel | Unit | Decimals | Thresholds |
|---|---|---|---|
| RPS | reqps | 2 | — |
| RPM | none | 0 | — |
| TPS | none | 2 | — |
| TPM | none | 0 | — |
| Total Requests | short | 0 | — |
| Successful Requests | short | 0 | — |
| Failed Requests | short | 0 | — |
| Error Rate | percent | 1 | green <1%, yellow ≥1%, red ≥5% |
| In-Flight Requests | short | 0 | green <10, yellow ≥10, red ≥50 |
| P95 Latency | ms | auto | green <1s, yellow ≥1s, red ≥5s |
| P99 Latency | ms | auto | green <2s, yellow ≥2s, red ≥10s |
| E2E / LLM API Latency | ms | auto | — |
| TTFT / TPOT / ITL | ms | auto | — |
| Spend Per Minute | currencyUSD | 4 | — |
| Total Spend | currencyUSD | 4 | — |
| Deployments Per Model | short | 0 | green ≥1, yellow ≥2, blue ≥3 |
| Deployment Cooldown Events | short | 0 | green=0, red ≥1 |

Access at `http://localhost:3000`, login with admin / `GRAFANA_PASSWORD`.
