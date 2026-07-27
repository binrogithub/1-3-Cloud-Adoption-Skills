INSERT INTO demo_migration.task_audit (
  pipeline_name,
  step_name,
  status,
  message,
  created_at
)
VALUES (
  'snowflake_to_dataarts_demo_v11_full_ai_async',
  'task_graph_completed',
  'SUCCESS',
  'DataArts pipeline v11 finished successfully using AI-generated runtime-safe artifacts',
  CURRENT_TIMESTAMP()
);
