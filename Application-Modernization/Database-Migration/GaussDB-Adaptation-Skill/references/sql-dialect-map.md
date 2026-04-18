# SQL Dialect Map — T-SQL / vanilla PG → GaussDB

All rows marked **UNSUPPORTED** are confirmed against GaussDB Kernel 505.2.1 (openGauss-based) — they will raise a runtime error, not a silent no-op. The dialect is otherwise ~95% PostgreSQL-compatible, so most vanilla PG code needs no change.

---

## 1. Identifiers & Schemas

| SQL Server | Vanilla PG | **GaussDB** | Notes |
|---|---|---|---|
| `[foo bar]` | `"foo bar"` | `"foo bar"` | prefer unquoted lowercase identifier when possible |
| `dbo.tab` | `public.tab` or `tab` | `public.tab` or `tab` | `dbo.` is SQL-Server only — strip it |
| `SET QUOTED_IDENTIFIER ON` | n/a | n/a | remove |
| `USE db;` | `\c db` (psql) | `\c db` (gsql) | session switch — not a statement executable via ADO.NET; use connection string |

## 2. Temp Tables

| Construct | SQL Server | Vanilla PG | **GaussDB** |
|---|---|---|---|
| declare | `#t` (session), `##t` (global) | `CREATE TEMP TABLE t` | same as PG |
| lifecycle | dropped at session end | default `ON COMMIT PRESERVE ROWS` | **only `PRESERVE ROWS` or `DELETE ROWS`** — `ON COMMIT DROP` raises `42P16: ON COMMIT only support PRESERVE ROWS or DELETE ROWS option` |
| exists-drop idiom | `IF OBJECT_ID('tempdb..#t') DROP TABLE #t` | `DROP TABLE IF EXISTS t` | `DROP TABLE IF EXISTS t` |

**Recommended reentrant pattern for GaussDB:**
```sql
DROP TABLE IF EXISTS t;
CREATE TEMP TABLE t (...) ON COMMIT DELETE ROWS;
```

## 3. Sequences & Auto-Increment

| Operation | SQL Server | Vanilla PG | **GaussDB** |
|---|---|---|---|
| get next value | `NEXT VALUE FOR seq` | `nextval('seq')` | `nextval('seq')` |
| declare sequence | `CREATE SEQUENCE seq` | `CREATE SEQUENCE seq` | same |
| temp sequence | n/a | `CREATE TEMPORARY SEQUENCE seq` | **UNSUPPORTED** — raises `0A000: Temporary sequences are not supported` |
| auto-increment column | `id INT IDENTITY(1,1)` | `id SERIAL` / `BIGSERIAL` | `id SERIAL` / `BIGSERIAL` (or explicit `DEFAULT nextval('seq')`) |
| get last inserted | `@@IDENTITY`, `SCOPE_IDENTITY()` | `lastval()`, `RETURNING col` | **prefer `RETURNING col`** |

**Replacement for `CREATE TEMPORARY SEQUENCE` in script-level code:**
```sql
DROP SEQUENCE IF EXISTS seq_x;
CREATE SEQUENCE seq_x START 1 INCREMENT 1;
-- ... use nextval('seq_x') ...
DROP SEQUENCE IF EXISTS seq_x;    -- at end of script
```

## 4. Data Types

| T-SQL | **GaussDB** | Notes |
|---|---|---|
| `NVARCHAR(n)` | `VARCHAR(n)` or `TEXT` | no separate `N` prefix; UTF-8 by default |
| `VARCHAR(n)` | `VARCHAR(n)` | OK |
| `DATETIME` / `DATETIME2` | `TIMESTAMP` | |
| `DATETIMEOFFSET` | `TIMESTAMPTZ` | |
| `UNIQUEIDENTIFIER` | `UUID` | |
| `BIT` | `BOOLEAN` | |
| `MONEY` | `NUMERIC(19,4)` | |
| `VARBINARY(MAX)` | `BYTEA` | |
| `SQL_VARIANT` | no equivalent | redesign required |
| `IMAGE`, `TEXT`, `NTEXT` (legacy) | `BYTEA` / `TEXT` | |

