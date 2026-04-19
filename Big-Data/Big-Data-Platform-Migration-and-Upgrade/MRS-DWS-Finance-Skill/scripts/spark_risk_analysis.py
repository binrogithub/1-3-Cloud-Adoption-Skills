#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spark_risk_analysis.py
MRS Spark job for financial risk control analysis
- Risk scoring
- Anomaly detection (rule-based)
- Customer clustering (K-Means)
- Regulatory compliance checks
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans

# ============================================================
# Spark Session
# ============================================================
spark = SparkSession.builder \
    .appName("FinanceRiskControl_Analysis") \
    .config("spark.sql.warehouse.dir", "/user/openbank/warehouse") \
    .enableHiveSupport() \
    .getOrCreate()

print("=" * 60)
print("Financial Risk Control - Spark Analysis")
print("=" * 60)

# ============================================================
# 1. Load Data from Hive (OBS-backed)
# ============================================================
print("\n1. Loading data...")

transactions_df = spark.sql("""
    SELECT
        transaction_id, customer_id, account_id,
        transaction_type, amount, currency, timestamp,
        merchant_category, merchant_id, location, city, state,
        device_id, ip_address, channel, payment_method,
        status, is_fraud, anomaly_type, kyc_level
    FROM openbank_risk.transactions
""")

customers_df = spark.sql("SELECT * FROM openbank_risk.customers")
accounts_df = spark.sql("SELECT * FROM openbank_risk.accounts")

txn_count = transactions_df.count()
cust_count = customers_df.count()
print(f"  Transactions: {txn_count:,}")
print(f"  Customers: {cust_count:,}")

# ============================================================
# 2. Feature Engineering
# ============================================================
print("\n2. Feature engineering...")

# Time features
transactions_df = transactions_df.withColumn(
    "hour", hour(to_timestamp(col("timestamp")))
).withColumn(
    "day_of_week", dayofweek(to_timestamp(col("timestamp")))
).withColumn(
    "is_weekend", when(col("day_of_week").isin([1, 7]), 1).otherwise(0)
).withColumn(
    "is_night", when(col("hour").between(0, 5), 1).otherwise(0)
)

# Customer transaction statistics
customer_stats = transactions_df.groupBy("customer_id").agg(
    count("*").alias("total_transactions"),
    sum("amount").alias("total_amount"),
    avg("amount").alias("avg_amount"),
    max("amount").alias("max_amount"),
    stddev("amount").alias("std_amount"),
    sum(when(col("is_fraud") == 1, 1).otherwise(0)).alias("fraud_count"),
    countDistinct("city").alias("unique_cities"),
    countDistinct("channel").alias("unique_channels"),
    countDistinct("payment_method").alias("unique_payment_methods")
)

print("  Customer statistics computed")

# ============================================================
# 3. Rule-Based Anomaly Detection
# ============================================================
print("\n3. Rule-based anomaly detection...")

# Large amount detection (CNBV threshold)
LARGE_AMOUNT_INDIVIDUAL = 50000
LARGE_AMOUNT_BUSINESS = 500000
large_amount_txns = transactions_df.filter(
    col("amount") > LARGE_AMOUNT_INDIVIDUAL
)
print(f"  Large amount transactions (>{LARGE_AMOUNT_INDIVIDUAL:,} MXN): {large_amount_txns.count():,}")

# Unusual time detection (2-5 AM)
unusual_time_txns = transactions_df.filter(col("hour").between(2, 5))
print(f"  Unusual time transactions (2-5 AM): {unusual_time_txns.count():,}")

# High-risk cities
HIGH_RISK_CITIES = ["Culiacan", "Ciudad Juarez", "Acapulco", "Tepic"]
high_risk_city_txns = transactions_df.filter(col("city").isin(HIGH_RISK_CITIES))
print(f"  High-risk city transactions: {high_risk_city_txns.count():,}")

# Structuring detection (multiple transactions just below 15,000 MXN)
structuring_txns = transactions_df.filter(
    (col("amount") > 10000) & (col("amount") < 15000)
)
print(f"  Potential structuring transactions: {structuring_txns.count():,}")

# Cross-border detection (border cities)
BORDER_CITIES = ["Tijuana", "Ciudad Juarez", "Nuevo Laredo", "Matamoros", "Reynosa"]
cross_border_txns = transactions_df.filter(col("city").isin(BORDER_CITIES))
print(f"  Cross-border city transactions: {cross_border_txns.count():,}")

# ============================================================
# 4. K-Means Customer Clustering
# ============================================================
print("\n4. K-Means customer clustering...")

