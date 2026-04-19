#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_pipeline_parity.py
Compare MRS Spark analysis results with DWS data warehouse outputs
to validate pipeline consistency and data parity
"""

import sys
import csv
import json
from collections import defaultdict

# ============================================================
# Configuration (replace placeholders before running)
# ============================================================
DWS_ENDPOINT = "<dws_endpoint>"
DWS_PORT = "<dws_port>"
DWS_DB = "financedb"
DWS_USER = "<db_user>"
DWS_PASSWORD = "<db_password>"

MRS_RESULTS_PATH = "<mrs_results_path>"  # Local path to MRS Parquet results

# ============================================================
# Metric Comparison Framework
# ============================================================

class PipelineParityValidator:
    """Validate parity between MRS and DWS analysis results."""

    def __init__(self):
        self.results = {
            "mrs": {},
            "dws": {},
            "comparisons": [],
            "summary": {}
        }

    def load_mrs_results(self, path):
        """Load MRS Spark analysis results from Parquet files."""
        try:
            import pandas as pd
            self.results["mrs"]["risk_scores"] = pd.read_parquet(f"{path}/risk_scores/")
            self.results["mrs"]["customer_clusters"] = pd.read_parquet(f"{path}/customer_clusters/")
            self.results["mrs"]["high_risk_customers"] = pd.read_parquet(f"{path}/high_risk_customers/")
            print(f"MRS results loaded from: {path}")
        except Exception as e:
            print(f"ERROR loading MRS results: {e}")
            sys.exit(1)

    def load_dws_results(self, endpoint, port, db, user, password):
        """Load DWS results via SQL queries."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=endpoint, port=port, dbname=db,
                user=user, password=password
            )
            cur = conn.cursor()

            # Load customer risk scores
            cur.execute("""
                SELECT customer_id, risk_score, risk_level,
                       total_transactions, total_amount, fraud_count
                FROM dm.dm_customer_risk
            """)
            self.results["dws"]["risk_scores"] = cur.fetchall()

            # Load city risk
            cur.execute("""
                SELECT city_name, total_transactions, fraud_transactions, fraud_rate
                FROM dm.dm_city_risk
            """)
            self.results["dws"]["city_risk"] = cur.fetchall()

            # Load risk overview
            cur.execute("""
                SELECT total_transactions, total_amount, fraud_transactions, fraud_rate
                FROM rpt.risk_overview
                ORDER BY report_date DESC LIMIT 1
            """)
            self.results["dws"]["risk_overview"] = cur.fetchone()

            cur.close()
            conn.close()
            print(f"DWS results loaded from: {endpoint}:{port}/{db}")
        except Exception as e:
            print(f"ERROR loading DWS results: {e}")
            sys.exit(1)

    def compare_metric(self, name, mrs_value, dws_value, tolerance=0.01):
        """Compare a single metric between MRS and DWS."""
        if mrs_value is None or dws_value is None:
            status = "SKIP"
            delta = None
        elif isinstance(mrs_value, (int, float)) and isinstance(dws_value, (int, float)):
            delta = abs(mrs_value - dws_value)
            if delta <= tolerance * max(abs(mrs_value), abs(dws_value), 1):
                status = "MATCH"
            else:
                status = "MISMATCH"
        else:
            status = "MATCH" if str(mrs_value) == str(dws_value) else "MISMATCH"
            delta = None

        result = {
            "metric": name,
            "mrs_value": mrs_value,
            "dws_value": dws_value,
            "delta": delta,
            "status": status
        }
        self.results["comparisons"].append(result)
        return status

    def validate(self):
        """Run all parity checks."""
        print("\n" + "=" * 60)
        print("Pipeline Parity Validation")
        print("=" * 60)

        # --- Total transaction count ---
        mrs_total = len(self.results["mrs"]["risk_scores"]) if "risk_scores" in self.results["mrs"] else None
        dws_total = len(self.results["dws"]["risk_scores"]) if "risk_scores" in self.results["dws"] else None
        self.compare_metric("customer_risk_count", mrs_total, dws_total)

        # --- Risk level distribution ---
        if "risk_scores" in self.results["mrs"]:
            mrs_risk_dist = self.results["mrs"]["risk_scores"]["risk_level"].value_counts().to_dict()
        else:
            mrs_risk_dist = {}

        for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            mrs_count = mrs_risk_dist.get(level, 0)
            # DWS comparison would require additional query
            self.compare_metric(f"risk_level_{level}_count", mrs_count, None)

        # --- Print results ---
        print("\nComparison Results:")
        print("-" * 60)
        matches = 0
        mismatches = 0
        skips = 0

        for comp in self.results["comparisons"]:
            symbol = {"MATCH": "✓", "MISMATCH": "✗", "SKIP": "?"}[comp["status"]]
            print(f"  [{symbol}] {comp['metric']}: MRS={comp['mrs_value']}, DWS={comp['dws_value']}")
            if comp["status"] == "MATCH":
                matches += 1
            elif comp["status"] == "MISMATCH":
                mismatches += 1
            else:
                skips += 1

        total = matches + mismatches + skips
        self.results["summary"] = {
            "total_checks": total,
            "matches": matches,
            "mismatches": mismatches,
            "skips": skips,
            "match_rate": f"{matches/total*100:.1f}%" if total > 0 else "N/A"
        }

        print("\n" + "=" * 60)
        print("Validation Summary")
        print("=" * 60)
        print(f"  Total checks: {total}")
        print(f"  Matches: {matches}")
        print(f"  Mismatches: {mismatches}")
        print(f"  Skips: {skips}")
        print(f"  Match rate: {self.results['summary']['match_rate']}")

        if mismatches > 0:
            print("\n⚠ MISMATCHES DETECTED - Review delta values above")
            return False
        else:
            print("\n✓ All comparable metrics match between MRS and DWS")
            return True


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    validator = PipelineParityValidator()

    # Load results from both systems
    validator.load_mrs_results(MRS_RESULTS_PATH)
    validator.load_dws_results(DWS_ENDPOINT, DWS_PORT, DWS_DB, DWS_USER, DWS_PASSWORD)

    # Run validation
    success = validator.validate()
    sys.exit(0 if success else 1)
