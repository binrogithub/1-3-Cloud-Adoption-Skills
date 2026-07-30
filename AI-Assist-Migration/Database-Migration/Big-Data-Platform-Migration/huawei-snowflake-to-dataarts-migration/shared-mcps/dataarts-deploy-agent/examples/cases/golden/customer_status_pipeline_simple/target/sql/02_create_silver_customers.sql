CREATE TABLE demo_migration.silver_customers AS
SELECT
  customer_id,
  customer_name,
  CASE
    WHEN active_flag = 'Y' THEN 'ACTIVE'
    WHEN active_flag = 'N' THEN 'INACTIVE'
    ELSE 'UNKNOWN'
  END AS customer_status,
  active_flag,
  CURRENT_TIMESTAMP() AS processed_at
FROM demo_migration.raw_customers
WHERE active_flag IN ('Y', 'N');
