#!/usr/bin/env python3
"""Small Teradata-to-DWS SQL helper for report and analysis scripts.

It handles common demo/reporting syntax only. Complex Teradata constructs such
as QUALIFY, volatile tables, macros, stored procedures, and proprietary UDFs
still need manual review.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TYPE_REPLACEMENTS = [
    (r"\bBYTEINT\b", "smallint"),
    (r"\bINTEGER\b", "integer"),
    (r"\bDECIMAL\b", "numeric"),
    (r"\bNUMBER\b", "numeric"),
    (r"\bVARCHAR\((\d+)\)\s+CHARACTER SET\s+\w+", r"varchar(\1)"),
    (r"\bFORMAT\s+'[^']+'", ""),
    (r"\bCOMPRESS\s*\([^)]+\)", ""),
    (r"\bNO\s+PRIMARY\s+INDEX\b", ""),
]


def convert(sql: str) -> str:
    result = sql

    # Teradata SELECT TOP n ... -> SELECT ... LIMIT n
    top_match = re.search(r"(?is)\bSELECT\s+TOP\s+(\d+)\s+", result)
    if top_match:
        limit = top_match.group(1)
        result = re.sub(r"(?is)\bSELECT\s+TOP\s+\d+\s+", "SELECT ", result, count=1)
        if not re.search(r"(?is)\bLIMIT\s+\d+\s*;?\s*$", result):
            result = re.sub(r";?\s*$", f"\nLIMIT {limit};\n", result)

    for pattern, replacement in TYPE_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # DWS distribution should be chosen explicitly after conversion review.
    result = re.sub(r"(?is)\bPRIMARY\s+INDEX\s*\([^)]+\)", "-- TODO: choose DWS DISTRIBUTE BY HASH(...) strategy", result)
    result = re.sub(r"(?is)\bMULTISET\s+TABLE\b", "TABLE", result)
    result = re.sub(r"(?is)\bSET\s+TABLE\b", "TABLE", result)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert simple Teradata SQL files to DWS-oriented SQL.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.input.is_dir():
        args.output.mkdir(parents=True, exist_ok=True)
        for path in sorted(args.input.glob("*.sql")):
            (args.output / path.name).write_text(convert(path.read_text(encoding="utf-8")), encoding="utf-8")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(convert(args.input.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

