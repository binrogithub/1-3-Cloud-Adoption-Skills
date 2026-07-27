SET search_path TO finance_dw, public;
SET datestyle = 'ISO, YMD';

INSERT INTO dim_branch (branch_id, branch_code, branch_name, province, city)
SELECT id,
       'BR' || lpad(id::text, 4, '0'),
       city || '分行',
       province,
       city
FROM (
  VALUES
    (1, '广东', '深圳'), (2, '广东', '广州'), (3, '上海', '上海'),
    (4, '北京', '北京'), (5, '浙江', '杭州'), (6, '江苏', '南京'),
    (7, '四川', '成都'), (8, '湖北', '武汉'), (9, '福建', '厦门'),
    (10, '重庆', '重庆')
) AS b(id, province, city);

INSERT INTO dim_product (product_id, product_code, product_name, product_type, annual_rate)
VALUES
  (1, 'DEP-CASA', '活期存款', 'DEPOSIT', 0.002000),
  (2, 'DEP-TD-1Y', '一年期定期存款', 'DEPOSIT', 0.018000),
  (3, 'LOAN-MORT', '个人住房贷款', 'LOAN', 0.041000),
  (4, 'LOAN-SME', '小微经营贷款', 'LOAN', 0.055000),
  (5, 'WM-FUND', '稳健理财产品', 'WEALTH', 0.032000),
  (6, 'CARD-CRD', '信用卡账户', 'CARD', 0.000000);

INSERT INTO dim_date (date_key, full_date, year_num, quarter_num, month_num, day_num, month_name)
SELECT to_char(d, 'YYYYMMDD')::integer,
       d::date,
       extract(year FROM d)::integer,
       extract(quarter FROM d)::integer,
       extract(month FROM d)::integer,
       extract(day FROM d)::integer,
       to_char(d, 'Mon')
FROM generate_series(date '2025-01-01', date '2025-06-30', interval '1 day') AS g(d);

INSERT INTO dim_customer (customer_id, customer_number, full_name, segment, risk_level, region, open_date, kyc_status)
SELECT id,
       'C' || lpad(id::text, 8, '0'),
       '客户' || lpad(id::text, 6, '0'),
       CASE
         WHEN id % 20 = 0 THEN 'PRIVATE_BANKING'
         WHEN id % 5 = 0 THEN 'SME_OWNER'
         WHEN id % 3 = 0 THEN 'SALARY'
         ELSE 'MASS'
       END,
       CASE
         WHEN id % 37 = 0 THEN 'HIGH'
         WHEN id % 11 = 0 THEN 'MEDIUM'
         ELSE 'LOW'
       END,
       CASE id % 8
         WHEN 0 THEN '珠三角'
         WHEN 1 THEN '长三角'
         WHEN 2 THEN '京津冀'
         WHEN 3 THEN '成渝'
         WHEN 4 THEN '海西'
         WHEN 5 THEN '华中'
         WHEN 6 THEN '西北'
         ELSE '东北'
       END,
       date '2020-01-01' + (id % 1600),
       CASE WHEN id % 97 = 0 THEN 'REVIEW' ELSE 'PASS' END
FROM generate_series(1, 2000) AS g(id);

INSERT INTO dim_account (account_id, customer_id, account_number, account_type, branch_id, currency_code, open_date, status)
SELECT account_id,
       customer_id,
       'A' || lpad(account_id::text, 10, '0'),
       CASE product_seed
         WHEN 1 THEN 'SAVING'
         WHEN 2 THEN 'TIME_DEPOSIT'
         WHEN 3 THEN 'MORTGAGE'
         WHEN 4 THEN 'SME_LOAN'
         WHEN 5 THEN 'WEALTH'
         ELSE 'CREDIT_CARD'
       END,
       ((customer_id + product_seed) % 10) + 1,
       CASE WHEN customer_id % 19 = 0 THEN 'USD' WHEN customer_id % 23 = 0 THEN 'HKD' ELSE 'CNY' END,
       date '2020-01-01' + (customer_id % 1600),
       CASE WHEN customer_id % 89 = 0 THEN 'FROZEN' ELSE 'ACTIVE' END
FROM (
  SELECT c.customer_id,
         product_seed,
         row_number() OVER (ORDER BY c.customer_id, product_seed)::integer AS account_id
  FROM dim_customer c
  CROSS JOIN LATERAL (
    SELECT unnest(ARRAY[1, 2, CASE WHEN c.customer_id % 4 = 0 THEN 3 ELSE 5 END, 6]) AS product_seed
  ) p
) s;

