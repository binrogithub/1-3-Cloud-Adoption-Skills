# Configuration Guide

## Purpose

Use this guide to configure a local Docker-based Dify NL2SQL proof of concept with:

- Dify as the workflow platform
- LiteLLM as an OpenAI-compatible model gateway
- PostgreSQL as the business database
- pgAdmin for database inspection
- a small HTTP SQL gateway between Dify and PostgreSQL

Do not commit real API keys, database passwords, or production hostnames. Replace all placeholders before running commands.

## Network Model

The most common source of connection errors is confusing host-local addresses with container-local addresses.

Use these rules:

```text
Windows or desktop tool -> localhost:<published-port>
Docker container -> other container name:<internal-port>
Docker container -> Windows host service: host.docker.internal:<host-port>
```

Examples:

```text
Desktop pgAdmin to PostgreSQL: localhost:15433
Docker pgAdmin to PostgreSQL: nl2sql-test-postgres:5432
Dify container to LiteLLM on host: host.docker.internal:4000/v1
Dify container to SQL gateway: nl2sql-query-api:8080
```

If two Docker containers cannot resolve each other by name, connect them to the same Docker network:

```powershell
docker network connect <network-name> <container-name>
```

## PostgreSQL Business Database

Create a local PostgreSQL container for test data:

```powershell
docker run -d `
  --name nl2sql-test-postgres `
  --network docker_default `
  -p 15433:5432 `
  -e POSTGRES_DB=ai_demo `
  -e POSTGRES_USER=ai_admin `
  -e POSTGRES_PASSWORD=<ADMIN_PASSWORD> `
  postgres:15-alpine
```

Create a read-only runtime user:

```sql
CREATE USER ai_readonly WITH PASSWORD '<READONLY_PASSWORD>';
GRANT CONNECT ON DATABASE ai_demo TO ai_readonly;
GRANT USAGE ON SCHEMA public TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ai_readonly;
```

Create a minimal test table:

```sql
CREATE TABLE IF NOT EXISTS orders (
  id serial PRIMARY KEY,
  order_date date NOT NULL,
  region varchar(50) NOT NULL,
  product varchar(100) NOT NULL,
  amount numeric(12,2) NOT NULL,
  status varchar(30) NOT NULL
);
```

Recommended sample dimensions:

```text
region: east, south, north
product: phone, laptop, headset, tablet
status: paid, refund
```

Validate:

```powershell
docker exec -e PGPASSWORD=<READONLY_PASSWORD> nl2sql-test-postgres `
  psql -U ai_readonly -d ai_demo `
  -c "SELECT COUNT(*) FROM orders;"
```

## SQL Execution Gateway

The gateway is the security boundary between Dify and PostgreSQL. It should:

- accept `POST /execute` with JSON body `{"sql": "..."}`
- strip or reject unsafe SQL
- allow only one `SELECT` statement
- restrict access to allowlisted tables
- reject `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `COPY`, and similar commands
- reject system schemas such as `information_schema` and `pg_catalog`
- enforce `LIMIT`
- execute with the read-only PostgreSQL account

Typical gateway environment variable:

```text
DB_DSN=postgresql://ai_readonly:<READONLY_PASSWORD>@nl2sql-test-postgres:5432/ai_demo
```

Validate from the Dify API container:

```powershell
docker exec docker-api-1 python -c "import urllib.request; print(urllib.request.urlopen('http://nl2sql-query-api:8080/health', timeout=5).read().decode())"
```

Validate execution:

```powershell
docker exec docker-api-1 python -c "import json, urllib.request; payload=json.dumps({'sql':'SELECT COUNT(*) FROM orders LIMIT 100'}).encode(); req=urllib.request.Request('http://nl2sql-query-api:8080/execute', data=payload, headers={'Content-Type':'application/json'}, method='POST'); print(urllib.request.urlopen(req, timeout=10).read().decode())"
```

## LiteLLM and Model Provider

Verify LiteLLM from the host:

```powershell
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri "http://localhost:4000/v1/models" `
  -Headers @{Authorization="Bearer <LITELLM_API_KEY>"}
