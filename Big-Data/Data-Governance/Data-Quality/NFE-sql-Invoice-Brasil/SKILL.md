# Hive NF-e/NFC-e Validation SQL Generator

## Purpose
Generate a single production-ready Hive SQL validation query for Brazilian Electronic Invoice (NF-e/NFC-e SEFAZ) fiscal rules using two input files:

1. A DDL/schema CSV containing the target Hive table columns and data types.
2. A rules CSV containing validation rules with at least `rule_id`, `error_code`, and `description`.

The output is a single `SELECT` statement over a Hive table, where each rule becomes an independent `CASE WHEN` column named `rule_<rule_id>`.

## When to Use This Skill
Use this skill when the user asks to:

- Generate Hive SQL from DDL and SEFAZ validation rules.
- Validate NF-e/NFC-e XML flattened Hive tables.
- Map SEFAZ tags from natural-language rule descriptions to Hive columns.
- Fix Hive SQL compilation errors caused by type mismatches such as ARRAY/LIST vs primitive scalar functions.
- Create Huawei Cloud MRS-compatible Hive SQL for fiscal validation.

## Inputs

### Required Files

#### 1. DDL CSV
Expected to contain the table schema. The file may have different column header names, but the generator should infer:

- Column name: examples include `column_name`, `name`, `col_name`, `field`, `column`.
- Data type: examples include `data_type`, `type`, `datatype`, `column_type`.

If type information is missing, default conservatively to `string`, but never apply scalar functions to columns known to be `array`, `map`, `struct`, `list`, or complex.

#### 2. Rules CSV
Expected columns:

- `rule_id`
- `error_code`
- `description`

The `description` field usually contains SEFAZ tags such as `tag:indPres`, `tag:finNFe`, `tag:ICMS`, `tag:pICMS`, etc.

## Output Requirements

Generate:

1. `nfce_validation_rules_hive_mrs.sql`
   - One single `SELECT` statement.
   - Scans the target table exactly once.
   - Produces one independent validation output column per rule.

2. `nfce_validation_rules_mapping_report.csv`
   - Rule ID.
   - Error code.
   - Extracted tags.
   - Mapped columns.
   - Column types.
   - Mapping status.
   - Notes for skipped/static rules.

## SQL Architecture

Use this structure:

```sql
SELECT
    <optional primary key columns>,
    CASE ... END AS rule_<sanitized_rule_id>,
    CASE ... END AS rule_<sanitized_rule_id>
FROM dbet_nfce.nfce_documentos_xml_flat_hive;
```

Default source table:

```sql
dbet_nfce.nfce_documentos_xml_flat_hive
```

Allow the user to override the table name if requested.

## Rule Column Naming

Sanitize `rule_id`:

- Replace non-alphanumeric characters with `_`.
- Collapse repeated underscores.
- Prefix with `rule_`.

Example:

```text
B25b-20 -> rule_B25b_20
```

## Required CASE Scenario Order

Every rule column must enforce the following four scenarios in this exact logical order:

1. Missing information
2. Valid
3. Error code
4. Other scenario

However, if the rule description explicitly defines an invalid condition, it is acceptable to place the error-condition check before the valid-condition check only when necessary to avoid semantic inversion. When the user explicitly demands a strict order, preserve the exact order and encode conditions accordingly.

Standard output strings:

```sql
'missing information for rule <rule_id>'
'valid'
'error_code: <error_code>'
'other scenario'
```

## Compilation Safety Rules

Before generating SQL for a rule:

1. Extract technical tags from the rule description.
2. Map tags to DDL columns using lowercase substring matching.
3. Verify mapped columns exist.
4. Verify mapped columns are primitive scalar types before applying scalar functions.

Primitive scalar types include:

- string
- varchar
- char
- int
- bigint
- smallint
- tinyint
- double
- float
- decimal
- boolean
- date
- timestamp

Complex/non-scalar types include:

- array
- list
- map
- struct
- uniontype

If a required column is missing or only maps to complex columns that cannot safely be evaluated, generate a static Scenario 1 block:

```sql
CASE
    WHEN 1 = 1 THEN 'missing information for rule <rule_id>'
    ELSE 'other scenario'
END AS rule_<rule_id>
```

