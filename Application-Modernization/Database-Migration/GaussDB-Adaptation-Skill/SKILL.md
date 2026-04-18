---
name: gaussdb-adaptation
description: Use this skill when porting SQL Server or vanilla PostgreSQL code to Huawei GaussDB (Kernel 505.x / openGauss-based). TRIGGER when source code or SQL contains any of — `Microsoft.Data.SqlClient`, `SqlBulkCopy`, `NEXT VALUE FOR`, `ON COMMIT DROP`, `CREATE TEMPORARY SEQUENCE`, `dbo.`, `NVARCHAR`, `ISNULL(`, `GETDATE()`, `OPTION (MAXDOP`, `TOP N`, `@@IDENTITY`, `WITH (NOLOCK)`, `[bracketed]` identifiers, `#tempTable`; OR csproj references `DotNetCore.GaussDB`, `DotNetCore.EntityFrameworkCore.GaussDB`, `HuaweiCloud.Driver.GaussDB`, `HuaweiCloud.EntityFrameworkCore.GaussDB`, `Npgsql.EntityFrameworkCore.PostgreSQL` alongside a GaussDB target; OR appsettings has `Persistence.Provider=GaussDb`; OR user mentions GaussDB / openGauss / 高斯数据库 / SHA256 SASL / `password_encryption_type` / apuração GaussDB migration.
---

# GaussDB Adaptation

## Overview

GaussDB (Huawei, kernel 505.x / openGauss-based) speaks **a PG-compatible but not identical dialect**. Code that compiles and runs against SQL Server — or even vanilla PostgreSQL — often fails on GaussDB in three categories:

1. **SQL dialect** — e.g. `CREATE TEMPORARY SEQUENCE` and `ON COMMIT DROP` are rejected at runtime
2. **Driver / authentication** — `DotNetCore.GaussDB` fails SHA256-only servers with a cryptic protocol error; Huawei's own `HuaweiCloud.Driver.GaussDB` works but uses a different namespace
3. **Bulk loading** — `SqlBulkCopy` has no drop-in replacement; the correct pattern is `BeginBinaryImport` + `COPY ... FROM STDIN BINARY`

The skill encodes landmines discovered on a real production port, with concrete before/after pairs.

## Quick Start

For any adaptation task, run this 4-step flow:

1. **Audit** — run `scripts/sql_dialect_audit.py <project-root>` to locate all anti-patterns, or grep for them manually (trigger list above)
2. **Map SQL dialect** — rewrite hits using [references/sql-dialect-map.md](references/sql-dialect-map.md)
3. **Verify driver + auth** — confirm csproj packages + `using` match the server's `password_encryption_type` per [references/connectivity-and-auth.md](references/connectivity-and-auth.md)
4. **Validate end-to-end** — run `scripts/gaussdb_connect_probe.cs` against the target GaussDB to confirm connection + BINARY COPY + `nextval` all work; then build the real project

## Workflow Decision Tree

| Task shape | Route |
|---|---|
| **One-off SQL rewrite** (single query / proc from T-SQL or vanilla PG) | Read [sql-dialect-map.md](references/sql-dialect-map.md), rewrite category-by-category |
| **App porting** (.NET project with `Microsoft.Data.SqlClient` / `Npgsql`) | Read [connectivity-and-auth.md](references/connectivity-and-auth.md) for driver choice, [bulk-load-patterns.md](references/bulk-load-patterns.md) for `SqlBulkCopy` replacement, then dialect-map for any embedded SQL |
| **Reviewing new code meant for GaussDB** | Scan with `sql_dialect_audit.py`; cross-reference [common-pitfalls.md](references/common-pitfalls.md) for subtle issues (copy-paste namespace leaks, wrong package versions, raw-string typos) |
| **Driver errors at runtime** (`Invalid username/password`, `AuthenticationRequest` protocol error) | Jump directly to [connectivity-and-auth.md](references/connectivity-and-auth.md) driver decision tree |

