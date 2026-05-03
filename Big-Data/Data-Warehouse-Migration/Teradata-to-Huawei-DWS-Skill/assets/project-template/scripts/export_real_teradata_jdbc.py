#!/usr/bin/env python3
"""Optional JDBC exporter for a real Teradata source.

This script is intentionally thin because Teradata JDBC drivers are not bundled
with this repository. Install jaydebeapi and provide TERADATA_JDBC_JAR to use it.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path


TABLES = [
    "finance_dw.dim_branch",
    "finance_dw.dim_product",
    "finance_dw.dim_customer",
    "finance_dw.dim_account",
    "finance_dw.dim_date",
    "finance_dw.fact_transaction",
    "finance_dw.fact_daily_balance",
    "finance_dw.fact_loan_snapshot",
]


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def main() -> int:
    try:
        import jaydebeapi
    except ImportError:
        raise RuntimeError("Install jaydebeapi first: python3 -m pip install --user jaydebeapi") from None

    host = require("TERADATA_HOST")
    user = require("TERADATA_USER")
    password = require("TERADATA_PASSWORD")
    jar = require("TERADATA_JDBC_JAR")
    database = os.getenv("TERADATA_DATABASE", "finance_dw")
    out_dir = Path(os.getenv("EXPORT_DIR", "data/export"))
    out_dir.mkdir(parents=True, exist_ok=True)

    url = f"jdbc:teradata://{host}/DATABASE={database},CHARSET=UTF8"
    conn = jaydebeapi.connect("com.teradata.jdbc.TeraDriver", url, [user, password], jar)
    try:
        cursor = conn.cursor()
        for table in TABLES:
            file_name = table.replace(".", "__") + ".csv"
            print(f"Exporting {table} -> {out_dir / file_name}")
            cursor.execute(f"SELECT * FROM {table}")
            columns = [col[0].lower() for col in cursor.description]
            with (out_dir / file_name).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                while True:
                    rows = cursor.fetchmany(10000)
                    if not rows:
                        break
                    writer.writerows(rows)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

