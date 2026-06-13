---
description: Oracle to PostgreSQL 17 SQL migration. Scans the project, identifies Oracle patterns, applies standard transformations and validates no residuals remain. Language/framework agnostic.
argument-hint: "[scope] — target connection/schema, e.g. 'default oracle connection' or 'all connections'"
---

# Oracle → PostgreSQL 17 Migration

## Purpose

Convert all SQL queries written in Oracle dialect to PostgreSQL 17 dialect, within the scope indicated by the user. The skill is agnostic to the programming language and framework.

Received argument: $ARGUMENTS

---

## Phase 1 — Define scope

Before touching any code, confirm with the user:

1. **Which connection/schema is being migrated?** (e.g. default connection, VUF schema, all connections)
2. **Which connections stay on Oracle?** (e.g. external integrations, legacy, third-party services)
3. **Is there an existing plan file or notes?** (read if it exists)
4. **How was the PostgreSQL DDL generated?** (UGO by Huawei Cloud, AWS SCT, ora2pg, manual conversion). This conditions Phase 7 — each tool leaves different semantic gaps.

Record the scope. Only touch files that use the target connection. If a file uses multiple connections, migrate only the blocks corresponding to the scope.

---

## Phase 2 — Initial scan

Recursively search the source code for Oracle patterns. Adapt the command to the project language:

```bash
# Broad scan for Oracle patterns in any language
grep -rn \
  "SYSDATE\|ROWNUM\|FROM dual\|ADD_MONTHS\|MONTHS_BETWEEN\|TO_DATE\|TO_CHAR\|TRUNC(\|DECODE(\|NVL(\|CONNECT BY LEVEL\|'RRRR\|'MM/DD/YYYY\|'DD-MON-YYYY\|NEXTVAL\|CURRVAL\|CLOB\|BLOB\|VARCHAR2\|NUMBER(" \
  ./src ./app ./lib \
  --include="*.php" --include="*.java" --include="*.py" --include="*.ts" --include="*.js" --include="*.rb" \
  | grep -v "vendor/\|node_modules/\|target/\|\.git/"
```

Classify each hit as:
- **In scope** — uses the target connection → must migrate
- **Out of scope** — uses a different explicit connection → ignore
- **SQL comment** — line starting with `--` or `//` → ignore (not executed)
- **Dead code** — constant/method never invoked → migrate anyway for consistency, mark as dead code

---

## Phase 3 — Standard transformation table

Apply these rules in order. If a pattern combines several, apply them from innermost to outermost.

### 3.1 Current date/time

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `SYSDATE` (date+time) | `CURRENT_TIMESTAMP` |
| `SYSDATE` (date only) | `CURRENT_DATE` |
| `TRUNC(SYSDATE)` | `CURRENT_DATE` |

### 3.2 Date arithmetic

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `SYSDATE - N` (N whole days) | `CURRENT_TIMESTAMP - INTERVAL 'N days'` |
| `TRUNC(SYSDATE) - (:qty - 1)` | `CURRENT_DATE - (:qty::int - 1)` |
| `SYSDATE + (1 - :qty)` | `CURRENT_TIMESTAMP - (:qty::int - 1) * INTERVAL '1 day'` |
| `TRUNC(SYSDATE + (1 - :qty))` | `CURRENT_TIMESTAMP - (:qty::int - 1) * INTERVAL '1 day'` |
| `ADD_MONTHS(SYSDATE, N)` | `NOW() + (N \|\| ' months')::interval` |
| `ADD_MONTHS(SYSDATE, 1 - :qty)` | `NOW() + ((1 - :qty::int) \|\| ' months')::interval` |
| `ADD_MONTHS(date, N)` | `date + (N \|\| ' months')::interval` |

