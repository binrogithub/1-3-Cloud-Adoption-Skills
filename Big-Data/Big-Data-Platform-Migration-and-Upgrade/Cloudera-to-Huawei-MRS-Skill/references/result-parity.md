# Result Parity Validation

## Goal

Prove that the migrated MRS workload preserves the Cloudera source business results before discussing tuning or production hardening.

## Validation Strategy

### Phase 1: Table-Level Validation

Compare row counts and basic statistics for every migrated table:

```sql
-- Run on both source (Cloudera) and target (MRS)
SELECT 'dim_branch' AS metric, cast(count(*) as string) AS value FROM dim_branch
UNION ALL SELECT 'dim_product', cast(count(*) as string) FROM dim_product
UNION ALL SELECT 'dim_customer', cast(count(*) as string) FROM dim_customer
UNION ALL SELECT 'dim_account', cast(count(*) as string) FROM dim_account
UNION ALL SELECT 'dim_date', cast(count(*) as string) FROM dim_date
UNION ALL SELECT 'fact_transaction', cast(count(*) as string) FROM fact_transaction
UNION ALL SELECT 'fact_daily_balance', cast(count(*) as string) FROM fact_daily_balance
UNION ALL SELECT 'fact_loan_snapshot', cast(count(*) as string) FROM fact_loan_snapshot;
```

### Phase 2: Aggregate Validation

Compare key business aggregates:

```sql
-- Transaction amount sum
SELECT 'amount_sum', cast(round(sum(amount),2) as string) FROM fact_transaction;

-- Suspicious transaction count
SELECT 'suspicious_count', cast(sum(CASE WHEN is_suspicious THEN 1 ELSE 0 END) as string) FROM fact_transaction;

-- Daily balance sum
SELECT 'ending_balance_sum', cast(round(sum(ending_balance),2) as string) FROM fact_daily_balance;

-- Expected credit loss
SELECT 'ecl_sum', cast(round(sum(pd_score*lgd*ead),2) as string) FROM fact_loan_snapshot;
```

### Phase 3: Report-Level Validation

Compare the output of migrated report views with source report outputs:

```sql
-- Run each report view and compare row count and key metrics
SELECT count(*) FROM reports.branch_kpi;
SELECT count(*) FROM reports.customer_profitability;
SELECT count(*) FROM reports.liquidity_gap;
SELECT count(*) FROM reports.loan_risk_snapshot;
SELECT count(*) FROM reports.suspicious_activity;
```

### Phase 4: Sample Record Validation

Spot-check individual records to verify data integrity:

```sql
-- Compare specific records between source and target
SELECT * FROM finance_dw.dim_branch WHERE branch_id = 1;
SELECT * FROM finance_dw.fact_transaction WHERE transaction_id = 1;
```

## Running Validation on MRS

### Method 1: Single UNION ALL Query (Recommended)

Run all validation metrics in a single Spark SQL query and save to HDFS:

```sql
-- Create a combined validation result
CREATE TEMPORARY VIEW validation_results AS
SELECT 'dim_branch' AS metric, cast(count(*) as string) AS value FROM finance_dw.dim_branch
UNION ALL SELECT 'dim_product', cast(count(*) as string) FROM finance_dw.dim_product
UNION ALL SELECT 'fact_transaction', cast(count(*) as string) FROM finance_dw.fact_transaction
UNION ALL SELECT 'amount_sum', cast(round(sum(amount),2) as string) FROM finance_dw.fact_transaction
UNION ALL SELECT 'suspicious_count', cast(sum(CASE WHEN is_suspicious THEN 1 ELSE 0 END) as string) FROM finance_dw.fact_transaction
UNION ALL SELECT 'ending_balance_sum', cast(round(sum(ending_balance),2) as string) FROM finance_dw.fact_daily_balance
UNION ALL SELECT 'ecl_sum', cast(round(sum(pd_score*lgd*ead),2) as string) FROM finance_dw.fact_loan_snapshot;

-- Save to HDFS for clean retrieval
INSERT OVERWRITE DIRECTORY '/tmp/mrs_validation'
USING csv OPTIONS ('delimiter'='\t')
SELECT * FROM validation_results;
```

Retrieve:

```bash
hdfs dfs -cat /tmp/mrs_validation/*
```

### Method 2: Individual Queries

Run each metric separately. Slower but easier to debug:

```bash
spark-sql --master yarn -e "SELECT count(*) FROM finance_dw.fact_transaction;"
```

**Warning:** Spark SQL terminal output can be mixed with progress bars. Saving to HDFS (Method 1) is more reliable for automated parsing.

## Comparison Rules

### Exact-Match Metrics

Use exact matches for:
- Row counts
- Distinct counts
- Rule-hit counts
- Status counts
- Categorical totals (deterministic)

### Numeric Metrics

Use exact matches first. If floating-point noise is expected:
- Compare rounded values (e.g., 2 decimal places)
- Compare absolute delta (e.g., |source - target| < 0.02)
- Compare relative delta (e.g., |source - target| / |source| < 0.0001)

Document the comparison rule used. Do not silently accept drift.

### Parity Report Format

```
metric,source_value,mrs_value,status
dim_branch,10,10,PASS
fact_transaction,120000,120000,PASS
amount_sum,1205934000.00,1205934000.00,PASS
ecl_sum,7499313.97,7499313.97,PASS
```

## Acceptance Criteria

Treat a migration as functionally aligned when:

1. All dimension table row counts match
2. All fact table row counts match
3. Core aggregate metrics match (amount sums, balance sums)
4. Exception counts match (suspicious transactions, overdue loans)
5. Category-level business outputs match
6. At least one sample business flow can be traced from source to final output

## Performance Comparison

Compare end-to-end wall-clock time **only after** the result set is proven equivalent.

When comparing run time, record:
- Data volume
- Storage path type (HDFS vs. OBS)
- Execution model (Spark SQL vs. Hive on Tez)
- Cluster sizing (node count, spec)
- Partition strategy

**Do not claim a platform is universally faster from a small or migration-scale timing result.**
