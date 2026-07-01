#!/usr/bin/env python3
"""Generate Huawei Cloud MRS-compatible Hive SQL for NF-e/NFC-e validation rules.

Usage:
  python generate_hive_validation_sql.py \
    --ddl ddl_invoice_hive_data.csv \
    --rules nte_summary_rules_pt1.csv \
    --table dbet_nfce.nfce_documentos_xml_flat_hive \
    --out-sql nfce_validation_rules_hive_mrs.sql \
    --out-report nfce_validation_rules_mapping_report.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PRIMITIVE_PREFIXES = (
    "string", "varchar", "char", "int", "bigint", "smallint", "tinyint",
    "double", "float", "decimal", "boolean", "date", "timestamp"
)
COMPLEX_PREFIXES = ("array", "list", "map", "struct", "uniontype")

COLUMN_HEADER_CANDIDATES = ["column_name", "col_name", "name", "field", "column", "columns"]
TYPE_HEADER_CANDIDATES = ["data_type", "type", "datatype", "column_type", "data type"]
RULE_ID_CANDIDATES = ["rule_id", "id", "rule"]
ERROR_CODE_CANDIDATES = ["error_code", "code", "rejection_code", "codigo", "código"]
DESCRIPTION_CANDIDATES = ["description", "descricao", "descrição", "rule_description"]


@dataclass
class DdlColumn:
    name: str
    dtype: str


@dataclass
class Mapping:
    tag: str
    column: Optional[str]
    dtype: Optional[str]
    status: str
    note: str


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(f, dialect=dialect))


def pick_header(headers: List[str], candidates: List[str]) -> Optional[str]:
    normalized = {h.strip().lower(): h for h in headers if h is not None}
    for c in candidates:
        if c in normalized:
            return normalized[c]
    for h in headers:
        hl = (h or "").strip().lower()
        if any(c in hl for c in candidates):
            return h
    return None


def is_primitive(dtype: str) -> bool:
    d = (dtype or "string").strip().lower()
    if d.startswith(COMPLEX_PREFIXES):
        return False
    return d.startswith(PRIMITIVE_PREFIXES)


def is_string_like(dtype: str) -> bool:
    d = (dtype or "string").strip().lower()
    return d.startswith(("string", "varchar", "char"))


def is_numeric_like(dtype: str) -> bool:
    d = (dtype or "").strip().lower()
    return d.startswith(("int", "bigint", "smallint", "tinyint", "double", "float", "decimal"))


def sanitize_rule_id(rule_id: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(rule_id).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return f"rule_{s or 'unknown'}"


def extract_tags(description: str) -> List[str]:
    tags = re.findall(r"(?i)tag\s*:\s*([A-Za-z0-9_]+)", description or "")
    seen = set()
    out = []
    for tag in tags:
        tl = tag.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(tl)
    return out


def load_ddl(path: Path) -> Dict[str, DdlColumn]:
    rows = read_csv(path)
    if not rows:
        raise ValueError("DDL CSV is empty")
    headers = list(rows[0].keys())
    col_h = pick_header(headers, COLUMN_HEADER_CANDIDATES)
    type_h = pick_header(headers, TYPE_HEADER_CANDIDATES)
    if not col_h:
        raise ValueError(f"Could not infer DDL column-name header from {headers}")
    ddl: Dict[str, DdlColumn] = {}
    for row in rows:
        name = (row.get(col_h) or "").strip()
        if not name:
            continue
        dtype = (row.get(type_h) or "string").strip() if type_h else "string"
        ddl[name.lower()] = DdlColumn(name=name, dtype=dtype)
    return ddl


def score_candidate(tag: str, col: DdlColumn) -> int:
    name = col.name.lower()
    parts = name.split("_")
    score = 0
    if parts and parts[-1] == tag:
        score += 100
    if f"_{tag}" in name or f"{tag}_" in name:
        score += 40
    if tag in name:
        score += 20
    if "_ide_" in name:
        score += 8
    if any(x in name for x in ["_imposto_", "_icms_", "_pis_", "_cofins_", "_ipi_"]):
        score += 5
    if is_primitive(col.dtype):
        score += 10
    else:
        score -= 100
    return score


def map_tag(tag: str, ddl: Dict[str, DdlColumn]) -> Mapping:
    candidates = [c for c in ddl.values() if tag in c.name.lower()]
    if not candidates:
        return Mapping(tag, None, None, "missing_column", "No DDL column contains the tag substring")
    candidates.sort(key=lambda c: score_candidate(tag, c), reverse=True)
    best = candidates[0]
    if not is_primitive(best.dtype):
        return Mapping(tag, best.name, best.dtype, "non_scalar", "Best mapped column is complex/non-primitive")
    ambiguous = len(candidates) > 1 and score_candidate(tag, candidates[0]) == score_candidate(tag, candidates[1])
    return Mapping(tag, best.name, best.dtype, "ambiguous" if ambiguous else "mapped", "Multiple equivalent candidates" if ambiguous else "")


def missing_check(col: str, dtype: str) -> str:
    if is_string_like(dtype):
        return f"{col} IS NULL OR TRIM({col}) = ''"
    return f"{col} IS NULL"


def int_expr(col: str, dtype: str) -> str:
    return f"CAST({col} AS INT)"


def guarded_int_condition(col: str, dtype: str, op: str, values: List[str]) -> str:
    vals = ", ".join(values)
    casted = int_expr(col, dtype)
    if is_string_like(dtype):
        return f"({col} RLIKE '^-?[0-9]+$' AND {casted} {op} ({vals}))"
    return f"({casted} {op} ({vals}))"


def infer_numeric_values(description: str) -> List[str]:
    # Prefer values inside parentheses containing tag expression.
    text = description or ""
    nums = re.findall(r"(?<![A-Za-z0-9])\d+(?![A-Za-z0-9])", text)
    # Preserve order and uniqueness.
    out = []
    for n in nums:
        if n not in out:
            out.append(n)
    return out


def infer_operator(description: str) -> Optional[str]:
    d = description or ""
    if "<>" in d or "!=" in d or re.search(r"(?i)not\s+in|diferente", d):
        return "NOT_IN_ERROR"
    if "=" in d:
        return "EQ_ERROR"
    return None


def static_missing_case(rule_id: str, alias: str) -> str:
    return (
        "CASE\n"
        f"    WHEN 1 = 1 THEN 'missing information for rule {rule_id}'\n"
        "    ELSE 'other scenario'\n"
        f"END AS {alias}"
    )


def generate_case(rule_id: str, error_code: str, description: str, mappings: List[Mapping]) -> Tuple[str, str]:
    alias = sanitize_rule_id(rule_id)
    usable = [m for m in mappings if m.column and m.dtype and is_primitive(m.dtype)]
    if not usable:
        return static_missing_case(rule_id, alias), "static_missing_no_usable_column"

    # Baseline: use first mapped primitive column for simple tag condition rules.
    m = usable[0]
    col = m.column
    dtype = m.dtype or "string"
    miss = missing_check(col, dtype)
    nums = infer_numeric_values(description)
    op = infer_operator(description)

    if nums and op == "NOT_IN_ERROR":
        valid = guarded_int_condition(col, dtype, "IN", nums)
        error = guarded_int_condition(col, dtype, "NOT IN", nums)
    elif nums and op == "EQ_ERROR":
        error = guarded_int_condition(col, dtype, "IN", nums)
        valid = guarded_int_condition(col, dtype, "NOT IN", nums)
    elif nums:
        valid = guarded_int_condition(col, dtype, "IN", nums)
        error = guarded_int_condition(col, dtype, "NOT IN", nums)
    else:
        # Presence-only conservative rule.
        valid = f"NOT ({miss})"
        error = "1 = 0"

    sql = (
        "CASE\n"
        f"    WHEN {miss}\n"
        f"        THEN 'missing information for rule {rule_id}'\n"
        f"    WHEN {valid}\n"
        "        THEN 'valid'\n"
        f"    WHEN {error}\n"
        f"        THEN 'error_code: {error_code}'\n"
        "    ELSE 'other scenario'\n"
        f"END AS {alias}"
    )
    return sql, "generated"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ddl", required=True, type=Path)
    p.add_argument("--rules", required=True, type=Path)
    p.add_argument("--table", default="dbet_nfce.nfce_documentos_xml_flat_hive")
    p.add_argument("--out-sql", required=True, type=Path)
    p.add_argument("--out-report", required=True, type=Path)
    p.add_argument("--include-columns", default="", help="Comma-separated source columns to include before rule outputs")
    args = p.parse_args()

    ddl = load_ddl(args.ddl)
    rules = read_csv(args.rules)
    if not rules:
        raise ValueError("Rules CSV is empty")
    headers = list(rules[0].keys())
    rule_h = pick_header(headers, RULE_ID_CANDIDATES) or "rule_id"
    err_h = pick_header(headers, ERROR_CODE_CANDIDATES) or "error_code"
    desc_h = pick_header(headers, DESCRIPTION_CANDIDATES) or "description"

    select_items: List[str] = []
    include_cols = [c.strip() for c in args.include_columns.split(",") if c.strip()]
    select_items.extend(include_cols)
    report_rows: List[Dict[str, str]] = []

    for row in rules:
        rule_id = (row.get(rule_h) or "").strip()
        if not rule_id:
            continue
        error_code = (row.get(err_h) or "").strip()
        description = (row.get(desc_h) or "").strip()
        tags = extract_tags(description)
        mappings = [map_tag(t, ddl) for t in tags]
        if not tags:
            mappings = []
        case_sql, generation_status = generate_case(rule_id, error_code, description, mappings)
        select_items.append(case_sql)
        report_rows.append({
            "rule_id": rule_id,
            "error_code": error_code,
            "description": description,
            "extracted_tags": "|".join(tags),
            "mapped_columns": "|".join([m.column or "" for m in mappings]),
            "mapped_types": "|".join([m.dtype or "" for m in mappings]),
            "mapping_status": "|".join([m.status for m in mappings]) if mappings else "no_tag_found",
            "generation_status": generation_status,
            "notes": "|".join([m.note for m in mappings]),
        })

    sql = "SELECT\n    " + ",\n    ".join(select_items) + f"\nFROM {args.table};\n"
    args.out_sql.write_text(sql, encoding="utf-8")

    with args.out_report.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["rule_id", "error_code", "description", "extracted_tags", "mapped_columns", "mapped_types", "mapping_status", "generation_status", "notes"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(report_rows)


if __name__ == "__main__":
    main()
