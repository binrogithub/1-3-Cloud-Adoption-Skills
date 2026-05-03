#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    normalized = "" if value is None else str(value).strip()
    if normalized.endswith(" 00:00:00"):
        normalized = normalized[:-9]
    if normalized.startswith("."):
        return "0" + normalized
    if normalized.startswith("-."):
        return "-0" + normalized[1:]
    return normalized


def as_decimal(value: str) -> Decimal:
    try:
        return Decimal(normalize(value))
    except InvalidOperation:
        raise AssertionError(f"not numeric: {value!r}") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two CSV files for migration validation.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--numeric", action="append", default=[])
    parser.add_argument("--tolerance", type=Decimal, default=Decimal("0.01"))
    args = parser.parse_args()

    expected = read_csv(args.expected)
    actual = read_csv(args.actual)

    if args.key:
        expected = sorted(expected, key=lambda row: tuple(normalize(row.get(k, "")) for k in args.key))
        actual = sorted(actual, key=lambda row: tuple(normalize(row.get(k, "")) for k in args.key))

    if len(expected) != len(actual):
        raise AssertionError(f"{args.expected} and {args.actual} row counts differ: {len(expected)} != {len(actual)}")

    for idx, (left, right) in enumerate(zip(expected, actual), start=1):
        if set(left) != set(right):
            raise AssertionError(f"CSV columns differ at row {idx}: {set(left)} != {set(right)}")
        for column in left:
            if column in args.numeric:
                delta = abs(as_decimal(left[column]) - as_decimal(right[column]))
                if delta > args.tolerance:
                    raise AssertionError(f"{column} differs at row {idx}: {left[column]} != {right[column]}")
            elif normalize(left[column]) != normalize(right[column]):
                raise AssertionError(f"{column} differs at row {idx}: {left[column]!r} != {right[column]!r}")

    print(f"OK: {args.expected} == {args.actual}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
