#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TABLE_FILES = [
    ("finance_dw.dim_branch", "finance_dw__dim_branch.csv"),
    ("finance_dw.dim_product", "finance_dw__dim_product.csv"),
    ("finance_dw.dim_customer", "finance_dw__dim_customer.csv"),
    ("finance_dw.dim_account", "finance_dw__dim_account.csv"),
    ("finance_dw.dim_date", "finance_dw__dim_date.csv"),
    ("finance_dw.fact_transaction", "finance_dw__fact_transaction.csv"),
    ("finance_dw.fact_daily_balance", "finance_dw__fact_daily_balance.csv"),
    ("finance_dw.fact_loan_snapshot", "finance_dw__fact_loan_snapshot.csv"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DWS OBS-load SQL template.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="teradata-dws-demo/export")
    parser.add_argument("--output", type=Path, default=Path("sql/dws/08_load_from_obs.generated.sql"))
    parser.add_argument("--access-key-placeholder", default="${OBS_AK}")
    parser.add_argument("--secret-key-placeholder", default="${OBS_SK}")
    args = parser.parse_args()

    prefix = args.prefix.strip("/")
    lines = [
        "-- Generated OBS load template.",
        "-- Review against your DWS version and security policy before execution.",
        "-- Prefer IAM agency/temporary credentials in production instead of long-lived AK/SK.",
        "",
    ]
    for table, file_name in TABLE_FILES:
        obs_path = f"obs://{args.bucket}/{prefix}/{file_name}" if prefix else f"obs://{args.bucket}/{file_name}"
        lines.extend(
            [
                f"-- {table}",
                f"-- Option A: adapt this COPY syntax to your DWS version:",
                f"-- COPY {table}",
                f"-- FROM '{obs_path}'",
                f"-- ACCESS_KEY '{args.access_key_placeholder}'",
                f"-- SECRET_ACCESS_KEY '{args.secret_key_placeholder}'",
                "-- FORMAT CSV",
                "-- HEADER true;",
                "",
                f"-- Option B: create an OBS/GDS external table for {obs_path}, then:",
                f"-- INSERT INTO {table} SELECT * FROM <external_table_for_{table.replace('.', '_')}>;",
                "",
            ]
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