INSERT INTO fact_transaction (
  transaction_id, account_id, customer_id, branch_id, product_id, transaction_ts, txn_date_key,
  txn_type, channel, amount, balance_after, counterparty_region, is_suspicious, risk_score
)
SELECT txn_id,
       a.account_id,
       a.customer_id,
       a.branch_id,
       CASE a.account_type
         WHEN 'SAVING' THEN 1
         WHEN 'TIME_DEPOSIT' THEN 2
         WHEN 'MORTGAGE' THEN 3
         WHEN 'SME_LOAN' THEN 4
         WHEN 'WEALTH' THEN 5
         ELSE 6
       END,
       d.full_date + (((txn_id * 37) % 86400) || ' seconds')::interval,
       d.date_key,
       CASE txn_id % 7
         WHEN 0 THEN 'TRANSFER_OUT'
         WHEN 1 THEN 'TRANSFER_IN'
         WHEN 2 THEN 'PAYMENT'
         WHEN 3 THEN 'WITHDRAW'
         WHEN 4 THEN 'DEPOSIT'
         WHEN 5 THEN 'PURCHASE'
         ELSE 'INTEREST'
       END,
       CASE txn_id % 5
         WHEN 0 THEN 'MOBILE'
         WHEN 1 THEN 'ATM'
         WHEN 2 THEN 'BRANCH'
         WHEN 3 THEN 'ONLINE'
         ELSE 'POS'
       END,
       round((50 + ((txn_id * 7919) % 200000) / 10.0)::numeric, 2),
       round((1000 + ((a.account_id * 3571 + txn_id * 17) % 900000) / 10.0)::numeric, 2),
       CASE txn_id % 8
         WHEN 0 THEN '珠三角'
         WHEN 1 THEN '长三角'
         WHEN 2 THEN '京津冀'
         WHEN 3 THEN '成渝'
         WHEN 4 THEN '海西'
         WHEN 5 THEN '华中'
         WHEN 6 THEN '西北'
         ELSE '境外'
       END,
       ((txn_id % 997 = 0) OR (a.customer_id % 37 = 0 AND txn_id % 23 = 0)),
       round((least(99, 5 + (txn_id % 80) + CASE WHEN a.customer_id % 37 = 0 THEN 15 ELSE 0 END))::numeric, 2)
FROM generate_series(1, 120000) AS g(txn_id)
JOIN dim_account a ON a.account_id = ((txn_id % 8000) + 1)
JOIN dim_date d ON d.full_date = date '2025-01-01' + ((txn_id % 181) * interval '1 day');

INSERT INTO fact_daily_balance (
  balance_date_key, account_id, customer_id, branch_id, product_id, currency_code,
  ending_balance, avg_balance, interest_accrued
)
SELECT d.date_key,
       a.account_id,
       a.customer_id,
       a.branch_id,
       CASE a.account_type
         WHEN 'SAVING' THEN 1
         WHEN 'TIME_DEPOSIT' THEN 2
         WHEN 'MORTGAGE' THEN 3
         WHEN 'SME_LOAN' THEN 4
         WHEN 'WEALTH' THEN 5
         ELSE 6
       END,
       a.currency_code,
       round((500 + ((a.account_id * 1009 + d.date_key) % 300000) / 10.0)::numeric, 2),
       round((500 + ((a.account_id * 997 + d.date_key) % 280000) / 10.0)::numeric, 2),
       round((((a.account_id * 997 + d.date_key) % 280000) / 10.0 * 0.00005)::numeric, 2)
FROM dim_account a
JOIN dim_date d ON d.full_date BETWEEN date '2025-04-01' AND date '2025-06-30';

INSERT INTO fact_loan_snapshot (
  snapshot_date_key, customer_id, branch_id, product_id, loan_account_id,
  outstanding_principal, days_past_due, pd_score, lgd, ead, risk_stage
)
SELECT d.date_key,
       a.customer_id,
       a.branch_id,
       CASE WHEN a.account_type = 'MORTGAGE' THEN 3 ELSE 4 END,
       a.account_id,
       round((50000 + ((a.account_id * 12347 + d.date_key) % 3000000) / 10.0)::numeric, 2),
       CASE
         WHEN a.customer_id % 41 = 0 THEN 95 + (a.account_id % 30)
         WHEN a.customer_id % 17 = 0 THEN 31 + (a.account_id % 50)
         WHEN a.customer_id % 9 = 0 THEN 1 + (a.account_id % 29)
         ELSE 0
       END,
       round((0.005 + (a.customer_id % 100) / 1000.0)::numeric, 6),
       round((0.25 + (a.account_id % 40) / 100.0)::numeric, 6),
       round((50000 + ((a.account_id * 12347 + d.date_key) % 3000000) / 10.0)::numeric, 2),
       CASE
         WHEN a.customer_id % 41 = 0 THEN 3
         WHEN a.customer_id % 17 = 0 THEN 2
         ELSE 1
       END
FROM dim_account a
JOIN dim_date d ON d.full_date IN (date '2025-04-30', date '2025-05-31', date '2025-06-30')
WHERE a.account_type IN ('MORTGAGE', 'SME_LOAN');

ANALYZE;

