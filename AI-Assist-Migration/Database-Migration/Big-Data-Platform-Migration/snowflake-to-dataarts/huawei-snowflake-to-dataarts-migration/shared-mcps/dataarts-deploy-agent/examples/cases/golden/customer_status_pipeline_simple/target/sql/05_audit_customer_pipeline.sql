INSERT INTO demo_migration.task_audit (
  pipeline_name,
  step_name,
  status,
  message,
  created_at
)
VALUES (
  'customer_status_pipeline',
  'task_graph_completed',
  'SUCCESS',
  'Customer status pipeline finished successfully',
  CURRENT_TIMESTAMP()
);
