DROP SCHEMA IF EXISTS reports CASCADE;
DROP SCHEMA IF EXISTS finance_dw CASCADE;

CREATE SCHEMA finance_dw;
CREATE SCHEMA reports;

CREATE TABLE finance_dw.dim_branch (
  branch_id integer,
  branch_code varchar(20) NOT NULL,
  branch_name varchar(100) NOT NULL,
  province varchar(60) NOT NULL,
  city varchar(60) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

CREATE TABLE finance_dw.dim_product (
  product_id integer,
  product_code varchar(30) NOT NULL,
  product_name varchar(120) NOT NULL,
  product_type varchar(40) NOT NULL,
  annual_rate numeric(9,6) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

CREATE TABLE finance_dw.dim_customer (
  customer_id integer,
  customer_number varchar(30) NOT NULL,
  full_name varchar(100) NOT NULL,
  segment varchar(30) NOT NULL,
  risk_level varchar(20) NOT NULL,
  region varchar(60) NOT NULL,
  open_date date NOT NULL,
  kyc_status varchar(20) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

CREATE TABLE finance_dw.dim_account (
  account_id integer,
  customer_id integer NOT NULL,
  account_number varchar(30) NOT NULL,
  account_type varchar(30) NOT NULL,
  branch_id integer NOT NULL,
  currency_code char(3) NOT NULL,
  open_date date NOT NULL,
  status varchar(20) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

CREATE TABLE finance_dw.dim_date (
  date_key integer,
  full_date date NOT NULL,
  year_num integer NOT NULL,
  quarter_num integer NOT NULL,
  month_num integer NOT NULL,
  day_num integer NOT NULL,
  month_name varchar(12) NOT NULL
)
WITH (orientation = column, compression = middle)
DISTRIBUTE BY REPLICATION;

CREATE TABLE finance_dw.fact_transaction (
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
DISTRIBUTE BY HASH (customer_id);

CREATE TABLE finance_dw.fact_daily_balance (
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
DISTRIBUTE BY HASH (customer_id);

CREATE TABLE finance_dw.fact_loan_snapshot (
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
DISTRIBUTE BY HASH (customer_id);

