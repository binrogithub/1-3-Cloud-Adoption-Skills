-- ============================================================
-- dws_generate_reports.sql
-- Generate financial risk control reports from DWS
-- ============================================================

\c financedb

-- ============================================================
-- Report 1: Risk Overview Dashboard
-- ============================================================
SELECT '=== RISK OVERVIEW ===' AS report;

SELECT
    report_date,
    total_transactions,
    total_amount,
    fraud_transactions,
    fraud_rate || '%' AS fraud_rate,
    high_risk_customers,
    critical_risk_customers,
    cnbv_compliance_rate || '%' AS cnbv_compliance,
    aml_kyc_compliance_rate || '%' AS aml_kyc_compliance
FROM rpt.risk_overview
ORDER BY report_date DESC
LIMIT 1;

-- ============================================================
-- Report 2: Top 20 High-Risk Customers
-- ============================================================
SELECT '=== TOP 20 HIGH-RISK CUSTOMERS ===' AS report;

SELECT
    customer_id,
    customer_segment,
    risk_score,
    risk_level,
    total_transactions,
    total_amount,
    fraud_count
FROM rpt.customer_risk_report
ORDER BY risk_score DESC
LIMIT 20;

-- ============================================================
-- Report 3: City Risk Analysis
-- ============================================================
SELECT '=== CITY RISK ANALYSIS ===' AS report;

SELECT
    city_name,
    state_name,
    total_transactions,
    total_amount,
    fraud_transactions,
    fraud_rate || '%' AS fraud_rate,
    risk_level
FROM dm.dm_city_risk
ORDER BY fraud_transactions DESC
LIMIT 15;

-- ============================================================
-- Report 4: Daily Fraud Trend
-- ============================================================
SELECT '=== DAILY FRAUD TREND ===' AS report;

SELECT
    calendar_date,
    total_transactions,
    total_amount,
    fraud_transactions,
    fraud_rate || '%' AS fraud_rate,
    avg_amount
FROM dm.dm_daily_transaction
ORDER BY calendar_date DESC
LIMIT 30;

-- ============================================================
-- Report 5: Payment Method Risk
-- ============================================================
SELECT '=== PAYMENT METHOD RISK ===' AS report;

SELECT
    payment_method_name,
    total_transactions,
    total_amount,
    fraud_transactions,
    fraud_rate || '%' AS fraud_rate,
    avg_amount
FROM dm.dm_payment_method_risk
ORDER BY fraud_rate DESC;

-- ============================================================
-- Report 6: Risk Level Distribution
-- ============================================================
SELECT '=== RISK LEVEL DISTRIBUTION ===' AS report;

SELECT
    risk_level,
    COUNT(*) AS customer_count,
    SUM(total_transactions) AS total_transactions,
    SUM(total_amount) AS total_amount,
    SUM(fraud_count) AS total_fraud,
    ROUND(AVG(risk_score), 1) AS avg_risk_score
FROM dm.dm_customer_risk
GROUP BY risk_level
ORDER BY
    CASE risk_level
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;

-- ============================================================
-- Report 7: Anomaly Type Distribution
-- ============================================================
SELECT '=== ANOMALY TYPE DISTRIBUTION ===' AS report;

SELECT
    anomaly_type,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dw.fact_transaction WHERE is_fraud = 1), 2) || '%' AS pct_of_fraud
FROM dw.fact_transaction
WHERE is_fraud = 1
GROUP BY anomaly_type
ORDER BY transaction_count DESC;

-- ============================================================
-- Report 8: Channel Risk Analysis
-- ============================================================
SELECT '=== CHANNEL RISK ANALYSIS ===' AS report;

SELECT
    channel,
    COUNT(*) AS total_transactions,
    SUM(amount) AS total_amount,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
    ROUND(SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) || '%' AS fraud_rate,
    AVG(amount) AS avg_amount
FROM dw.fact_transaction
GROUP BY channel
ORDER BY fraud_transactions DESC;

-- ============================================================
-- Report 9: Cross-Border Transaction Analysis
-- ============================================================
SELECT '=== CROSS-BORDER ANALYSIS ===' AS report;

SELECT
    cy.city_name,
    cy.state_name,
    COUNT(*) AS total_transactions,
    SUM(f.amount) AS total_amount,
    SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
    ROUND(SUM(CASE WHEN f.is_fraud = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) || '%' AS fraud_rate
FROM dw.fact_transaction f
JOIN dw.dim_city cy ON f.city_key = cy.city_key
WHERE cy.is_border_city = TRUE
GROUP BY cy.city_name, cy.state_name
ORDER BY fraud_transactions DESC;

-- ============================================================
-- Report 10: KYC Level Compliance
-- ============================================================
SELECT '=== KYC LEVEL COMPLIANCE ===' AS report;

SELECT
    kyc_level,
    COUNT(*) AS total_transactions,
    SUM(CASE
        WHEN kyc_level = 'LEVEL_1' AND amount > 7500 THEN 1
        WHEN kyc_level = 'LEVEL_2' AND amount > 30000 THEN 1
        ELSE 0
    END) AS violations,
    ROUND(
        (COUNT(*) - SUM(CASE
            WHEN kyc_level = 'LEVEL_1' AND amount > 7500 THEN 1
            WHEN kyc_level = 'LEVEL_2' AND amount > 30000 THEN 1
            ELSE 0
        END)) * 100.0 / COUNT(*), 2
    ) || '%' AS compliance_rate
FROM dw.fact_transaction
WHERE kyc_level IN ('LEVEL_1', 'LEVEL_2')
GROUP BY kyc_level
ORDER BY kyc_level;

-- ============================================================
-- Report 11: Structuring Detection
-- ============================================================
SELECT '=== STRUCTURING DETECTION ===' AS report;

SELECT
    c.customer_id,
    c.customer_segment,
    COUNT(*) AS suspicious_transactions,
    SUM(f.amount) AS total_suspicious_amount,
    MIN(f.amount) AS min_amount,
    MAX(f.amount) AS max_amount,
    ROUND(AVG(f.amount), 2) AS avg_amount
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
WHERE f.amount BETWEEN 10000 AND 15000
  AND f.is_fraud = 1
GROUP BY c.customer_id, c.customer_segment
HAVING COUNT(*) >= 3
ORDER BY suspicious_transactions DESC
LIMIT 20;

-- ============================================================
-- Report 12: Large Transaction Summary
-- ============================================================
SELECT '=== LARGE TRANSACTION SUMMARY ===' AS report;

SELECT
    transaction_type,
    COUNT(*) AS large_transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount,
    MAX(amount) AS max_amount,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
FROM dw.fact_transaction
WHERE amount > 100000
GROUP BY transaction_type
ORDER BY large_transaction_count DESC;
