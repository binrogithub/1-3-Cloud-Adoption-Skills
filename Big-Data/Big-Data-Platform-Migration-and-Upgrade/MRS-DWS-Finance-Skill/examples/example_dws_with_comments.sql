-- ============================================================
-- example_dws_with_comments.sql
-- DWS table creation with detailed comments explaining each
-- design decision. Based on actual deployment experience.
--
-- Key learnings:
-- - Use COLUMN orientation for analytical workloads
-- - Use MIDDLE compression as default (balance speed/size)
-- - Distribute fact tables on most common join key
-- - Replicate small dimension tables for broadcast join
-- - Add COMMENT ON for documentation
-- ============================================================

-- Create database
CREATE DATABASE financedb;
\c financedb

-- Create schemas (layered architecture)
CREATE SCHEMA IF NOT EXISTS ods;   -- Operational Data Store: raw 1:1 copy
CREATE SCHEMA IF NOT EXISTS dw;    -- Data Warehouse: cleaned, conformed
CREATE SCHEMA IF NOT EXISTS dm;    -- Data Mart: aggregated by subject area
CREATE SCHEMA IF NOT EXISTS rpt;   -- Report: final output for dashboards

-- ============================================================
-- ODS Layer: Raw data landing zone
-- These tables mirror the source CSV structure exactly.
-- Use HASH distribution on the primary key for even data spread.
-- ============================================================

