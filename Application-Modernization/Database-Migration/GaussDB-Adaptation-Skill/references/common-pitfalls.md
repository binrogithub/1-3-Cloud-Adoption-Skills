# Common Pitfalls

Real landmines discovered during a production GaussDB port. Each entry includes the **signature** (how it manifests), the **root cause**, and the **fix**.

---

## Category A — Dialect Leaks

### A1. `ON COMMIT DROP` in temp table DDL
- **Signature:** `PostgresException 42P16: ON COMMIT only support PRESERVE ROWS or DELETE ROWS option`
- **Cause:** PG allows `DROP`, GaussDB doesn't
- **Fix:** `ON COMMIT DELETE ROWS` + explicit `DROP TABLE IF EXISTS` in reentrant loops

### A2. `CREATE TEMPORARY SEQUENCE`
- **Signature:** `PostgresException 0A000: Temporary sequences are not supported`
- **Cause:** GaussDB lacks session-scoped sequences
- **Fix:** `DROP SEQUENCE IF EXISTS x; CREATE SEQUENCE x START 1;` at the top, symmetric `DROP SEQUENCE IF EXISTS x;` at the bottom

### A3. T-SQL hints leaking into GaussDB SQL
- **Signature:** syntax error on `OPTION (MAXDOP 1)`, `WITH (NOLOCK)`, `TOP 10`
- **Cause:** copy-pasted from T-SQL without review
- **Fix:** `OPTION (...)` → remove entirely; `WITH (NOLOCK)` → remove (set isolation at tx level if actually needed); `TOP N` → `LIMIT N`

