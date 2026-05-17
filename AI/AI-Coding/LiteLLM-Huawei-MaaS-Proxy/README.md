# LiteLLM Huawei MaaS Proxy

Docker Compose deployment of [LiteLLM](https://github.com/BerriAI/litellm) as an OpenAI-compatible API proxy, routing through **Huawei ModelArts MaaS** (ap-southeast-1) with PostgreSQL persistence, Prometheus metrics, and Grafana dashboards.

> This config includes 5 models selected arbitrarily. Huawei MaaS supports many more — browse the [ModelArts MaaS console](https://console.huaweicloud.com/modelarts/) to discover and add additional models to `litellm_config.yaml`.

For the full agent-facing deployment workflow, validation sequence, repair playbook, and exit criteria, see [SKILL.md](./SKILL.md).

## Skill Level

**Level 2 — Tested in production.** Proxy validated with real MaaS traffic, spend tracking confirmed, custom metrics operational, Grafana dashboard in daily use.

## Applicable Scenario

Single-host AI gateway for teams that need centralized key management, spend tracking, rate limiting, and LLM traffic observability on Huawei Cloud MaaS — without the complexity of a full ECS deployment with SearXNG and claude-code-router.

This is the **observability-focused counterpart** to [LiteLLM-SearXNG-AICoding-Gateway-Single-ECS](../LiteLLM-SearXNG-AICoding-Gateway-Single-ECS/). That skill targets a single ECS with SearXNG search MCP and claude-code-router integration. This skill targets a simpler Docker Compose stack focused on proxy + metrics + dashboards.

## Business Problem Addressed

- **No centralized control** over MaaS API key usage — every developer uses the raw key directly, bypassing spend tracking and rate limiting.
- **No visibility** into LLM latency, token throughput, or cost per model — issues are discovered late or not at all.
- **No way to enforce budgets** per team or service — a single runaway client can consume the entire MaaS quota.
- **No audit trail** — who called which model, when, and at what cost is untracked.

## Required Cloud and Domain Knowledge

- Huawei Cloud ModelArts MaaS (ap-southeast-1 region)
- Docker Compose on a single Linux host
- Prometheus + Grafana observability fundamentals
- LiteLLM proxy configuration (model routing, callbacks, virtual keys)

## Required AI, Tools, and Platforms

| Tool | Version | Purpose |
|---|---|---|
| LiteLLM proxy | v1.83.14-stable.patch.3 | OpenAI-compatible API gateway |
| PostgreSQL | 16-alpine | Key storage, usage logs, spend records |
| Prometheus | v3.3.1 | LLM metrics scraping and TSDB |
| Grafana | 11.5.2 | Pre-built latency/spend/token dashboard |
| Huawei MaaS API | ap-southeast-1 | Upstream LLM inference |
| Docker | 20.10+ with Compose V2 | Container orchestration |

## Workflow / Method

1. **Clone and configure** — copy `.env.example` to `.env`, generate secrets, fill MaaS credentials.
2. **Deploy** — `docker compose up -d`. Healthcheck-gated startup chain: PostgreSQL → LiteLLM → Prometheus → Grafana.
3. **Validate** — 12-step validation sequence (see SKILL.md): direct MaaS check, proxy health, chat completion, streaming, metrics, dashboard, virtual key minting.
4. **Operate** — mint virtual keys per team/service with budget and model restrictions. Monitor via Grafana dashboard or PromQL.
5. **Extend** — add models from MaaS console to `litellm_config.yaml`, restart LiteLLM, verify pricing is non-zero.

## Expected Outputs

- Running 4-service Docker Compose stack (LiteLLM, PostgreSQL, Prometheus, Grafana), all healthy.
- OpenAI-compatible endpoint on `localhost:4000` with 5 configured models.
- Pre-built Grafana dashboard with request rates, latency percentiles, spend, token rates, deployment state, and custom TTFT/TPOT/ITL histograms.
- Virtual key management API for multi-user budget enforcement.

## Validation Method

See [SKILL.md](./SKILL.md) **Verification Exit Criteria** — a 12-item checklist covering: `.env` completeness and permissions, all services healthy, per-model health check, sync and streaming completions, Prometheus metrics flowing, Grafana reachable, and virtual key minting.

## Reusable Assets

| Asset | Description |
|---|---|
| `litellm_config.yaml` | Model catalog with `openai/` provider prefix, MaaS endpoint, per-model `tpm`/`rpm` and per-token pricing, Huawei logo branding |
| `custom_callbacks.py` | `PrometheusTTFTTPOTITL` callback — emits `litellm_custom_ttft_seconds`, `litellm_custom_tpot_seconds`, `litellm_custom_itl_seconds` histograms labeled by model/group/provider |
| `prometheus.yml` | 15s scrape job targeting `litellm:4000` |
| `grafana/provisioning/` | Auto-linked Prometheus datasource + file-based dashboard provider with pre-built `litellm_overview.json` |
| `docker-compose.yml` | 4-service stack with healthcheck dependency chain, YAML anchor for shared restart/logging, named volumes |
| `.env.example` | Template with all required and optional environment variables |

## KPIs / Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Proxy uptime | > 99.9% | Measured by `/health/liveliness` |
| P99 latency overhead | < 50ms | Proxy latency above direct MaaS call |
| Spend tracking accuracy | 100% | Every call logged with model, tokens, cost |
| Custom metric coverage | Streaming calls | TTFT and ITL emitted for all streaming requests; TPOT for all requests |
| Dashboard freshness | < 15s | Prometheus scrape interval |
| Budget enforcement | Zero bypass | All clients use virtual keys, never raw MaaS key |

## Common Risks and Troubleshooting

| Risk | Impact | Mitigation |
|------|--------|------------|
| `LITELLM_SALT_KEY` changed after virtual keys exist | All keys unreadable | Never change salt after first key; if lost, full reset (`down -v`) is the only option |
| Model name typo in `litellm_config.yaml` | 404 at runtime | Model names are case-sensitive; verify exact name in MaaS console |
| Zero pricing on a model | Budgets don't consume spend | Always set non-zero `input_cost_per_token` and `output_cost_per_token`; verify via `/model/info` |
| MaaS API key expired or wrong region | 403 from upstream | Verify key in MaaS console; region must be `ap-southeast-1` |
| `.env` committed to git | All secrets leaked | `.env` is gitignored; never `git add .env` |
| Config change without restart | New settings not applied | `litellm_config.yaml` is read at startup only; `docker compose restart litellm` after edits |

For the full 11-entry failure modes table and 8-step repair playbook, see [SKILL.md](./SKILL.md).

## Architecture

```
                      Huawei MaaS (ap-southeast-1)
                      ┌──────────────────────────┐
                      │  glm-5.1    glm-5        │
                      │  deepseek-v4-pro         │
                      │  deepseek-v4-flash       │
                      │  deepseek-v3.2           │
                      └─────────▲────────────────┘
                                │ HTTPS / Bearer
 ┌──────────────────────────────┼───────────────────────────┐
 │ Docker Network               │                           │
 │                              │                           │
 │  ┌────────────────────┐      │  ┌──────────────┐         │
 │  │  Prometheus :9090  │      │  │ PostgreSQL   │         │
 │  │  scrape /metrics   │      │  │ :5432        │         │
 │  └─────────▲──────────┘      │  └──────▲───────┘         │
 │            │                 │         │                 │
 │  ┌─────────┴──────────┐      │         │                 │
 │  │  Grafana :3000     │      │         │                 │
 │  │  auto-provisioned  │      │         │                 │
 │  └────────────────────┘      │         │                 │
 │            ▲                 │         │                 │
 │            │                 │         │                 │
 │  ┌─────────┴─────────────────┴─────────┴───────────┐     │
 │  │            LiteLLM Proxy :4000                  │     │
 │  │  /v1/chat/completions  /v1/models  /ui  /metrics│     │
 │  └─────────────────────────────────────────────────┘     │
 └──────────────────────────▲───────────────────────────────┘
                            │
                       API consumers
```

**Startup chain:** PostgreSQL (`pg_isready`) → LiteLLM (`/health/liveliness`) → Prometheus (scrape) → Grafana

**Request flow:** Client → LiteLLM:4000 → Huawei MaaS. LiteLLM logs usage/spend to PostgreSQL, exposes `/metrics` for Prometheus, returns response.

## Quick Start

```bash
git clone <repo-url> && cd litellm-huawei-maas
cp .env.example .env && $EDITOR .env   # fill in all values
docker compose up -d
docker compose ps                      # verify all healthy
```

Generate secrets:

```bash
python3 -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"   # MASTER_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"            # SALT_KEY, passwords
```

## Endpoints

| Service | URL | Auth |
|---|---|---|
| LiteLLM API | `http://localhost:4000` | `Authorization: Bearer <key>` |
| LiteLLM Admin UI | `http://localhost:4000/ui` | Login with `LITELLM_MASTER_KEY` |
| Prometheus | `http://localhost:9090` | None |
| Grafana | `http://localhost:3000` | admin / `GRAFANA_PASSWORD` |

## Configured Models

| Name | Context (in/out) | RPM | TPM | Cost (in/out per token) |
|---|---|---|---|---|
| `glm-5.1` | 192K / 128K | 30 | 500K | $1.078 / $3.774 × 10⁻⁶ |
| `glm-5` | 192K / 64K | 30 | 500K | $0.809 / $2.965 × 10⁻⁶ |
| `deepseek-v4-pro` | 1M / 128K | 3 | 30K | $1.617 / $3.235 × 10⁻⁶ |
| `deepseek-v4-flash` | 1M / 128K | 3 | 30K | $0.135 / $0.270 × 10⁻⁶ |
| `deepseek-v3.2` | 128K / 32K | 700 | 500K | $0.270 / $0.404 × 10⁻⁶ |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | Yes | — | Admin key. Must start with `sk-`. |
| `LITELLM_SALT_KEY` | Yes | — | Encryption salt for stored keys. **Immutable after first virtual key.** |
| `DB_PASSWORD` | Yes | — | PostgreSQL `llmproxy` user password. |
| `HUAWEI_MAAS_API_KEY` | Yes | — | From ModelArts MaaS console (CN-Hong Kong region). |
| `HUAWEI_MAAS_API_BASE` | Yes | — | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| `PROMETHEUS_RETENTION` | No | `15d` | TSDB retention. |
| `GRAFANA_PASSWORD` | No | `admin` | Admin password. |
