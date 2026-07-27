#!/usr/bin/env python3
"""Generic MRS Spark pattern for migrated Databricks logic."""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


SOURCE_BASE = "<obs-or-hdfs-source-base>"
DATABASE = "<target_database>"
CURATED_BASE = "<obs-or-hdfs-curated-base>"


spark = SparkSession.builder.appName("databricks-migration-pattern").enableHiveSupport().getOrCreate()
spark.sql(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")

source_df = (
    spark.read.option("header", True)
    .option("inferSchema", True)
    .csv(f"{SOURCE_BASE}/<source_file>.csv")
)

target_df = (
    source_df
    .withColumn("processing_timestamp", F.current_timestamp())
)

target_df.write.mode("overwrite").saveAsTable(f"{DATABASE}.<target_table>")
target_df.write.mode("overwrite").parquet(f"{CURATED_BASE}/<target_table>")

print(f"target_rows={spark.table(f'{DATABASE}.<target_table>').count()}")
spark.stop()

# Example submit shape:
# spark-submit --master yarn --deploy-mode client mrs_spark_submit_pattern.py