```

Verify LiteLLM from the Dify API container:

```powershell
docker exec docker-api-1 python -c "import urllib.request; req=urllib.request.Request('http://host.docker.internal:4000/v1/models', headers={'Authorization':'Bearer <LITELLM_API_KEY>'}); print(urllib.request.urlopen(req, timeout=10).read().decode())"
```

In Dify, configure:

```text
Provider: OpenAI-API-compatible
Model type: LLM
Model name: <MODEL_ID_FROM_LITELLM>
API endpoint URL: http://host.docker.internal:4000/v1
API key: <LITELLM_API_KEY>
Completion mode: Chat
Temperature: 0 in the workflow node
```

If the OpenAI-compatible provider is missing, install the Dify marketplace plugin:

```text
Plugin: langgenius/openai_api_compatible
Provider name in Dify: langgenius/openai_api_compatible/openai_api_compatible
```

## Dify Workflow

Recommended workflow:

```text
Start
-> Generate SQL
-> Sanitize SQL
-> Execute Safe SQL
-> Parse Answer
-> Answer
```

LLM prompt skeleton:

```text
You are an NL2SQL SQL generator.
Only output PostgreSQL SQL.
Do not output Markdown, comments, or explanations.

Schema:
orders(
  id integer,
  order_date date,
  region text,
  product text,
  amount numeric,
  status text
)

Rules:
- Sales amount means SUM(amount) where status = 'paid'.
- Refund amount means SUM(amount) where status = 'refund'.
- Only query the orders table.
- Only generate SELECT.
- Always add LIMIT 100.
- Map user synonyms to actual values.
```

Sanitize SQL code node pattern:

```python
import re

def main(raw_sql: str) -> dict:
    sql = (raw_sql or "").strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
    sql = re.sub(r"\s*```$", "", sql).strip()
    sql = re.sub(r"^\s*SQL\s*:\s*", "", sql, flags=re.I).strip()
    sql = " ".join(sql.split())
    return {"sql": sql}
```

HTTP Request node:

```text
Method: POST
URL: http://nl2sql-query-api:8080/execute
Body type: JSON
Body: {"sql": "{{#sanitize_sql.sql#}}"}
```

Parse Answer code node pattern:

```python
import json

def main(response_body: str) -> dict:
    payload = json.loads(response_body or "{}")
    return {
        "answer": str(payload.get("answer") or payload.get("error") or response_body),
        "sql": str(payload.get("sql") or ""),
    }
```

## pgAdmin

Desktop pgAdmin:

```text
Host: localhost
Port: 15433
Database: ai_demo
Username: ai_admin or ai_readonly
```

Docker pgAdmin:

```text
Host: nl2sql-test-postgres
Port: 5432
Database: ai_demo
Username: ai_admin or ai_readonly
```

If Docker pgAdmin cannot connect:

```powershell
docker network connect docker_default pgadmin
docker exec pgadmin python3 -c "import socket; s=socket.create_connection(('nl2sql-test-postgres',5432),5); print('ok'); s.close()"
```

## End-to-End Validation

Test questions:

```text
Sales by region last month
Monthly sales trend from January to May 2026
Refund amount by region this month
Top product by sales last month
List paid laptop orders in east region this month
```

A successful result proves:

```text
Dify WebApp -> Dify Workflow -> LiteLLM model -> SQL gateway -> PostgreSQL -> Dify answer
```

## Troubleshooting

Connection refused to `localhost:<port>` from pgAdmin:

```text
If pgAdmin is Docker-based, localhost is the pgAdmin container itself.
Use the PostgreSQL container name and internal port instead.
```

Dify cannot reach LiteLLM:

```text
Use http://host.docker.internal:4000/v1 from Dify containers on Docker Desktop.
Alternatively, connect the LiteLLM container to Dify's Docker network and use its container name.
```

LLM returns Markdown instead of SQL:

```text
Make the prompt stricter and keep the sanitize node.
Do not rely on prompt instructions as the only safety layer.
```

Unsafe SQL reaches the gateway:

```text
Reject it in the gateway.
Never let Dify or the model execute SQL directly against production data.
```

