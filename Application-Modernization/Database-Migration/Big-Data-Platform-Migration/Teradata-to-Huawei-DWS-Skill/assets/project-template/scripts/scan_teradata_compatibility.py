#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str
    category: str
    pattern: str
    message: str
    recommendation: str


RULES = [
    Rule("TD001", "HIGH", "DDL", r"\bPRIMARY\s+INDEX\b", "Teradata PRIMARY INDEX found.", "Map to DWS DISTRIBUTE BY HASH(...) after workload and skew review."),
    Rule("TD002", "HIGH", "SQL", r"\bQUALIFY\b", "Teradata QUALIFY found.", "Rewrite with subquery/CTE and WHERE filter on window-function result."),
    Rule("TD003", "HIGH", "TEMP", r"\bVOLATILE\s+TABLE\b", "Volatile table found.", "Rewrite as temporary table or staged table; validate transaction/session semantics."),
    Rule("TD004", "MEDIUM", "DDL", r"\bCOLLECT\s+STATISTICS\b", "Teradata statistics command found.", "Replace with DWS ANALYZE and post-load statistics workflow."),
    Rule("TD005", "MEDIUM", "SQL", r"\bSELECT\s+TOP\s+\d+\b", "SELECT TOP found.", "Rewrite as LIMIT with deterministic ORDER BY."),
    Rule("TD006", "MEDIUM", "SQL", r"\bSAMPLE\b", "Teradata SAMPLE found.", "Rewrite with DWS sampling pattern or random ordering; validate repeatability."),
    Rule("TD007", "MEDIUM", "DDL", r"\bPARTITION\s+BY\s+(RANGE|CASE_N|COLUMN|HASH)\b", "Teradata partition definition found.", "Review and map to DWS RANGE/LIST partitioning."),
    Rule("TD008", "MEDIUM", "DDL", r"\bFORMAT\s+'[^']+'", "Teradata FORMAT clause found.", "Remove display format and handle formatting in reporting layer."),
    Rule("TD009", "MEDIUM", "DDL", r"\bCOMPRESS\b", "Teradata COMPRESS clause found.", "Map to DWS column-store compression choices, not column-level COMPRESS."),
    Rule("TD010", "HIGH", "SCRIPT", r"^\s*\.(LOGON|EXPORT|IMPORT|RUN|IF|QUIT|SET)\b", "BTEQ command found.", "Separate orchestration from SQL; replace with shell/Python workflow."),
    Rule("TD011", "HIGH", "PROGRAM", r"\b(REPLACE|CREATE)\s+(MACRO|PROCEDURE)\b", "Teradata macro/procedure found.", "Manually migrate to DWS SQL, PL/pgSQL-compatible logic, or external scheduler code."),
    Rule("TD012", "LOW", "TYPE", r"\bBYTEINT\b", "Teradata BYTEINT type found.", "Map to DWS smallint."),
    Rule("TD013", "LOW", "TYPE", r"\bCHARACTER\s+SET\s+\w+\b", "Character set clause found.", "Remove or map to database/client encoding policy."),
    Rule("TD014", "MEDIUM", "DDL", r"\bNO\s+PRIMARY\s+INDEX\b", "NO PRIMARY INDEX found.", "Choose explicit DWS distribution strategy."),
    Rule("TD015", "MEDIUM", "SQL", r"\bOREPLACE\s*\(", "Teradata OREPLACE function found.", "Map to DWS replace() and verify NULL behavior."),
    Rule("TD016", "LOW", "DDL", r"\b(MULTISET|SET)\s+TABLE\b", "Teradata SET/MULTISET table attribute found.", "Remove and validate duplicate-row semantics if SET TABLE was used."),
]


DEFAULT_EXTENSIONS = {".sql", ".btq", ".bteq", ".tpt", ".ddl", ".dml"}


def iter_files(paths: list[Path], extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in extensions)
        elif path.is_file():
            files.append(path)
    return sorted(files)


def scan_file(path: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="latin-1").splitlines()

    for line_no, line in enumerate(lines, start=1):
        for rule in RULES:
            if re.search(rule.pattern, line, flags=re.IGNORECASE):
                findings.append(
                    {
                        "file": str(path),
                        "line": str(line_no),
                        "rule_id": rule.rule_id,
                        "severity": rule.severity,
                        "category": rule.category,
                        "message": rule.message,
                        "recommendation": rule.recommendation,
                        "snippet": line.strip()[:240],
                    }
                )
    return findings


def write_csv(path: Path, findings: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["file", "line", "rule_id", "severity", "category", "message", "recommendation", "snippet"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(findings)


def write_markdown(path: Path, findings: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

    lines = [
        "# Teradata SQL Compatibility Scan",
        "",
        "## Summary",
        "",
        f"- Total findings: `{len(findings)}`",
        f"- HIGH: `{counts.get('HIGH', 0)}`",
        f"- MEDIUM: `{counts.get('MEDIUM', 0)}`",
        f"- LOW: `{counts.get('LOW', 0)}`",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines.extend(
            [
                "| severity | rule | file | line | message | recommendation |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in findings:
            lines.append(
                "| {severity} | {rule_id} | `{file}` | {line} | {message} | {recommendation} |".format(**item)
            )
    else:
        lines.append("_No compatibility findings._")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Teradata SQL/BTEQ/TPT files for DWS migration risk patterns.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--csv", default="reports/teradata_compatibility_scan.csv", type=Path)
    parser.add_argument("--markdown", default="reports/teradata_compatibility_scan.md", type=Path)
    parser.add_argument("--extensions", default=",".join(sorted(DEFAULT_EXTENSIONS)))
    parser.add_argument("--fail-on-high", action="store_true")
    args = parser.parse_args()

    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions.split(",") if ext}
    findings: list[dict[str, str]] = []
    for path in iter_files(args.paths, extensions):
        findings.extend(scan_file(path))

    findings.sort(key=lambda item: (item["severity"] != "HIGH", item["file"], int(item["line"]), item["rule_id"]))
    write_csv(args.csv, findings)
    write_markdown(args.markdown, findings)
    print(f"Findings: {len(findings)}")
    print(f"CSV: {args.csv}")
    print(f"Markdown: {args.markdown}")

    if args.fail_on_high and any(item["severity"] == "HIGH" for item in findings):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
