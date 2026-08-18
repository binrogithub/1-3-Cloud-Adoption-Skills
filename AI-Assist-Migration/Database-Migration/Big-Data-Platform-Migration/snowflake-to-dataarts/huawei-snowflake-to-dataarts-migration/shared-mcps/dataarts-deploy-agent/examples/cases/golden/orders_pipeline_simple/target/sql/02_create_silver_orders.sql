CREATE TABLE demo_migration.silver_orders AS
SELECT
  order_id,
  customer_id,
  order_date,
  order_amount,
  CURRENT_TIMESTAMP() AS processed_at
FROM demo_migration.raw_orders
WHERE order_amount > 0;
