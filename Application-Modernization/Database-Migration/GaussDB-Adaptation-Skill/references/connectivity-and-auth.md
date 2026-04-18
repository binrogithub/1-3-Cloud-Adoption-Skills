# Connectivity & Authentication

The single biggest landmine in .NET + GaussDB integration is the **driver ↔ server auth-mode mismatch**. This doc tells you how to diagnose and fix it.

---

## 1. Diagnose the Server (run these **as a trusted user**, read-only)

```sql
SHOW server_version;                      -- e.g. 9.2.4 (PG-compat version)
SELECT version();                         -- e.g. gaussdb (GaussDB Kernel 505.2.1.SPC0800 ...)
SHOW password_encryption_type;            -- 0|1|2|3  — the key number
SHOW auth_iteration_count;                -- e.g. 10000
SHOW ssl;                                 -- on/off
SELECT rolname,
       substring(rolpassword, 1, 3) AS pw_prefix,
       length(rolpassword) AS pw_len
FROM pg_authid WHERE rolname = current_user;
```

`password_encryption_type` values:

| Value | Meaning | What the server will send during handshake |
|---|---|---|
| `0` | MD5 only | `AuthenticationMD5Password` (standard PG) |
| `1` | **SHA256 + MD5 (both stored)** | **MD5 path available** — most drivers work |
| `2` | SHA256 only | GaussDB-proprietary SHA256 SASL challenge |
| `3` | SM3 only (Chinese national crypto) | GaussDB-proprietary SM3 challenge |

Default on fresh GaussDB 505+ clusters is commonly `2`.

## 2. .NET Driver Decision Tree

| Server `pwd_enc_type` | Target framework | Use | Auth path | Works? |
|---|---|---|---|---|
| `0` or `1` | **net9.0** | `DotNetCore.GaussDB 9.0.0` + `DotNetCore.EntityFrameworkCore.GaussDB 9.0.0` | MD5 | ✅ |
| `2` | **net9.0** | `DotNetCore.GaussDB 9.0.0` | SHA256 SASL | ❌ fails with `Received backend message AuthenticationRequest while expecting AuthenticationRequestMessage` |
| `2` | **net9.0** | **`HuaweiCloud.Driver.GaussDB 0.1.0`** | SHA256 SASL | ✅ |
| `2` | **net10.0** | `HuaweiCloud.Driver.GaussDB 0.1.0` (ADO.NET) + `HuaweiCloud.EntityFrameworkCore.GaussDB 0.0.1` (EF Core) | SHA256 SASL | ✅ |
| `3` | any | no public .NET driver currently ships SM3 support | — | ❌ ask DBA to change encryption type |

**DO NOT** use:
- `Npgsql 9.x` / `Npgsql.EntityFrameworkCore.PostgreSQL 9.x` against GaussDB with SHA256 (same failure mode as DotNetCore.GaussDB against `type=2`)
- `DotNetCore.GaussDB 10.0.0` against `type=2` from net10.0 — handshake completes but server rejects with `28P01 Invalid username/password` (driver's proof hash differs from server's)

## 3. Namespace & Type Reference

Both driver families expose the same **type names** but under **different namespaces**.

| Package | Top-level namespace | Types enum namespace |
|---|---|---|
| `DotNetCore.GaussDB` | `GaussDB` | `GaussDBTypes` (not nested under `GaussDB`) |
| `HuaweiCloud.Driver.GaussDB` | `HuaweiCloud.GaussDB` | `HuaweiCloud.GaussDBTypes` |

Common types present in both (pick the right namespace):

- `GaussDBConnection` : `DbConnection`
- `GaussDBTransaction` : `DbTransaction`
- `GaussDBCommand` : `DbCommand`
- `GaussDBBinaryImporter` — returned by `BeginBinaryImport(string)` / `BeginBinaryImportAsync(string, ct)`
- `GaussDBDbType` enum — note **`Bigint`** (not `BigInt`), `Integer`, `Numeric`, `Text`, `Boolean`, `Timestamp`, `Uuid`, `Bytea`, …

**Correct `using` blocks by driver choice:**

