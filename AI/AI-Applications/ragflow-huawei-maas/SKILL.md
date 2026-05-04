---
name: ragflow-huawei-maas
description: Install, configure, validate, troubleshoot, or explain RAGFlow with Huawei Cloud MaaS / ModelArts MaaS through RAGFlow's OpenAI-API-Compatible provider. Use when Codex needs to deploy RAGFlow with Docker Compose, connect it to Huawei MaaS chat models such as glm-5.1, register MaaS models in RAGFlow, verify UI/API login and LLM calls, handle Docker or RAGFlow startup issues, or protect MaaS API keys from logs and telemetry.
---

# RAGFlow Huawei MaaS

## Core Model

RAGFlow calls Huawei Cloud MaaS as an OpenAI-compatible LLM provider.

```text
RAGFlow UI/API -> RAGFlow LLM provider: OpenAI-API-Compatible -> Huawei Cloud MaaS
```

Do not design a custom MaaS adapter unless the user explicitly asks for one. Prefer RAGFlow's built-in `OpenAI-API-Compatible` provider and keep credentials in environment variables or RAGFlow's local model configuration.

## Safe Defaults

- Never print raw MaaS API keys, cookies, access tokens, or session values.
- Mask discovered keys as `<prefix>...<suffix> (len=N)` or `***redacted***`.
- Do not commit `.env`, generated `service_conf.yaml`, database dumps, or logs containing secrets.
- RAGFlow may print custom `api_key` values from `user_default_llm` in startup logs. After startup or troubleshooting, scan and scrub local `docker/ragflow-logs/*.log`.
- Prefer these environment names:
  - `HUAWEI_MAAS_API_BASE`, for example `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
  - `HUAWEI_MAAS_API_KEY`
  - `HUAWEI_MAAS_MODEL`, for example `glm-5.1`

## Prerequisites

Use Docker deployment unless the user asks for source development.

- Docker: `24.0.0` or newer.
- Docker Compose: `2.26.1` or newer.
- Linux host setting for Elasticsearch:

```bash
sysctl -w vm.max_map_count=262144
```

If Docker is too old, upgrade Docker first and verify:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

## Deployment Workflow

1. Download or clone the desired RAGFlow release. Prefer an official release tag over an unknown branch for demos.
2. Configure ports in `docker/.env` to avoid conflicts. Known working local defaults:

```dotenv
EXPOSE_MYSQL_PORT=5455
MINIO_PORT=9100
MINIO_CONSOLE_PORT=9101
REDIS_PORT=6389
SVR_WEB_HTTP_PORT=8088
SVR_WEB_HTTPS_PORT=8443
```

3. Add MaaS settings to `docker/.env` without printing the key:

```dotenv
HUAWEI_MAAS_API_BASE=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
HUAWEI_MAAS_API_KEY=<set locally, do not commit>
HUAWEI_MAAS_MODEL=glm-5.1
```

4. In `docker/service_conf.yaml.template`, set the default chat model:

```yaml
user_default_llm:
  default_models:
    chat_model:
      name: '${HUAWEI_MAAS_MODEL:-glm-5.1}'
      factory: 'OpenAI-API-Compatible'
      api_key: '${HUAWEI_MAAS_API_KEY:-}'
      base_url: '${HUAWEI_MAAS_API_BASE:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}'
```

5. Start RAGFlow:

```bash
cd /path/to/ragflow/docker
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml ps
```

6. Open the UI at:

```text
http://127.0.0.1:8088/
```

Default local login, if unchanged:

```text
Email: admin@ragflow.io
Password: admin
```

Ask the user to change the default password after validation.

## MaaS Validation

Validate direct MaaS connectivity before blaming RAGFlow. Use Python or another HTTP client if host `curl` is broken.

```python
import json
import os
import urllib.request

url = os.environ["HUAWEI_MAAS_API_BASE"].rstrip("/") + "/chat/completions"
payload = {
    "model": os.getenv("HUAWEI_MAAS_MODEL", "glm-5.1"),
    "messages": [{"role": "user", "content": "Reply with OK only."}],
    "temperature": 0.1,
    "max_tokens": 32,
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["HUAWEI_MAAS_API_KEY"],
    },
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())
print({"status": "ok", "model": data.get("model"), "usage": data.get("usage")})
```

## Register The MaaS Model In RAGFlow

RAGFlow's default tenant may show `glm-5.1@OpenAI-API-Compatible` but still need a tenant model record. Register it through RAGFlow's own API so RAGFlow validates the provider path.

1. Encrypt the default password inside the RAGFlow container:

```bash
docker compose -f docker-compose.yml exec -T ragflow-cpu \
  python3 -c 'from api.utils.crypt import crypt; print(crypt("admin"), end="")'
