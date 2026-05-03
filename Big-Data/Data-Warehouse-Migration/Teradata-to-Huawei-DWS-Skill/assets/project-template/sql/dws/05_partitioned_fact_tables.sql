-- Alternative partitioned DDL for larger production-style migrations.
-- Run this in a fresh target schema before loading data if the workload is
-- dominated by monthly reports, date range filters, and snapshot analysis.

DROP SCHEMA IF EXISTS finance_dw_partitioned CASCADE;
CREATE SCHEMA finance_dw_partitioned;

CREATE TABLE finance_dw_partitioned.fact_transaction (
  transaction_id bigint NOT NULL,
  account_id integer NOT NULL,
  customer_id integer NOT NULL,
  branch_id integer NOT NULL,
  product_id integer NOT NULL,
  transaction_ts timestamp NOT NULL,
  txn_date_key integer NOT NULL,
  txn_type varchar(30) NOT NULL,
  channel varchar(30) NOT NULL,
  amount numeric(18,2) NOT NULL,
  balance_after numeric(18,2) NOT NULL,
  counterparty_region varchar(60) NOT NULL,
  is_suspicious boolean NOT NULL,
  risk_score numeric(6,2) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH (customer_id)
PARTITION BY RANGE (txn_date_key) (
  PARTITION p202501 VALUES LESS THAN (20250201),
  PARTITION p202502 VALUES LESS THAN (20250301),
  PARTITION p202503 VALUES LESS THAN (20250401),
  PARTITION p202504 VALUES LESS THAN (20250501),
  PARTITION p202505 VALUES LESS THAN (20250601),
  PARTITION p202506 VALUES LESS THAN (20250701),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

CREATE TABLE finance_dw_partitioned.fact_daily_balance (
  balance_date_key integer NOT NULL,
  account_id integer NOT NULL,
  customer_id integer NOT NULL,
  branch_id integer NOT NULL,
  product_id integer NOT NULL,
  currency_code char(3) NOT NULL,
  ending_balance numeric(18,2) NOT NULL,
  avg_balance numeric(18,2) NOT NULL,
  interest_accrued numeric(18,2) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH (customer_id)
PARTITION BY RANGE (balance_date_key) (
  PARTITION p202504 VALUES LESS THAN (20250501),
  PARTITION p202505 VALUES LESS THAN (20250601),
  PARTITION p202506 VALUES LESS THAN (20250701),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

CREATE TABLE finance_dw_partitioned.fact_loan_snapshot (
  snapshot_date_key integer NOT NULL,
  customer_id integer NOT NULL,
  branch_id integer NOT NULL,
  product_id integer NOT NULL,
  loan_account_id integer NOT NULL,
  outstanding_principal numeric(18,2) NOT NULL,
  days_past_due integer NOT NULL,
  pd_score numeric(8,6) NOT NULL,
  lgd numeric(8,6) NOT NULL,
  ead numeric(18,2) NOT NULL,
  risk_stage integer NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY HASH (customer_id)
PARTITION BY RANGE (snapshot_date_key) (
  PARTITION p202504 VALUES LESS THAN (20250501),
  PARTITION p202505 VALUES LESS THAN (20250601),
  PARTITION p202506 VALUES LESS THAN (20250701),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

INSERT INTO finance_dw_partitioned.fact_transaction
SELECT * FROM finance_dw.fact_transaction;

INSERT INTO finance_dw_partitioned.fact_daily_balance
SELECT * FROM finance_dw.fact_daily_balance;

INSERT INTO finance_dw_partitioned.fact_loan_snapshot
SELECT * FROM finance_dw.fact_loan_snapshot;

ANALYZE finance_dw_partitioned.fact_transaction;
ANALYZE finance_dw_partitioned.fact_daily_balance;
ANALYZE finance_dw_partitioned.fact_loan_snapshot;

