# Bulk-Load Patterns

Three patterns cover 95% of batch scenarios: **BINARY COPY** (replaces `SqlBulkCopy`), **nextval block allocation** (replaces `IDENTITY`), and **reentrant temp tables** (replaces `#tempTable ON COMMIT DROP`).

---

## 1. BINARY COPY — the `SqlBulkCopy` replacement

GaussDB has no drop-in equivalent of `SqlBulkCopy`. The fast path is `BeginBinaryImport` + `COPY ... FROM STDIN BINARY`.

### Template (C#, uses common types from either driver namespace)

```csharp
using System.Data;
using System.Data.Common;
// using GaussDB;            // DotNetCore.GaussDB
// using GaussDBTypes;
using HuaweiCloud.GaussDB;   // HuaweiCloud.Driver.GaussDB
using HuaweiCloud.GaussDBTypes;

public static async Task BulkInsertAsync(
    DbConnection connection,
    DbTransaction transaction,   // transaction lives on the connection; writer attaches to current tx implicitly
    string tableName,
    DataTable table,
    CancellationToken ct)
{
    var conn = (GaussDBConnection)connection;
    // Quote the identifier to preserve case/specials:
    var sql = $"""COPY "{tableName}" FROM STDIN BINARY""";  // ← exactly 3 closing quotes!

    await using var writer = await conn.BeginBinaryImportAsync(sql, ct);
    foreach (DataRow row in table.Rows)
    {
        await writer.StartRowAsync(ct);
        foreach (DataColumn col in table.Columns)
            await writer.WriteAsync(row[col], MapType(col.DataType), ct);
    }
    await writer.CompleteAsync(ct);
}
```

### .NET → `GaussDBDbType` map

| .NET type | `GaussDBDbType` member | Notes |
|---|---|---|
| `string` | `Text` | or `Varchar` |
| `int`, `int?` | `Integer` | |
| `long`, `long?` | **`Bigint`** | lowercase-d — not `BigInt` |
| `short`, `short?` | `Smallint` | |
| `decimal`, `decimal?` | `Numeric` | |
| `float`, `double` | `Real`, `Double` | |
| `bool`, `bool?` | `Boolean` | |
| `DateTime` | `Timestamp` | |
| `DateTimeOffset` | `TimestampTz` | |
| `TimeSpan` | `Interval` or `Time` | |
| `Guid` | `Uuid` | |
| `byte[]` | `Bytea` | |
| `char[]`, `char(8)` | `Char` | fixed length — use `PadRight` client-side to match column width |

### Sync vs Async overloads

Both `BeginBinaryImport(string)` (sync) and `BeginBinaryImportAsync(string, ct)` (async) exist. Same for `StartRow[Async]`, `Write[Async]`, `Complete[Async]`, `DisposeAsync`. `using var writer = conn.BeginBinaryImport(...)` is fine for synchronous pipelines.

### Pitfalls

1. **Raw string quote count** — `$"""COPY "{t}" FROM STDIN BINARY""""` (4 trailing quotes) is a **compile error** `CS8998`. Use exactly 3: `""")`.
2. **Table-name injection** — never interpolate user-supplied names without validation; use `"` quoting and validate against a whitelist.
3. **Transaction** — the importer shares the current transaction on the connection. Don't pass the `DbTransaction` separately — the API doesn't accept it. Just make sure the transaction is already started on `conn`.
4. **Column order** — `StartRow` + sequential `Write` calls must match the table's physical column order. If you use `COPY "t" (col1, col2) FROM STDIN BINARY`, write values in the listed order.
5. **Error recovery** — if a row fails mid-stream, the whole import aborts. Catch exceptions around `CompleteAsync` and retry the batch.

## 2. Sequence Block Allocation — the `IDENTITY` replacement

**Problem:** round-tripping `nextval()` per row is slow. For N rows, you want a single call that **reserves N IDs**.

**Formula:** after `nextval` advances the sequence by N in one statement, `returned_value - N + 1` is the first ID of the block.

