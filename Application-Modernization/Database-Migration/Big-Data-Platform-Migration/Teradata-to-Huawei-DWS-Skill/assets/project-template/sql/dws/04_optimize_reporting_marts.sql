DROP TABLE IF EXISTS reports.branch_kpi_mart;
DROP TABLE IF EXISTS reports.customer_profitability_mart;
DROP TABLE IF EXISTS reports.liquidity_gap_mart;
DROP TABLE IF EXISTS reports.loan_risk_snapshot_mart;
DROP TABLE IF EXISTS reports.suspicious_activity_mart;
DROP TABLE IF EXISTS reports.optimization_metadata;

CREATE TABLE reports.branch_kpi_mart
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION
AS
SELECT *
FROM reports.branch_kpi;

CREATE TABLE reports.customer_profitability_mart
WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH (customer_number)
AS
SELECT *
FROM reports.customer_profitability;

CREATE TABLE reports.liquidity_gap_mart
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION
AS
SELECT *
FROM reports.liquidity_gap;

CREATE TABLE reports.loan_risk_snapshot_mart
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION
AS
SELECT *
FROM reports.loan_risk_snapshot;

CREATE TABLE reports.suspicious_activity_mart
WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH (customer_number)
AS
SELECT *
FROM reports.suspicious_activity;

CREATE TABLE reports.optimization_metadata
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION
AS
SELECT 'branch_kpi_mart' AS object_name, count(*)::bigint AS row_count, current_timestamp AS refreshed_at
FROM reports.branch_kpi_mart
UNION ALL
SELECT 'customer_profitability_mart', count(*)::bigint, current_timestamp
FROM reports.customer_profitability_mart
UNION ALL
SELECT 'liquidity_gap_mart', count(*)::bigint, current_timestamp
FROM reports.liquidity_gap_mart
UNION ALL
SELECT 'loan_risk_snapshot_mart', count(*)::bigint, current_timestamp
FROM reports.loan_risk_snapshot_mart
UNION ALL
SELECT 'suspicious_activity_mart', count(*)::bigint, current_timestamp
FROM reports.suspicious_activity_mart;

ANALYZE finance_dw.dim_branch;
ANALYZE finance_dw.dim_product;
ANALYZE finance_dw.dim_customer;
ANALYZE finance_dw.dim_account;
ANALYZE finance_dw.dim_date;
ANALYZE finance_dw.fact_transaction;
ANALYZE finance_dw.fact_daily_balance;
ANALYZE finance_dw.fact_loan_snapshot;
ANALYZE reports.branch_kpi_mart;
ANALYZE reports.customer_profitability_mart;
ANALYZE reports.liquidity_gap_mart;
ANALYZE reports.loan_risk_snapshot_mart;
ANALYZE reports.suspicious_activity_mart;
ANALYZE reports.optimization_metadata;

