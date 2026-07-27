# Discovery Prompt

You are performing discovery for a PostgreSQL ECS-to-RDS cross-region migration.

Given the following inputs:
- Source region: {{source_region}}
- Target region: {{target_region}}
- Source database: {{source_database}}
- Target RDS ID: {{target_rds_id}}

Execute these DRS MCP operations:
1. drs_read_context() — Get current DRS console state
2. drs_list_tasks({ region: "{{target_region}}", source_engine: "postgresql" }) — List existing tasks
3. drs_find_matching_tasks({ region: "{{target_region}}", task_name: "{{task_name}}", ... }) — Find matching tasks

Report the current state and whether any existing tasks match this scenario.
