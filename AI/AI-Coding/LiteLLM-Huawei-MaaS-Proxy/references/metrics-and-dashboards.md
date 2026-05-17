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

## Grafana Dashboard

The pre-built dashboard (`litellm_overview.json`) provides:

- Auto-refresh: 10s, default time range: Last 1 hour
- Template variables: `model` (multi-select), `datasource` (Prometheus selector)
- Panel sections: Request Rates, Latency Percentiles, Spend, Token Rates, Deployment State, Custom TTFT/TPOT/ITL

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

Access at `http://localhost:3000`, login with admin / `GRAFANA_PASSWORD`.
