# Hive NF-e/NFC-e Validation SQL Generator Skill

This skill generates Huawei Cloud MRS-compatible Hive SQL from:

- A DDL/schema CSV.
- A SEFAZ validation-rules CSV.

It creates a single-scan Hive `SELECT` query with one `CASE WHEN` output column per validation rule.

## Example

```bash
python scripts/generate_hive_validation_sql.py \
  --ddl ddl_invoice_hive_data.csv \
  --rules nte_summary_rules_pt1.csv \
  --table dbet_nfce.nfce_documentos_xml_flat_hive \
  --out-sql nfce_validation_rules_hive_mrs.sql \
  --out-report nfce_validation_rules_mapping_report.csv
```

## Key Safety Feature

The generator checks DDL data types before applying Hive functions. Complex columns such as `array`, `map`, `struct`, or `list` are not passed to `TRIM`, `CAST`, `REGEXP`, or other scalar functions.
