---
name: litellm-huawei-maas-single-ecs
description: Use this skill when deploying LiteLLM Proxy on a single Huawei Cloud ECS instance and connecting it to Huawei Cloud MaaS through the OpenAI-compatible endpoint, especially when the host also needs local Redis and PostgreSQL, systemd services, and multi-user token proxy setup.
---

# LiteLLM on Single ECS for Huawei Cloud MaaS

Use this skill when the task is to install, configure, validate, or repair a single-host LiteLLM proxy that fronts Huawei Cloud MaaS.

This skill assumes:
- One ECS host runs everything.
- Redis and PostgreSQL are local to the same host.
- LiteLLM is used as a multi-user token proxy.
- Huawei MaaS is accessed through its OpenAI-compatible endpoint.

Use bundled resources selectively:

- Read [references/architecture.md](references/architecture.md) when the user asks about architecture, FinOps, multi-user isolation, spend control, or cache design.
- Read [references/finops-ecs-cache-exploration.md](references/finops-ecs-cache-exploration.md) when the user asks for a narrative explanation, article, solution overview, or customer-facing write-up about LiteLLM with Huawei MaaS, FinOps, ECS stability, and cache limitations.
- Use [assets/config/litellm.config.yaml.example](assets/config/litellm.config.yaml.example) as the base proxy config.
- Use [assets/config/litellm.env.example](assets/config/litellm.env.example) for runtime secrets and ports.
- Use [assets/config/redis-local.conf.example](assets/config/redis-local.conf.example) and [assets/config/litellm.service.example](assets/config/litellm.service.example) as starting templates for system files.
- Use [scripts/bootstrap_finops_team.py](scripts/bootstrap_finops_team.py) to create a team plus a scoped virtual key for a downstream user or service.
- Use [scripts/validate_single_ecs.py](scripts/validate_single_ecs.py) to test both direct MaaS access and proxied LiteLLM access.

## Required Inputs

Collect or confirm these values before making changes:

- Huawei MaaS API base, usually `https://api-<region>.modelarts-maas.com/openai/v1`
- Huawei MaaS API key
- Explicit MaaS model IDs to expose, for example `glm-5.1`
- LiteLLM listen port, for example `4000`
- Whether the host can use system packages or needs source builds

If the user only gives one model, prefer explicit routing for that model instead of wildcard routing.

## Core Rules

- Prefer explicit model mappings such as `huawei/glm-5.1 -> openai/glm-5.1`.
- Avoid wildcard mappings like `huawei/* -> openai/*` unless the user explicitly wants dynamic model passthrough.
- Bind Redis and PostgreSQL to localhost unless the user asks for external access.
- Store runtime secrets in an environment file and keep the LiteLLM config free of hardcoded secrets.
- Use systemd units for Redis, PostgreSQL, and LiteLLM.
- Validate both direct MaaS access and proxied LiteLLM access.
- For FinOps, make the proxy the only egress path for MaaS traffic so budgets, rate limits, and spend logs stay centralized.
- For budget enforcement, always confirm the exposed model has non-zero `input_cost_per_token` and `output_cost_per_token`; otherwise successful calls may not consume spend.
- For multi-user proxying, keep the master key admin-only and mint child keys per team, service, or environment.
- For cache design, distinguish Redis-backed response caching from auth-key metadata caching and explain both clearly.

## Deployment Workflow

### 1. Inspect the Host First

Before installing anything:

- Check OS, architecture, and existing ports.
- Check whether Python 3.10+ is available.
- Check whether `dnf`, `apt`, `curl`, and `openssl` are usable.
- Check whether Redis, PostgreSQL, or nginx are already present.
- Check whether Docker is available. If not, proceed with a host-native deployment.

If the package manager or OpenSSL tooling is broken, switch to source builds and avoid destructive changes to the host.

### 2. Prepare Runtime Components

Install or build:

- Python 3.11 preferred
- Redis
- PostgreSQL
- LiteLLM Python environment with:
  - `litellm[proxy]`
  - `prisma`
  - `psycopg`
  - `redis`

Create dedicated system users where appropriate:

- `redis`
- `postgres`
- `litellm`

### 3. Configure Redis

Use a local-only Redis config:

- bind `127.0.0.1`
- set a password
- enable persistence if the proxy should survive restarts cleanly

Typical service responsibilities:

- request caching
- router state
- rate-limit or transient proxy state

### 4. Configure PostgreSQL

Use a local-only PostgreSQL config:

- listen on `127.0.0.1`
- create a dedicated database, for example `litellm`
- create a dedicated role, for example `litellm`
- use password auth for the LiteLLM role

LiteLLM Proxy metadata, keys, teams, and budgets should live in PostgreSQL.

### 5. Configure LiteLLM

Create an environment file such as `/etc/litellm/litellm.env` with:

- `LITELLM_MASTER_KEY`
- `DATABASE_URL`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `HUAWEI_MAAS_API_BASE`
- `HUAWEI_MAAS_API_KEY`

Create a config file such as `/etc/litellm/config.yaml`. Start from `assets/config/litellm.config.yaml.example` and keep only the explicit models the user actually wants to expose.

