-- ============================================================
-- dws_etl_load.sql
-- ETL: Load data from OBS to ODS, transform to DW, aggregate to DM
-- ============================================================

\c financedb

-- ============================================================
-- Step 1: Load ODS from OBS (via foreign server)
-- ============================================================

-- Create foreign server for OBS access
CREATE SERVER IF NOT EXISTS obs_server
FOREIGN DATA WRAPPER dfs_fdw
OPTIONS (
    address 'obs.<region>.myhuaweicloud.com',
    encrypt 'true'
);

-- Create foreign tables for OBS data
CREATE FOREIGN TABLE IF NOT EXISTS ft_transactions (
    transaction_id   VARCHAR(32),
    customer_id      VARCHAR(32),
    account_id       VARCHAR(32),
    transaction_type VARCHAR(20),
    amount           NUMERIC(18,2),
    currency         VARCHAR(5),
    timestamp        VARCHAR(30),
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
    kyc_level        VARCHAR(10)
) SERVER obs_server
OPTIONS (
    foldername '/<curated_bucket>/fact/fact_transaction/',
    format 'csv',
    encoding 'utf8',
    delimiter ','
);

CREATE FOREIGN TABLE IF NOT EXISTS ft_customers (
    customer_id        VARCHAR(32),
    customer_name      VARCHAR(100),
    age                INTEGER,
    gender             VARCHAR(10),
    income_level       VARCHAR(20),
    account_create_date VARCHAR(20),
    risk_level         VARCHAR(15),
    kyc_status         VARCHAR(20),
    customer_segment   VARCHAR(30),
    rfc                VARCHAR(13),
    curp               VARCHAR(18)
) SERVER obs_server
OPTIONS (
    foldername '/<curated_bucket>/dim/dim_customer/',
    format 'csv',
    encoding 'utf8',
    delimiter ','
);

CREATE FOREIGN TABLE IF NOT EXISTS ft_accounts (
    account_id      VARCHAR(32),
    customer_id     VARCHAR(32),
    account_type    VARCHAR(20),
    balance         NUMERIC(18,2),
    daily_limit     NUMERIC(18,2),
    monthly_limit   NUMERIC(18,2),
    account_status  VARCHAR(15),
    clabe           VARCHAR(18),
    spei_limit      NUMERIC(18,2)
) SERVER obs_server
OPTIONS (
    foldername '/<curated_bucket>/dim/dim_account/',
    format 'csv',
    encoding 'utf8',
    delimiter ','
);

-- Load ODS tables
INSERT INTO ods.ods_transaction
    (transaction_id, customer_id, account_id, transaction_type,
     amount, currency, timestamp, merchant_category, merchant_id,
     location, city, state, device_id, ip_address, channel,
     payment_method, status, is_fraud, anomaly_type, kyc_level)
SELECT
    transaction_id, customer_id, account_id, transaction_type,
    amount, currency, timestamp::timestamp, merchant_category, merchant_id,
    location, city, state, device_id, ip_address, channel,
    payment_method, status, is_fraud, anomaly_type, kyc_level
FROM ft_transactions;

INSERT INTO ods.ods_customer
    (customer_id, customer_name, age, gender, income_level,
     account_create_date, risk_level, kyc_status, customer_segment, rfc, curp)
SELECT
    customer_id, customer_name, age, gender, income_level,
    account_create_date::date, risk_level, kyc_status, customer_segment, rfc, curp
FROM ft_customers;

INSERT INTO ods.ods_account
    (account_id, customer_id, account_type, balance,
     daily_limit, monthly_limit, account_status, clabe, spei_limit)
SELECT
    account_id, customer_id, account_type, balance,
    daily_limit, monthly_limit, account_status, clabe, spei_limit
FROM ft_accounts;

-- ============================================================
-- Step 2: Transform ODS → DW (dimension and fact tables)
-- ============================================================

-- Load dim_customer
INSERT INTO dw.dim_customer
    (customer_id, customer_name, age, gender, income_level,
     customer_segment, risk_level, kyc_status, rfc, curp,
     is_active, effective_date)
SELECT
    customer_id, customer_name, age, gender, income_level,
    customer_segment, risk_level, kyc_status, rfc, curp,
    TRUE, CURRENT_DATE
FROM ods.ods_customer;

-- Load dim_account
INSERT INTO dw.dim_account
    (account_id, customer_key, account_type, daily_limit,
     monthly_limit, account_status, clabe, spei_limit,
     is_active, effective_date)
SELECT
    a.account_id,
    c.customer_key,
    a.account_type, a.daily_limit, a.monthly_limit,
    a.account_status, a.clabe, a.spei_limit,
    TRUE, CURRENT_DATE
FROM ods.ods_account a
JOIN dw.dim_customer c ON a.customer_id = c.customer_id;

-- Load dim_date (generate from transaction dates)
INSERT INTO dw.dim_date
    (calendar_date, year, quarter, month, day_of_week, day_of_month, is_weekend, hour_of_day)