### A4. Hybrid dialect in one statement (mid-port)
- **Signature:** malformed SQL that looks like it was machine-translated half-way
  - e.g. `CALL sp_sequence_get_range(sequence_name => '{seq}', range_size => count, range_first_value => first);` with undeclared `count` (C# variable name literally embedded in SQL)
  - e.g. `/*OPTION (MAXDOP 1)*/ RETURNING col` — commented T-SQL hint alongside PG `RETURNING`
- **Cause:** partial refactor where only some constructs were translated
- **Fix:** read the whole block, rewrite end-to-end; never leave half-translated SQL in place

### A5. `dbo.` schema prefix
- **Signature:** `ERROR: schema "dbo" does not exist`
- **Cause:** SQL-Server-specific default schema
- **Fix:** remove the prefix; use `public.` only if you explicitly mean it

---

## Category B — Driver & Package Issues

### B1. SHA256 authentication protocol mismatch
- **Signature:** `GaussDBException: Received backend message AuthenticationRequest while expecting AuthenticationRequestMessage. Please file a bug.`
- **Cause:** `DotNetCore.GaussDB` (all versions 8.0.1, 9.0.0) attempting SASL-SHA256 against a GaussDB 505+ server with `password_encryption_type=2`
- **Fix:** switch csproj to `HuaweiCloud.Driver.GaussDB 0.1.0`, update usings: `using GaussDB;` → `using HuaweiCloud.GaussDB;`, `using GaussDBTypes;` → `using HuaweiCloud.GaussDBTypes;`. If you must stay on `DotNetCore.GaussDB`, ask DBA to set `password_encryption_type=1`

### B2. Wrong package at all (`Npgsql` where `GaussDB` was expected)
- **Signature:** `error CS0246: The type or namespace name 'GaussDBConnection' could not be found` despite csproj having a `Npgsql` reference
- **Cause:** source code written against `GaussDB` namespace (Huawei driver family), but csproj still lists `Npgsql`
- **Fix:** swap `Npgsql` for one of `DotNetCore.GaussDB` / `HuaweiCloud.Driver.GaussDB` per the driver decision tree

### B3. Fake package name in csproj
- **Signature:** `error NU1101: Unable to find package GaussDB. No packages exist with this id in source(s): nuget.org`
- **Cause:** someone text-replaced `Npgsql` → `GaussDB` in csproj without checking if that's a real NuGet id
- **Fix:** real package ids are `DotNetCore.GaussDB` or `HuaweiCloud.Driver.GaussDB` — bare `GaussDB` does not exist on nuget.org

### B4. Nested namespace that doesn't exist
- **Signature:** `error CS0246: The type or namespace name 'GaussDBTypes' could not be found` inside `GaussDB.GaussDBTypes`
- **Cause:** `using GaussDB.GaussDBTypes;` — the enum namespace is top-level `GaussDBTypes`, NOT nested under `GaussDB`
- **Fix:** two separate usings: `using GaussDB; using GaussDBTypes;` (or under `HuaweiCloud.*` if using Huawei driver)

### B5. Enum member casing
- **Signature:** `error CS0117: 'GaussDBDbType' does not contain a definition for 'BigInt'`
- **Cause:** C# is case-sensitive; the real member is `Bigint` (lowercase d), not `BigInt`
- **Fix:** `GaussDBDbType.Bigint`, `.Integer`, `.Numeric`, `.Text`, `.Boolean`, `.Timestamp`, `.Uuid`

### B6. EF Core provider version pin mismatch
- **Signature:** NuGet `NU1202` (net10.0 only) or runtime binding failure
- **Cause:** `HuaweiCloud.EntityFrameworkCore.GaussDB 0.0.1` only targets `net10.0`; using it from a `net9.0` project fails
- **Fix:** either upgrade to net10.0 *or* stay on `DotNetCore.EntityFrameworkCore.GaussDB 9.0.0` for the EF Core path (with server `password_encryption_type=1`)

---

## Category C — Code Quality / Translation Artifacts

### C1. Raw string quote count CS8998
- **Signature:** `error CS8998: The raw string literal does not start with enough quote characters to allow this many consecutive quote characters as content`
- **Example:** `$"""COPY "{t}" FROM STDIN BINARY""""` — **four** trailing quotes
- **Cause:** text-replacement added an extra `"` or copy from richer original
- **Fix:** exactly three trailing quotes: `$"""COPY "{t}" FROM STDIN BINARY"""`

### C2. Namespace copy-paste leak
- **Signature:** files in `IBSAPUR.Persistencia.GaussDb/Repositories/` declaring `namespace IBSAPUR.Persistencia.SqlServer.Repositories;`
- **Cause:** initial port was `git cp -r SqlServer GaussDb` without fixing namespaces
- **Consequence:** when both assemblies are referenced from an IoC project, compiler sees **duplicate type definitions** across assemblies → `CS0433` ambiguous type references
- **Fix:** rename namespaces to match the folder. `sed -i 's|namespace IBSAPUR.Persistencia.SqlServer|namespace IBSAPUR.Persistencia.GaussDb|' *.cs`

### C3. Case typo `GaussDB` vs `GaussDb` in class-name suffixes
- **Signature:** inconsistent class names between files
- **Cause:** convention in this codebase is `GaussDb` (camel-cased suffix) but some files have `GaussDB` (the product name, all-caps)
- **Fix:** class names and namespace segments use `GaussDb`; product references in comments/strings stay `GaussDB` (that's the real product name)

### C4. Orphaned DI registrations
- **Signature:** `error CS0246: The type or namespace name 'BulkInsertHelper' could not be found` in a `GaussDbPersistenceModule.cs`
- **Cause:** DI registrations copied over from `SqlServerPersistenceModule` reference classes that only exist in the SqlServer assembly; the GaussDb project doesn't reference SqlServer
- **Fix:** comment out the offending `AddSingleton<...>()` lines; add an explicit `TODO` noting the GaussDb-specific implementation needs to be written before reactivating

### C5. Contract namespace moves after package version bump
- **Signature:** `error CS0246: The type or namespace name 'ApuracaoEntePayload' could not be found` after a minor version bump of a private contracts package (e.g. `IBSAPUR.Contratos 2026.3.20 → 2026.3.27`)
- **Cause:** package maintainer relocated types from `IBSAPUR.Contratos.Payloads.Fornecimento` to `IBSAPUR.Contratos.Payloads.Shared` without a deprecation shim
- **Fix:** add the new namespace alongside the old one — `using IBSAPUR.Contratos.Payloads.Fornecimento; using IBSAPUR.Contratos.Payloads.Shared;` — don't replace, because the old namespace still holds *other* types

---

## Category D — Tooling / IDE False Positives

### D1. "Task / CancellationToken / TimeZoneInfo not found" in VS Code
- **Signature:** VS Code Error List shows dozens of `CS0246` for standard .NET types, plus `The type or namespace name 'XYZ' could not be found`
- **Misleading assumption:** developer thinks `<ImplicitUsings>enable</ImplicitUsings>` is broken or `using System.Threading.Tasks;` is missing
- **Real cause:** NuGet restore hasn't completed; `obj/*.g.targets` / `project.assets.json` don't exist yet; SDK targets can't load → **no** framework references in compilation
- **Diagnostic:** command line `cd <project>; dotnet restore; dotnet build` — all "missing" errors vanish
- **Fix:** `Ctrl+Shift+P → .NET: Restore All Projects` in VS Code, or run `dotnet restore` in terminal before investigating "missing" .NET types

### D2. VS Code with per-solution `NuGet.Config` but opened at repo root
- **Signature:** restore fails for some sub-projects with `NU1101 private package not found`, but succeeds for others
- **Cause:** `NuGet.Config` is colocated with only one solution but not the others; VS Code walks up from each csproj looking for NuGet.Config — if none found before repo root, private feed isn't known
- **Fix:** place a `NuGet.Config` **at the repo root** *or* in each solution folder. Content can be identical; relative paths to `LocalPackages/` change per location

### D3. Pre-built `bin/` and `obj/` shipped in source zip
- **Signature:** fresh clone, `dotnet build` produces incorrect or inconsistent outputs; IDE shows stale errors
- **Cause:** someone zipped their workspace without cleaning `bin/` / `obj/`; those pin SDK and dependency metadata to the packager's environment
- **Fix:** `rm -rf **/bin **/obj` before re-running `dotnet restore && dotnet build`; when re-packaging, exclude those dirs (`zip -x "*/bin/*" "*/obj/*"`)

---

## Category E — Runtime Behavioral Differences

### E1. Case-sensitive identifier binding
- **Signature:** `ERROR: column "Id" does not exist`
- **Cause:** GaussDB folds unquoted identifiers to lowercase, so `SELECT Id FROM T` looks for a column named `id`. If the table was created with `CREATE TABLE T ("Id" INT)` (quoted), the column really is `"Id"` and unquoted reference fails
- **Fix:** either always quote at creation + access, or always lowercase. Pick a convention early

### E2. Transaction + DataReader interleaving
- **Signature:** `GaussDBOperationInProgressException: A command is already in progress: SELECT ...` at `tx.Commit()`
- **Cause:** an unclosed `GaussDBDataReader` holds the connector; `CommitAsync` wants to start a new command but the reader hasn't disposed
- **Fix:** use `await using (var r = await cmd.ExecuteReaderAsync(ct)) { ... }` properly and close/dispose the reader before committing

### E3. Expected datetime format differences
- **Signature:** values round-trip to a different timezone than expected
- **Cause:** if client sends `DateTime.Now` (local time) but the column is `TIMESTAMPTZ`, server applies its own timezone interpretation
- **Fix:** standardize on UTC in the application (`DateTime.UtcNow`, `DateTimeKind.Utc`), and decide once whether columns are `TIMESTAMP` (naive) or `TIMESTAMPTZ` (aware)
