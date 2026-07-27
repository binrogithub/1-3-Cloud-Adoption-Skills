#!/usr/bin/env python3
"""Compare Databricks and MRS metric outputs."""

from __future__ import annotations

import csv
import sys
from decimal import Decimal


def load_metrics(path: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metrics[row["metric_name"]] = row["metric_value"]
    return metrics


def maybe_decimal(value: str):
    try:
        return Decimal(value)
    except Exception:
        return value


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: compare_metrics_template.py databricks_metrics.csv mrs_metrics.csv")

    left = load_metrics(sys.argv[1])
    right = load_metrics(sys.argv[2])
    all_keys = sorted(set(left) | set(right))

    print("metric_name,databricks_value,mrs_value,match_flag,delta")
    for key in all_keys:
        left_raw = left.get(key, "")
        right_raw = right.get(key, "")
        left_val = maybe_decimal(left_raw)
        right_val = maybe_decimal(right_raw)
        match_flag = left_raw == right_raw
        delta = ""
        if isinstance(left_val, Decimal) and isinstance(right_val, Decimal):
            delta = str(right_val - left_val)
        print(f"{key},{left_raw},{right_raw},{str(match_flag).lower()},{delta}")


if __name__ == "__main__":
    main()