```csharp
// DotNetCore.GaussDB
using GaussDB;
using GaussDBTypes;

// HuaweiCloud.Driver.GaussDB
using HuaweiCloud.GaussDB;
using HuaweiCloud.GaussDBTypes;
```

## 4. Connection String

All standard PG keys work. Common examples:

```
Host=<ip>;Port=<port>;Username=<user>;Password=<pwd>;Database=<db>;
```

Optional tuning:

| Key | Effect |
|---|---|
| `SSL Mode=Disable|Allow|Prefer|Require|VerifyCA|VerifyFull` | default Prefer |
| `Channel Binding=Disable|Prefer|Require` | set to `Disable` in environments where proxy breaks channel binding |
| `Timeout=15` | connection timeout seconds |
| `Pooling=false` | disable pool (diagnostic only) |
| `Include Error Detail=true` | richer PG error info in exceptions |
| `Server Compatibility Mode=None|Redshift|NoTypeLoading` | only `None` is safe for GaussDB |

## 5. EF Core Provider

| Target .NET | Provider choice | Notes |
|---|---|---|
| net9.0 | `DotNetCore.EntityFrameworkCore.GaussDB 9.0.0` | internally uses `DotNetCore.GaussDB 9.0.0`, so subject to same SHA256 limitation — best for servers at `pwd_enc_type=1` |
| net10.0 | `HuaweiCloud.EntityFrameworkCore.GaussDB 0.0.1` | uses `HuaweiCloud.Driver.GaussDB`, works with `pwd_enc_type=2` |

Extension method in both: `DbContextOptionsBuilder.UseGaussDB(connectionString, opts => ...)`.

## 6. Mixed Strategy (when stuck on net9.0 but server is `pwd_enc_type=2`)

If you cannot upgrade to net10.0 and cannot convince the DBA to switch the server to `type=1`, you can coexist:

- **csproj**: reference **both** `DotNetCore.EntityFrameworkCore.GaussDB` (for the EF Core provider to compile) and `HuaweiCloud.Driver.GaussDB` (for ADO.NET actual connections)
- **ADO.NET code paths**: open `HuaweiCloud.GaussDB.GaussDBConnection` directly (works)
- **EF Core code paths**: they will call `DotNetCore.GaussDB` internally → still fail on this server

This is a **compile-green, partial-runtime-fail** setup — acceptable only if your runtime flow never exercises the EF Core DB paths. Otherwise, plan the net10.0 upgrade or get the server changed.

## 7. Server-Side Fix Recipe

The cleanest fix when driver choice is constrained:

```sql
-- as a DBA:
ALTER SYSTEM SET password_encryption_type = 1;   -- needs SIGHUP / restart depending on install
-- then for each user whose password was SHA256-only:
ALTER USER app_user IDENTIFIED BY '<new-pwd>' REPLACE '<old-pwd>';
-- verify:
SELECT rolname, substring(rolpassword, 1, 5) AS pw_prefix FROM pg_authid WHERE rolname = 'app_user';
-- now MD5+SHA256 are both stored; DotNetCore.GaussDB can log in via MD5
```

Requires DB admin access; not possible over the wire alone.

## 8. Diagnostic Signatures

When you see these, jump to this doc:

| Error | Cause | Fix |
|---|---|---|
| `GaussDBException: Received backend message AuthenticationRequest while expecting AuthenticationRequestMessage` | `DotNetCore.GaussDB` vs `pwd_enc_type=2` | switch to `HuaweiCloud.Driver.GaussDB` or upgrade server |
| `PostgresException 28P01: Invalid username/password, login denied` (after SHA256 handshake) | driver sent wrong proof hash (e.g. `DotNetCore.GaussDB 10.0.0`) | use `HuaweiCloud.Driver.GaussDB` |
| `psycopg2 OperationalError: none of the server's SASL authentication mechanisms are supported` | libpq doesn't support GaussDB SHA256 SASL variant | no direct fix; only GaussDB-aware drivers work |
| `GaussDBAuthenticateSASLSha256` in stack trace + cryptic failure | any SHA256 flavor mismatch | verify driver / server combination per table above |