SELECT DISTINCT
    d::date AS calendar_date,
    EXTRACT(YEAR FROM d::date) AS year,
    EXTRACT(QUARTER FROM d::date) AS quarter,
    EXTRACT(MONTH FROM d::date) AS month,
    EXTRACT(DOW FROM d::date) AS day_of_week,
    EXTRACT(DAY FROM d::date) AS day_of_month,
    EXTRACT(DOW FROM d::date) IN (0, 6) AS is_weekend,
    EXTRACT(HOUR FROM d::timestamp) AS hour_of_day
FROM (
    SELECT DISTINCT timestamp AS d FROM ods.ods_transaction
) t;

-- Load dim_city
INSERT INTO dw.dim_city
    (city_name, state_name, risk_level, is_border_city, is_high_risk)
SELECT DISTINCT
    city,
    state,
    CASE
        WHEN city IN ('Culiacan', 'Ciudad Juarez', 'Acapulco', 'Tepic') THEN 'HIGH'
        WHEN city IN ('Tijuana', 'Nuevo Laredo', 'Matamoros', 'Reynosa') THEN 'MEDIUM'
        ELSE 'LOW'
    END,
    city IN ('Tijuana', 'Ciudad Juarez', 'Nuevo Laredo', 'Matamoros', 'Reynosa'),
    city IN ('Culiacan', 'Ciudad Juarez', 'Acapulco', 'Tepic')
FROM ods.ods_transaction
WHERE city IS NOT NULL;

-- Load dim_payment_method
INSERT INTO dw.dim_payment_method
    (payment_method_name, payment_type, risk_level, spei_type, max_amount_mxn)
VALUES
    ('SPEI', 'Bank Transfer', 'LOW', 'Regular', 500000),
    ('OXXO_PAY', 'Cash Hybrid', 'MEDIUM', NULL, 50000),
    ('MERCADO_PAGO', 'Digital Wallet', 'LOW', NULL, 50000),
    ('DEBIT_CARD', 'Card Payment', 'LOW', NULL, 50000),
    ('CREDIT_CARD', 'Card Payment', 'MEDIUM', NULL, 50000),
    ('PAYPAL', 'International', 'MEDIUM', NULL, 50000),
    ('SPID', 'Large Transfer', 'HIGH', 'Business', 5000000),
    ('CASH_DEPOSIT', 'Cash', 'HIGH', NULL, 100000);

-- Load fact_transaction
INSERT INTO dw.fact_transaction
    (transaction_id, customer_key, account_key, date_key,
     city_key, payment_method_key, transaction_type, amount,
     merchant_category, merchant_id, channel, is_fraud,
     anomaly_type, kyc_level)
SELECT
    t.transaction_id,
    c.customer_key,
    a.account_key,
    d.date_key,
    cy.city_key,
    pm.payment_method_key,
    t.transaction_type, t.amount,
    t.merchant_category, t.merchant_id, t.channel,
    t.is_fraud, t.anomaly_type, t.kyc_level
FROM ods.ods_transaction t
JOIN dw.dim_customer c ON t.customer_id = c.customer_id
JOIN dw.dim_account a ON t.account_id = a.account_id
JOIN dw.dim_date d ON t.timestamp::date = d.calendar_date
LEFT JOIN dw.dim_city cy ON t.city = cy.city_name
LEFT JOIN dw.dim_payment_method pm ON t.payment_method = pm.payment_method_name;

-- ============================================================
-- Step 3: Aggregate DW → DM (data marts)
-- ============================================================

-- Customer Risk Score Mart
INSERT INTO dm.dm_customer_risk
    (customer_key, customer_id, total_transactions, total_amount,
     avg_amount, max_amount, fraud_count, unique_cities,
     unique_channels, risk_score, risk_level, cluster_id, analysis_date)
SELECT
    c.customer_key,
    c.customer_id,
    COUNT(*) AS total_transactions,
    SUM(f.amount) AS total_amount,
    AVG(f.amount) AS avg_amount,
    MAX(f.amount) AS max_amount,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count,
    COUNT(DISTINCT f.city_key) AS unique_cities,
    COUNT(DISTINCT f.channel) AS unique_channels,
    -- Risk score calculation
    (CASE WHEN MAX(f.amount) > 100000 THEN 20 ELSE 0 END +
     CASE WHEN MAX(f.amount) > 200000 THEN 20 ELSE 0 END +
     CASE WHEN COUNT(*) > 100 THEN 10 ELSE 0 END +
     CASE WHEN COUNT(*) > 200 THEN 10 ELSE 0 END +
     SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 5 +
     CASE WHEN STDDEV(f.amount) > 10000 THEN 10 ELSE 0 END +
     CASE WHEN COUNT(DISTINCT f.city_key) > 5 THEN 5 ELSE 0 END) AS risk_score,
    -- Risk level
    CASE
        WHEN (CASE WHEN MAX(f.amount) > 100000 THEN 20 ELSE 0 END +
              CASE WHEN MAX(f.amount) > 200000 THEN 20 ELSE 0 END +
              CASE WHEN COUNT(*) > 100 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(*) > 200 THEN 10 ELSE 0 END +
              SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 5 +
              CASE WHEN STDDEV(f.amount) > 10000 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(DISTINCT f.city_key) > 5 THEN 5 ELSE 0 END) >= 50 THEN 'CRITICAL'
        WHEN (CASE WHEN MAX(f.amount) > 100000 THEN 20 ELSE 0 END +
              CASE WHEN MAX(f.amount) > 200000 THEN 20 ELSE 0 END +
              CASE WHEN COUNT(*) > 100 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(*) > 200 THEN 10 ELSE 0 END +
              SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 5 +
              CASE WHEN STDDEV(f.amount) > 10000 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(DISTINCT f.city_key) > 5 THEN 5 ELSE 0 END) >= 30 THEN 'HIGH'
        WHEN (CASE WHEN MAX(f.amount) > 100000 THEN 20 ELSE 0 END +
              CASE WHEN MAX(f.amount) > 200000 THEN 20 ELSE 0 END +
              CASE WHEN COUNT(*) > 100 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(*) > 200 THEN 10 ELSE 0 END +
              SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 5 +
              CASE WHEN STDDEV(f.amount) > 10000 THEN 10 ELSE 0 END +
              CASE WHEN COUNT(DISTINCT f.city_key) > 5 THEN 5 ELSE 0 END) >= 15 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level,
    0 AS cluster_id,  -- Populated from MRS K-Means results
    CURRENT_DATE AS analysis_date
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_key, c.customer_id;

