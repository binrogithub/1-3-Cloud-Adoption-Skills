-- ============================================================
-- check_structuring_detection.sql
-- Detect structuring (smurfing) patterns to avoid CNBV reporting
-- Structuring: Multiple transactions below 15,000 MXN threshold
-- ============================================================

\c financedb

-- ============================================================
-- Pattern 1: Classic Structuring
-- Same customer, multiple transactions in same day, each < 15,000 MXN
-- Total exceeds 15,000 MXN
-- ============================================================
SELECT '=== CLASSIC STRUCTURING DETECTION ===' AS pattern;

SELECT
    c.customer_id,
    c.customer_segment,
    d.calendar_date,
    COUNT(*) AS transaction_count,
    SUM(f.amount) AS total_amount,
    MIN(f.amount) AS min_amount,
    MAX(f.amount) AS max_amount,
    ROUND(AVG(f.amount), 2) AS avg_amount,
    CASE
        WHEN COUNT(*) >= 5 AND SUM(f.amount) > 50000 THEN 'CRITICAL'
        WHEN COUNT(*) >= 3 AND SUM(f.amount) > 15000 THEN 'HIGH'
        ELSE 'MEDIUM'
    END AS structuring_risk
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
JOIN dw.dim_date d ON f.date_key = d.date_key
WHERE f.amount BETWEEN 10000 AND 14999
GROUP BY c.customer_id, c.customer_segment, d.calendar_date
HAVING COUNT(*) >= 3 AND SUM(f.amount) > 15000
ORDER BY total_amount DESC
LIMIT 30;

-- ============================================================
-- Pattern 2: Time-Based Structuring
-- Same customer, transactions spread across hours in same day
-- Each below threshold, but concentrated in short time window
-- ============================================================
SELECT '=== TIME-BASED STRUCTURING DETECTION ===' AS pattern;

SELECT
    c.customer_id,
    c.customer_segment,
    d.calendar_date,
    COUNT(*) AS transaction_count,
    SUM(f.amount) AS total_amount,
    MAX(d.hour_of_day) - MIN(d.hour_of_day) AS hour_span,
    CASE
        WHEN MAX(d.hour_of_day) - MIN(d.hour_of_day) <= 2 AND COUNT(*) >= 4 THEN 'HIGH'
        WHEN MAX(d.hour_of_day) - MIN(d.hour_of_day) <= 4 AND COUNT(*) >= 3 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS structuring_risk
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
JOIN dw.dim_date d ON f.date_key = d.date_key
WHERE f.amount BETWEEN 10000 AND 14999
GROUP BY c.customer_id, c.customer_segment, d.calendar_date
HAVING COUNT(*) >= 3
  AND MAX(d.hour_of_day) - MIN(d.hour_of_day) <= 4
ORDER BY transaction_count DESC
LIMIT 20;

-- ============================================================
-- Pattern 3: Geographic Structuring
-- Same customer, transactions from different cities in same day
-- Each below threshold, using different locations
-- ============================================================
SELECT '=== GEOGRAPHIC STRUCTURING DETECTION ===' AS pattern;

SELECT
    c.customer_id,
    c.customer_segment,
    d.calendar_date,
    COUNT(*) AS transaction_count,
    COUNT(DISTINCT f.city_key) AS unique_cities,
    SUM(f.amount) AS total_amount,
    CASE
        WHEN COUNT(DISTINCT f.city_key) >= 3 THEN 'HIGH'
        WHEN COUNT(DISTINCT f.city_key) >= 2 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS structuring_risk
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
JOIN dw.dim_date d ON f.date_key = d.date_key
WHERE f.amount BETWEEN 10000 AND 14999
GROUP BY c.customer_id, c.customer_segment, d.calendar_date
HAVING COUNT(*) >= 2 AND COUNT(DISTINCT f.city_key) >= 2
ORDER BY unique_cities DESC, transaction_count DESC
LIMIT 20;

-- ============================================================
-- Pattern 4: Account-Based Structuring
-- Same customer, transactions from different accounts
-- Each below threshold, distributed across accounts
-- ============================================================
SELECT '=== ACCOUNT-BASED STRUCTURING DETECTION ===' AS pattern;

SELECT
    c.customer_id,
    c.customer_segment,
    d.calendar_date,
    COUNT(*) AS transaction_count,
    COUNT(DISTINCT f.account_key) AS unique_accounts,
    SUM(f.amount) AS total_amount,
    CASE
        WHEN COUNT(DISTINCT f.account_key) >= 3 THEN 'HIGH'
        WHEN COUNT(DISTINCT f.account_key) >= 2 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS structuring_risk
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
JOIN dw.dim_date d ON f.date_key = d.date_key
WHERE f.amount BETWEEN 10000 AND 14999
GROUP BY c.customer_id, c.customer_segment, d.calendar_date
HAVING COUNT(*) >= 2 AND COUNT(DISTINCT f.account_key) >= 2
ORDER BY unique_accounts DESC, transaction_count DESC
LIMIT 20;

-- ============================================================
-- Summary: All Structuring Patterns
-- ============================================================
SELECT '=== STRUCTURING DETECTION SUMMARY ===' AS summary;

SELECT
    'Classic' AS pattern_type,
    COUNT(*) AS instances,
    SUM(total_amount) AS total_structured_amount,
    COUNT(DISTINCT customer_id) AS customers_involved
FROM (
    SELECT
        c.customer_id,
        SUM(f.amount) AS total_amount
    FROM dw.fact_transaction f
    JOIN dw.dim_customer c ON f.customer_key = c.customer_key
    JOIN dw.dim_date d ON f.date_key = d.date_key
    WHERE f.amount BETWEEN 10000 AND 14999
    GROUP BY c.customer_id, d.calendar_date
    HAVING COUNT(*) >= 3 AND SUM(f.amount) > 15000
) classic

UNION ALL

SELECT
    'Time-Based' AS pattern_type,
    COUNT(*) AS instances,
    SUM(total_amount),
    COUNT(DISTINCT customer_id)
FROM (
    SELECT
        c.customer_id,
        SUM(f.amount) AS total_amount
    FROM dw.fact_transaction f
    JOIN dw.dim_customer c ON f.customer_key = c.customer_key
    JOIN dw.dim_date d ON f.date_key = d.date_key
    WHERE f.amount BETWEEN 10000 AND 14999
    GROUP BY c.customer_id, d.calendar_date
    HAVING COUNT(*) >= 3 AND MAX(d.hour_of_day) - MIN(d.hour_of_day) <= 4
) time_based

UNION ALL

SELECT
    'Geographic' AS pattern_type,
    COUNT(*) AS instances,
    SUM(total_amount),
    COUNT(DISTINCT customer_id)
FROM (
    SELECT
        c.customer_id,
        SUM(f.amount) AS total_amount
    FROM dw.fact_transaction f
    JOIN dw.dim_customer c ON f.customer_key = c.customer_key
    JOIN dw.dim_date d ON f.date_key = d.date_key
    WHERE f.amount BETWEEN 10000 AND 14999
    GROUP BY c.customer_id, d.calendar_date
    HAVING COUNT(*) >= 2 AND COUNT(DISTINCT f.city_key) >= 2
) geographic;
