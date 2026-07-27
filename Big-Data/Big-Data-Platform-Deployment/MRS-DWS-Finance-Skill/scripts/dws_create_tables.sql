-- ============================================================
-- dws_create_tables.sql
-- Create DWS data warehouse schema for financial risk control
-- Layered architecture: ODS → DW → DM → RPT
-- ============================================================

-- ============================================================
-- Database and Schemas
-- ============================================================
CREATE DATABASE financedb;
\c financedb

CREATE SCHEMA IF NOT EXISTS ods;      -- Operational Data Store
CREATE SCHEMA IF NOT EXISTS dw;       -- Data Warehouse (cleaned)
CREATE SCHEMA IF NOT EXISTS dm;       -- Data Mart (aggregated)
CREATE SCHEMA IF NOT EXISTS rpt;      -- Report (final output)

-- ============================================================
-- ODS Layer: Raw data (1:1 with source)
-- ============================================================

CREATE TABLE IF NOT EXISTS ods.ods_transaction (
    transaction_id   VARCHAR(32),
    customer_id      VARCHAR(32),
    account_id       VARCHAR(32),
    transaction_type VARCHAR(20),
    amount           NUMERIC(18,2),
    currency         VARCHAR(5),
    timestamp        TIMESTAMP,
    merchant_category VARCHAR(30),
    merchant_id      VARCHAR(32),
    location         VARCHAR(100),
    city             VARCHAR(50),
    state            VARCHAR(50),
    device_id        VARCHAR(32),
    ip_address       VARCHAR(45),
    channel          VARCHAR(20),
    payment_method   VARCHAR(20),
    status           VARCHAR(15),
    is_fraud         INTEGER,
    anomaly_type     VARCHAR(30),
    kyc_level        VARCHAR(10),
    load_time        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(transaction_id);

CREATE TABLE IF NOT EXISTS ods.ods_customer (
    customer_id        VARCHAR(32),
    customer_name      VARCHAR(100),
    age                INTEGER,
    gender             VARCHAR(10),
    income_level       VARCHAR(20),
    account_create_date DATE,
    risk_level         VARCHAR(15),
    kyc_status         VARCHAR(20),
    customer_segment   VARCHAR(30),
    rfc                VARCHAR(13),
    curp               VARCHAR(18),
    load_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_id);

CREATE TABLE IF NOT EXISTS ods.ods_account (
    account_id      VARCHAR(32),
    customer_id     VARCHAR(32),
    account_type    VARCHAR(20),
    balance         NUMERIC(18,2),
    daily_limit     NUMERIC(18,2),
    monthly_limit   NUMERIC(18,2),
    account_status  VARCHAR(15),
    clabe           VARCHAR(18),
    spei_limit      NUMERIC(18,2),
    load_time       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(account_id);

-- ============================================================
-- DW Layer: Cleaned and conformed data
-- ============================================================

-- Dimension: Customer
CREATE TABLE IF NOT EXISTS dw.dim_customer (
    customer_key    SERIAL,
    customer_id     VARCHAR(32),
    customer_name   VARCHAR(100),
    age             INTEGER,
    gender          VARCHAR(10),
    income_level    VARCHAR(20),
    customer_segment VARCHAR(30),
    risk_level      VARCHAR(15),
    kyc_status      VARCHAR(20),
    rfc             VARCHAR(13),
    curp            VARCHAR(18),
    is_active       BOOLEAN DEFAULT TRUE,
    effective_date  DATE,
    expiry_date     DATE DEFAULT '9999-12-31'
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_key);

-- Dimension: Account
CREATE TABLE IF NOT EXISTS dw.dim_account (
    account_key     SERIAL,
    account_id      VARCHAR(32),
    customer_key    INTEGER,
    account_type    VARCHAR(20),
    daily_limit     NUMERIC(18,2),
    monthly_limit   NUMERIC(18,2),
    account_status  VARCHAR(15),
    clabe           VARCHAR(18),
    spei_limit      NUMERIC(18,2),
    is_active       BOOLEAN DEFAULT TRUE,
    effective_date  DATE,
    expiry_date     DATE DEFAULT '9999-12-31'
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(account_key);

-- Dimension: Date
CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key        SERIAL,
    calendar_date   DATE,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    day_of_week     INTEGER,
    day_of_month    INTEGER,
    is_weekend      BOOLEAN,
    is_holiday      BOOLEAN DEFAULT FALSE,
    hour_of_day     INTEGER
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

-- Dimension: City
CREATE TABLE IF NOT EXISTS dw.dim_city (
    city_key        SERIAL,
    city_name       VARCHAR(50),
    state_name      VARCHAR(50),
    country         VARCHAR(50) DEFAULT 'Mexico',
    risk_level      VARCHAR(15),
    is_border_city  BOOLEAN,
    is_high_risk    BOOLEAN
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

-- Dimension: Payment Method
CREATE TABLE IF NOT EXISTS dw.dim_payment_method (
    payment_method_key SERIAL,
    payment_method_name VARCHAR(30),
    payment_type     VARCHAR(20),
    risk_level       VARCHAR(15),
    spei_type        VARCHAR(20),
    max_amount_mxn   NUMERIC(18,2)
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

-- Fact: Transaction
CREATE TABLE IF NOT EXISTS dw.fact_transaction (
    transaction_key    SERIAL,
    transaction_id     VARCHAR(32),
    customer_key       INTEGER,
    account_key        INTEGER,
    date_key           INTEGER,
    city_key           INTEGER,
    payment_method_key INTEGER,
    transaction_type   VARCHAR(20),
    amount             NUMERIC(18,2),
    merchant_category  VARCHAR(30),
    merchant_id        VARCHAR(32),
    channel            VARCHAR(20),
    is_fraud           INTEGER,
    anomaly_type       VARCHAR(30),
    kyc_level          VARCHAR(10)
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(transaction_key);

-- ============================================================
-- DM Layer: Aggregated data marts
-- ============================================================

-- Customer Risk Score Mart
CREATE TABLE IF NOT EXISTS dm.dm_customer_risk (
    customer_key       INTEGER,
    customer_id        VARCHAR(32),
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    avg_amount         NUMERIC(18,2),
    max_amount         NUMERIC(18,2),
    fraud_count        INTEGER,
    unique_cities      INTEGER,
    unique_channels    INTEGER,
    risk_score         INTEGER,
    risk_level         VARCHAR(15),
    cluster_id         INTEGER,
    analysis_date      DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_key);

-- City Risk Mart
CREATE TABLE IF NOT EXISTS dm.dm_city_risk (
    city_key           INTEGER,
    city_name          VARCHAR(50),
    state_name         VARCHAR(50),
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    fraud_transactions INTEGER,
    fraud_rate         NUMERIC(5,2),
    risk_level         VARCHAR(15),
    analysis_date      DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(city_key);

-- Daily Transaction Mart
CREATE TABLE IF NOT EXISTS dm.dm_daily_transaction (
    date_key           INTEGER,
    calendar_date      DATE,
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    fraud_transactions INTEGER,
    fraud_rate         NUMERIC(5,2),
    avg_amount         NUMERIC(18,2),
    analysis_date      DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(date_key);

-- Payment Method Risk Mart
CREATE TABLE IF NOT EXISTS dm.dm_payment_method_risk (
    payment_method_key INTEGER,
    payment_method_name VARCHAR(30),
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    fraud_transactions INTEGER,
    fraud_rate         NUMERIC(5,2),
    avg_amount         NUMERIC(18,2),
    analysis_date      DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(payment_method_key);

-- ============================================================
-- RPT Layer: Final report tables
-- ============================================================

-- Risk Overview Report
CREATE TABLE IF NOT EXISTS rpt.risk_overview (
    report_date        DATE,
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    fraud_transactions INTEGER,
    fraud_rate         NUMERIC(5,2),
    high_risk_customers INTEGER,
    critical_risk_customers INTEGER,
    cnbv_compliance_rate NUMERIC(5,2),
    aml_kyc_compliance_rate NUMERIC(5,2)
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

-- Customer Risk Report
CREATE TABLE IF NOT EXISTS rpt.customer_risk_report (
    customer_id        VARCHAR(32),
    customer_segment   VARCHAR(30),
    risk_score         INTEGER,
    risk_level         VARCHAR(15),
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    fraud_count        INTEGER,
    cluster_id         INTEGER,
    report_date        DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_id);

-- Compliance Report
CREATE TABLE IF NOT EXISTS rpt.compliance_report (
    report_date        DATE,
    regulation         VARCHAR(30),
    check_type         VARCHAR(50),
    total_checked      INTEGER,
    violations         INTEGER,
    compliance_rate    NUMERIC(5,2),
    status             VARCHAR(15)
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;
