---
name: dify-nl2sql-docker
description: Configure, validate, document, or troubleshoot a local Docker-based Dify NL2SQL proof of concept that uses Dify workflows, an OpenAI-compatible LiteLLM model such as GLM-5.1, PostgreSQL, pgAdmin, and a safe read-only SQL execution gateway. Use when setting up Dify-to-database communication, building NL2SQL workflows, creating project reports, or adapting this architecture to another local or cloud database.
---

# Dify NL2SQL Docker

## Overview

Use this skill to reproduce or adapt a Dify NL2SQL architecture where Dify does not connect directly to the business database. Dify calls an OpenAI-compatible LLM to generate SQL, then sends the SQL to a small HTTP gateway that validates and executes only safe read-only queries against PostgreSQL.

Core pattern:

```text
User
-> Dify WebApp
-> Dify Workflow
-> LLM node through LiteLLM / OpenAI-compatible provider
-> Code node to sanitize SQL
-> HTTP Request node to a SQL execution gateway
-> PostgreSQL using a read-only account
-> Dify answer node
```

## Start Here

For implementation details, read only the reference file needed for the task:

- `references/configuration-guide.md`: use when configuring or troubleshooting Dify, LiteLLM, PostgreSQL, pgAdmin, workflow nodes, or connectivity.
- `references/report-template.md`: use when generating a project report or handover document for this architecture.

## Required Design Decisions

Before changing an environment, identify:

1. Whether Dify is running in Docker, cloud SaaS, or another host.
2. Whether pgAdmin is a desktop app or a Docker container.
3. Whether the model endpoint is OpenAI-compatible.
4. Whether the database is local Docker PostgreSQL, host PostgreSQL, or a cloud database.
5. Whether Dify should use a database plugin directly or the recommended HTTP gateway pattern.

Prefer the HTTP gateway pattern for NL2SQL tests and production-like proofs of concept. It keeps database credentials out of Dify workflow nodes and gives one place to enforce SQL safety, row limits, allowlists, logging, and user authorization.

## Recommended Architecture

Use this architecture unless the user explicitly asks for a direct Dify database plugin setup:

```text
Dify Workflow
  LLM node:
    provider = OpenAI-compatible
    model = configured LiteLLM model, for example glm-5.1
    output = SQL only
  Code node:
    strip Markdown fences, prefixes, and extra whitespace
  HTTP Request node:
    POST http://<sql-gateway-host>:<port>/execute
    body = {"sql": "{{#sanitize_sql.sql#}}"}

SQL gateway
  validates SQL:
    SELECT only
    single statement only
    allowed tables only
    forbidden keywords blocked
    LIMIT enforced
  connects to database:
    read-only account only
```

## Environment Defaults

Use placeholders for secrets in published artifacts. Never commit real API keys or database passwords.

Typical local Docker values:

```text
Dify console: http://localhost:8088
Dify WebApp: http://localhost:8088/chat/<site-code>
LiteLLM from Windows host: http://localhost:4000
LiteLLM from Dify container: http://host.docker.internal:4000/v1
Business PostgreSQL from Windows host: localhost:15433
Business PostgreSQL from Docker network: <postgres-container-name>:5432
SQL gateway from Dify: http://<sql-gateway-container>:8080/execute
```

Account pattern:

```text
admin account: database owner or migration account; do not use from Dify runtime
readonly account: SELECT-only account used by the SQL gateway
```

## Workflow Node Checklist

Create or update these nodes in Dify:

1. `Start`: receive `sys.query`.
2. `Generate SQL`: LLM node with a strict prompt and `temperature = 0`.
3. `Sanitize SQL`: Code node that extracts a single SQL string from the LLM output.
4. `Execute Safe SQL`: HTTP Request node that calls the gateway.
5. `Parse Answer`: Code node that extracts `answer`, `sql`, and optional `rows`.
6. `Answer`: return the parsed answer.

Prompt rules for the LLM node:

```text
Only output SQL.
Do not output Markdown.
Only generate SELECT statements.
Query only allowlisted tables.
Always add LIMIT.
Apply business metric definitions exactly.
Map user-facing synonyms to actual column values.
```

## Validation Checklist

Validate from the inside out:

1. Confirm PostgreSQL is running and reachable from its own container.
2. Confirm the read-only account can query the target tables.
3. Confirm the SQL gateway can reach PostgreSQL.
4. Confirm the Dify API container can reach the SQL gateway.
5. Confirm the Dify API or plugin daemon can reach LiteLLM.
6. Run the Dify draft workflow from the console API or UI.
7. Publish the workflow and test the public WebApp endpoint.

Common pgAdmin rule:

```text
desktop pgAdmin -> use localhost:<published-port>
Docker pgAdmin -> use <postgres-container-name>:5432 after joining the same Docker network
```

## Report Generation

When asked for a report, include:

- deployed components and container names
- model provider configuration
- database schema and accounts
- workflow nodes
- architecture diagram
- Dify-to-database communication path
- security boundary around the SQL gateway
- validation results and troubleshooting commands

Use `references/report-template.md` as the structure.

