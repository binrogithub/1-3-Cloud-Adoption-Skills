-- ============================================================
-- 03_source_validation.sql - Pre-migration validation on source PostgreSQL
-- ============================================================
-- Run on: Source ECS PostgreSQL BEFORE starting DRS migration
-- Record all results for comparison with target RDS after migration
-- ============================================================

SELECT '=== SOURCE VALIDATION START ===' AS section;

SELECT current_database() AS database_name;
SELECT now() AS validation_timestamp;
SELECT version() AS postgresql_version;

SELECT '--- ROW COUNTS ---' AS section;

SELECT 'demo_customers'    AS table_name, count(*) AS row_count FROM demo_customers
UNION ALL
SELECT 'demo_products'     AS table_name, count(*) AS row_count FROM demo_products
UNION ALL
SELECT 'demo_orders'       AS table_name, count(*) AS row_count FROM demo_orders
UNION ALL
SELECT 'demo_order_items'  AS table_name, count(*) AS row_count FROM demo_order_items
UNION ALL
SELECT 'demo_migration_audit' AS table_name, count(*) AS row_count FROM demo_migration_audit;

SELECT '--- ORDER STATUS SUMMARY ---' AS section;

SELECT status, count(*) AS order_count
FROM demo_orders
GROUP BY status
ORDER BY status;

SELECT '--- REVENUE TOTALS ---' AS section;

SELECT sum(line_total) AS total_revenue
FROM demo_order_items;

SELECT sum(line_total) AS total_revenue,
       count(*)        AS total_line_items
FROM demo_order_items;

SELECT '--- REVENUE BY ORDER ---' AS section;

SELECT o.order_code,
       o.status,
       sum(oi.line_total) AS order_total
FROM demo_orders o
JOIN demo_order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_code, o.status
ORDER BY o.order_code;

SELECT '--- SAMPLE CUSTOMERS ---' AS section;

SELECT customer_id, customer_code, full_name, country
FROM demo_customers
ORDER BY customer_id;

SELECT '--- SAMPLE PRODUCTS ---' AS section;

SELECT product_id, product_code, product_name, category, unit_price
FROM demo_products
ORDER BY product_id;

SELECT '--- MIGRATION AUDIT ---' AS section;

SELECT audit_id, phase, status, note, recorded_at
FROM demo_migration_audit
ORDER BY audit_id;

SELECT '=== SOURCE VALIDATION END ===' AS section;
