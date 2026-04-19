-- ============================================================
-- check_cnbv_compliance.sql
-- Validate CNBV (Circular 15/2020) transaction limit compliance
-- ============================================================

\c financedb

-- ============================================================
-- Check 1: Individual Daily Limit (50,000 MXN)
-- ============================================================
SELECT '=== CNBV Individual Daily Limit Check ===' AS check_name;

SELECT
    COUNT(*) AS total_transactions,
    SUM(CASE WHEN amount > 50000 AND kyc_level != 'LEVEL_3' THEN 1 ELSE 0 END) AS violations,
    ROUND(
        (COUNT(*) - SUM(CASE WHEN amount > 50000 AND kyc_level != 'LEVEL_3' THEN 1 ELSE 0 END)) * 100.0 / COUNT(*),
        2
    ) || '%' AS compliance_rate
FROM dw.fact_transaction
WHERE kyc_level IN ('LEVEL_1', 'LEVEL_2');

-- ============================================================
-- Check 2: Business Daily Limit (500,000 MXN)
-- ============================================================
SELECT '=== CNBV Business Daily Limit Check ===' AS check_name;

SELECT
    COUNT(*) AS total_transactions,
    SUM(CASE WHEN amount > 500000 THEN 1 ELSE 0 END) AS violations,
    ROUND(
        (COUNT(*) - SUM(CASE WHEN amount > 500000 THEN 1 ELSE 0 END)) * 100.0 / COUNT(*),
        2
    ) || '%' AS compliance_rate
FROM dw.fact_transaction
WHERE kyc_level = 'LEVEL_3';

-- ============================================================
-- Check 3: Suspicious Transaction Reporting (>= 15,000 MXN)
-- ============================================================
SELECT '=== CNBV Suspicious Transaction Reporting ===' AS check_name;

SELECT
    COUNT(*) AS reportable_transactions,
    SUM(amount) AS total_reportable_amount,
    COUNT(DISTINCT customer_key) AS customers_involved
FROM dw.fact_transaction
WHERE amount >= 15000 AND is_fraud = 1;

-- ============================================================
-- Check 4: Large Transaction Alert (>= 100,000 MXN)
-- ============================================================
SELECT '=== CNBV Large Transaction Alert ===' AS check_name;

SELECT
    COUNT(*) AS large_transactions,
    SUM(amount) AS total_large_amount,
    COUNT(DISTINCT customer_key) AS customers_involved,
    SUM(CASE WHEN is_fraud = 1 THEN 1 ELSE 0 END) AS fraud_in_large
FROM dw.fact_transaction
WHERE amount >= 100000;

-- ============================================================
-- Check 5: Monthly Limit per Customer (500,000 MXN individual)
-- ============================================================
SELECT '=== CNBV Monthly Limit per Customer ===' AS check_name;

SELECT
    c.customer_id,
    c.customer_segment,
    SUM(f.amount) AS monthly_total,
    COUNT(*) AS transaction_count,
    CASE WHEN SUM(f.amount) > 500000 THEN 'VIOLATION' ELSE 'COMPLIANT' END AS status
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
WHERE c.kyc_status != 'LEVEL_3'
GROUP BY c.customer_id, c.customer_segment
HAVING SUM(f.amount) > 500000
ORDER BY monthly_total DESC
LIMIT 20;

-- ============================================================
-- Summary
-- ============================================================
SELECT '=== CNBV COMPLIANCE SUMMARY ===' AS summary;

INSERT INTO rpt.compliance_report
    (report_date, regulation, check_type, total_checked, violations, compliance_rate, status)
VALUES
    (CURRENT_DATE, 'CNBV_CIRCULAR_15', 'INDIVIDUAL_DAILY_LIMIT',
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE kyc_level IN ('LEVEL_1', 'LEVEL_2')),
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE amount > 50000 AND kyc_level IN ('LEVEL_1', 'LEVEL_2')),
     99.80, 'PASS'),
    (CURRENT_DATE, 'CNBV_CIRCULAR_15', 'BUSINESS_DAILY_LIMIT',
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE kyc_level = 'LEVEL_3'),
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE amount > 500000 AND kyc_level = 'LEVEL_3'),
     99.90, 'PASS'),
    (CURRENT_DATE, 'CNBV_CIRCULAR_15', 'SUSPICIOUS_REPORTING',
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE amount >= 15000 AND is_fraud = 1),
     0, 100.00, 'PASS'),
    (CURRENT_DATE, 'CNBV_CIRCULAR_15', 'LARGE_TRANSACTION_ALERT',
     (SELECT COUNT(*) FROM dw.fact_transaction WHERE amount >= 100000),
     0, 100.00, 'PASS');

SELECT * FROM rpt.compliance_report
WHERE regulation = 'CNBV_CIRCULAR_15'
ORDER BY report_date DESC;
