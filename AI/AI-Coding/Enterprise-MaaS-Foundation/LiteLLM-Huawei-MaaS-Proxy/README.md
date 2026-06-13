# LiteLLM Huawei MaaS Proxy

Docker Compose deployment of [LiteLLM](https://github.com/BerriAI/litellm) as an OpenAI-compatible API proxy routing through **Huawei ModelArts MaaS** (ap-southeast-1) with PostgreSQL persistence, Prometheus metrics, and Grafana dashboards.

This repo ships **runtime stack files** for deterministic clone-and-run deployment. See [SKILL.md](./SKILL.md) for the agent-facing workflow, validation sequence, and exit criteria.

## Layout

```
README.md                                       this file
SKILL.md                                        agent-facing workflow and trigger rules
docker-compose.yml                              4-service Docker stack (references assets/config/)
assets/config/
  litellm_config.yaml.example                    model catalog example (tracked in git)
  litellm_config.yaml                            generated config (gitignored, created by generate_config.sh)
  custom_callbacks.py                            TTFT/TPOT/ITL metrics, Exa search injection, image routing
  prometheus.yml                                 15s scrape config
  .env.example                                   environment template
  grafana/
    └── provisioning/
        ├── datasources/prometheus.yml           auto-linked Prometheus datasource
        └── dashboards/
            ├── dashboards.yml                   file-based dashboard provider
            └── litellm_overview.json            pre-built overview dashboard
references/
  architecture.md                                topology, services, volumes, environment
  metrics-and-dashboards.md                      PromQL, custom metrics, Grafana panel config
  operations.md                                  health checks, backup, restart, usage, endpoints
  troubleshooting.md                             repair playbook, failure modes, common mistakes
scripts/
  init_env.sh                                    interactive .env setup (manual, agent-guided, or CI)
  validate_e2e.sh                                12-step end-to-end validation
  generate_config.sh                             generates litellm_config.yaml from .env
```

## Skill Level

**Level 2 — Tested in production.**

## Applicable Scenario

Single-host AI gateway for centralized key management, spend tracking, rate limiting, and LLM traffic observability on Huawei Cloud MaaS — without the complexity of a full ECS deployment.

## Business Problem Addressed

| Problem | Impact |
|---|---|
| No centralized MaaS API key control | Developers bypass spend tracking and rate limiting |
| No LLM latency/throughput/cost visibility | Issues discovered late or not at all |
| No per-team budget enforcement | Single runaway client can consume entire MaaS quota |
| No audit trail | Who called which model, when, at what cost is untracked |

## Required Knowledge

- Huawei Cloud ModelArts MaaS (ap-southeast-1)
- Docker Compose on a single Linux host
- Prometheus + Grafana observability fundamentals
- LiteLLM proxy configuration (model routing, callbacks, virtual keys)

## Required Tools

| Tool | Version | Purpose |
|---|---|---|
| LiteLLM proxy | v1.83.14-stable.patch.3 | OpenAI-compatible API gateway |
| PostgreSQL | 16-alpine | Key storage, usage logs, spend records |
| Prometheus | v3.3.1 | LLM metrics scraping and TSDB |
| Grafana | 11.5.2 | Pre-built latency/spend/token dashboard |
| Huawei MaaS API | ap-southeast-1 | Upstream LLM inference |
| Docker | 20.10+ with Compose V2 | Container orchestration |
| Exa API | Optional | Current web search injection for search-intent prompts |
| OpenRouter API | Optional | Vision model routing for image prompts |

## Workflow

1. **Install and configure** — extract from monorepo to `/home/LiteLLM-Huawei-MaaS-Proxy`, then `./scripts/init_env.sh` (guided) or manual `.env` setup.
2. **Deploy** — `docker compose up -d`. Healthcheck-gated chain: PostgreSQL → LiteLLM → Prometheus → Grafana.
3. **Validate** — `./scripts/validate_e2e.sh` (12-step).
4. **Operate** — mint virtual keys per team/service with budget and model restrictions.
5. **Extend** — add models from MaaS console to `assets/config/litellm_config.yaml`, restart LiteLLM, verify pricing.

## Expected Outputs

- 4-service Docker Compose stack, all healthy
- OpenAI-compatible endpoint on `localhost:4000` with MaaS text models, Claude Code aliases, and optional `vision-openrouter`
- Pre-built Grafana dashboard with request rates, latency percentiles, spend, token rates, and custom TTFT/TPOT/ITL histograms
- Virtual key management API for multi-user budget enforcement

## Validation

See [SKILL.md](./SKILL.md) **Verification Exit Criteria** — 12-item checklist covering `.env` completeness, service health, per-model health, sync/streaming completions, metrics, Grafana, and virtual key minting.

## Reusable Assets

| Asset | Description |
|---|---|
| `docker-compose.yml` | 4-service stack with healthcheck chain, YAML anchor, named volumes |
| `assets/config/litellm_config.yaml.example` | Model catalog example with `openai/` prefix, MaaS endpoint, per-model tpm/rpm and pricing |
| `assets/config/litellm_config.yaml` | Generated config (gitignored), created by `generate_config.sh` |
| `assets/config/custom_callbacks.py` | TTFT/TPOT/ITL metrics, Exa result injection, image-to-OpenRouter routing, Responses tool repair |
| `assets/config/prometheus.yml` | 15s scrape job targeting `litellm:4000` |
| `assets/config/grafana/provisioning/` | Auto-linked Prometheus datasource + pre-built dashboard |
| `assets/config/.env.example` | Template with all required and optional variables |
| `scripts/init_env.sh` | Interactive .env setup (manual, agent-guided, or CI) |
| `scripts/generate_config.sh` | Generates litellm_config.yaml from .env and template |
| `scripts/validate_e2e.sh` | 12-step end-to-end validation |
| `references/` | Architecture, metrics, operations, and troubleshooting deep-dives |

## KPIs

| Metric | Target | Description |
|---|---|---|
| Proxy uptime | > 99.9% | Measured by `/health/liveliness` |
| P99 latency overhead | < 50ms | Proxy latency above direct MaaS call |
| Spend tracking accuracy | 100% | Every call logged with model, tokens, cost |
| Custom metric coverage | Streaming calls | TTFT and ITL for streaming; TPOT for all requests |
| Dashboard freshness | < 15s | Prometheus scrape interval |
| Budget enforcement | Zero bypass | All clients use virtual keys, never raw MaaS key |
| Deployment distribution | Even | Requests evenly distributed across N deployments per model |

## Common Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `LITELLM_SALT_KEY` changed after virtual keys exist | All keys unreadable | Never change salt after first key; if lost, `down -v` and start fresh |
| Model name typo in config | 404 at runtime | Model names are case-sensitive; verify in MaaS console |
| Zero pricing on a model | Budgets don't consume spend | Set non-zero `input_cost_per_token` and `output_cost_per_token` |
| MaaS API key expired or wrong region | 403 from upstream | Verify key in MaaS console; region must be `ap-southeast-1` |
| `.env` committed to git | All secrets leaked | `.env` is gitignored; never `git add .env` |
| Config change without restart | New settings not applied | `docker compose restart litellm` after edits |
| One MaaS API key expired (multi-key) | Partial degradation | Monitor cooldown events in Grafana; rotate expired key |
| `request_timeout` too low | Intermittent TimeoutErrors on non-trivial requests | Set `request_timeout: 600` (default); add `stream_timeout: 60` for TTFT |

## Quick Start

**Guided setup (recommended):**

```bash
git clone --depth 1 https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git /home/1-3-Cloud-Adoption-Skills
cp -r /home/1-3-Cloud-Adoption-Skills/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy /home/LiteLLM-Huawei-MaaS-Proxy
rm -rf /home/1-3-Cloud-Adoption-Skills
cd /home/LiteLLM-Huawei-MaaS-Proxy
./scripts/init_env.sh              # interactive — choose each secret, prompts for extra keys
./scripts/generate_config.sh       # generates litellm_config.yaml from .env
docker compose up -d
./scripts/validate_e2e.sh
```

**Agent-guided setup:**

```bash
git clone --depth 1 https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git /home/1-3-Cloud-Adoption-Skills
cp -r /home/1-3-Cloud-Adoption-Skills/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy /home/LiteLLM-Huawei-MaaS-Proxy
rm -rf /home/1-3-Cloud-Adoption-Skills
cd /home/LiteLLM-Huawei-MaaS-Proxy
./scripts/init_env.sh --auto       # auto-generate secrets, prompt for MaaS API key(s)
./scripts/generate_config.sh       # generates litellm_config.yaml from .env
docker compose up -d
./scripts/validate_e2e.sh
```

**Manual setup (full control):**

```bash
git clone --depth 1 https://github.com/binrogithub/1-3-Cloud-Adoption-Skills.git /home/1-3-Cloud-Adoption-Skills
cp -r /home/1-3-Cloud-Adoption-Skills/AI/AI-Coding/LiteLLM-Huawei-MaaS-Proxy /home/LiteLLM-Huawei-MaaS-Proxy
rm -rf /home/1-3-Cloud-Adoption-Skills
cd /home/LiteLLM-Huawei-MaaS-Proxy
cp assets/config/.env.example .env
$EDITOR .env                       # add all secrets and HUAWEI_MAAS_API_KEY(s)
chmod 600 .env
./scripts/generate_config.sh       # generates litellm_config.yaml from .env
docker compose up -d
./scripts/validate_e2e.sh
```

## Endpoints

| Service | URL | Auth |
|---|---|---|
| LiteLLM API | `http://localhost:4000` | `Authorization: Bearer <key>` |
| LiteLLM Admin UI | `http://localhost:4000/ui` | Login with `LITELLM_MASTER_KEY` |
| Prometheus | `http://localhost:9090` | None |
| Grafana | `http://localhost:3000` | admin / `GRAFANA_PASSWORD` |

## Configured Models

| Name | Context (in/out) | RPM (per-key) | TPM (per-key) | Cost (in/out per token) |
|---|---|---|---|---|
| `glm-5.1` | 192K / 128K | 30 | 500K | $1.078 / $3.774 × 10⁻⁶ |
| `glm-5` | 192K / 64K | 30 | 500K | $0.809 / $2.965 × 10⁻⁶ |
| `deepseek-v4-pro` | 1M / 128K | 3 | 30K | $1.617 / $3.235 × 10⁻⁶ |
| `deepseek-v4-flash` | 1M / 128K | 3 | 30K | $0.135 / $0.270 × 10⁻⁶ |
| `deepseek-v3.2` | 128K / 32K | 700 | 500K | $0.270 / $0.404 × 10⁻⁶ |
| `claude-glm1` | 192K / 128K | 30 | 500K | Alias to `glm-5.1` for Claude Code router clients |
| `claude-opus-4-6` | 192K / 128K | 30 | 500K | Compatibility alias to `glm-5.1` |
| `vision-openrouter` | Provider-dependent | 50-100 | 400K-800K | OpenRouter fallback group for image prompts |

> **Effective totals:** With N MaaS API keys configured, each model has N deployments. Effective RPM = per-key × N, effective TPM = per-key × N. LiteLLM load-balances across all deployments.

## Multi-Key Load Balancing

The proxy supports multiple MaaS API keys for load balancing and increased throughput:

- **Main key** (`HUAWEI_MAAS_API_KEY`): Mandatory, always required
- **Extra keys**: Optional, configured via `init_env.sh` prompts or `HUAWEI_MAAS_EXTRA_API_KEYS` env var
- **Internal env vars**: `HUAWEI_MAAS_API_KEY_COUNT`, `HUAWEI_MAAS_API_KEY_0`, `HUAWEI_MAAS_API_KEY_1`, etc.
- **Config generation**: `scripts/generate_config.sh` reads `.env` and generates `litellm_config.yaml` from the example
- **Router settings**: `simple-shuffle` strategy (default), `cooldown_time: 30`, `allowed_fails: 3`
- **N deployments per model**: With N keys, each model has N deployments. LiteLLM automatically load-balances.
- **Backward compatible**: Single key = identical behavior to before

### Grafana panels for multi-key

The dashboard includes a "Deployment Load Balancing" row with 5 panels:
- **Deployments Per Model**: Shows N deployments per model
- **Request Distribution**: Per-deployment request counts
- **Cooldown Events**: Deployments temporarily removed from rotation
- **Per-Deployment Latency**: Latency breakdown by deployment

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | Yes | — | Admin key. Must start with `sk-`. |
| `LITELLM_SALT_KEY` | Yes | — | Encryption salt for stored keys. **Immutable after first virtual key.** |
| `DB_PASSWORD` | Yes | — | PostgreSQL `llmproxy` user password. |
| `HUAWEI_MAAS_API_KEY` | Yes | — | Main MaaS API key from ModelArts console (CN-Hong Kong region). |
| `HUAWEI_MAAS_API_BASE` | Yes | — | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| `HUAWEI_MAAS_API_KEY_COUNT` | Auto | 1 | Number of MaaS API keys (set by init_env.sh). |
| `HUAWEI_MAAS_API_KEY_N` | Auto | — | Indexed keys (0, 1, 2...). Set by init_env.sh. |
| `HUAWEI_MAAS_EXTRA_API_KEYS` | No | — | Comma-separated extra keys for CI mode. |
| `PROMETHEUS_RETENTION` | No | `15d` | TSDB retention. |
| `GRAFANA_PASSWORD` | No | `admin` | Admin password. |
| `EXA_API_KEY` | No | — | Enables LiteLLM-side search result injection for current/search prompts. |
| `OpenRouter_API_KEY` | No | — | Enables automatic image request routing through `vision-openrouter`. |
| `LITELLM_CCR_KEY` | No | — | Optional virtual key for a local CCR/`claude-glm` client. |

## Claude Code Search And Image Routing

`assets/config/custom_callbacks.py` extends the metrics callback with request mutation hooks:

- Search prompts matching `搜索`, `新闻`, `最新`, `current`, `latest`, `today`, `news`, or `search` call Exa when `EXA_API_KEY` is set. The callback injects compact result snippets and source URLs into the request before GLM is called.
- Image prompts containing OpenAI-style `image_url` blocks or Anthropic-style `image` blocks are rewritten to the `vision-openrouter` model group.
- Responses API function tool shapes are repaired before deployment calls so LiteLLM can bridge CCR `/v1/responses` traffic to OpenAI-compatible chat models.

For `claude-glm`, pair this LiteLLM proxy with `claude-code-huawei-maas/scripts/configure-ccr-search.py`. CCR should strip local Claude Code `WebSearch`/`WebFetch` tools for search-intent prompts, while LiteLLM performs the actual Exa prefetch.
