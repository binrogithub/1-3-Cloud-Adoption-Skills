# DAS Validation Guide - Target RDS PostgreSQL

## Overview

This guide walks you through using Huawei Cloud Database Admin Service (DAS) to validate the migrated data on the target RDS for PostgreSQL in la-south-2.

## Prerequisites

- DRS full sync has completed
- You have access to the Huawei Cloud console
- Target RDS instance is running and accessible

## Step 1: Open DAS

1. Log in to Huawei Cloud console
2. Navigate to **Database Admin Service (DAS)**
3. Or: Go to **RDS** → find your instance → click **Login** or **DAS**

## Step 2: Connect to Target RDS

1. Select the RDS PostgreSQL instance in la-south-2
2. Enter the database admin credentials
3. Select the `demomigration` database
4. Click **Connect** or **Login**

## Step 3: Run Full Migration Validation

In the DAS SQL query window, paste and execute the queries from `sql/04_target_validation_das.sql`.

### Expected Results After Full Sync

| Query | Expected Result |
|-------|-----------------|
| Row count: demo_customers | 5 |
| Row count: demo_products | 5 |
| Row count: demo_orders | 5 |
| Row count: demo_order_items | 9 |
| Row count: demo_migration_audit | 1 |
| Order status: COMPLETED | 3 |
| Order status: PENDING | 1 |
| Order status: SHIPPED | 1 |
| Total revenue | 3106.41 |
| Total line items | 9 |
| Audit phase | INITIAL_LOAD |
| Audit status | READY |

### Revenue by Order (Expected)

| Order | Status | Total |
|-------|--------|-------|
| ORD001 | COMPLETED | 749.48 |
| ORD002 | COMPLETED | 768.97 |
| ORD003 | SHIPPED | 699.97 |
| ORD004 | PENDING | 299.00 |
| ORD005 | COMPLETED | 588.99 |

### How to Compare

1. Run `sql/03_source_validation.sql` on the source ECS PostgreSQL
2. Run `sql/04_target_validation_das.sql` on the target RDS via DAS
3. Compare every result:
   - Row counts must match exactly
   - Revenue totals must match exactly
   - Sample data rows must match
   - Audit rows must match

## Step 4: Validate Incremental Sync

After inserting incremental data on the source (using `sql/05_incremental_test_source.sql`):

1. Wait 10-30 seconds for DRS incremental replication
2. In DAS, run the queries from `sql/06_incremental_validation_target_das.sql`

### Expected Results After Incremental Sync

| Query | Expected Result |
|-------|-----------------|
| C006 customer | Frank Okafor, Nigeria |
| ORD006 order | status=PENDING |
| ORD006 line item | product P001, qty=1, line_total=299.99 |
| INCREMENTAL_TEST audit | phase=INCREMENTAL_TEST, status=INSERTED |
| Final customer count | 6 |
| Final order count | 6 |
| Final order items count | 10 |
| Final audit count | 2 |
| Final total revenue | 3406.40 |

## Step 5: Visual Verification in DAS

DAS also provides a schema browser. Use it to:

1. Browse the `public` schema
2. Verify all 5 tables exist: `demo_customers`, `demo_products`, `demo_orders`, `demo_order_items`, `demo_migration_audit`
3. Check table row counts shown in the browser
4. Verify column definitions match the source schema

## Step 6: Record Results

Save all validation outputs to `reports/` for the demo presentation:

```
reports/
  source_validation_output.txt
  target_full_sync_validation.txt
  target_incremental_validation.txt
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cannot connect to DAS | Check RDS security group allows DAS access |
| Missing tables | DRS full sync may still be in progress; wait and retry |
| Row count mismatch | Check DRS task for errors; compare source and target counts |
| Revenue mismatch | Check for partial data; verify all order items replicated |
| Incremental data missing | Wait longer; check DRS incremental sync status and delay |