## 5. Functions

| T-SQL | **GaussDB (PG-style)** |
|---|---|
| `ISNULL(x, y)` | `COALESCE(x, y)` |
| `GETDATE()` | `CURRENT_TIMESTAMP` or `now()` |
| `GETUTCDATE()` | `CURRENT_TIMESTAMP AT TIME ZONE 'UTC'` |
| `DATEADD(day, n, x)` | `x + n * INTERVAL '1 day'` |
| `DATEDIFF(day, a, b)` | `(b::date - a::date)` |
| `NEWID()` | `gen_random_uuid()` (requires `pgcrypto` ext or GaussDB native) |
| `LEN(s)` | `char_length(s)` or `length(s)` |
| `CHARINDEX(a, b)` | `strpos(b, a)` |
| `SUBSTRING(s, i, n)` | same (SUBSTRING syntax) |
| `CAST(x AS NVARCHAR)` | `CAST(x AS TEXT)` |
| `CONVERT(type, x, style)` | `to_char(x, fmt)` or `CAST(x AS type)` — style codes not supported |
| `IIF(cond, a, b)` | `CASE WHEN cond THEN a ELSE b END` |
| `CHOOSE(n, a, b, c)` | `CASE n WHEN 1 THEN a WHEN 2 THEN b ...` |

## 6. Query Hints & Session Flags

| T-SQL | **GaussDB** | Action |
|---|---|---|
| `TOP N` | `LIMIT N` | rewrite |
| `OPTION (MAXDOP N)` | no equivalent | **remove** — parallelism is server-configured |
| `OPTION (RECOMPILE)` | n/a | remove |
| `OPTION (HASH JOIN)`, `OPTION (MERGE JOIN)` | use `set enable_hashjoin=on/off`, etc., at session level | rewrite to GUC or remove |
| `WITH (NOLOCK)` | set `default_transaction_isolation = 'read uncommitted'` (or per-tx) | **remove the hint**, adjust isolation only if actually needed |
| `SET XACT_ABORT ON` | n/a (PL/pgSQL tx model is different) | remove |
| `SET NOCOUNT ON` | n/a | remove |
| `SET ANSI_NULLS ON` | n/a (always ANSI) | remove |

## 7. Bulk / Batch Operations

| Operation | SQL Server | **GaussDB** |
|---|---|---|
| fast bulk insert from client | `SqlBulkCopy.WriteToServerAsync(dataTable)` | `conn.BeginBinaryImport("COPY \"t\" FROM STDIN BINARY")` — see [bulk-load-patterns.md](bulk-load-patterns.md) |
| insert with generated key | `INSERT ... OUTPUT INSERTED.id VALUES(...)` | `INSERT ... VALUES(...) RETURNING id` |
| upsert | `MERGE target USING source ... WHEN MATCHED ... WHEN NOT MATCHED THEN INSERT ... OUTPUT inserted.*` | `INSERT ... ON CONFLICT (keys) DO UPDATE SET ... RETURNING *` |
| conditional delete returning rows | `DELETE t OUTPUT DELETED.* WHERE ...` | `DELETE FROM t WHERE ... RETURNING *` |
| `MERGE` statement | supported (MSSQL flavor) | supported (**different syntax** — PG-style; avoid if portability matters) |

## 8. Stored Procedures / Scripts / PL