### 3.3 Type conversion and formatting

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `TO_DATE(col, 'YYYY-MM-DD HH24:MI:SS')` | `col::timestamp` |
| `TO_DATE(col, 'YYYYMMDD')` | `col::date` |
| `TO_DATE(str_literal, fmt)` | `str_literal::timestamp` or `str_literal::date` depending on format |
| `TO_CHAR(col)` (no format) | `col::text` |
| `TO_CHAR(col, 'RRRR/MM')` | `TO_CHAR(col, 'YYYY/MM')` |
| `TO_CHAR(col, 'DD-MM-YYYY')` | `TO_CHAR(col, 'DD-MM-YYYY')` ← same, do not change |
| `TRUNC(col)` (truncate to day) | `DATE_TRUNC('day', col)` |
| `TRUNC(MONTHS_BETWEEN(SYSDATE, date) / 12)` | `EXTRACT(YEAR FROM AGE(date))::int` |
| `TO_DATE(TO_CHAR(ADD_MONTHS(SYSDATE,(1-:qty)),'RRRR/MM'),'YYYY/MM')` | `date_trunc('month', NOW() + ((1-:qty::int) \|\| ' months')::interval)` |

### 3.4 Nullability and conditional functions

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `NVL(a, b)` | `COALESCE(a, b)` |
| `NVL2(a, b, c)` | `CASE WHEN a IS NOT NULL THEN b ELSE c END` |
| `DECODE(col, v1, r1, v2, r2, default)` | `CASE col WHEN v1 THEN r1 WHEN v2 THEN r2 ELSE default END` |

### 3.5 Pagination and row limiting

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `WHERE ROWNUM <= N` (simple query) | `LIMIT N` at end of query |
| `SELECT * FROM (...) WHERE ROWNUM <= :qty` | Move `LIMIT :qty` inside the subquery before `)`, add alias `subq` |

Standard pattern for ROWNUM as wrapper:
```sql
-- Oracle
SELECT * FROM (
    SELECT ... ORDER BY col ASC
) WHERE ROWNUM <= :qty

-- PostgreSQL
SELECT * FROM (
    SELECT ... ORDER BY col ASC
    LIMIT :qty
) subq
```

Standard pattern for ROWNUM as COUNT guard:
```sql
-- Oracle
SELECT COUNT(*) FROM table WHERE condition AND ROWNUM <= 99

-- PostgreSQL
SELECT COUNT(*) as total FROM (
    SELECT 1 FROM table WHERE condition LIMIT 99
) subq
```

### 3.6 Sequences

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `seq_name.NEXTVAL` | `nextval('seq_name')` |
| `seq_name.CURRVAL` | `currval('seq_name')` |
| `CREATE SEQUENCE ... INCREMENT BY 1 NOCACHE` | `CREATE SEQUENCE ... INCREMENT BY 1` |

### 3.7 Series generation / range tables

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `SELECT LEVEL FROM dual CONNECT BY LEVEL <= N` | `SELECT generate_series(1, N)` |
| `SELECT date_col FROM dual CONNECT BY ...` (date range) | `SELECT d::date FROM generate_series(:since::date, :until::date, '1 day'::interval) AS d` |
| `FROM dual` (dummy table) | Remove — PostgreSQL does not need FROM for literal SELECTs |

### 3.8 DDL data types

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `VARCHAR2(N)` | `VARCHAR(N)` |
| `NUMBER(p,s)` | `NUMERIC(p,s)` |
| `NUMBER` (integer) | `INTEGER` or `BIGINT` |
| `CLOB` | `TEXT` |
| `BLOB` | `BYTEA` |
| `DATE` (includes time in Oracle) | `TIMESTAMP` |
| `TIMESTAMP WITH TIME ZONE` | `TIMESTAMPTZ` |

### 3.9 Concatenation and text

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `col1 \|\| col2` | `col1 \|\| col2` ← same |
| `SUBSTR(str, pos, len)` | `SUBSTRING(str, pos, len)` or `SUBSTR(str, pos, len)` ← both work |
| `INSTR(str, sub)` | `POSITION(sub IN str)` |
| `LENGTH(str)` | `LENGTH(str)` ← same |

### 3.10 Legacy outer join syntax

| Oracle | PostgreSQL 17 |
|--------|--------------|
| `table1, table2 WHERE table1.col = table2.col(+)` | `table1 LEFT JOIN table2 ON table1.col = table2.col` |
| `table1, table2 WHERE table1.col(+) = table2.col` | `table1 RIGHT JOIN table2 ON table1.col = table2.col` |

---

## Phase 4 — Application strategy

### Recommended order