CREATE TABLE IF NOT EXISTS ods.ods_transaction (
    transaction_id   VARCHAR(32),     -- Unique transaction identifier
    customer_id      VARCHAR(32),     -- FK to customer
    account_id       VARCHAR(32),     -- FK to account
    transaction_type VARCHAR(20),     -- TRANSFER, PAYMENT, DEPOSIT, WITHDRAWAL
    amount           NUMERIC(18,2),   -- Transaction amount in MXN
    currency         VARCHAR(5),      -- Always MXN for Mexico
    timestamp        TIMESTAMP,       -- Transaction timestamp
    merchant_category VARCHAR(30),    -- GROCERY, RESTAURANT, etc.
    merchant_id      VARCHAR(32),     -- Merchant identifier
    location         VARCHAR(100),    -- Lat/Lng coordinates
    city             VARCHAR(50),     -- Mexico city
    state            VARCHAR(50),     -- Mexico state
    device_id        VARCHAR(32),     -- Device identifier
    ip_address       VARCHAR(45),     -- IP address (Mexico ranges: 189.x.x.x)
    channel          VARCHAR(20),     -- MOBILE_APP, WEB_PORTAL, ATM, BRANCH, API
    payment_method   VARCHAR(20),     -- SPEI, OXXO_PAY, MERCADO_PAGO, etc.
    status           VARCHAR(15),     -- SUCCESS, FAILED, PENDING
    is_fraud         INTEGER,         -- 0 = normal, 1 = flagged
    anomaly_type     VARCHAR(30),     -- NORMAL, large_amount, structuring, etc.
    kyc_level        VARCHAR(10),     -- LEVEL_1, LEVEL_2, LEVEL_3
    load_time        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(transaction_id);

COMMENT ON TABLE ods.ods_transaction IS 'Transaction data - ODS layer (raw from OBS)';

-- Customer table (replicated - small dimension)
CREATE TABLE IF NOT EXISTS ods.ods_customer (
    customer_id        VARCHAR(32),
    customer_name      VARCHAR(100),
    age                INTEGER,
    gender             VARCHAR(10),
    income_level       VARCHAR(20),
    account_create_date DATE,
    risk_level         VARCHAR(15),    -- LOW, MEDIUM, HIGH, CRITICAL
    kyc_status         VARCHAR(20),    -- LEVEL_1, LEVEL_2, LEVEL_3
    customer_segment   VARCHAR(30),    -- BANCO_AZTECA, TRADITIONAL_BANK, etc.
    rfc                VARCHAR(13),    -- Mexico RFC (tax ID)
    curp               VARCHAR(18),    -- Mexico CURP (population registry)
    load_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_id);

COMMENT ON TABLE ods.ods_customer IS 'Customer data - ODS layer';

-- Account table
CREATE TABLE IF NOT EXISTS ods.ods_account (
    account_id      VARCHAR(32),
    customer_id     VARCHAR(32),
    account_type    VARCHAR(20),     -- SAVINGS, CHECKING, BUSINESS
    balance         NUMERIC(18,2),
    daily_limit     NUMERIC(18,2),   -- CNBV daily limit (50,000 individual)
    monthly_limit   NUMERIC(18,2),   -- CNBV monthly limit (500,000 individual)
    account_status  VARCHAR(15),
    clabe           VARCHAR(18),     -- Mexico CLABE (bank account number)
    spei_limit      NUMERIC(18,2),   -- SPEI transfer limit
    load_time       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(account_id);

COMMENT ON TABLE ods.ods_account IS 'Account data - ODS layer';

-- ============================================================
-- DW Layer: Cleaned and conformed data
-- Dimension tables use SCD Type 2 for historical tracking.
-- Small dimensions are REPLICATED for broadcast join optimization.
-- ============================================================

-- Date dimension (replicated - small, frequently joined)
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

COMMENT ON TABLE dw.dim_date IS 'Date dimension - replicated for broadcast join';

-- City dimension (replicated - small lookup)
CREATE TABLE IF NOT EXISTS dw.dim_city (
    city_key        SERIAL,
    city_name       VARCHAR(50),
    state_name      VARCHAR(50),
    country         VARCHAR(50) DEFAULT 'Mexico',
    risk_level      VARCHAR(15),       -- LOW, MEDIUM, HIGH
    is_border_city  BOOLEAN,           -- US-Mexico border flag
    is_high_risk    BOOLEAN            -- CNBV flagged
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

COMMENT ON TABLE dw.dim_city IS 'City dimension with risk levels - replicated';

-- Payment method dimension (replicated - small lookup)
CREATE TABLE IF NOT EXISTS dw.dim_payment_method (
    payment_method_key SERIAL,
    payment_method_name VARCHAR(30),
    payment_type     VARCHAR(20),       -- Bank Transfer, Card, Wallet, Cash
    risk_level       VARCHAR(15),
    spei_type        VARCHAR(20),       -- Instantaneo, Regular, Business
    max_amount_mxn   NUMERIC(18,2)      -- Regulatory limit
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

COMMENT ON TABLE dw.dim_payment_method IS 'Payment method dimension with SPEI limits';

-- Customer dimension (SCD Type 2 - tracks historical changes)
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
    effective_date  DATE,               -- SCD Type 2: when this version became active
    expiry_date     DATE DEFAULT '9999-12-31'  -- SCD Type 2: when this version expired
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_key);

COMMENT ON TABLE dw.dim_customer IS 'Customer dimension - SCD Type 2 for historical tracking';

-- Transaction fact table (HASH distributed for even data spread)
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

COMMENT ON TABLE dw.fact_transaction IS 'Transaction fact table - HASH distributed on surrogate key';

-- ============================================================
-- DM Layer: Aggregated data marts for specific analysis
-- ============================================================

-- Customer risk score mart
CREATE TABLE IF NOT EXISTS dm.dm_customer_risk (
    customer_key       INTEGER,
    customer_id        VARCHAR(32),
    total_transactions INTEGER,
    total_amount       NUMERIC(18,2),
    avg_amount         NUMERIC(18,2),
    max_amount         NUMERIC(18,2),
    fraud_count        INTEGER,
    unique_cities      INTEGER,
    risk_score         INTEGER,         -- Computed risk score (0-100+)
    risk_level         VARCHAR(15),     -- LOW, MEDIUM, HIGH, CRITICAL
    cluster_id         INTEGER,         -- K-Means cluster from MRS
    analysis_date      DATE
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY HASH(customer_key);

-- City risk mart
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

-- ============================================================
-- RPT Layer: Final report tables for dashboards
-- ============================================================

-- Risk overview report (replicated - single row per day)
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

-- Compliance report (replicated - small result set)
CREATE TABLE IF NOT EXISTS rpt.compliance_report (
    report_date        DATE,
    regulation         VARCHAR(30),     -- CNBV_CIRCULAR_15, LEY_FINTECH_AML_KYC
    check_type         VARCHAR(50),
    total_checked      INTEGER,
    violations         INTEGER,
    compliance_rate    NUMERIC(5,2),
    status             VARCHAR(15)      -- PASS, FAIL, WARNING
) WITH (ORIENTATION = COLUMN, COMPRESSION = MIDDLE)
DISTRIBUTE BY REPLICATION;

-- ============================================================
-- Indexes for common query patterns
-- ============================================================

CREATE INDEX idx_fact_txn_date ON dw.fact_transaction(date_key);
CREATE INDEX idx_fact_txn_customer ON dw.fact_transaction(customer_key);
CREATE INDEX idx_fact_txn_fraud ON dw.fact_transaction(is_fraud);
CREATE INDEX idx_dm_cust_risk_level ON dm.dm_customer_risk(risk_level);

\echo 'DWS tables created with comments and indexes'