## Core Rules

- **Never** use in a GaussDB target: `ON COMMIT DROP`, `CREATE TEMPORARY SEQUENCE`, `TOP N`, `OPTION (...)`, `WITH (NOLOCK)`, `dbo.` schema prefix, `IDENTITY(…)` column type, `@@IDENTITY`, `#tempTable`, `[bracketed]` identifiers, `NVARCHAR`, `ISNULL(`, `GETDATE()`, `DATEADD(`, `NEWID()`, `LEN(`, `SET XACT_ABORT`, `SET NOCOUNT`, `BEGIN TRY … END CATCH`, `EXEC proc @p=v`, `DECLARE @var`, `MERGE ... OUTPUT`, `INSERT ... OUTPUT`
- **Always** check `SHOW password_encryption_type` on the target server before choosing a driver:
  - `0` or `1` → `DotNetCore.GaussDB 9.0.0` (MD5 path works, net9.0 OK)
  - `2` (SHA256-only, GaussDB 505+ default) → `HuaweiCloud.Driver.GaussDB 0.1.0` (only one with working SHA256 SASL for this server family)
- **Replace** `SqlBulkCopy.WriteToServerAsync(tbl)` with `using var w = conn.BeginBinaryImport($"""COPY "{t}" FROM STDIN BINARY"""); foreach row → w.StartRow(); w.Write(v, GaussDBDbType.X); await w.CompleteAsync(ct);`
- **Reserve id blocks** via `SELECT nextval('seq') - N + 1` in a single roundtrip; never `IDENTITY` columns in new tables
- **Temp tables**: `CREATE TEMP TABLE x (...) ON COMMIT DELETE ROWS;` — preceded by `DROP TABLE IF EXISTS x;` for reentrant batches
- **Temp sequences**: don't create them. Use a permanent sequence with `DROP SEQUENCE IF EXISTS x; CREATE SEQUENCE x ...;` bracket, and a final `DROP SEQUENCE IF EXISTS x;` at script end

## Default Deliverables

When invoked, produce:

- A **hit list** from the dialect audit (file:line → category → suggested replacement)
- **Rewritten code** for each hit, preserving business semantics
- A **driver/auth verdict** (is current csproj compatible with target server?) with upgrade steps if not
- An **e2e verification command** the user can run (usually the bundled probe script, parameterized with their DSN)

## Sanitization Rules

- Never emit real connection strings, passwords, hostnames, or customer identifiers into checked-in files. Use placeholders: `<host>`, `<port>`, `<user>`, `<pwd>`, `<database>`
- When demonstrating a connection in a generated file, read DSN from environment (`GAUSSDB_DSN`) rather than hard-coding
- Treat private NuGet package names, internal namespaces, and business domain terms in examples as illustrative; genericize when documenting

## Script Use

- `scripts/sql_dialect_audit.py <dir>` — stdlib-only Python, walks a tree and reports every anti-pattern by file:line → category. Use to **quickly inventory** an unfamiliar codebase before planning a port.
- `scripts/gaussdb_connect_probe.cs` — single-file .NET 9 probe. `GAUSSDB_DSN=... dotnet run` to verify a driver + server combo. Exercises connect, encryption check, BINARY COPY, `nextval`, commit. Use to **confirm the environment** before touching business code.

## Reference Use

Pull in only when the task demands:

- [references/sql-dialect-map.md](references/sql-dialect-map.md) — the authoritative side-by-side rewrite table
- [references/connectivity-and-auth.md](references/connectivity-and-auth.md) — driver decision tree, server encryption modes, connection-string keys
- [references/bulk-load-patterns.md](references/bulk-load-patterns.md) — BINARY COPY template, id block allocation, reentrant temp tables
- [references/common-pitfalls.md](references/common-pitfalls.md) — real-world traps: raw-string CS8998, namespace copy-paste leaks, DI that compiles-but-fails-at-runtime, private package namespace moves
