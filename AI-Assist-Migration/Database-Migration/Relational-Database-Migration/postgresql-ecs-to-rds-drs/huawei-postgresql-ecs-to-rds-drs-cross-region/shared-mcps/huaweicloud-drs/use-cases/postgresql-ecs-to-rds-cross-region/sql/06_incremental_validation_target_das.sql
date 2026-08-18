-- ============================================================
-- 06_incremental_validation_target_das.sql - Incremental validation on TARGET RDS
-- ============================================================
-- Run on: Target RDS for PostgreSQL via Huawei Cloud DAS
-- AFTER inserting incremental rows on source and waiting for DRS replication
-- Wait 10-30 seconds after source insert before running this
-- ============================================================

SELECT '=== INCREMENTAL TARGET VALIDATION START ===' AS section;

SELECT '--- INCREMENTAL CUSTOMER (EXPECTED: C006, Frank Okafor, Nigeria) ---' AS section;

SELECT customer_id, customer_code, full_name, country, created_at
FROM demo_customers
WHERE customer_code = 'C006';

SELECT '--- INCREMENTAL ORDER (EXPECTED: ORD006, status=PENDING) ---' AS section;

SELECT o.order_id, o.order_code, o.customer_id, o.order_date, o.status
FROM demo_orders o
WHERE o.order_code = 'ORD006';

SELECT '--- INCREMENTAL ORDER ITEM (EXPECTED: product P001, qty=1, line_total=299.99) ---' AS section;

SELECT oi.order_item_id, oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_total
FROM demo_order_items oi
JOIN demo_orders o ON oi.order_id = o.order_id
WHERE o.order_code = 'ORD006';

SELECT '--- INCREMENTAL AUDIT (EXPECTED: phase=INCREMENTAL_TEST, status=INSERTED) ---' AS section;

SELECT audit_id, phase, status, note, recorded_at
FROM demo_migration_audit
WHERE phase = 'INCREMENTAL_TEST';

SELECT '--- FINAL ROW COUNTS (EXPECTED: customers=6, products=5, orders=6, items=10, audit=2) ---' AS section;

SELECT 'demo_customers'    AS table_name, count(*) AS row_count FROM demo_customers
UNION ALL
SELECT 'demo_products'     AS table_name, count(*) AS row_count FROM demo_products
UNION ALL
SELECT 'demo_orders'       AS table_name, count(*) AS row_count FROM demo_orders
UNION ALL
SELECT 'demo_order_items'  AS table_name, count(*) AS row_count FROM demo_order_items
UNION ALL
SELECT 'demo_migration_audit' AS table_name, count(*) AS row_count FROM demo_migration_audit;

SELECT '--- FINAL TOTAL REVENUE (EXPECTED: 3106.41 + 299.99 = 3406.40) ---' AS section;

SELECT sum(line_total) AS total_revenue FROM demo_order_items;

SELECT '=== INCREMENTAL TARGET VALIDATION END ===' AS section;
