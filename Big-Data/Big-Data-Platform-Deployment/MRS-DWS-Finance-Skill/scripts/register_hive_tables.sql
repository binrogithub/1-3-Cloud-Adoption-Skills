-- ============================================================
-- register_hive_tables.sql
-- Create Hive external tables over OBS data for MRS Spark
-- ============================================================

-- Create database
CREATE DATABASE IF NOT EXISTS openbank_risk;
USE openbank_risk;

-- ============================================================
-- External Tables (pointing to OBS raw data)
-- ============================================================

-- Transactions table
CREATE EXTERNAL TABLE IF NOT EXISTS transactions (
    transaction_id STRING,
    customer_id STRING,
    account_id STRING,
    transaction_type STRING,
    amount DOUBLE,
    currency STRING,
    timestamp STRING,
    merchant_category STRING,
    merchant_id STRING,
    location STRING,
    city STRING,
    state STRING,
    device_id STRING,
    ip_address STRING,
    channel STRING,
    payment_method STRING,
    status STRING,
    is_fraud INT,
    anomaly_type STRING,
    kyc_level STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 'obs://<raw_bucket>/transactions/';

-- Customers table
CREATE EXTERNAL TABLE IF NOT EXISTS customers (
    customer_id STRING,
    customer_name STRING,
    age INT,
    gender STRING,
    income_level STRING,
    account_create_date STRING,
    risk_level STRING,
    kyc_status STRING,
    customer_segment STRING,
    rfc STRING,
    curp STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 'obs://<raw_bucket>/customers/';

-- Accounts table
CREATE EXTERNAL TABLE IF NOT EXISTS accounts (
    account_id STRING,
    customer_id STRING,
    account_type STRING,
    balance DOUBLE,
    daily_limit DOUBLE,
    monthly_limit DOUBLE,
    account_status STRING,
    clabe STRING,
    spei_limit DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 'obs://<raw_bucket>/accounts/';

-- ============================================================
-- Result Tables (pointing to OBS results bucket)
-- ============================================================

-- Risk scores result table
CREATE EXTERNAL TABLE IF NOT EXISTS risk_scores (
    customer_id STRING,
    total_transactions INT,
    total_amount DOUBLE,
    avg_amount DOUBLE,
    max_amount DOUBLE,
    fraud_count INT,
    risk_score INT,
    risk_level STRING
)
STORED AS PARQUET
LOCATION 'obs://<results_bucket>/risk_scores/';

-- Customer clusters result table
CREATE EXTERNAL TABLE IF NOT EXISTS customer_clusters (
    customer_id STRING,
    total_transactions INT,
    total_amount DOUBLE,
    cluster INT
)
STORED AS PARQUET
LOCATION 'obs://<results_bucket>/customer_clusters/';

-- High risk customers result table
CREATE EXTERNAL TABLE IF NOT EXISTS high_risk_customers (
    customer_id STRING,
    total_transactions INT,
    total_amount DOUBLE,
    fraud_count INT,
    risk_score INT,
    risk_level STRING
)
STORED AS PARQUET
LOCATION 'obs://<results_bucket>/high_risk_customers/';
