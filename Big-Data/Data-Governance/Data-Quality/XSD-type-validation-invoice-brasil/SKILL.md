# XSD to Hive Validation Skill

## Purpose

Use this skill when the user needs to process one or more XML Schema Definition files (`.xsd`, `.xsd.txt`, or XML schema text files), extract validation rules into a CSV table, and generate Hive SQL validation logic for a flat Huawei Cloud MRS Hive table.

The skill has two main outputs:

1. A CSV file containing all validation rules extracted from every `xs:element` and `xs:simpleType` definition.
2. A Hive SQL query that applies those validation rules to available columns in a flat Hive table.

## Required Inputs

Ask for or locate the following inputs:

- One or more XSD source files.
- Target Hive table name, for example:
  - `dbet_nfce.nfce_documentos_xml_flat_hive`
- Target Hive table column list, preferably from DDL or pasted schema.
- Optional: user-provided mapping rules between XSD elements and Hive columns.

## Output 1: Validation Rules CSV

Generate a CSV file with exactly these headers:

```csv
xsd_element,description,data type,whitespace,pattern
```

Every field must be quoted with double quotes, including `null` values:

```csv
"xsd_element","description","data type","whitespace","pattern"
"TCodUfIBGE","Tipo Código da UF da tabela do IBGE","string","preserve","11, 12, 13"
```

### Extraction Rules

For every `xs:simpleType` and `xs:element`:

- `xsd_element`
  - Use the value of the `name` attribute.
  - Ignore anonymous elements without a `name` unless they are nested under a named element and contain an inline `xs:simpleType`; in that case use the parent element name.

- `description`
  - Extract text inside the nearest associated `xs:documentation` tag.
  - Normalize internal whitespace and line breaks to a single space.
  - If no documentation exists, output `null`.

- `data type`
  - If an inline or direct `xs:restriction` exists, extract the `base` attribute.
  - Remove namespace prefixes such as `xs:` or `nfe:`.
  - Example: `xs:string` becomes `string`.
  - If the element only references an external type through `type="..."` and has no inline restriction, output `null`.

- `whitespace`
  - Extract the `value` attribute from `xs:whiteSpace`.
  - If no `xs:whiteSpace` exists, output `null`.

- `pattern`
  - If one or more `xs:pattern` tags exist, extract their `value` attributes exactly as written.
  - If multiple patterns exist, join with ` | `.
  - If no pattern exists but `xs:enumeration` tags exist, join all enumeration values using comma + space.
  - If neither pattern nor enumeration exists, output `null`.

### CSV Quoting Rules

Use a proper CSV writer. Do not build CSV manually with string concatenation.

Requirements:

- Quote every field.
- Escape internal double quotes by doubling them.
- Preserve regex backslashes exactly.
- Preserve commas inside pattern values by quoting the field.

## Output 2: Hive SQL Validation Query

Generate one executable Hive SQL script using `CASE WHEN` flags.

The query should begin with traceability columns, usually:

```sql
SELECT
    source_filename,
    nfeproc_nfe_infnfe_attr_id,
```

Each validation flag should follow this pattern:

```sql
CASE
    WHEN <column> IS NOT NULL
     AND <validation fails>
    THEN 1 ELSE 0
END AS err_<column_suffix>
```

## Critical Hive/MRS Type Handling

Huawei Cloud MRS Hive can represent flattened XML repeated paths as `ARRAY`, `LIST`, or primitive `STRING` depending on the ingestion schema.

Do not apply `RLIKE` directly to an ARRAY/LIST.
Do not apply `size()` to a STRING.

To avoid both errors, prefer this universal string-normalization pattern when the actual column type is unknown:

```sql
concat_ws('|', <column>)
```

This works safely for array/list columns in Hive. If the column is confirmed primitive string and the Hive version rejects `concat_ws` for strings, use direct `CAST(<column> AS STRING)` for primitive columns only.

Recommended robust strategy:

1. If DDL says column is `array<string>` or list:
   - Use `concat_ws('|', column)`.
2. If DDL says column is primitive:
   - Use `CAST(column AS STRING)`.
3. If DDL is unavailable or mixed errors occurred:
   - Generate a configurable CTE layer where problematic columns are normalized manually.

### Safe Pattern for ARRAY/LIST Regex Validation

