# Finance Demo Reference

## Business Narrative

This demo models a bank migrating SQL Server-backed account and payment reporting to Babelfish/PostgreSQL. The migration goal is to keep SQL Server-compatible client behavior through the TDS port while exposing the migrated data through PostgreSQL for future modernization.

## Objects

`Customers`
: Customer master data. Includes segment (`Corporate`, `Retail`, `Private`) and risk rating (`Low`, `Medium`, `High`).

`Accounts`
: Customer bank accounts. Demonstrates unique account numbers, product codes, currency, balances, and a foreign key to customers.

`Payments`
: Payment ledger rows. Demonstrates debit and credit account foreign keys, payment timestamps, high-value amounts, channels, statuses, and unique reference numbers.

`RiskAlerts`
: Payment-linked alerts. Demonstrates operational risk events for high value transfers and customer risk mismatch.

`v_customer_exposure`
: Aggregates account count, total balance, outgoing payment amount, and open alerts by customer. This is the main executive risk view.

`v_daily_payment_liquidity`
: Aggregates payment count, total debit amount, and high-value transfer count by business date and currency. This is the liquidity operations view.

`usp_customer_exposure`
: Stored procedure for customer exposure. Optional `@RiskRating` filter.

`usp_daily_payment_liquidity`
: Stored procedure for daily liquidity. Optional `@BusinessDate` filter.

## Demo Talking Points

- Babelfish supports a SQL Server-compatible TDS endpoint and a PostgreSQL endpoint over the same migrated data.
- The demo covers common migration surfaces: tables, identity columns, primary keys, unique constraints, foreign keys, views, stored procedures, decimal money-like values, dates, and `DATETIME2`.
- Query result display can differ by client: FreeTDS may render dates and decimals differently from `sqlcmd` or `psql`, while the logical values match.
- In PostgreSQL, a SQL Server database/schema pair maps to a PostgreSQL schema. `FinanceDemo.dbo.Payments` appears as `financedemo_dbo.payments`.