Never guess a column name.

## Safe Null / Blank Checks

For primitive string-like columns:

```sql
col IS NULL OR TRIM(col) = ''
```

For primitive numeric/date/timestamp/boolean columns:

```sql
col IS NULL
```

Do not use `TRIM`, `CAST`, `REGEXP`, `LOWER`, `UPPER`, `LENGTH`, or scalar comparisons directly on `array`, `map`, `struct`, or `list` columns.

## Safe Numeric Comparison Pattern

When a string column stores a numeric SEFAZ code, use guarded casts to prevent runtime or compile problems:

```sql
col RLIKE '^-?[0-9]+$' AND CAST(col AS INT) IN (1, 4, 5)
```

For numeric typed columns:

```sql
CAST(col AS INT) IN (1, 4, 5)
```

## Tag Extraction

Extract tags using patterns such as:

```text
tag:<TAG>
Tag:<TAG>
TAG:<TAG>
```

Regex concept:

```regex
(?i)tag\s*:\s*([A-Za-z0-9_]+)
```

Normalize extracted tags to lowercase.

## Tag-to-Column Mapping

Use lowercase substring matching:

```text
tag:indPres -> columns containing indpres
```

Prefer exact terminal or segment matches:

```text
nfeproc_nfe_infnfe_ide_indpres
```

Avoid mapping a generic tag such as `ICMS` to many complex or repeated child columns unless a specific child tag is also present.

If multiple primitive candidates exist:

1. Prefer columns whose final segment equals the tag.
2. Prefer columns containing `_ide_` for identification tags.
3. Prefer columns containing tax group segments for tax tags, such as `_imposto_`, `_icms_`, `_pis_`, `_cofins_`, `_ipi_`.
4. Record ambiguity in the mapping report.

## Business Logic Inference

Supported baseline patterns:

### Not-in condition
Description example:

```text
NFC-e em uma operação não presencial (tag:indPres<>1, 4 e 5)
```

Generate:

```sql
CASE
    WHEN indpres_col IS NULL OR TRIM(indpres_col) = ''
        THEN 'missing information for rule B25b-20'
    WHEN CAST(indpres_col AS INT) IN (1, 4, 5)
        THEN 'valid'
    WHEN CAST(indpres_col AS INT) NOT IN (1, 4, 5)
        THEN 'error_code: 717'
    ELSE 'other scenario'
END AS rule_B25b_20
```

### Equals forbidden condition
If description says `tag:X=Y` and the rule describes a rejection/error, then `X = Y` is the error condition and `X <> Y` is valid, unless the description explicitly says the opposite.

### Required presence condition
If a rule says a tag must be informed, use missing-information for null/blank and valid when present.

### Unsupported or ambiguous condition
If the generator cannot safely infer business logic, generate a conservative missing-information/static block and record it in the mapping report. Do not hallucinate fiscal rules.

## Huawei Cloud MRS / Hive Compatibility

Generate Hive SQL that avoids:

- Applying primitive functions to complex types.
- Using unsupported functions from Spark SQL or Presto.
- Regex on arrays/lists/maps.
- `SIZE()` on strings.
- `TRIM()` on non-string complex columns.

Prefer broadly supported Hive syntax:

- `CASE WHEN`
- `CAST(... AS INT)`
- `TRIM()` only on strings
- `RLIKE` only on primitive string columns
- `IN` / `NOT IN`

## Recommended Workflow

1. Load both CSV files.
2. Normalize header names.
3. Build a DDL dictionary: `{column_name: data_type}`.
4. Extract tags from each rule description.
5. Map tags to DDL columns.
6. Check mapped type safety.
7. Infer validation logic from the description.
8. Generate CASE block.
9. Assemble one `SELECT` over the table.
10. Save SQL and mapping report.
11. If Hive throws a compile error, inspect the offending rule and type, then regenerate with stricter type safety.

## User-Facing Response

When done, provide links to:

- The generated SQL file.
- The mapping report.

Briefly mention any conservative fallbacks, such as rules that were statically marked as missing information because columns were absent or non-scalar.