For a single value regex:

```regex
0|0\.[0-9]{2}|[1-9]{1}[0-9]{0,12}(\.[0-9]{2})?
```

Use this repeated-list regex:

```sql
concat_ws('|', column) RLIKE '^(0|0\\.[0-9]{2}|[1-9]{1}[0-9]{0,12}(\\.[0-9]{2})?)(\\|(0|0\\.[0-9]{2}|[1-9]{1}[0-9]{0,12}(\\.[0-9]{2})?))*$'
```

The general form is:

```sql
concat_ws('|', array_col) RLIKE '^(single_value_regex)(\\|(single_value_regex))*$'
```

### Safe Pattern for Primitive Regex Validation

```sql
CAST(column AS STRING) RLIKE '^(single_value_regex)$'
```

### Safe Pattern for ARRAY/LIST Enumeration Validation

For values `0`, `1`, `2`:

```sql
concat_ws('|', array_col) RLIKE '^(0|1|2)(\\|(0|1|2))*$'
```

### Safe Pattern for Primitive Enumeration Validation

```sql
CAST(column AS STRING) IN ('0', '1', '2')
```

## Mapping XSD Rules to Hive Columns

Map XSD rule names to Hive columns using semantic suffix matching.

Common examples:

| XSD Rule | Hive Column Suffixes |
|---|---|
| `TCodUfIBGE` | `_cuf`, `_uf`, `_ufpag`, `_cuforig`, `_corgao` |
| `TCodMunIBGE` | `_cmun`, `_cmunfg`, `_cmunfgibs` |
| `TChNFe` | `_chnfe`, `_refnfe` |
| `TCnpj` | `_cnpj`, `_cnpjpag`, `_cnpjreceb` |
| `TCpf` | `_cpf` |
| `TStat` | `_cstat` |
| `TProt` | `_nprot` |
| `TMod` | `_mod` when context means fiscal model |
| `TNF` | `_nnf`, `_nnfini`, `_nnffin` |
| `TSerie` | `_serie` |
| `TAmb` | `_tpamb` |
| `TDateTimeUTC` | fields beginning with `dh` or containing `_dh` |
| `TData` | fields beginning with `d` where semantic type is date |
| `CFOP` | `_cfop` |
| `NCM` | `_ncm` |
| `CEST` | `_cest` |
| `CST`, `TCST` | `_cst` |
| `TcClassTrib` | `_cclasstrib` |
| `TDec_1302` | monetary fields like `_vbc`, `_vprod`, `_vnf`, `_vpis`, `_vcofins` |
| `TDec_1104v` | quantity fields like `_qcom`, `_qtrib` |
| `TDec_1110v` | unit price fields like `_vuncom`, `_vuntrib` |

Use exact name matches first. Then use suffix-based matches. Avoid mapping generic rules such as `TString` too broadly unless the user explicitly asks for string length/character validation.

## Hive SQL Generation Rules

For every mapped rule and column:

- Allow `NULL` values to pass validation.
- Return `1` when the value violates the rule.
- Return `0` when the value is valid or null.
- Use alias pattern:

```sql
err_<column_suffix>
```

Example for primitive scalar:

```sql
CASE
    WHEN col IS NOT NULL
     AND NOT (CAST(col AS STRING) RLIKE '^[0-9]{7}$')
    THEN 1 ELSE 0
END AS err_col
```

Example for array/list:

```sql
CASE
    WHEN col IS NOT NULL
     AND concat_ws('|', col) <> ''
     AND NOT (concat_ws('|', col) RLIKE '^([0-9]{7})(\\|[0-9]{7})*$')
    THEN 1 ELSE 0
END AS err_col
```

Example for primitive enumeration:

```sql
CASE
    WHEN col IS NOT NULL
     AND CAST(col AS STRING) NOT IN ('1', '2')
    THEN 1 ELSE 0
END AS err_col
```

Example for array/list enumeration:

```sql
CASE
    WHEN col IS NOT NULL
     AND concat_ws('|', col) <> ''
     AND NOT (concat_ws('|', col) RLIKE '^(1|2)(\\|(1|2))*$')
    THEN 1 ELSE 0
END AS err_col
```

## Recommended SQL Architecture

