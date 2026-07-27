CREATE TABLE demo_migration.gold_customer_status AS
SELECT
  customer_status,
  COUNT(*) AS customer_count,
  CURRENT_TIMESTAMP() AS processed_at
FROM demo_migration.silver_customers
GROUP BY customer_status;
