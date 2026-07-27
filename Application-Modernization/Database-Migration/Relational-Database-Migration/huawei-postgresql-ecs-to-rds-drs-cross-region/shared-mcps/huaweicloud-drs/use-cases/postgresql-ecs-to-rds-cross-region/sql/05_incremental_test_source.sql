-- ============================================================
-- 05_incremental_test_source.sql - Incremental sync test on SOURCE
-- ============================================================
-- Run on: Source ECS PostgreSQL
-- AFTER DRS full sync completes AND incremental sync is running
-- These inserts must replicate to target RDS via DRS incremental sync
-- ============================================================

INSERT INTO demo_customers (customer_code, full_name, email, country, created_at) VALUES
('C006', 'Frank Okafor', 'frank.okafor@example.com', 'Nigeria', now());

INSERT INTO demo_orders (order_code, customer_id, order_date, status, created_at) VALUES
('ORD006', (SELECT customer_id FROM demo_customers WHERE customer_code = 'C006'), current_date, 'PENDING', now());

INSERT INTO demo_order_items (order_id, product_id, quantity, unit_price, created_at) VALUES
((SELECT order_id FROM demo_orders WHERE order_code = 'ORD006'), 1, 1, 299.99, now());

INSERT INTO demo_migration_audit (phase, status, note, recorded_at) VALUES
('INCREMENTAL_TEST', 'INSERTED', 'New row inserted after full sync to test incremental replication', now());

SELECT '=== INCREMENTAL SOURCE VALIDATION ===' AS section;

SELECT 'New customer:' AS label;
SELECT customer_id, customer_code, full_name, country, created_at
FROM demo_customers
WHERE customer_code = 'C006';

SELECT 'New order:' AS label;
SELECT o.order_id, o.order_code, o.customer_id, o.order_date, o.status
FROM demo_orders o
WHERE o.order_code = 'ORD006';

SELECT 'New order item:' AS label;
SELECT oi.order_item_id, oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_total
FROM demo_order_items oi
JOIN demo_orders o ON oi.order_id = o.order_id
WHERE o.order_code = 'ORD006';

SELECT 'Incremental audit:' AS label;
SELECT audit_id, phase, status, note, recorded_at
FROM demo_migration_audit
WHERE phase = 'INCREMENTAL_TEST';

SELECT 'Updated row counts:' AS label;
SELECT 'demo_customers'    AS table_name, count(*) AS row_count FROM demo_customers
UNION ALL
SELECT 'demo_orders'       AS table_name, count(*) AS row_count FROM demo_orders
UNION ALL
SELECT 'demo_order_items'  AS table_name, count(*) AS row_count FROM demo_order_items
UNION ALL
SELECT 'demo_migration_audit' AS table_name, count(*) AS row_count FROM demo_migration_audit;

SELECT 'Updated total revenue:' AS label;
SELECT sum(line_total) AS total_revenue FROM demo_order_items;
