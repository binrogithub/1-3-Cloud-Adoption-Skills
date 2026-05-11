# Architecture

## 1. Single-ECS Topology

Recommended layout on one ECS instance:

- LiteLLM Proxy listens on `0.0.0.0:4000`
- Redis listens on `127.0.0.1:6379`
- PostgreSQL listens on `127.0.0.1:5432`
- Optional reverse proxy such as nginx terminates TLS and forwards to LiteLLM

Control-plane split:

- Huawei MaaS key is only used by LiteLLM
- clients never receive the MaaS key
- clients receive LiteLLM virtual keys instead

Data-plane split:

- request path: client -> LiteLLM -> Huawei MaaS
- metadata path: LiteLLM -> PostgreSQL
- cache and transient state path: LiteLLM -> Redis

## 2. Why This Works for a Single Host

This layout keeps the ECS simple while still supporting:

- multi-user authentication
- spend tracking
- budget enforcement
- rate limiting
- response caching
- centralized model exposure

It is a good fit when:

- traffic volume is moderate
- one team owns the host
- high availability is not yet required
- the main goal is safe shared access to MaaS

## 3. FinOps Design

### Objectives

Use LiteLLM as the financial control point for MaaS usage:

- track spend per team, project, service, or user
- restrict which models each tenant can call
- enforce budget ceilings
- enforce TPM and RPM ceilings
- keep one audited place for proxy-issued keys

### Recommended FinOps Hierarchy

Use this structure unless the user wants something else:

1. One LiteLLM master key for operators only
2. One team per internal group, product, or environment
3. One child key per application, bot, or service account
4. Optional metadata and tags for cost attribution

Examples:

- `team_alias=finance-prod`
- `team_alias=research-sandbox`
- `key_alias=finance-prod-api`
- metadata such as `{"cost_center":"FIN-001","service":"risk-api","env":"prod"}`

### Budget Controls

Prefer team-level controls first:

- `max_budget`
- `budget_duration`
- `tpm_limit`
- `rpm_limit`
- optional `model_tpm_limit`
- optional `model_rpm_limit`

Then apply tighter key-level controls only where needed.

This avoids unmanaged sprawl and makes reporting easier.

### Unit Cost Controls

LiteLLM budgets are enforced against spend in USD. Model unit costs must be configured before budget tests are meaningful.

For Huawei MaaS `glm-5.1`, use the highest validated unit prices when the user wants conservative budget enforcement:

- Input: `$1.078 / 1M tokens` -> `input_cost_per_token = 1.078e-06`
- Output: `$3.774 / 1M tokens` -> `output_cost_per_token = 3.774e-06`

Set these directly on each exposed LiteLLM model group in `litellm_params`:

```yaml
model_list:
  - model_name: "huawei-glm-5.1"
    litellm_params:
      model: "openai/glm-5.1"
      api_base: os.environ/HUAWEI_MAAS_API_BASE
      api_key: os.environ/HUAWEI_MAAS_API_KEY
      timeout: 120
      input_cost_per_token: 1.078e-06
      output_cost_per_token: 3.774e-06
```

If using `model_prices_and_context_window.json`, the price-map key must match the provider path used by LiteLLM. For generic OpenAI-compatible MaaS usage:

```json
"custom_openai/glm-5.1": {
  "input_cost_per_token": 1.078e-06,
  "litellm_provider": "custom_openai",
  "mode": "chat",
  "output_cost_per_token": 3.774e-06
}
```

If the live proxy config uses `model: openai/glm-5.1`, setting only `custom_openai/glm-5.1` will not affect the running model group. Put pricing in `litellm_params` or update the matching price-map entry and restart/reload LiteLLM.

### Virtual-Key Budget Operations

Create a monthly child key:

```bash
curl -X POST "$LITELLM_BASE/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "huawei-glm-5.1-monthly",
    "models": ["huawei-glm-5.1"],
    "max_budget": 0.1,
    "budget_duration": "1mo"
  }'
```

Update an existing key budget:

```bash
curl -X POST "$LITELLM_BASE/key/update" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "<virtual_key>",
    "max_budget": 0.00001,
    "budget_duration": "1mo"
  }'
```

Check current key spend:

