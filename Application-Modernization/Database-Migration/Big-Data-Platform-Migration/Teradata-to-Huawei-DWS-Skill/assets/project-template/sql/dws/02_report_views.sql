CREATE OR REPLACE VIEW reports.branch_kpi AS
SELECT b.province,
       b.city,
       b.branch_code,
       b.branch_name,
       d.year_num,
       d.month_num,
       count(*) AS transaction_count,
       round(sum(t.amount), 2) AS transaction_amount,
       count(DISTINCT t.customer_id) AS active_customers,
       round(avg(t.risk_score), 2) AS avg_risk_score,
       sum(CASE WHEN t.is_suspicious THEN 1 ELSE 0 END) AS suspicious_transaction_count
FROM finance_dw.fact_transaction t
JOIN finance_dw.dim_branch b ON b.branch_id = t.branch_id
JOIN finance_dw.dim_date d ON d.date_key = t.txn_date_key
GROUP BY b.province, b.city, b.branch_code, b.branch_name, d.year_num, d.month_num;

CREATE OR REPLACE VIEW reports.customer_profitability AS
SELECT c.customer_number,
       c.full_name,
       c.segment,
       c.risk_level,
       d.year_num,
       d.month_num,
       round(sum(CASE WHEN p.product_type IN ('LOAN', 'CARD') THEN t.amount * 0.0008 ELSE t.amount * 0.0002 END), 2) AS estimated_revenue,
       round(sum(CASE WHEN p.product_type = 'DEPOSIT' THEN t.amount * 0.0001 ELSE t.amount * 0.0003 END), 2) AS estimated_cost,
       round(sum(CASE WHEN p.product_type IN ('LOAN', 'CARD') THEN t.amount * 0.0008 ELSE t.amount * 0.0002 END)
             - sum(CASE WHEN p.product_type = 'DEPOSIT' THEN t.amount * 0.0001 ELSE t.amount * 0.0003 END), 2) AS contribution_margin,
       count(*) AS transaction_count
FROM finance_dw.fact_transaction t
JOIN finance_dw.dim_customer c ON c.customer_id = t.customer_id
JOIN finance_dw.dim_product p ON p.product_id = t.product_id
JOIN finance_dw.dim_date d ON d.date_key = t.txn_date_key
GROUP BY c.customer_number, c.full_name, c.segment, c.risk_level, d.year_num, d.month_num
HAVING count(*) >= 5;

CREATE OR REPLACE VIEW reports.loan_risk_snapshot AS
SELECT d.full_date AS snapshot_date,
       b.province,
       b.city,
       p.product_name,
       s.risk_stage,
       count(*) AS loan_count,
       round(sum(s.outstanding_principal), 2) AS outstanding_principal,
       round(avg(s.days_past_due), 2) AS avg_days_past_due,
       round(avg(s.pd_score), 6) AS avg_pd_score,
       round(sum(s.pd_score * s.lgd * s.ead), 2) AS expected_credit_loss
FROM finance_dw.fact_loan_snapshot s
JOIN finance_dw.dim_date d ON d.date_key = s.snapshot_date_key
JOIN finance_dw.dim_branch b ON b.branch_id = s.branch_id
JOIN finance_dw.dim_product p ON p.product_id = s.product_id
GROUP BY d.full_date, b.province, b.city, p.product_name, s.risk_stage;

CREATE OR REPLACE VIEW reports.suspicious_activity AS
SELECT c.customer_number,
       c.full_name,
       c.segment,
       c.risk_level,
       count(*) AS transaction_count,
       sum(CASE WHEN t.is_suspicious THEN 1 ELSE 0 END) AS suspicious_count,
       round(sum(t.amount), 2) AS total_amount,
       round(max(t.amount), 2) AS max_amount,
       round(avg(t.risk_score), 2) AS avg_risk_score,
       max(t.transaction_ts) AS last_transaction_ts
FROM finance_dw.fact_transaction t
JOIN finance_dw.dim_customer c ON c.customer_id = t.customer_id
WHERE t.is_suspicious OR t.risk_score >= 85 OR t.amount >= 15000
GROUP BY c.customer_number, c.full_name, c.segment, c.risk_level
HAVING sum(CASE WHEN t.is_suspicious THEN 1 ELSE 0 END) >= 1
    OR round(avg(t.risk_score), 2) >= 80;

CREATE OR REPLACE VIEW reports.liquidity_gap AS
SELECT d.full_date AS balance_date,
       p.product_type,
       p.product_name,
       fb.currency_code,
       count(DISTINCT fb.account_id) AS account_count,
       round(sum(CASE WHEN p.product_type = 'DEPOSIT' THEN fb.ending_balance ELSE 0 END), 2) AS deposit_balance,
       round(sum(CASE WHEN p.product_type IN ('LOAN', 'CARD') THEN fb.ending_balance ELSE 0 END), 2) AS credit_exposure,
       round(sum(CASE WHEN p.product_type = 'DEPOSIT' THEN fb.ending_balance ELSE -fb.ending_balance END), 2) AS liquidity_gap
FROM finance_dw.fact_daily_balance fb
JOIN finance_dw.dim_date d ON d.date_key = fb.balance_date_key
JOIN finance_dw.dim_product p ON p.product_id = fb.product_id
WHERE d.full_date IN (date '2025-04-30', date '2025-05-31', date '2025-06-30')
GROUP BY d.full_date, p.product_type, p.product_name, fb.currency_code;

