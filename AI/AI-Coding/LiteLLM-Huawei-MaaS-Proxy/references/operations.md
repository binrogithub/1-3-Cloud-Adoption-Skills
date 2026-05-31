# Operations

## Environment Setup

```bash
./scripts/init_env.sh              # interactive — choose each secret, add extra MaaS keys
./scripts/init_env.sh --auto       # agent mode — auto-generate, prompt for MaaS keys only
./scripts/init_env.sh --ci         # CI mode — all from env vars, no prompts
```

### Multi-key setup

After entering the main `HUAWEI_MAAS_API_KEY`, `init_env.sh` asks for the number of additional keys. Each extra key creates an additional deployment per model, multiplying effective RPM/TPM.

In CI mode, set `HUAWEI_MAAS_EXTRA_API_KEYS` (comma-separated) for additional keys.

After `.env` is written, `init_env.sh` automatically runs `scripts/generate_config.sh` to generate `litellm_config.yaml`.

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

## Environment Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | Yes | — | Admin key, must start with `sk-` |
| `LITELLM_SALT_KEY` | Yes | — | Key encryption salt — **immutable after first virtual key** |
| `DB_PASSWORD` | Yes | — | PostgreSQL password for `llmproxy` user |
| `HUAWEI_MAAS_API_KEY` | Yes | — | Main MaaS API key from ModelArts console (CN-Hong Kong) |
| `HUAWEI_MAAS_API_BASE` | Yes | — | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| `HUAWEI_MAAS_API_KEY_COUNT` | Auto | 1 | Number of MaaS API keys (set by init_env.sh) |
| `HUAWEI_MAAS_API_KEY_N` | Auto | — | Indexed keys (0, 1, 2...). Set by init_env.sh. |
| `HUAWEI_MAAS_EXTRA_API_KEYS` | No | — | Comma-separated extra keys for CI mode |
| `PROMETHEUS_RETENTION` | No | `15d` | Prometheus TSDB retention period |
| `GRAFANA_PASSWORD` | No | `admin` | Grafana admin password |

## Multi-Key Operations

### Adding a MaaS API key

```bash
# 1. Add new key to .env
echo 'HUAWEI_MAAS_API_KEY_2="your-new-key"' >> .env

# 2. Update count
# Edit HUAWEI_MAAS_API_KEY_COUNT in .env to increment

# 3. Regenerate config
./scripts/generate_config.sh

# 4. Restart LiteLLM
docker compose restart litellm

# 5. Verify deployment count
curl -s http://localhost:4000/model/info \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '[.data[].model_name] | length'
```

### Removing a MaaS API key

```bash
# 1. Remove key from .env
# 2. Decrement HUAWEI_MAAS_API_KEY_COUNT
# 3. Re-index remaining keys (must be contiguous: 0, 1, 2...)
# 4. Regenerate and restart
./scripts/generate_config.sh
docker compose restart litellm
```

### Rotating an expired key

```bash
# 1. Replace the key value in .env
# 2. Regenerate and restart
./scripts/generate_config.sh
docker compose restart litellm
```

### Changing routing strategy

Run `./scripts/generate_config.sh --routing-strategy=<strategy>` to change routing strategy:

| Strategy | Description |
|---|---|
| `simple-shuffle` | Random selection (default) |
| `least-latency` | Select deployment with lowest latency |
| `round-robin` | Cycle through deployments in order |

After editing the template:

```bash
./scripts/generate_config.sh
docker compose restart litellm
```

### Checking deployment health

```bash
# Per-deployment health
curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.deployments'

# Cooldown status
curl -s http://localhost:4000/metrics | grep litellm_deployment_cooled_down
```

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

## Multi-Key Operations

### Add a MaaS API key

1. Add the key to `.env` as `HUAWEI_MAAS_API_KEY_N` (next index)
2. Increment `HUAWEI_MAAS_API_KEY_COUNT`
3. Re-run: `./scripts/generate_config.sh`
4. Restart: `docker compose restart litellm`
5. Validate: `./scripts/validate_e2e.sh`

Or re-run `./scripts/init_env.sh` to be guided through the process.

### Remove a MaaS API key

1. Remove the `HUAWEI_MAAS_API_KEY_N` line from `.env`
2. Re-number remaining keys (_0, _1, ...) to be contiguous
3. Update `HUAWEI_MAAS_API_KEY_COUNT`
4. Re-run: `./scripts/generate_config.sh`
5. Restart: `docker compose restart litellm`

### Change routing strategy

```bash
./scripts/generate_config.sh --routing-strategy=least-busy
docker compose restart litellm
```

Available strategies: `simple-shuffle` (default), `least-busy`, `latency-based-routing`, `usage-based-routing`, `cost-based-routing`

### Regenerate config after .env changes

```bash
./scripts/generate_config.sh
docker compose restart litellm
```

## Health checks

```bash
docker compose ps

curl -s http://localhost:4000/health/liveliness

curl -s http://localhost:4000/health \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | jq '.healthy_count, .unhealthy_count'

curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

curl -s https://api-ap-southeast-1.modelarts-maas.com/openai/v1/models \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY"
```

## Backup & restore

```bash
docker compose exec db pg_dump -U llmproxy litellm > backup_$(date +%Y%m%d).sql

cat backup_20260516.sql | docker compose exec -T db psql -U llmproxy litellm
```

## Restart & reset

```bash
docker compose restart litellm

docker compose down && docker compose up -d

docker compose down -v && docker compose up -d
```

## Troubleshooting commands

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