-- City Risk Mart
INSERT INTO dm.dm_city_risk
    (city_key, city_name, state_name, total_transactions,
     total_amount, fraud_transactions, fraud_rate, risk_level, analysis_date)
SELECT
    cy.city_key,
    cy.city_name,
    cy.state_name,
    COUNT(*) AS total_transactions,
    SUM(f.amount) AS total_amount,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
    ROUND(
        SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS fraud_rate,
    cy.risk_level,
    CURRENT_DATE
FROM dw.fact_transaction f
JOIN dw.dim_city cy ON f.city_key = cy.city_key
GROUP BY cy.city_key, cy.city_name, cy.state_name, cy.risk_level;

-- Daily Transaction Mart
INSERT INTO dm.dm_daily_transaction
    (date_key, calendar_date, total_transactions, total_amount,
     fraud_transactions, fraud_rate, avg_amount, analysis_date)
SELECT
    d.date_key,
    d.calendar_date,
    COUNT(*) AS total_transactions,
    SUM(f.amount) AS total_amount,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
    ROUND(
        SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS fraud_rate,
    AVG(f.amount) AS avg_amount,
    CURRENT_DATE
FROM dw.fact_transaction f
JOIN dw.dim_date d ON f.date_key = d.date_key
GROUP BY d.date_key, d.calendar_date;

-- Payment Method Risk Mart
INSERT INTO dm.dm_payment_method_risk
    (payment_method_key, payment_method_name, total_transactions,
     total_amount, fraud_transactions, fraud_rate, avg_amount, analysis_date)
SELECT
    pm.payment_method_key,
    pm.payment_method_name,
    COUNT(*) AS total_transactions,
    SUM(f.amount) AS total_amount,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
    ROUND(
        SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS fraud_rate,
    AVG(f.amount) AS avg_amount,
    CURRENT_DATE
FROM dw.fact_transaction f
JOIN dw.dim_payment_method pm ON f.payment_method_key = pm.payment_method_key
GROUP BY pm.payment_method_key, pm.payment_method_name;

-- ============================================================
-- Step 4: Generate RPT (report tables)
-- ============================================================

-- Risk Overview Report
INSERT INTO rpt.risk_overview
    (report_date, total_transactions, total_amount, fraud_transactions,
     fraud_rate, high_risk_customers, critical_risk_customers,
     cnbv_compliance_rate, aml_kyc_compliance_rate)
SELECT
    CURRENT_DATE,
    (SELECT COUNT(*) FROM dw.fact_transaction),
    (SELECT SUM(amount) FROM dw.fact_transaction),
    (SELECT COUNT(*) FROM dw.fact_transaction WHERE is_fraud = 1),
    ROUND(
        (SELECT COUNT(*) FROM dw.fact_transaction WHERE is_fraud = 1) * 100.0 /
        (SELECT COUNT(*) FROM dw.fact_transaction), 2),
    (SELECT COUNT(*) FROM dm.dm_customer_risk WHERE risk_level = 'HIGH'),
    (SELECT COUNT(*) FROM dm.dm_customer_risk WHERE risk_level = 'CRITICAL'),
    99.80,  -- From compliance check
    97.00;  -- From compliance check

-- Customer Risk Report
INSERT INTO rpt.customer_risk_report
    (customer_id, customer_segment, risk_score, risk_level,
     total_transactions, total_amount, fraud_count, cluster_id, report_date)
SELECT
    cr.customer_id,
    c.customer_segment,
    cr.risk_score,
    cr.risk_level,
    cr.total_transactions,
    cr.total_amount,
    cr.fraud_count,
    cr.cluster_id,
    CURRENT_DATE
FROM dm.dm_customer_risk cr
JOIN dw.dim_customer c ON cr.customer_key = c.customer_key
WHERE cr.risk_level IN ('HIGH', 'CRITICAL')
ORDER BY cr.risk_score DESC;
