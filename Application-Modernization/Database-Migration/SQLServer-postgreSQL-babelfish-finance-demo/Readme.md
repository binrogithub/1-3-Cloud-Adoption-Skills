# SQLServer-postgreSQL-babelfish-finance-demo

This skill provides a local, repeatable finance migration demo from SQL Server to PostgreSQL through Babelfish.

## Scenario

The demo models a bank migrating SQL Server-backed account and payment reporting to Babelfish/PostgreSQL while preserving SQL Server-compatible client access through the TDS port.

The demo database is `FinanceDemo` and includes:

- Customer master data
- Bank accounts and balances
- Payment ledger rows
- Risk alerts
- Customer exposure reporting
- Daily payment liquidity reporting

## What It Demonstrates

- SQL Server source database creation
- Babelfish/PostgreSQL initialization
- T-SQL DDL and DML execution through Babelfish TDS
- Identity columns, primary keys, unique constraints, and foreign keys
- Views and stored procedures
- Validation through SQL Server, Babelfish TDS, and PostgreSQL protocol

## Directory Layout

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── demo-template/
│       ├── scripts/
│       │   ├── start-demo.sh
│       │   ├── migrate.sh
│       │   ├── verify.sh
│       │   └── stop-demo.sh
│       └── sql/
│           ├── 01_source_sqlserver.sql
│           ├── 02_target_babelfish_schema.sql
│           └── 03_generate_insert_script.sql
└── references/
    └── finance-demo.md
```

## Quick Start

Copy `assets/demo-template` into a working directory, then run:

```bash
cd demo-template
./scripts/start-demo.sh
```

To rerun migration and validation:

```bash
./scripts/migrate.sh
./scripts/verify.sh
```

To stop the containers:

```bash
./scripts/stop-demo.sh
```

## Default Ports and Credentials

- SQL Server source: `127.0.0.1:11433`
- Babelfish TDS target: `127.0.0.1:21433`
- Babelfish PostgreSQL target: `127.0.0.1:15432`
- Default password: `Demo_Passw0rd!`

Override the password with:

```bash
DEMO_PASSWORD='<new-password>' ./scripts/start-demo.sh
```

## Notes

Some host environments set `LD_LIBRARY_PATH` in a way that breaks system tools such as Docker, `dnf`, or `psql`. The bundled scripts call Docker with `env -u LD_LIBRARY_PATH` to avoid that issue.