When many columns may have mixed primitive/list types, generate a two-step query:

```sql
WITH normalized AS (
    SELECT
        source_filename,
        nfeproc_nfe_infnfe_attr_id,
        concat_ws('|', array_col_1) AS array_col_1_norm,
        CAST(string_col_1 AS STRING) AS string_col_1_norm
    FROM db.schema.table
)
SELECT
    source_filename,
    nfeproc_nfe_infnfe_attr_id,
    CASE WHEN array_col_1_norm IS NOT NULL AND array_col_1_norm <> ''
          AND NOT (array_col_1_norm RLIKE '^(rule)(\\|(rule))*$')
         THEN 1 ELSE 0 END AS err_array_col_1,
    CASE WHEN string_col_1_norm IS NOT NULL
          AND NOT (string_col_1_norm RLIKE '^(rule)$')
         THEN 1 ELSE 0 END AS err_string_col_1
FROM normalized;
```

This prevents `RLIKE got LIST` and `SIZE expected LIST but found string` errors.

## Important Regex Corrections

Do not use comma characters inside regex character classes for enumerated digits.

Wrong:

```regex
[1,2,3,5,6,7]
```

This allows commas.

Correct:

```regex
[123567]
```

For CFOP:

```regex
[123567][0-9]{3}
```

Array/list version:

```sql
concat_ws('|', cfop_col) RLIKE '^([123567][0-9]{3})(\\|[123567][0-9]{3})*$'
```

## Python Implementation Guidance

Use Python to parse XSD and generate CSV and SQL.

Recommended libraries:

- `xml.etree.ElementTree` or `lxml.etree`
- `csv`
- `re`
- `pathlib`

### Parser Outline

1. Load every file matching:
   - `*.xsd`
   - `*.xsd.txt`
   - `*.xml`
   - optionally `*.txt` when content begins with XML schema.
2. Parse XML with namespaces.
3. Walk all `xs:simpleType` and `xs:element` nodes.
4. Extract documentation, restriction base, whitespace, pattern, and enumerations.
5. Deduplicate rows by `(source_file, xsd_element, description, data type, whitespace, pattern)` or by `(xsd_element, pattern)` depending on user request.
6. Write strict CSV.
7. Build Hive SQL using mapping rules and table columns.

### CSV Writer Example

```python
import csv

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    writer.writerow(["xsd_element", "description", "data type", "whitespace", "pattern"])
    for row in rows:
        writer.writerow([
            row["xsd_element"] or "null",
            row["description"] or "null",
            row["data type"] or "null",
            row["whitespace"] or "null",
            row["pattern"] or "null",
        ])
```

## Deliverables

When completing the task, produce:

1. `xsd_validation_rules_summary.csv`
2. `hive_validation_query.sql`
3. Optional `mapping_summary.csv` with:

```csv
"hive_column","xsd_rule","pattern","validation_type","is_array_or_list","generated_error_column"
```

## Quality Checks

Before final response:

- Confirm all uploaded XSD files were scanned.
- Confirm CSV headers exactly match the requested headers.
- Confirm every CSV field is quoted.
- Confirm Hive SQL starts with traceability columns.
- Confirm no direct `RLIKE` is applied to known ARRAY/LIST columns.
- Confirm no `size()` is applied to primitive STRING columns.
- Confirm CFOP regex uses `[123567]`, not `[1,2,3,5,6,7]`.
- Confirm `NULL` values bypass validation.
- Confirm output SQL ends with the correct `FROM <target_table>;`.

## Failure Recovery

If Hive raises:

```text
regexp only takes primitive types as 1st argument, got LIST
```

Fix the column by replacing:

```sql
column RLIKE 'pattern'
```

with:

```sql
concat_ws('|', column) RLIKE '^(pattern)(\\|(pattern))*$'
```

If Hive raises:

```text
"map" or "list" is expected at function SIZE, but "string" is found
```

Remove `size(column)` and treat the column as primitive:

```sql
CAST(column AS STRING) RLIKE '^(pattern)$'
```

If column types are unknown, ask for the Hive DDL or generate two versions: primitive-safe and array-safe.

## Response Style

Be direct. Provide downloadable artifacts when possible. If the SQL is too large for one response, generate a `.sql` file instead of splitting manually into many chat messages.