```csharp
public static async Task<long> ReserveIdsAsync(
    string sequenceName,
    int count,
    DbConnection connection,
    DbTransaction transaction,
    CancellationToken ct)
{
    await using var cmd = connection.CreateCommand();
    cmd.Transaction = transaction;
    cmd.CommandText = $"SELECT nextval('{sequenceName}') - {count} + 1 AS first_value";
    // ^ sequenceName and count must be safe (validate server-side identifier, count > 0)
    return (long)await cmd.ExecuteScalarAsync(ct);
}
```

Caller then uses `firstId`, `firstId + 1`, …, `firstId + count - 1` for the N rows.

**Why `nextval - N + 1`?** A single call to `nextval` on a GaussDB sequence with default `CACHE 1, INCREMENT 1` returns one value and advances by 1. To advance by N, call `nextval()` inside a set-returning function or rely on an incrementing trick. **A cleaner variant:**

```sql
SELECT nextval('seq') FROM generate_series(1, N);
```

returns N consecutive values — use the first. If the sequence has `INCREMENT 1`, both forms give the same result. If the sequence is defined with a larger `INCREMENT` or `CACHE`, use `generate_series` and take the min.

## 3. Reentrant Temp Table (replaces `#t ... ON COMMIT DROP`)

**Pattern:**

```sql
DROP TABLE IF EXISTS tmp_batch;
CREATE TEMP TABLE tmp_batch (
    id BIGINT NOT NULL,
    docto_id BIGINT,
    created TIMESTAMP DEFAULT now()
) ON COMMIT DELETE ROWS;
```

**Lifecycle semantics:**

| Option | Behavior at COMMIT |
|---|---|
| `PRESERVE ROWS` (default) | rows kept, table persists in session |
| `DELETE ROWS` | rows truncated, table persists in session |
| `DROP` | **UNSUPPORTED in GaussDB** — raises `42P16` |

**Recommended for reentrant batches:** `ON COMMIT DELETE ROWS`, combined with `DROP TABLE IF EXISTS` before each run. This guarantees:

- each batch starts with an empty table
- schema is recreated if column definition changed between runs
- table stays within session scope so it doesn't leak to other connections

### Supporting C# helper

```csharp
public static async Task PrepareBatchTableAsync(
    DbConnection conn,
    DbTransaction tx,
    string tableName,
    string columnName,
    string columnType,    // "BIGINT", "CHAR(8)", ...
    CancellationToken ct)
{
    var q = (string s) => "\"" + s.Replace("\"", "\"\"") + "\"";
    await using var cmd = conn.CreateCommand();
    cmd.Transaction = tx;
    cmd.CommandText = $"""
        DROP TABLE IF EXISTS {q(tableName)};
        CREATE TEMP TABLE {q(tableName)} (
            {q(columnName)} {columnType} NOT NULL PRIMARY KEY
        ) ON COMMIT DELETE ROWS;
        """;
    await cmd.ExecuteNonQueryAsync(ct);
}
```

## 4. End-to-End Batch Recipe

Put it together for a typical "receive N payloads, insert and get IDs" flow:

```csharp
await using var tx = await conn.BeginTransactionAsync(ct);

// 1. prepare reentrant staging
await PrepareBatchTableAsync(conn, tx, "tmp_stg", "row_idx", "INT", ct);

// 2. bulk-load staging
await BulkInsertAsync(conn, tx, "tmp_stg", rowsTable, ct);

// 3. reserve id block
var firstId = await ReserveIdsAsync("seq_docto_id", rowsTable.Rows.Count, conn, tx, ct);

// 4. materialize into real table joined with staging
await using (var cmd = conn.CreateCommand())
{
    cmd.Transaction = tx;
    cmd.CommandText = $"""
        INSERT INTO docto (id, payload_key, created)
        SELECT {firstId} + s.row_idx - 1, p.key, now()
        FROM   tmp_stg s
        JOIN   payload p ON p.idx = s.row_idx;
        """;
    await cmd.ExecuteNonQueryAsync(ct);
}

await tx.CommitAsync(ct);
```

This pattern is **O(1) roundtrips** in ID allocation and **O(batch-size) in COPY** — typical throughput is several hundred thousand rows/second on a warm connection.