feature_cols = ["total_transactions", "total_amount", "avg_amount", "max_amount"]
assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
customer_features = assembler.transform(customer_stats.na.fill(0))

scaler = StandardScaler(inputCol="features", outputCol="scaled_features")
scaler_model = scaler.fit(customer_features)
customer_scaled = scaler_model.transform(customer_features)

kmeans = KMeans(k=5, featuresCol="scaled_features", predictionCol="cluster")
kmeans_model = kmeans.fit(customer_scaled)
customer_clusters = kmeans_model.transform(customer_scaled)

print("  Customer clustering complete")
customer_clusters.groupBy("cluster").count().show()

# ============================================================
# 5. Risk Score Calculation
# ============================================================
print("\n5. Risk score calculation...")

customer_risk_scores = customer_stats.withColumn(
    "risk_score",
    lit(0) +
    # Large transaction risk
    when(col("max_amount") > 100000, 20).otherwise(0) +
    when(col("max_amount") > 200000, 20).otherwise(0) +
    # Frequent transaction risk
    when(col("total_transactions") > 100, 10).otherwise(0) +
    when(col("total_transactions") > 200, 10).otherwise(0) +
    # Fraud history risk
    col("fraud_count") * 5 +
    # Amount volatility risk
    when(col("std_amount") > 10000, 10).otherwise(0) +
    # Geographic diversity risk
    when(col("unique_cities") > 5, 5).otherwise(0) +
    # Channel diversity risk
    when(col("unique_channels") > 3, 5).otherwise(0)
).withColumn(
    "risk_level",
    when(col("risk_score") >= 50, "CRITICAL")
    .when(col("risk_score") >= 30, "HIGH")
    .when(col("risk_score") >= 15, "MEDIUM")
    .otherwise("LOW")
)

print("  Risk scores computed")
customer_risk_scores.groupBy("risk_level").count().show()

# ============================================================
# 6. Regulatory Compliance Checks
# ============================================================
print("\n6. Regulatory compliance checks...")

# CNBV daily limit check (individual: 50,000 MXN)
cnbv_daily_violations = transactions_df.filter(
    (col("amount") > 50000) & (col("kyc_level") != "LEVEL_3")
)
print(f"  CNBV daily limit violations: {cnbv_daily_violations.count():,}")

# KYC level compliance
# Level 1: <= 7,500 MXN, Level 2: <= 30,000 MXN
kyc_violations = transactions_df.filter(
    ((col("kyc_level") == "LEVEL_1") & (col("amount") > 7500)) |
    ((col("kyc_level") == "LEVEL_2") & (col("amount") > 30000))
)
print(f"  KYC level violations: {kyc_violations.count():,}")

# SPEI limit check
spei_violations = transactions_df.filter(
    (col("payment_method") == "SPEI") & (col("amount") > 500000)
)
print(f"  SPEI limit violations: {spei_violations.count():,}")

# ============================================================
# 7. Save Results to OBS (via Hive)
# ============================================================
print("\n7. Saving results...")

# Save risk scores
customer_risk_scores.select(
    "customer_id", "total_transactions", "total_amount",
    "avg_amount", "max_amount", "fraud_count",
    "risk_score", "risk_level"
).write.mode("overwrite").format("parquet") \
    .save("obs://<results_bucket>/risk_scores/")

# Save customer clusters
customer_clusters.select(
    "customer_id", "total_transactions", "total_amount", "cluster"
).write.mode("overwrite").format("parquet") \
    .save("obs://<results_bucket>/customer_clusters/")

# Save high risk customers
customer_risk_scores.filter(
    col("risk_level").isin(["HIGH", "CRITICAL"])
).select(
    "customer_id", "total_transactions", "total_amount",
    "fraud_count", "risk_score", "risk_level"
).orderBy(col("risk_score").desc()) \
 .write.mode("overwrite").format("parquet") \
 .save("obs://<results_bucket>/high_risk_customers/")

print("  Results saved to OBS")

# ============================================================
# 8. Summary
# ============================================================
print("\n" + "=" * 60)
print("Analysis Summary")
print("=" * 60)

total_txns = transactions_df.count()
total_amount = transactions_df.agg(sum("amount")).collect()[0][0]
fraud_txns = transactions_df.filter(col("is_fraud") == 1).count()

print(f"\nTotal transactions: {total_txns:,}")
print(f"Total amount: {total_amount:,.2f} MXN")
print(f"Fraud transactions: {fraud_txns:,}")
print(f"Fraud rate: {fraud_txns/total_txns*100:.2f}%")
print(f"\nAnalysis complete!")

spark.stop()
