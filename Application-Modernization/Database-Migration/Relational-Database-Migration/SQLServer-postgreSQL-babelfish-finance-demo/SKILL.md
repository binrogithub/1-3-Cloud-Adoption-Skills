---
name: sqlserver-babelfish-finance-demo
description: Build, adapt, or explain a local finance migration demo from SQL Server to PostgreSQL through Babelfish. Use when Codex needs to create a small host-local SQL Server source database, initialize Babelfish/PostgreSQL, migrate a banking FinanceDemo workload through the TDS port, validate SQL Server/Babelfish/PostgreSQL query parity, or troubleshoot this demo's Docker, FreeTDS, sqlcmd, Babelfish initialization, md5 auth, UTF-8, or LD_LIBRARY_PATH issues.
---

# SQL Server Babelfish Finance Demo

## Purpose

Use this skill to reproduce or customize a host-local migration demo where a SQL Server finance workload is moved to Babelfish/PostgreSQL while SQL Server client protocol compatibility is preserved.

The bundled template is in `assets/demo-template/`. Copy it into a working directory before editing or running it.

## Default Scenario

Use `FinanceDemo` as the demo database unless the user asks for another business story.

The scenario is a bank migrating core account reporting and payment liquidity queries from SQL Server to PostgreSQL:

- `Customers`: customer master data, segment, risk rating
- `Accounts`: bank accounts, product, currency, balance
- `Payments`: payment and transfer ledger rows
- `RiskAlerts`: risk events tied to payments
- `v_customer_exposure`: account balance, outgoing payment, open alert exposure by customer
- `v_daily_payment_liquidity`: daily payment totals and high-value transfer count
- `usp_customer_exposure`, `usp_daily_payment_liquidity`: T-SQL stored procedure query surfaces

For detailed table and procedure intent, read `references/finance-demo.md`.

## Workflow

1. Inspect the host first:
   - Check Docker availability with `env -u LD_LIBRARY_PATH docker --version`.
   - Check FreeTDS `tsql` and SQL Server client availability. In the SQL Server 2019 container, `sqlcmd` is usually `/opt/mssql-tools18/bin/sqlcmd`.
   - If system tools fail with OpenSSL/LDAP symbol errors, run affected commands with `env -u LD_LIBRARY_PATH`.

2. Create or update the demo workspace:
   - Copy `assets/demo-template/scripts` and `assets/demo-template/sql` into the target project directory.
   - Keep scripts executable.
   - If adding a README for the user's project, describe ports, credentials, commands, and the finance story there; do not add auxiliary docs inside the skill itself.

3. Start the demo:
   - Run `./scripts/start-demo.sh` from the demo workspace.
   - The default containers are `sqlserver-demo` and `babelfish-demo`.
   - The default ports are SQL Server `11433`, Babelfish TDS `21433`, and Babelfish PostgreSQL `15432`.
   - The default password is `Demo_Passw0rd!`, override with `DEMO_PASSWORD`.

4. Validate the migration:
   - Run `./scripts/verify.sh`.
   - Confirm SQL Server source and Babelfish TDS target return the same stored procedure results.
   - Confirm PostgreSQL sees mapped schemas such as `financedemo_dbo.payments`.

5. Stop the demo when requested:
   - Run `./scripts/stop-demo.sh`.

## Babelfish Setup Notes

Use these implementation details when adapting the template:

- Initialize Babelfish with UTF-8, for example `POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale=C.UTF-8 --auth-host=md5"`.
- Set `LD_LIBRARY_PATH=/usr/local/lib` inside the Babelfish container when using the bundled `rsubr/postgres-babelfish` image; otherwise extension loading can fail with missing `babelfishpg_common.so`.
- Use `password_encryption=md5` and md5 host auth for this Babelfish 2.3.0 demo image; TDS login may reject SCRAM host auth.
- Set `babelfishpg_tsql.database_name` to the PostgreSQL database that owns Babelfish, usually `demo`.
- Load Babelfish through the PostgreSQL port, then use the TDS port for SQL Server-compatible DDL/DML and procedure calls.

## Expected Validation Shape

A successful run shows:

- SQL Server source procedure `usp_customer_exposure` returns four customers.
- SQL Server source procedure `usp_daily_payment_liquidity` returns three business dates.
- Babelfish TDS returns the same logical result sets, though date/decimal display formatting can differ.
- PostgreSQL protocol lists `financedemo_dbo` tables: `accounts`, `customers`, `payments`, `riskalerts`.

## Troubleshooting

- `dnf`, `psql`, `sudo`, or Docker fail with `EVP_md2` or LDAP/OpenSSL errors: run the command with `env -u LD_LIBRARY_PATH`.
- Babelfish extension creation fails with unsupported encoding: rebuild the container with UTF-8 init args.
- Babelfish extension creation fails loading `babelfishpg_tsql.so`: ensure container `LD_LIBRARY_PATH=/usr/local/lib`.
- TDS login fails with unsupported authentication: rebuild with `POSTGRES_HOST_AUTH_METHOD=md5`, `--auth-host=md5`, and `password_encryption=md5`.
- FreeTDS connection fails unexpectedly: set `TDSVER=7.4`.
