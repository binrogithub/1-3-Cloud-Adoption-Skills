CREATE TABLE demo_migration.gold_daily_sales AS
SELECT
  order_date,
  COUNT(*) AS order_count,
  SUM(order_amount) AS total_amount,
  AVG(order_amount) AS avg_amount,
  CURRENT_TIMESTAMP() AS processed_at
FROM demo_migration.silver_orders
GROUP BY order_date;