```

2. Log in through `http://127.0.0.1:8088/api/v1/auth/login` and capture the `Authorization` response header. Do not print the header.
3. POST to `http://127.0.0.1:8088/v1/llm/add_llm` with:

```json
{
  "llm_factory": "OpenAI-API-Compatible",
  "llm_name": "glm-5.1",
  "model_type": "chat",
  "api_key": "<HUAWEI_MAAS_API_KEY>",
  "api_base": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
  "max_tokens": 8192
}
```

Success returns `{"code":0,"data":true,"message":"success"}` and creates a tenant model row like:

```text
llm_factory=OpenAI-API-Compatible
llm_name=glm-5.1___OpenAI-API
model_type=chat
api_base=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
```

Verify without exposing secrets:

```bash
docker compose -f docker-compose.yml exec -T mysql \
  mysql -uroot -pinfini_rag_flow rag_flow \
  -e "select llm_factory,llm_name,model_type,case when api_key is null then 'NULL' else concat('len=',length(api_key)) end as api_key_state,api_base from tenant_llm;"
```

## End-To-End Checks

Use these checks after startup:

```bash
docker compose -f docker-compose.yml ps
```

Expected services include `mysql`, `es01`, `minio`, `redis`, and `ragflow-cpu`. Dependency services should be healthy.

Check the UI:

```bash
python3 - <<'PY'
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8088/", timeout=10) as r:
    print(r.status, r.headers.get("content-type"))
PY
```

Check tenant model state through the authenticated RAGFlow API:

- `/api/v1/users/me/models` should include `llm_id: glm-5.1@OpenAI-API-Compatible`.
- `/v1/llm/my_llms?include_details=true` should include `OpenAI-API-Compatible` and `glm-5.1`.

For a close-to-real backend check, run a short `LLMBundle` chat inside the RAGFlow container. Call `settings.init_settings()` first when running outside the normal server process.

```bash
docker compose -f docker-compose.yml exec -T ragflow-cpu python3 - <<'PY'
import asyncio, json, logging
logging.getLogger().setLevel(logging.CRITICAL)
from common import settings
settings.init_settings()
from api.db.services.user_service import UserService
from api.db.joint_services.tenant_model_service import get_tenant_default_model_by_type
from api.db.services.llm_service import LLMBundle
from common.constants import LLMType

users = UserService.query(email="admin@ragflow.io")
tenant_id = users[0].id
cfg = get_tenant_default_model_by_type(tenant_id, LLMType.CHAT)
bundle = LLMBundle(tenant_id, cfg)
msg = asyncio.run(bundle.async_chat(
    system="Answer briefly.",
    history=[{"role": "user", "content": "Say RAGFlow MaaS integration test OK in one short sentence."}],
    gen_conf={"temperature": 0.1, "max_tokens": 64},
))
print(json.dumps({
    "status": "ok" if msg and not str(msg).startswith("ERROR:") else "error",
    "llm_id": cfg.get("llm_name") + "@" + cfg.get("llm_factory"),
    "reply_prefix": str(msg).replace("\n", " ")[:180],
}, ensure_ascii=False))
PY
```

Expected result:

```json
{"status": "ok", "reply_prefix": "RAGFlow MaaS integration test is OK."}
```

## Troubleshooting

- `./entrypoint.sh: permission denied`: the release zip may extract `docker/entrypoint.sh` without executable mode. Fix with `chmod +x docker/entrypoint.sh`, then restart `ragflow-cpu`.
- `Tenant Model with name glm-5.1@OpenAI-API-Compatible and type chat not found`: add the model through `/v1/llm/add_llm`; a default tenant `llm_id` alone is not enough.
- Direct access to `http://127.0.0.1:9380/` resets or fails: use the web entrypoint `http://127.0.0.1:8088/`; nginx proxies the UI/API.
- Elasticsearch fails to start: confirm `vm.max_map_count=262144` and Docker memory is sufficient.
- Port conflicts: edit `docker/.env` ports before `docker compose up -d`.
- Host `curl` has OpenSSL or LDAP symbol errors: use Python `urllib.request` or run HTTP checks inside a container.
- Logs contain a raw MaaS key: scrub immediately and verify zero remaining occurrences.

Example scrub pattern:

```bash
set -a
. /path/to/ragflow/docker/.env
set +a
for f in /path/to/ragflow/docker/ragflow-logs/*.log; do
  [ -f "$f" ] || continue
  perl -0pi -e 'BEGIN { $k=$ENV{"HUAWEI_MAAS_API_KEY"} // ""; } if (length($k)) { s/\Q$k\E/***redacted***/g }' "$f"
done
```

## Stop Or Clean Up

Stop containers without deleting data:

```bash
docker compose -f docker-compose.yml down
```

Delete volumes only when the user explicitly wants to remove the local RAGFlow data:

```bash
docker compose -f docker-compose.yml down -v
```