Preferred pattern for explicit Huawei MaaS model exposure:

```yaml
model_list:
  - model_name: "huawei/glm-5.1"
    litellm_params:
      model: "openai/glm-5.1"
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      timeout: 120
      input_cost_per_token: 1.078e-06
      output_cost_per_token: 3.774e-06

  - model_name: "huawei-glm-5.1"
    litellm_params:
      model: "openai/glm-5.1"
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      timeout: 120
      input_cost_per_token: 1.078e-06
      output_cost_per_token: 3.774e-06

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  store_model_in_db: true

router_settings:
  redis_host: os.environ/REDIS_HOST
  redis_port: os.environ/REDIS_PORT
  redis_password: os.environ/REDIS_PASSWORD
  enable_pre_call_checks: true
```

Do not add wildcard model exposure unless the user accepts noisier health checks and looser routing.

For `glm-5.1`, use the highest validated Huawei MaaS unit prices when the user wants conservative budget enforcement:

- `input_cost_per_token: 1.078e-06`
- `output_cost_per_token: 3.774e-06`

These values are USD per token. Convert prices quoted per 1M tokens by dividing by `1_000_000`.

If the deployment needs FinOps and multi-user controls from day one, also configure:

- Redis-backed LiteLLM response cache in `litellm_settings`
- `general_settings.user_api_key_cache_ttl` to reduce repeated PostgreSQL lookups for hot keys
- explicit model allow-lists on generated team keys
- per-team `max_budget`, `budget_duration`, `tpm_limit`, and `rpm_limit`

### 6. Handle Prisma Carefully

LiteLLM Proxy depends on Prisma for PostgreSQL-backed management features.

Preferred startup pattern:

- generate Prisma client
- sync schema with `prisma db push` or LiteLLM `--use_prisma_db_push`
- then start LiteLLM

If the host has OpenSSL or distro-detection problems:

- verify whether Prisma can run `openssl version -v`
- if Prisma cannot detect the platform correctly, pin the Prisma query engine path
- if needed, use a compatibility wrapper for `openssl`

Do not assume Prisma will work unchanged on every enterprise Linux image.

### 7. Create systemd Units

Create or update services for:

- Redis
- PostgreSQL
- LiteLLM

LiteLLM service should usually:

- run as `litellm`
- load the environment file
- use `--config /etc/litellm/config.yaml`
- bind to `0.0.0.0` only if external clients need network access
- use `--use_prisma_db_push` if schema sync through Prisma migration is fragile on this host

### 8. Validate End-to-End

Always validate in this order:

1. Redis local auth works
2. PostgreSQL accepts the LiteLLM role and database connection
3. Direct Huawei MaaS request works
4. LiteLLM service is active and listening
5. LiteLLM `/health` works with the master key
6. LiteLLM `/chat/completions` succeeds with the exposed model name
7. LiteLLM `/key/generate` can mint a virtual key for downstream users
8. LiteLLM `/model/info` shows non-zero input and output token costs for budgeted models
9. A low-budget virtual key is blocked with `budget_exceeded` after spend crosses `max_budget`

Use a direct MaaS request similar to:

```python
from openai import OpenAI

client = OpenAI(
    api_key="HUAWEI_MAAS_API_KEY",
    base_url="https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
)

response = client.chat.completions.create(
    model="glm-5.1",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "hello"},
    ],
)
```

Then verify the proxy path using LiteLLM:

- model `huawei/glm-5.1`
- `Authorization: Bearer <LITELLM_MASTER_KEY>`
- if the user wants multi-user readiness, also create one sample team and one sample team-scoped key using `scripts/bootstrap_finops_team.py`

## Health Check Interpretation

If `/health` returns:

- `401`: missing LiteLLM auth header
- upstream auth error: MaaS API key is invalid or missing
- `Invalid model`: the mapped upstream model name is wrong
- rate limit error: the mapping is valid, but the upstream provider is throttling frequent probes

If health check noise appears for models the user did not request, inspect the config for wildcard mappings and remove them.

## Repair Playbook

When fixing an existing single-host deployment:

- inspect current `config.yaml` before editing
- preserve working explicit models
- remove wildcard passthrough if health checks are noisy
- confirm the environment file still contains the real MaaS key
- inspect `journalctl -u litellm.service`
- inspect whether Prisma schema sync or query engine startup is the actual blocker

If the user reports cost or noisy usage attribution problems:

- confirm all real clients use LiteLLM child keys instead of the MaaS key directly
- confirm teams and keys carry distinct aliases, tags, or metadata for chargeback
- confirm wildcard proxy models are not hiding accidental model usage
- confirm cache policy is intentional so hit ratios do not distort expectations about upstream token usage

## Output Expectations

When completing the task, leave behind:

- a working LiteLLM service
- local Redis and PostgreSQL services
- explicit Huawei MaaS model mappings
- a documented FinOps stance for budgets, key scoping, and spend ownership
- a documented cache stance for what is cached and why
- a validated direct MaaS request
- a validated proxied LiteLLM request
- a short operator note listing the config file, env file, service name, and exposed model names
