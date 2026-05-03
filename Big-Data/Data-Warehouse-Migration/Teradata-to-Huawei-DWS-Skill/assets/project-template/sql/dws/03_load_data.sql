\copy finance_dw.dim_branch FROM '/work/data/export/finance_dw__dim_branch.csv' WITH CSV HEADER
\copy finance_dw.dim_product FROM '/work/data/export/finance_dw__dim_product.csv' WITH CSV HEADER
\copy finance_dw.dim_customer FROM '/work/data/export/finance_dw__dim_customer.csv' WITH CSV HEADER
\copy finance_dw.dim_account FROM '/work/data/export/finance_dw__dim_account.csv' WITH CSV HEADER
\copy finance_dw.dim_date FROM '/work/data/export/finance_dw__dim_date.csv' WITH CSV HEADER
\copy finance_dw.fact_transaction FROM '/work/data/export/finance_dw__fact_transaction.csv' WITH CSV HEADER
\copy finance_dw.fact_daily_balance FROM '/work/data/export/finance_dw__fact_daily_balance.csv' WITH CSV HEADER
\copy finance_dw.fact_loan_snapshot FROM '/work/data/export/finance_dw__fact_loan_snapshot.csv' WITH CSV HEADER