1. Global transformations with `replace_all: true` for unique and safe (unambiguous) patterns
2. Contextual edits when the pattern has variants
3. Always verify after `replace_all` that there are no collateral changes in out-of-scope code

### Criteria for replace_all vs targeted edit

- **replace_all** — when the pattern is identical across all occurrences and does not appear in out-of-scope files
- **Targeted edit** — when there are variants within the same file, or the pattern appears in blocks using different connections

### Caution with named parameters

PostgreSQL uses `:param` the same as Oracle in PDO/JDBC. Do not change parameter names, only the SQL that wraps them.

---

## Phase 5 — Final Oracle pattern validation

After all edits, run the Phase 2 scan again and filter:

```bash
grep -rn "SYSDATE\|ROWNUM\|FROM dual\|ADD_MONTHS\|MONTHS_BETWEEN\|'RRRR\|CONNECT BY LEVEL" \
  ./src ./app \
  --include="*.php" --include="*.java" --include="*.py" --include="*.ts" \
  | grep -v "vendor/\|node_modules/\|target/\|\.git/" \
  | grep -v "^.*--.*$"
```

For each remaining hit, classify as:
- SQL comment → ignore
- Out of scope → ignore, document why
- In scope not yet migrated → migrate now

Report to the user:
- Modified files
- Patterns found and not migrated (with justification)
- Files excluded from scope (with the connection they use)

---

## Phase 6 — Exhaustive identifier case verification (tables and columns)

> **CRITICAL — do not skip.** PostgreSQL stores all unquoted identifiers in **lowercase** internally. If the code references `TABLE` or `column_NAME` but the DDL declares `table` / `column_name`, the query fails with *"relation does not exist"* or *"column does not exist"* even when the schema is correctly migrated.
>
> This phase must be done **by comparing the actual PostgreSQL DDL** (backup/dump file or live schema) against **every identifier** in the code. A case scan alone is not enough: there may also be differences in the exact column names that were named differently in Oracle.

**Mandatory flow:**
1. Get the canonical list of tables and columns from the PostgreSQL DDL (§6.1).
2. Scan the code for uppercase identifiers (§6.2–§6.3).
3. Compare each reference found against the canonical DDL list and fix discrepancies (§6.4–§6.5).
4. Verify `AS NAME` aliases returned to the client (§6.6).
5. **Re-scan** after corrections to confirm zero residuals (§6.7).

PostgreSQL stores all unquoted identifiers in **lowercase**. Oracle was case-insensitive but the convention was UPPERCASE. After migrating the SQL, verify that all table and column names in the code are lowercase for consistency and to avoid confusion with quoted identifiers.

### 6.1 Get table list from the backup schema

If a PostgreSQL dump file exists (e.g. `backup_<schema>_metadata_<date>.sql`):

```bash
grep -E "^CREATE TABLE" backup_*.sql | sed "s/CREATE TABLE [^.]*\.\([^ ]*\).*/\1/" | sort
```

Use this list to verify that every table referenced in the code uses the exact lowercase name.

### 6.2 Scan for uppercase tables in FROM/JOIN contexts

```bash
grep -rnP "(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+[A-Z][A-Z_]{2,}" \
  ./app --include="*.php" --include="*.py" --include="*.ts" \
  | grep -v "vendor/\|node_modules/" \
  | grep -v "^\s*--" \
  | grep -vP "(?:FROM|JOIN)\s+(?:CURRENT|INTERVAL|NULL|EXTRACT|GENERATE|AGE)"
```

### 6.3 Scan for qualified uppercase columns (table.COLUMN)

```bash
grep -rnP "\b[a-z][a-z_]+\.[A-Z][A-Z_0-9]{2,}\b" \
  ./app --include="*.php" --include="*.py" --include="*.ts" \
  | grep -v "vendor/\|node_modules/"
```

### 6.4 Python script for bulk correction

Use this pattern to replace known table names and qualified references:

```python
import re

# Table name map: uppercase → lowercase
TABLE_MAP = {
    'TABLE_NAME': 'table_name',
    # ... add all schema tables
}

files = ['app/.../*.php']

for path in files:
    with open(path) as f:
        content = f.read()
    original = content
    for upper, lower in TABLE_MAP.items():
        content = re.sub(r'\b' + re.escape(upper) + r'\b', lower, content)
    if content != original:
        with open(path, 'w') as f:
            f.write(content)

# Step 2: lowercase qualified columns with full table name
QUALIFIED_PATTERN = re.compile(
    r'(\b(?:source_table|other_table)\.)'
    r'([A-Z][A-Z0-9_]+)\b'
)
# ... apply with sub() lowercasing group(2)

# Step 3: lowercase qualified columns with short aliases (U.COLUMN, Z.COLUMN)
SHORT_ALIAS_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{0,3})\.([A-Z][A-Z0-9_]{1,})\b')
# ... apply lowercasing only group(2)
```

### 6.5 Verify tables against schema

```bash
# For each table used in the code, verify it exists in the backup
for table in table1 table2 table3; do
  grep -q "CREATE TABLE schema\.$table " backup_*.sql \
    && echo "OK: $table" || echo "MISSING: $table"
done
```

### 6.6 Uppercase AS aliases

PostgreSQL returns unquoted aliases in lowercase. Ensure that application code does not access columns by uppercase key. Lowercase `AS ALIAS_NAME` → `AS alias_name` for consistency:

```bash
grep -rnP "\bAS\s+[A-Z][A-Z_]{3,}\b" ./app --include="*.php" | grep -v "^\s*--"
```

### 6.7 Final DDL vs code re-scan — zero residuals

After all case corrections, run a definitive cross-check:

```bash
# 1. Extract ALL tables from the PostgreSQL DDL
grep -E "^CREATE TABLE" backup_*.sql \
  | sed 's/CREATE TABLE [^.]*\.\([^ ]*\).*/\1/' \
  | sort > /tmp/pg_tables.txt

# 2. Extract ALL columns from each table in the DDL
grep -E "^\s+[a-z_]+ (varchar|numeric|integer|bigint|text|timestamp|date|boolean|bytea)" backup_*.sql \
  | awk '{print $1}' | sort -u > /tmp/pg_columns.txt

# 3. Detect any identifier that is not pure lowercase in the code
grep -rnP "(?:FROM|JOIN|INTO|UPDATE|TABLE|SELECT)\s+[A-Z]" \
  ./app --include="*.php" --include="*.py" --include="*.ts" \
  | grep -v "vendor/\|node_modules/\|^\s*--"

# 4. Detect uppercase key access in PHP ($row->COL, $row['COL'])
grep -rnP "\\\$\w+->([A-Z][A-Z_0-9]+)\b|\\\$\w+\['([A-Z][A-Z_0-9]+)'\]" \
  ./app --include="*.php" | grep -v "vendor/"
```

If any of these commands produces output, **fix before considering the migration complete**. The success criterion is empty output from all of them.

---

## Phase 7 — Post-tool DDL verification (UGO / SCT / ora2pg)

> **CRITICAL when the PG dump was generated by UGO (Huawei Cloud) or another automated tool.** DDL conversion is **syntactic** and does not preserve semantics that in Oracle lived in triggers or column configuration (auto-increment, automatic timestamps, derived defaults). The schema compiles in PG but INSERTs from the application fail at runtime with NOT NULL violations or other constraint errors.

### 7.1 Confirmed case: sequences not linked to tables

**Symptom**: `ERROR: null value in column "id" of relation "X" violates not-null constraint` on INSERT from ORM/app, even though the sequence exists in PG.

**Why it happens**: in Oracle, PK auto-increment is typically implemented with `CREATE SEQUENCE` + `CREATE TRIGGER BEFORE INSERT ... :NEW.id := seq.NEXTVAL`. UGO migrates both objects to PG syntax, but:

- The sequence is created correctly (`CREATE SEQUENCE <schema>.table_id_seq`).
- The table is created with `id numeric NOT NULL` **without `DEFAULT nextval(...)`**.
- The Oracle trigger is not translated to `IDENTITY` or a column default.

Result: the sequence exists as an orphan, `id` has no automatic population, and every `INSERT` that does not specify an explicit `id` fails.

**Detection**:

```bash
# 1. List sequences in the PG dump
grep -E "CREATE SEQUENCE \"?[a-z_]+\"?\.\"?[a-z_]+\"?" dump_postgres.sql \
  | sed -E 's/.*"([a-z_]+)"\.\"?([a-z_]+).*/\1.\2/' \
  | sort > /tmp/pg_sequences.txt

# 2. Find nextval defaults already linked in the dump
grep -nE "DEFAULT nextval\('?\"?[a-z_]+\"?\.\"?[a-z_]+\"?'?\)" dump_postgres.sql

# 3. If (2) is empty or reports fewer links than sequences exist → gap confirmed
```

On the live database (more reliable):

```sql
-- Sequences without owner (not linked to any column)
SELECT s.schemaname, s.sequencename
FROM pg_sequences s
LEFT JOIN pg_depend d
  ON d.objid = (s.schemaname||'.'||s.sequencename)::regclass
 AND d.deptype = 'a'
WHERE s.schemaname = :schema
  AND d.objid IS NULL;
```

**seq → table.column mapping**: UGO truncates names to 30 chars (Oracle limit), so the `<table>_<column>_seq` convention match may break. Typical cases to verify:

| Oracle pattern | Resulting PG sequence (UGO) | Actual table.column |
|---|---|---|
| `long_table_name_col_id_seq` (truncated to 30 chars) | `long_table_name_col_id_s` | `long_table_name.col_id` |
| `entity_id_seq` | `entity_id_seq` | `entity.id` |
| `other_table_code_seq` | `other_table_code_seq` | `other_table.code` |

When the heuristic does not apply, read the original Oracle trigger (`CREATE TRIGGER ... BEFORE INSERT ON table ... :NEW.col := seq.NEXTVAL`) in the Oracle dump to confirm the mapping.

**Standard patch** (for each sequence→table.column pair):

```sql
ALTER TABLE <schema>.<table>
  ALTER COLUMN <column> SET DEFAULT nextval('<schema>.<sequence>');

-- Sync to current maximum in case the table already has rows
SELECT setval('<schema>.<sequence>',
              COALESCE((SELECT MAX(<column>) FROM <schema>.<table>), 0) + 1,
              false);
```

Deliver the patch as a versioned idempotent SQL file (`docker/init-sequences.sql`, Flyway/Liquibase migration, etc.) so that any dump rehydration applies it.

### 7.2 Other semantic gaps to verify

Same principle as §7.1 — Oracle resolved via trigger, not replicated by UGO:

| Oracle behavior (typically via trigger) | Verify in PG |
|---|---|
| Auto `created_at` / `updated_at` on INSERT/UPDATE | Does the column have `DEFAULT CURRENT_TIMESTAMP`? Is there an equivalent PG trigger? |
| Automatic code generation (`folio`, `code`) | Does it have `DEFAULT nextval(...)` or is it generated by the application? |
| Domain validation (`CHECK` implicit via trigger) | Was the constraint migrated or only the comment left? |
| Audit to `_log` or `_hist` table | Was a PG trigger created, or must the app replicate the shadow write? |
| Cascade soft-delete via trigger | `FK ON DELETE` or PG trigger? |

**Verification commands**:

```bash
# Triggers in Oracle dump
grep -nE "CREATE (OR REPLACE )?TRIGGER" dump_oracle.sql | wc -l

# Triggers in PG dump
grep -nE "CREATE (OR REPLACE )?TRIGGER" dump_postgres.sql | wc -l

# If counts differ significantly → manually review which triggers were not ported
```

```sql
-- Inventory of live triggers in PG
SELECT event_object_schema, event_object_table, trigger_name, event_manipulation
FROM information_schema.triggers
WHERE event_object_schema = :schema
ORDER BY event_object_table;
```

### 7.3 Mandatory post-DDL smoke test

Before declaring the DDL migration "done", run at least one real `INSERT` (via app or `psql`) on every table with an auto-increment PK and on every table with automatic timestamp columns. If it fails → return to §7.1/§7.2 before touching application code. Do not confuse "the schema loaded" with "INSERTs work".

### 7.4 Phase deliverables

- List of detected orphan sequences.
- List of Oracle triggers not ported with their justification (discarded / pending / moved to app).
- Idempotent SQL script with `ALTER ... SET DEFAULT nextval(...)` + `setval(...)` for each detected pair.
- Smoke test confirmation of INSERTs on critical tables.

---

## Accumulated context notes

These observations come from real migrations and complement the tables above:

- **`BETWEEN` with dates**: In Oracle `BETWEEN TO_DATE(:a, fmt) AND TO_DATE(:b, fmt)` → in PG `BETWEEN :a::timestamp AND :b::timestamp`. If values come from PHP/Java as strings `'YYYY-MM-DD HH:MM:SS'`, the `::timestamp` cast is sufficient.
- **`TO_CHAR` on integers for concatenation**: `TO_CHAR(numeric_col)` without format → `numeric_col::text`.
- **`ROWNUM` as guard in count methods** (recurring pattern in notification models): convert to subquery `SELECT 1 ... LIMIT N` with outer `COUNT(*)`.
- **Deprecated constants**: even if never executed, migrate them to avoid future confusion.
- **`MONTHS_BETWEEN` for age calculation**: `TRUNC(MONTHS_BETWEEN(SYSDATE, birth_date) / 12)` → `EXTRACT(YEAR FROM AGE(birth_date))::int`.
- **`TRUNC` on a date column without argument**: in Oracle this truncates to day. In PG use `DATE_TRUNC('day', col)` or simply `col::date` if the context is only date comparison.
- **Verify connection before migrating**: look for `DB::connection('name')` / `getConnection("name")` / `@PersistenceContext` / datasource bean name. If a file mixes connections, migrate only the blocks for the target connection.
- **Identifier case**: Oracle was tolerant of UPPERCASE table and column names. PostgreSQL is also case-insensitive for unquoted identifiers (folds them to lowercase internally), but **the code becomes inconsistent** and `AS ALIAS_NAME` aliases are returned in lowercase by PG to the PHP client — so PHP code accessing `$row->ALIAS_NAME` is already broken. Always apply Phase 6 after migrating Oracle patterns.
- **Table name in string literal**: if the code stores a table name as a string (e.g. `'SOURCE_TABLE_NAME' AS source_table`), it must also be lowercased for consistency with the PG schema.
- **UGO (Huawei Cloud) and auto-increment**: UGO correctly migrates `CREATE SEQUENCE` but **does not link the sequence as `DEFAULT` for the PK column**. Oracle triggers `BEFORE INSERT ... :NEW.id := seq.NEXTVAL` are lost in translation. Runtime symptom: `null value in column "id" violates not-null constraint`. Apply Phase 7 before testing inserts. Pattern confirmed in real migrations: it is common for no sequences to be linked in the resulting PG dump, causing all INSERTs from the app to fail on the first attempt until the `ALTER ... SET DEFAULT nextval(...)` patch is applied.
- **UGO sequence name truncation**: Oracle limits identifiers to 30 chars. UGO preserves the truncated name in PG (which supports 63 chars), so the heuristic `<table>_<column>_seq` match may not work. Example: a sequence `long_table_name_col_id_proc_se` may correspond to `long_table_name.id_process`. When the heuristic does not apply, read the original Oracle trigger in the source dump to confirm the seq → table.column mapping.

---

## Phase 8 — Runtime gotchas not visible in SQL scan

> These bugs are not detected by grepping Oracle patterns. They only surface during **manual testing** after migrating the SQL, because they depend on driver semantics, the application runtime, or how the code interacts with stored data. Document and verify before closing the migration.

### 8.1 Empty string `''` is not NULL in PostgreSQL

**Symptom**: `SQLSTATE[22P02] invalid input syntax for type numeric: ""` (or `date`, `integer`, etc.) when saving a form with empty fields in non-string columns.

**Why**: Oracle treated `''` as NULL **implicitly in all columns** (a documented dialect quirk, not a bug). PostgreSQL is strict: `''` is only a valid string for `text`/`varchar`; for `numeric`/`date`/`integer` it fails parsing.

**Typical origin**: HTML forms send `''` for unfilled inputs; controllers build `update([...])` arrays with those values and pass them to the ORM/query builder without normalizing.

**Fix in 2 layers** (full coverage):

1. **Top-level helper** to normalize arrays before passing to the query builder:

```php
public static function nullifyEmpty(array $data): array {
  foreach ($data as $k => $v) {
    if ($v === '') $data[$k] = null;
  }
  return $data;
}
```

