# LiteLLM Huawei MaaS Proxy

Build a single-host Docker Compose LiteLLM proxy for Huawei ModelArts MaaS with PostgreSQL, Prometheus, and Grafana.

This skill is a **from-scratch build guide**. This repository path does **not** ship the runtime stack files. The operator creates them locally by following [SKILL.md](./SKILL.md).

## Skill Level

**Level 2 - Tested in production.** The documented stack shape, validation flow, and operational constraints come from a working MaaS proxy deployment, but the repository contribution here is the guide, not a bundled deployment folder.

## Applicable Scenario

Use this when a team needs:

- one OpenAI-compatible endpoint in front of Huawei MaaS
- centralized key control instead of exposing the raw MaaS key
- usage, latency, and spend visibility
- per-team or per-service virtual keys with budgets
- a simple single-host deployment without Kubernetes

This is the observability-focused counterpart to [LiteLLM-SearXNG-AICoding-Gateway-Single-ECS](../LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/), which targets a larger ECS-based coding gateway with SearXNG and `claude-code-router`.

## Business Problem Addressed

- Developers calling MaaS directly bypass cost controls and audit trails.
- Budget enforcement is hard without a proxy-owned key surface.
- Teams cannot see latency, throughput, and spend in one place.
- Troubleshooting upstream model failures is harder without centralized health and metrics.

## Required Cloud and Domain Knowledge

- Huawei Cloud ModelArts MaaS in the `ap-southeast-1` endpoint family
- Docker Compose on Linux
- LiteLLM model routing and virtual keys
- Prometheus and Grafana basics

## Required AI, Tools, and Platforms

| Tool | Version | Purpose |
|---|---|---|
| LiteLLM proxy | `v1.83.14-stable.patch.3` | OpenAI-compatible proxy |
| PostgreSQL | `16-alpine` | Key, usage, and spend persistence |
| Prometheus | `v3.3.1` | Metrics scrape and storage |
| Grafana | `11.5.2` | Dashboarding |
| Docker | `20.10+` + Compose V2 | Runtime |
| Huawei MaaS API | `ap-southeast-1` | Upstream inference |

## Workflow / Method

1. Create an empty working directory on the target host.
2. Create the required files from the templates in [SKILL.md](./SKILL.md):
   `docker-compose.yml`, `.env.example`, `litellm_config.yaml`, `custom_callbacks.py`, `prometheus.yml`, and Grafana provisioning files.
3. Copy `.env.example` to `.env`, fill real secrets, and lock it to `0600`.
4. Start the stack with `docker compose up -d`.
5. Validate direct MaaS access, proxy health, chat completion, streaming, metrics, Grafana reachability, and virtual key generation.
6. Add or change models only after confirming exact MaaS model IDs and non-zero pricing.

## Expected Outputs

- A running 4-service stack: LiteLLM, PostgreSQL, Prometheus, and Grafana
- `http://localhost:4000` serving OpenAI-compatible chat completions
- `/metrics` scraped by Prometheus
- Grafana reachable on `http://localhost:3000`
- Virtual key generation working through LiteLLM

## Validation Method

Use the verification checklist in [SKILL.md](./SKILL.md). The deployment is complete only when all of these are true:

- `.env` contains real values and has `0600` permissions
- LiteLLM liveness and per-model health succeed
- sync and streaming completions succeed
- Prometheus can scrape LiteLLM metrics
- Grafana is reachable
- virtual key generation works

## Reusable Assets

This skill contributes **templates and procedures**, not checked-in runtime assets. The reusable outputs you create locally are:

- `docker-compose.yml`
- `.env.example`
- `litellm_config.yaml`
- `custom_callbacks.py`
- `prometheus.yml`
- `grafana/provisioning/datasources/prometheus.yml`
- `grafana/provisioning/dashboards/dashboards.yml`

## KPIs / Evaluation Metrics

| Metric | Target | Description |
|---|---|---|
| Proxy uptime | `> 99.9%` | Measured by LiteLLM liveliness |
| P99 proxy overhead | `< 50ms` | Proxy overhead above direct MaaS call |
| Spend tracking | `100%` | Every proxied call records usage and cost |
| Metrics freshness | `< 15s` | Driven by Prometheus scrape interval |
| Budget enforcement | `No raw-key bypass` | Clients use virtual keys, not the MaaS key |

## Common Risks and Troubleshooting

| Risk | Impact | Mitigation |
|---|---|---|
| Changing `LITELLM_SALT_KEY` after keys exist | Existing virtual keys break | Treat the salt as immutable after first key |
| Wrong MaaS region or expired key | Upstream 403 | Verify MaaS key and use `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| Wrong model ID | Runtime 404 | Copy the exact model name from the MaaS console |
| Zero model pricing | Budgets do not decrement | Set non-zero `input_cost_per_token` and `output_cost_per_token` |
| Editing config without restart | Changes do not apply | Restart LiteLLM after config edits |
| Assuming files are bundled in this repo | Setup fails immediately | Create each file from the templates in `SKILL.md` |

## Quick Start

Create a fresh working directory such as `~/litellm-huawei-maas/`, then follow [SKILL.md](./SKILL.md) to create the files and run:

```bash
cp .env.example .env
chmod 600 .env
docker compose up -d
docker compose ps
```

## Endpoints

| Service | URL | Auth |
|---|---|---|
| LiteLLM API | `http://localhost:4000` | `Authorization: Bearer <key>` |
| LiteLLM Admin UI | `http://localhost:4000/ui` | Login with `LITELLM_MASTER_KEY` |
| Prometheus | `http://localhost:9090` | None |
| Grafana | `http://localhost:3000` | `admin / GRAFANA_PASSWORD` |
