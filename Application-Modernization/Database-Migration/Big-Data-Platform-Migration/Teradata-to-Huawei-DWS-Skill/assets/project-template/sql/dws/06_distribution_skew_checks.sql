DROP TABLE IF EXISTS reports.distribution_skew_report;

CREATE TABLE reports.distribution_skew_report
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION
AS
WITH bucketed AS (
  SELECT mod(abs(hashint4(customer_id)), 32) AS bucket_id, count(*) AS bucket_rows
  FROM finance_dw.fact_transaction
  GROUP BY mod(abs(hashint4(customer_id)), 32)
),
summary AS (
  SELECT count(*)::bigint AS row_count,
         count(DISTINCT customer_id)::bigint AS distinct_key_count
  FROM finance_dw.fact_transaction
)
SELECT 'finance_dw.fact_transaction' AS table_name,
       'customer_id' AS distribution_key,
       s.row_count,
       s.distinct_key_count,
       max(b.bucket_rows)::bigint AS max_bucket_rows,
       min(b.bucket_rows)::bigint AS min_bucket_rows,
       round(avg(b.bucket_rows), 2) AS avg_bucket_rows,
       round(max(b.bucket_rows) / nullif(avg(b.bucket_rows), 0), 4) AS skew_ratio
FROM bucketed b
CROSS JOIN summary s
GROUP BY s.row_count, s.distinct_key_count;

INSERT INTO reports.distribution_skew_report
WITH bucketed AS (
  SELECT mod(abs(hashint4(customer_id)), 32) AS bucket_id, count(*) AS bucket_rows
  FROM finance_dw.fact_daily_balance
  GROUP BY mod(abs(hashint4(customer_id)), 32)
),
summary AS (
  SELECT count(*)::bigint AS row_count,
         count(DISTINCT customer_id)::bigint AS distinct_key_count
  FROM finance_dw.fact_daily_balance
)
SELECT 'finance_dw.fact_daily_balance',
       'customer_id',
       s.row_count,
       s.distinct_key_count,
       max(b.bucket_rows)::bigint,
       min(b.bucket_rows)::bigint,
       round(avg(b.bucket_rows), 2),
       round(max(b.bucket_rows) / nullif(avg(b.bucket_rows), 0), 4)
FROM bucketed b
CROSS JOIN summary s
GROUP BY s.row_count, s.distinct_key_count;

INSERT INTO reports.distribution_skew_report
WITH bucketed AS (
  SELECT mod(abs(hashint4(customer_id)), 32) AS bucket_id, count(*) AS bucket_rows
  FROM finance_dw.fact_loan_snapshot
  GROUP BY mod(abs(hashint4(customer_id)), 32)
),
summary AS (
  SELECT count(*)::bigint AS row_count,
         count(DISTINCT customer_id)::bigint AS distinct_key_count
  FROM finance_dw.fact_loan_snapshot
)
SELECT 'finance_dw.fact_loan_snapshot',
       'customer_id',
       s.row_count,
       s.distinct_key_count,
       max(b.bucket_rows)::bigint,
       min(b.bucket_rows)::bigint,
       round(avg(b.bucket_rows), 2),
       round(max(b.bucket_rows) / nullif(avg(b.bucket_rows), 0), 4)
FROM bucketed b
CROSS JOIN summary s
GROUP BY s.row_count, s.distinct_key_count;

ANALYZE reports.distribution_skew_report;