Wrap every `Model::where(...)->update([...])` and `DB::table(...)->update([...])`  with `nullifyEmpty(...)`. **Important**: Laravel's query builder **does NOT fire Eloquent mutators**.

2. **Model mutator** to catch property-assignment and Eloquent fill:

```php
public function setAttribute($key, $value) {
  if ($value === '') $value = null;
  return parent::setAttribute($key, $value);
}
```

This covers `$model->field = ''; $model->save()`, `$model->update([...])` on instance, and `Model::create([...])`.

**Coverage**:

| Write path | Layer that covers it |
|---------------------|-------------------|
| `$model->field = ''; $model->save()` | mutator |
| `$model->update([...])` (instance) | mutator (via Eloquent fill) |
| `Model::create([...])` | mutator |
| `Model::where(...)->update([...])` (query builder) | `nullifyEmpty` helper |
| `DB::table(...)->update([...])` | `nullifyEmpty` helper |

**Replicate the mutator in all models** that receive form input. It typically appears first in the main model (forms, questionnaires) and later in logs/history as the flow progresses.

**Java/Spring equivalent**: `@PrePersist`/`@PreUpdate` validator that replaces empty strings with null in numeric/date fields.

### 8.2 Oracle driver APIs absent in the PG driver

**Symptom**: `Call to undefined method Illuminate\Database\PostgresConnection::<method>` (or Spring equivalent: `NoSuchMethodError` in Oracle datasource wrappers).

**Why**: Oracle-specific packages (in Laravel: `yajra/laravel-oci8`) extend the connection with non-standard methods. When switching to the native PG driver those methods disappear.

**Observed cases**:

- `DB::getSequence()->nextValue('seq_name')` — exclusive to yajra/oci8. PG uses `SELECT nextval('seq_name')`.
- `DB::executeProcedure(...)` — yajra/oci8. PG needs an explicit `DB::select('SELECT function(?)', [...])` call or `CALL` for stored procedures.

**Fix**: create a portable helper that detects the driver and uses the correct API. Maintains compatibility while other connections remain on Oracle:

```php
public static function nextSequenceValue(string $sequenceName, ?string $connection = null) {
  $conn = $connection ? DB::connection($connection) : DB::connection();
  $driver = $conn->getDriverName();

  if ($driver === 'oracle' || $driver === 'oci') {
    return $conn->getSequence()->nextValue($sequenceName);
  }
  // pgsql, mysql, sqlite — all support nextval with select
  return $conn->selectOne("SELECT nextval(?) AS val", [$sequenceName])->val;
}
```

Refactor all usages to call the helper.

### 8.3 Sequence `START` outdated after restore

**Symptom**: the app generates a PK (id, code) via `nextval` and when using it in an immediately subsequent query receives a "not found" / "incorrect state" error, or fails with a uniqueness violation.

**Why**: when UGO/ora2pg exports the PG dump, each `CREATE SEQUENCE ... START WITH N` captures `N` at the moment of the **DDL export**. If the **data** is restored from a more recent separate dump (or if there are inserts between the two exports), the values stored in the table exceed the sequence counter. The first `nextval` returns an already-existing number.

**Detection**:

```sql
-- For each sequence linked to table.column, compare counter vs MAX
SELECT s.sequence_schema, s.sequence_name,
       (SELECT MAX(<column>) FROM <schema>.<table>) AS max_data,
       (SELECT last_value FROM <schema>.<sequence>) AS seq_value
FROM information_schema.sequences s
WHERE s.sequence_schema = :schema;
```

If `max_data > seq_value` → the sequence is behind.

**Bulk idempotent fix** (run post-restore):

```sql
-- Re-align ALL sequences linked to schema columns
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT n.nspname AS schema, c.relname AS table_name, a.attname AS column_name,
           pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname) AS seq
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0
    WHERE n.nspname = '<schema>'
      AND pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname) IS NOT NULL
  LOOP
    EXECUTE format('SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I.%I), 0) + 1, false)',
                   r.seq, r.column_name, r.schema, r.table_name);
  END LOOP;
END $$;
```

**Combine with Phase 7.1**: first link `DEFAULT nextval(...)` to the column (Phase 7.1), then re-align with the script above (Phase 8.3). Both steps are mandatory post-restore. The Phase 8.3 script only works after Phase 7.1 because `pg_get_serial_sequence` returns `NULL` for columns without a linked default.