```bash
curl "$LITELLM_BASE/key/info?key=<virtual_key>" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

Reset spend only when explicitly requested:

```bash
curl -X POST "$LITELLM_BASE/key/reset-spend" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "<virtual_key>", "reset_to": 0}'
```

Expected budget block:

```json
{
  "error": {
    "message": "Budget has been exceeded! Current cost: <spend>, Max budget: <budget>",
    "type": "budget_exceeded",
    "code": "400"
  }
}
```

If a budget does not trigger, inspect `/model/info`; if the deployed model shows `input_cost_per_token: 0` and `output_cost_per_token: 0`, successful calls will not consume spend.

### Currency Conversion

LiteLLM `max_budget` is USD. Convert user-provided local currency before setting budgets.

Example:

```text
0.001 CNY * 0.1465 USD/CNY ~= 0.0001465 USD
```

Use a current exchange rate for production accounting. For a conservative enforcement test, set `max_budget` lower than the expected request cost.

### External VS Code and Cline Through LiteLLM

When Cline should call Huawei MaaS through LiteLLM:

```text
Provider: OpenAI Compatible
Base URL: http://<litellm-host>:4000/v1
API Key: <LiteLLM virtual key>
Model: huawei-glm-5.1
```

Start with a plain text prompt such as `Reply with exactly: ok`. Only enable agentic or tool-heavy Cline behavior after `/v1/chat/completions` succeeds.

### Spend Ownership

For good chargeback, make sure:

- every downstream service uses a distinct LiteLLM child key
- every team has a stable alias
- metadata and tags are populated consistently
- users do not bypass LiteLLM and call MaaS directly

If a user asks for FinOps support, challenge any design that shares one child key across many unrelated services. It weakens attribution.

## 4. Multi-User Proxy Design

### Key Separation

Use these key classes:

- MaaS key: only in LiteLLM env file
- LiteLLM master key: admin and automation only
- LiteLLM child keys: issued to apps, teams, bots, or users

### Team-Scoped Access

For a shared ECS proxy, teams are the cleanest unit of policy:

- allowed models
- budget windows
- rate limits
- key generation rights
- route permissions

Typical flow:

1. admin creates a team
2. admin or team admin generates a team-bound child key
3. app uses the child key against LiteLLM
4. LiteLLM records spend and enforces limits centrally

### Suggested Operating Pattern

For internal shared access:

- operators keep the master key out of app configs
- app teams receive only child keys
- each child key has:
  - a team association
  - a clear alias
  - a restricted model list
  - optional budget or throughput cap

## 5. Cache Design

There are two separate cache concerns on a single ECS host.

### Response Cache

Use LiteLLM response caching when:

- prompts repeat often
- latency matters
- the user accepts that some requests should not hit MaaS every time

Recommended backend:

- Redis

Recommended call types:

- `completion`
- `acompletion`
- `embedding`
- `aembedding`

Be explicit about cache behavior. Response caching affects:

- upstream request count
- observed latency
- expected spend at MaaS

Do not enable response caching silently for workloads that require strict fresh generation semantics.

### Key/Auth Metadata Cache

LiteLLM also benefits from auth-key caching:

- use `general_settings.user_api_key_cache_ttl`
- this reduces repeated PostgreSQL lookups for hot keys

This is not the same as response caching. It improves control-plane efficiency, not model output reuse.

### Health Check Noise

Avoid wildcard model passthrough on single-ECS deployments unless needed. Wildcards create confusing health check probes and can obscure which models are truly supported.

## 6. Config Responsibilities

Recommended ownership by file:

- `litellm.env`: secrets and ports
- `config.yaml`: model exposure, Redis wiring, budgets-related proxy settings
- `redis.conf`: local cache service behavior
- `litellm.service`: process startup, environment loading, Prisma mode

## 7. Scaling Limits of This Architecture

Call out these limits when relevant:

- single point of failure
- no native HA for Redis or PostgreSQL
- local disk and memory are shared across proxy and databases
- heavy response caching can pressure Redis memory
- Prisma and Postgres maintenance are still operator responsibilities

When the user asks for HA or horizontal scale, recommend moving Redis and PostgreSQL off-box first, then adding more LiteLLM instances behind a load balancer.
