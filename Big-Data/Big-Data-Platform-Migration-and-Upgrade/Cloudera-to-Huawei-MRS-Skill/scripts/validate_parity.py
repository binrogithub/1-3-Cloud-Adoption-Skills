#!/usr/bin/env python3
"""
Cloudera-to-MRS Parity Validation Script

Compares source (Cloudera) metrics with MRS metrics to validate migration accuracy.

Usage:
    # Validate from local source against MRS via SSH
    python3 validate_parity.py \
        --source_metrics reports/cloudera_to_mrs/parity_metrics.csv \
        --mrs_eip <eip> \
        --mrs_password <password>

    # Validate from pre-computed MRS results
    python3 validate_parity.py \
        --source_metrics reports/cloudera_to_mrs/parity_metrics.csv \
        --mrs_results mrs_validation.csv

Requirements:
    pip install paramiko
"""

import argparse
import csv
import sys


def parse_source_metrics(path):
    """Parse local parity_metrics.csv into a dict of metric -> value."""
    metrics = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            table = row.get("table_name", "")
            metric = row.get("metric_name", "")
            source_val = row.get("source_value", "")
            if metric == "row_count":
                key = table
            else:
                key = f"{table}.{metric}"
            metrics[key] = source_val
    return metrics


def parse_mrs_results(path):
    """Parse MRS validation results (tab-separated metric\\tvalue)."""
    metrics = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                metrics[parts[0]] = parts[1]
    return metrics


def compare_metrics(source, mrs, tolerance=0.02):
    """Compare source and MRS metrics, return list of results."""
    results = []
    all_pass = True

    for key in sorted(source.keys()):
        src_val = source[key]
        mrs_val = mrs.get(key, "N/A")

        try:
            src_f = float(src_val.replace(",", ""))
            mrs_f = float(mrs_val.replace(",", ""))
            delta = abs(src_f - mrs_f)
            if delta < tolerance:
                status = "PASS"
            else:
                status = f"FAIL (delta={delta})"
                all_pass = False
        except (ValueError, AttributeError):
            status = "FAIL (parse error)"
            all_pass = False

        results.append({
            "metric": key,
            "source_value": src_val,
            "mrs_value": mrs_val,
            "status": status,
        })

    return results, all_pass


def main():
    parser = argparse.ArgumentParser(description="Validate Cloudera-to-MRS migration parity")
    parser.add_argument("--source_metrics", required=True, help="Path to source parity_metrics.csv")
    parser.add_argument("--mrs_results", default=None, help="Path to MRS validation results")
    parser.add_argument("--tolerance", type=float, default=0.02, help="Numeric tolerance")
    args = parser.parse_args()

    source = parse_source_metrics(args.source_metrics)
    print(f"Loaded {len(source)} source metrics")

    if args.mrs_results:
        mrs = parse_mrs_results(args.mrs_results)
        print(f"Loaded {len(mrs)} MRS metrics")
    else:
        print("ERROR: --mrs_results is required (SSH-based validation not yet implemented)")
        sys.exit(1)

    results, all_pass = compare_metrics(source, mrs, args.tolerance)

    print("\n=== Parity Validation Results ===")
    for r in results:
        print(f"  {r['metric']}: source={r['source_value']} mrs={r['mrs_value']} => {r['status']}")

    if all_pass:
        print("\nALL PASS - Migration validated!")
    else:
        print("\nSOME CHECKS FAILED - Review results above")
        sys.exit(1)


if __name__ == "__main__":
    main()
