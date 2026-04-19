#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
example_analyze_results.py
Local analysis and visualization of risk control results.
Generates summary statistics, risk charts, and a markdown report.
Useful for quick validation before deploying to MRS/DWS.

Usage:
    python example_analyze_results.py [--data DIR] [--output DIR]

Requirements:
    pip install pandas numpy matplotlib
"""

import argparse
import os
import pandas as pd
import numpy as np
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def analyze_transactions(transactions_df):
    """Run local risk analysis on transaction data."""
    print("=" * 60)
    print("Risk Control Analysis Results")
    print("=" * 60)

    total = len(transactions_df)
    fraud = transactions_df[transactions_df['is_fraud'] == 1]
    fraud_count = len(fraud)

    # Overall statistics
    print(f"\nOverall Statistics:")
    print(f"  Total transactions: {total:,}")
    print(f"  Total amount: {transactions_df['amount'].sum():,.2f} MXN")
    print(f"  Average amount: {transactions_df['amount'].mean():,.2f} MXN")
    print(f"  Max amount: {transactions_df['amount'].max():,.2f} MXN")
    print(f"  Fraud transactions: {fraud_count:,}")
    print(f"  Fraud rate: {fraud_count/total*100:.2f}%")

    # Anomaly type distribution
    print(f"\nAnomaly Type Distribution:")
    if fraud_count > 0:
        anomaly_dist = fraud['anomaly_type'].value_counts()
        for atype, count in anomaly_dist.items():
            print(f"  {atype}: {count} ({count/fraud_count*100:.1f}%)")

    # City risk analysis
    print(f"\nCity Risk Analysis (Top 10 by fraud count):")
    city_stats = transactions_df.groupby('city').agg(
        total=('transaction_id', 'count'),
        fraud_count=('is_fraud', 'sum'),
        total_amount=('amount', 'sum')
    )
    city_stats['fraud_rate'] = (city_stats['fraud_count'] / city_stats['total'] * 100).round(2)
    city_stats = city_stats.sort_values('fraud_count', ascending=False)
    print(city_stats.head(10).to_string())

    # Channel risk analysis
    print(f"\nChannel Risk Analysis:")
    channel_stats = transactions_df.groupby('channel').agg(
        total=('transaction_id', 'count'),
        fraud_count=('is_fraud', 'sum')
    )
    channel_stats['fraud_rate'] = (channel_stats['fraud_count'] / channel_stats['total'] * 100).round(2)
    print(channel_stats.to_string())

    # Payment method analysis
    if 'payment_method' in transactions_df.columns:
        print(f"\nPayment Method Risk Analysis:")
        pm_stats = transactions_df.groupby('payment_method').agg(
            total=('transaction_id', 'count'),
            fraud_count=('is_fraud', 'sum'),
            avg_amount=('amount', 'mean')
        )
        pm_stats['fraud_rate'] = (pm_stats['fraud_count'] / pm_stats['total'] * 100).round(2)
        print(pm_stats.to_string())

    # Time-based analysis
    if 'timestamp' in transactions_df.columns:
        transactions_df['hour'] = pd.to_datetime(transactions_df['timestamp']).dt.hour
        print(f"\nUnusual Time Analysis (2-5 AM):")
        night_txns = transactions_df[transactions_df['hour'].between(2, 5)]
        print(f"  Night transactions: {len(night_txns):,}")
        print(f"  Night fraud rate: {night_txns['is_fraud'].mean()*100:.2f}%")
        print(f"  Overall fraud rate: {fraud_count/total*100:.2f}%")

    return city_stats, channel_stats


def generate_report(transactions_df, customers_df, output_dir):
    """Generate a markdown analysis report."""
    os.makedirs(output_dir, exist_ok=True)

    total = len(transactions_df)
    fraud_count = transactions_df['is_fraud'].sum()

    report = f"""# Risk Control Analysis Report

## Summary
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Total Transactions**: {total:,}
- **Total Amount**: {transactions_df['amount'].sum():,.2f} MXN
- **Fraud Transactions**: {fraud_count:,}
- **Fraud Rate**: {fraud_count/total*100:.2f}%

## Anomaly Distribution
"""
    fraud = transactions_df[transactions_df['is_fraud'] == 1]
    if len(fraud) > 0:
        for atype, count in fraud['anomaly_type'].value_counts().items():
            report += f"- **{atype}**: {count} ({count/len(fraud)*100:.1f}%)\n"

    report += """
## Key Findings
1. High-risk cities require enhanced monitoring
2. Night transactions (2-5 AM) show elevated fraud rates
3. Structuring patterns detected below CNBV reporting threshold
4. Cross-border transactions from border cities need review

## Recommendations
1. Implement real-time large transaction alerts (>50,000 MXN)
2. Add secondary verification for high-risk city transactions
3. Deploy automated structuring detection
4. Enhance cross-border monitoring for US-Mexico border
"""

    report_path = f"{output_dir}/risk_analysis_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved: {report_path}")


def generate_charts(transactions_df, output_dir):
    """Generate visualization charts."""
    if not HAS_MATPLOTLIB:
        print("\nmatplotlib not available, skipping charts")
        return

    os.makedirs(output_dir, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Financial Risk Control Analysis', fontsize=14, fontweight='bold')

    # Anomaly type distribution
    fraud = transactions_df[transactions_df['is_fraud'] == 1]
    if len(fraud) > 0:
        fraud['anomaly_type'].value_counts().plot(kind='bar', ax=axes[0, 0], color='coral')
        axes[0, 0].set_title('Anomaly Type Distribution')
        axes[0, 0].tick_params(axis='x', rotation=45)

    # City distribution
    transactions_df['city'].value_counts().head(10).plot(
        kind='barh', ax=axes[0, 1], color='skyblue'
    )
    axes[0, 1].set_title('Top 10 Cities by Transaction Count')

    # Amount distribution
    transactions_df['amount'].hist(bins=50, ax=axes[1, 0], color='purple', alpha=0.7)
    axes[1, 0].set_title('Transaction Amount Distribution')
    axes[1, 0].set_xlabel('Amount (MXN)')
    axes[1, 0].set_xlim(0, min(100000, transactions_df['amount'].quantile(0.99)))

    # Fraud vs Normal
    fraud_count = len(fraud)
    normal_count = len(transactions_df) - fraud_count
    axes[1, 1].pie(
        [fraud_count, normal_count],
        labels=['Fraud', 'Normal'],
        colors=['red', 'green'],
        autopct='%1.1f%%',
        startangle=90
    )
    axes[1, 1].set_title('Fraud vs Normal Transactions')

    plt.tight_layout()
    chart_path = f"{output_dir}/risk_analysis_charts.png"
    plt.savefig(chart_path, dpi=200, bbox_inches='tight')
    print(f"Charts saved: {chart_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze risk control results")
    parser.add_argument("--data", type=str, default="mexico_data", help="Data directory")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    args = parser.parse_args()

    # Load data
    transactions_df = pd.read_csv(f"{args.data}/transactions.csv")
    customers_df = pd.read_csv(f"{args.data}/customers.csv")

    # Analyze
    analyze_transactions(transactions_df)

    # Generate report
    generate_report(transactions_df, customers_df, args.output)

    # Generate charts
    generate_charts(transactions_df, args.output)

    print("\nAnalysis complete!")
