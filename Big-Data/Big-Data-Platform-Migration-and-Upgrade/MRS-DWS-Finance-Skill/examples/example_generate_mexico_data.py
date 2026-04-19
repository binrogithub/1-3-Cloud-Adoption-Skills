#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
example_generate_mexico_data.py
Generate Mexico-specific financial transaction data for testing.

This example generates realistic Mexico OpenBank data including:
- Mexico locations with risk levels (CNBV flagged regions)
- Mexico payment methods (SPEI, OXXO Pay, Mercado Pago, etc.)
- Mexico customer segments (Banco Azteca, Traditional, Fintech, Premium, Corporate)
- CNBV/Banxico regulatory limits
- Mexico-specific anomaly types (structuring, cross-border, suspicious_pattern)

Usage:
    python example_generate_mexico_data.py [--customers N] [--days N] [--output DIR]

Requirements:
    pip install pandas numpy
"""

import random
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

# ============================================================
# Mexico OpenBank Business Characteristics
# ============================================================

MEXICO_LOCATIONS = [
    {"city": "Mexico City", "state": "CDMX", "lat": 19.4326, "lng": -99.1332,
     "weight": 0.25, "risk_level": "LOW"},
    {"city": "Monterrey", "state": "Nuevo Leon", "lat": 25.6866, "lng": -100.3161,
     "weight": 0.10, "risk_level": "LOW"},
    {"city": "Guadalajara", "state": "Jalisco", "lat": 20.6597, "lng": -103.3496,
     "weight": 0.12, "risk_level": "LOW"},
    {"city": "Queretaro", "state": "Queretaro", "lat": 20.5888, "lng": -100.3899,
     "weight": 0.05, "risk_level": "LOW"},
    {"city": "Puebla", "state": "Puebla", "lat": 19.0414, "lng": -98.2062,
     "weight": 0.06, "risk_level": "LOW"},
    {"city": "Tijuana", "state": "Baja California", "lat": 32.5149, "lng": -117.0382,
     "weight": 0.06, "risk_level": "MEDIUM"},
    {"city": "Cancun", "state": "Quintana Roo", "lat": 21.1619, "lng": -86.8515,
     "weight": 0.05, "risk_level": "MEDIUM"},
    {"city": "Merida", "state": "Yucatan", "lat": 20.9677, "lng": -89.6327,
     "weight": 0.04, "risk_level": "MEDIUM"},
    {"city": "Culiacan", "state": "Sinaloa", "lat": 24.7903, "lng": -107.4468,
     "weight": 0.03, "risk_level": "HIGH"},
    {"city": "Ciudad Juarez", "state": "Chihuahua", "lat": 31.6906, "lng": -106.4245,
     "weight": 0.02, "risk_level": "HIGH"},
    {"city": "Acapulco", "state": "Guerrero", "lat": 16.8695, "lng": -99.8737,
     "weight": 0.02, "risk_level": "HIGH"},
    {"city": "Tepic", "state": "Nayarit", "lat": 21.5050, "lng": -104.8922,
     "weight": 0.01, "risk_level": "HIGH"},
]

PAYMENT_METHODS = [
    {"method": "SPEI", "weight": 0.35, "is_instant": True},
    {"method": "OXXO_PAY", "weight": 0.15, "is_instant": True},
    {"method": "DEBIT_CARD", "weight": 0.15, "is_instant": True},
    {"method": "MERCADO_PAGO", "weight": 0.12, "is_instant": True},
    {"method": "CREDIT_CARD", "weight": 0.08, "is_instant": True},
    {"method": "PAYPAL", "weight": 0.08, "is_instant": True},
    {"method": "SPID", "weight": 0.05, "is_instant": False},
    {"method": "CASH_DEPOSIT", "weight": 0.02, "is_instant": False},
]

CUSTOMER_SEGMENTS = [
    {"segment": "BANCO_AZTECA", "weight": 0.25, "avg_income": 15000},
    {"segment": "TRADITIONAL_BANK", "weight": 0.30, "avg_income": 35000},
    {"segment": "FINTECH_USER", "weight": 0.25, "avg_income": 45000},
    {"segment": "PREMIUM", "weight": 0.15, "avg_income": 120000},
    {"segment": "CORPORATE", "weight": 0.05, "avg_income": 500000},
]

# CNBV Regulatory Limits
CNBV_LIMITS = {
    "daily_limit_individual": 50000,
    "monthly_limit_individual": 500000,
    "suspicious_threshold": 15000,
    "large_transaction_threshold": 100000,
}

SPEI_LIMITS = {
    "instant_limit": 8000,
    "regular_limit": 500000,
}

AML_KYC = {
    "level_1_limit": 7500,
    "level_2_limit": 30000,
}

ANOMALY_TYPES = [
    "large_amount", "frequent_transactions", "unusual_location",
    "unusual_time", "round_amount", "suspicious_pattern",
    "cross_border", "structuring"
]


def generate_customers(num_customers):
    """Generate Mexico-specific customer data."""
    customers = []
    for i in range(num_customers):
        segment = random.choices(
            CUSTOMER_SEGMENTS,
            weights=[s['weight'] for s in CUSTOMER_SEGMENTS]
        )[0]

        age = max(18, min(80, int(np.random.normal(35, 12))))
        income = segment['avg_income'] * random.uniform(0.5, 2.0)

        if income <= AML_KYC['level_1_limit']:
            kyc_level = "LEVEL_1"
        elif income <= AML_KYC['level_2_limit']:
            kyc_level = "LEVEL_2"
        else:
            kyc_level = "LEVEL_3"

        customers.append({
            "customer_id": f"CUST_{str(i+1).zfill(6)}",
            "customer_name": f"Customer_{i+1}",
            "age": age,
            "gender": random.choice(["M", "F"]),
            "income_level": segment['avg_income'],
            "customer_segment": segment['segment'],
            "kyc_level": kyc_level,
            "risk_level": np.random.choice(
                ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                p=[0.6, 0.25, 0.12, 0.03]
            ),
        })
    return pd.DataFrame(customers)


def generate_accounts(customers_df):
    """Generate Mexico-specific account data."""
    accounts = []
    for _, cust in customers_df.iterrows():
        num_accounts = random.randint(1, 3)
        for j in range(num_accounts):
            accounts.append({
                "account_id": f"ACC_{str(len(accounts)+1).zfill(8)}",
                "customer_id": cust['customer_id'],
                "account_type": random.choice(["SAVINGS", "CHECKING", "BUSINESS"]),
                "balance": round(cust['income_level'] * random.uniform(0.5, 3.0), 2),
                "daily_limit": CNBV_LIMITS['daily_limit_individual'],
                "monthly_limit": CNBV_LIMITS['monthly_limit_individual'],
                "account_status": "ACTIVE",
            })
    return pd.DataFrame(accounts)


def generate_transactions(accounts_df, customers_df, num_days, txns_per_day):
    """Generate Mexico-specific transaction data with anomalies."""
    transactions = []
    start_date = datetime.now() - timedelta(days=num_days)
    acc_cust = accounts_df.merge(customers_df, on='customer_id')

    anomaly_counts = {a: 0 for a in ANOMALY_TYPES}

    for day in range(num_days):
        current_date = start_date + timedelta(days=day)
        daily_count = int(txns_per_day * random.uniform(0.8, 1.2))

        for _ in range(daily_count):
            acc = acc_cust.sample(1).iloc[0]
            location = random.choices(
                MEXICO_LOCATIONS,
                weights=[l['weight'] for l in MEXICO_LOCATIONS]
            )[0]
            payment = random.choices(
                PAYMENT_METHODS,
                weights=[p['weight'] for p in PAYMENT_METHODS]
            )[0]

            hour = random.randint(0, 23)
            amount = random.uniform(100, 50000)

            # Inject anomaly (6% rate)
            is_fraud = 0
            anomaly_type = "NORMAL"

            if random.random() < 0.06:
                is_fraud = 1
                anomaly_type = random.choice(ANOMALY_TYPES)
                anomaly_counts[anomaly_type] += 1

                if anomaly_type == "large_amount":
                    amount = random.uniform(100000, 500000)
                elif anomaly_type == "round_amount":
                    amount = random.choice([50000, 100000, 150000, 200000])
                elif anomaly_type == "unusual_time":
                    hour = random.randint(2, 5)
                    amount = random.uniform(30000, 100000)
                elif anomaly_type == "unusual_location":
                    location = random.choice(
                        [l for l in MEXICO_LOCATIONS if l['risk_level'] == 'HIGH']
                    )
                elif anomaly_type == "suspicious_pattern":
                    amount = CNBV_LIMITS['suspicious_threshold'] * random.uniform(0.8, 0.99)
                elif anomaly_type == "cross_border":
                    location = random.choice(
                        [l for l in MEXICO_LOCATIONS if l['city'] in
                         ["Tijuana", "Ciudad Juarez", "Culiacan"]]
                    )
                    amount = random.uniform(50000, 200000)
                elif anomaly_type == "structuring":
                    amount = CNBV_LIMITS['suspicious_threshold'] * random.uniform(0.5, 0.9)

            txn_time = current_date.replace(
                hour=hour,
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            )

            transactions.append({
                "transaction_id": f"TXN_{str(len(transactions)+1).zfill(10)}",
                "customer_id": acc['customer_id'],
                "account_id": acc['account_id'],
                "transaction_type": random.choice(["TRANSFER", "PAYMENT", "DEPOSIT", "WITHDRAWAL"]),
                "amount": round(amount, 2),
                "currency": "MXN",
                "timestamp": txn_time.strftime("%Y-%m-%d %H:%M:%S"),
                "city": location['city'],
                "state": location['state'],
                "channel": random.choice(["MOBILE_APP", "WEB_PORTAL", "ATM", "BRANCH", "API"]),
                "payment_method": payment['method'],
                "is_fraud": is_fraud,
                "anomaly_type": anomaly_type,
                "kyc_level": acc['kyc_level'],
            })

    print(f"\nAnomaly distribution:")
    for a, c in anomaly_counts.items():
        print(f"  {a}: {c}")

    return pd.DataFrame(transactions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Mexico OpenBank test data")
    parser.add_argument("--customers", type=int, default=2000, help="Number of customers")
    parser.add_argument("--days", type=int, default=30, help="Number of days")
    parser.add_argument("--output", type=str, default="mexico_data", help="Output directory")
    args = parser.parse_args()

    print(f"Generating Mexico OpenBank data: {args.customers} customers, {args.days} days")

    customers_df = generate_customers(args.customers)
    accounts_df = generate_accounts(customers_df)
    transactions_df = generate_transactions(accounts_df, customers_df, args.days, 6000)

    os.makedirs(args.output, exist_ok=True)
    customers_df.to_csv(f"{args.output}/customers.csv", index=False)
    accounts_df.to_csv(f"{args.output}/accounts.csv", index=False)
    transactions_df.to_csv(f"{args.output}/transactions.csv", index=False)

    print(f"\nData saved to {args.output}/")
    print(f"  customers.csv: {len(customers_df)} records")
    print(f"  accounts.csv: {len(accounts_df)} records")
    print(f"  transactions.csv: {len(transactions_df)} records")
    print(f"  Anomaly rate: {transactions_df['is_fraud'].mean()*100:.2f}%")