### 8.4 VARCHAR values storing Oracle uppercase identifiers

**Symptom**: SQL queries work but application code fails with `Undefined index: <lowercase_name>` (PHP) or `NullPointerException` in map lookup (Java) when accessing by key.

**Why**: Oracle stores unquoted identifiers in **uppercase**. When source code uses column names as **values** (not as identifiers) — for example, a table `answers_per_question` with a `question_id varchar` column that stores the literal name of a questionnaire column (`'SECTION_Q6_GENDER'`) — those values remain uppercase in the DB.

Migration to PG: **columns** are renamed to lowercase (DDL Phase 6). The **VARCHAR values** of the field are exported as-is → they remain uppercase. Raw SQL without quotes against those columns works (PG automatic fold), but code lookups by string key are **case-sensitive at the language level**, not the SQL level.

**Detection**: inspect VARCHAR/TEXT columns whose values look like Oracle-style identifiers:

```sql
SELECT DISTINCT <string_column>
FROM <schema>.<table>
WHERE <string_column> ~ '^[A-Z][A-Z_0-9]+$'
LIMIT 20;
```

If rows are returned → those values are Oracle-style identifiers.

**Two options**:

| Option | Change | Risk |
|--------|--------|------|
| A (pragmatic) | Leave values uppercase. Ensure the code uses them uppercase consistently. | Maintains visual inconsistency with lowercase columns. Zero data migration. |
| B (clean) | `UPDATE table SET col = LOWER(col)` + sweep all lookups (PHP/Java/JS) to lowercase. | Cleaner. Must hunt down all uses of values as keys. If strings are hardcoded in the frontend too. |

Recommendation: option A unless the frontend is being migrated simultaneously.

### 8.5 Silent try/catch hiding the root cause

**Symptom**: a UI action produces no visible error but redirects to `/` or a generic screen. The user reports "it doesn't work" with no further details.

**Why**: a common pattern in legacy Laravel/Spring controllers:

```php
try {
  // ... complete logic ...
} catch (Exception $e) {
  Log::error('ERROR <flow>');
  Log::error($e);
  return redirect('/');
}
```

The error is **logged** but the user never sees it. During manual migration testing, always assume **the log is the single source of truth** and open it before theorizing.

**Diagnostic command**:

```bash
tail -200 storage/logs/laravel.log | grep -nE "ERROR|Exception|SQLSTATE|Undefined|Call to" | head -30
```

(Spring equivalent: `tail -200 logs/application.log | grep -nE "ERROR|Exception|PSQLException" | head -30`)

If the first line of output is a `SQLSTATE` or `Undefined index/method`, the cause is right there. If there are no logs, add a temporary log of `$exception->getMessage()` before the `redirect` or enable `APP_DEBUG=true` locally to surface the exception in the browser.

### 8.6 ORM identifier quoting

**Symptom**: `SQLSTATE[42703] column "COL_UPPERCASE" does not exist` even though the column exists (in lowercase) and the query worked in Oracle.

**Why**: the query builder of many ORMs wraps **every identifier in double quotes** when generating the final SQL. PG with quotes is **case-sensitive**.

Confirmed in Laravel: `Model::select('COL', 'OTHER')->where('COL', $v)->orderBy('COL')` generates:

```sql
SELECT "COL", "OTHER" FROM ... WHERE "COL" = ? ORDER BY "COL"
```

With yajra/oci8 it worked because Oracle columns were stored uppercase and matched. With PG columns are lowercase → fails.

This is **different** from raw SQL via `DB::select($sqlString)` where the code builds the string without quotes and PG automatically folds to lowercase. That is why the same flow can fail in an ORM call but work in a raw call in the same controller.

**Fix**: apply Phase 6 fully, **especially on string arguments to** `select()` / `where()` / `orderBy()` / `pluck()` / `groupBy()`. The `'col AS ALIAS'` aliases are also quoted and returned to the client as uppercase quoted — prefer lowercase aliases.

**Hibernate/JPA equivalent**: same trap with `@Column(name = "COL_UPPER")` in entities. Verify that annotations reference the exact name from the PG DDL.