| T-SQL | **GaussDB (PL/pgSQL or A-compat)** |
|---|---|
| `DECLARE @v INT;` | `DECLARE v INT;` — no `@` prefix on variables |
| `SET @v = 1;` | `v := 1;` |
| `PRINT 'x'` | `RAISE NOTICE 'x';` |
| `EXEC proc @p=1, @q=2` | `CALL proc(p => 1, q => 2);` — or positional: `CALL proc(1, 2);` |
| `CREATE PROCEDURE foo @x INT AS BEGIN ... END` | `CREATE OR REPLACE PROCEDURE foo(x INT) AS $$ BEGIN ... END; $$ LANGUAGE plpgsql;` |
| `BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH` | `BEGIN ... EXCEPTION WHEN <cond> THEN ... END;` |
| `RAISERROR('...', 16, 1)` | `RAISE EXCEPTION '...';` |
| `@@ROWCOUNT` | `GET DIAGNOSTICS n = ROW_COUNT;` |
| table variables `DECLARE @t TABLE(...)` | not supported; use `CREATE TEMP TABLE` + `ON COMMIT DELETE ROWS` |
| `OUTPUT INTO @tbl` | insert `RETURNING ...` into a temp table |

## 9. Indexes / DDL

| T-SQL | **GaussDB** | Notes |
|---|---|---|
| `CREATE CLUSTERED INDEX` | `CREATE INDEX ...` | GaussDB doesn't cluster data by index in the MSSQL sense; use `CLUSTER t USING idx` separately if needed |
| `CREATE NONCLUSTERED INDEX` | `CREATE INDEX ...` | plain index |
| `CREATE INDEX ... INCLUDE (cols)` | `CREATE INDEX ... INCLUDE (cols)` | supported |
| `FILESTREAM`, `SPARSE COLUMN` | no equivalent | redesign |
| `COLUMNSTORE INDEX` | no equivalent in row-store tables; consider **CStore** / **ColStore** table storage (GaussDB-specific) |
| `WITH (FILLFACTOR=80)` | `WITH (fillfactor=80)` | supported, lowercase |

## 10. Common Rewrite Examples

### Paged top query
```sql
-- T-SQL
SELECT TOP 100 * FROM dbo.Pedidos WHERE Status = 'A' ORDER BY CriadoEm DESC;
-- GaussDB
SELECT * FROM Pedidos WHERE Status = 'A' ORDER BY CriadoEm DESC LIMIT 100;
```

### Null coalescing + date filter
```sql
-- T-SQL
SELECT ISNULL(Nome, '<vazio>') FROM Cliente WHERE Atualizado >= DATEADD(DAY, -7, GETDATE());
-- GaussDB
SELECT COALESCE(Nome, '<vazio>') FROM Cliente WHERE Atualizado >= CURRENT_TIMESTAMP - INTERVAL '7 days';
```

### Stored proc with output param
```sql
-- T-SQL
CREATE PROCEDURE NextId @out BIGINT OUTPUT AS
BEGIN
    SET @out = NEXT VALUE FOR seq_id;
END;
EXEC NextId @out = @x OUTPUT;

-- GaussDB
CREATE OR REPLACE FUNCTION NextId() RETURNS BIGINT AS $$
BEGIN
    RETURN nextval('seq_id');
END;
$$ LANGUAGE plpgsql;
SELECT NextId() INTO x;    -- or: x := NextId();
```

### Temp table + sequence (classic batch pattern)
```sql
-- T-SQL
IF OBJECT_ID('tempdb..#batch') IS NOT NULL DROP TABLE #batch;
CREATE TABLE #batch (Id INT IDENTITY(1,1), PayloadId BIGINT);
INSERT INTO #batch (PayloadId) SELECT Id FROM Payload WHERE Status = 'P';

-- GaussDB (reentrant)
DROP TABLE IF EXISTS batch;
DROP SEQUENCE IF EXISTS seq_batch_id;
CREATE SEQUENCE seq_batch_id;
CREATE TEMP TABLE batch (
    Id BIGINT NOT NULL DEFAULT nextval('seq_batch_id'),
    PayloadId BIGINT
) ON COMMIT DELETE ROWS;
INSERT INTO batch (PayloadId) SELECT Id FROM Payload WHERE Status = 'P';
-- at end of script: DROP SEQUENCE IF EXISTS seq_batch_id;
```
