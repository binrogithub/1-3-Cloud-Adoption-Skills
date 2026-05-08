# Dify NL2SQL Docker Skill

This repository contains a Codex Skill for configuring and documenting a local Docker-based Dify NL2SQL proof of concept.

The skill captures a reusable architecture proven in a local setup:

```text
Dify WebApp
-> Dify Workflow
-> LiteLLM / OpenAI-compatible LLM
-> SQL sanitization node
-> HTTP SQL execution gateway
-> read-only PostgreSQL business database
```

## What This Skill Helps With

- Configure Dify to use an OpenAI-compatible model endpoint through LiteLLM.
- Build a Dify workflow that converts natural language questions into PostgreSQL `SELECT` queries.
- Route database access through a safe HTTP SQL gateway instead of connecting Dify directly to the database.
- Configure local Docker PostgreSQL, pgAdmin, and container networking.
- Troubleshoot common connectivity issues such as Docker pgAdmin using the wrong `localhost`.
- Generate a project report that explains the deployed environment, workflow, architecture, and Dify-to-database communication path.

## Files

```text
dify-nl2sql-docker/
  SKILL.md
  README.md
  agents/
    openai.yaml
  references/
    configuration-guide.md
    report-template.md
```

## Installation

To install this skill locally for Codex, copy the `dify-nl2sql-docker` folder into your Codex skills directory:

```powershell
Copy-Item -Recurse .\dify-nl2sql-docker "$env:USERPROFILE\.codex\skills\dify-nl2sql-docker"
```

Restart Codex or refresh the skill registry if needed.

## Usage Examples

Ask Codex:

```text
Use the Dify NL2SQL Docker skill to configure a local Dify workflow that queries PostgreSQL through a safe SQL gateway.
```

```text
Use the Dify NL2SQL Docker skill to troubleshoot why Docker pgAdmin cannot connect to my PostgreSQL container.
```

```text
Use the Dify NL2SQL Docker skill to generate a project report for my Dify NL2SQL deployment.
```

## Publishing Notes

Before uploading this folder to GitHub:

- Remove real API keys.
- Remove real database passwords.
- Replace private hostnames with placeholders.
- Keep example credentials clearly marked as examples only.
- Do not include local Docker volumes, database dumps, or Dify internal secrets.

## Recommended Runtime Pattern

Do not let LLM-generated SQL execute directly against a production database. Use this boundary:

```text
LLM generates SQL
-> gateway validates SQL
-> gateway executes with read-only credentials
-> gateway returns rows and rendered answer
```

This keeps Dify workflows cleaner and gives one place to enforce SQL allowlists, limits, auditing, and access control.

