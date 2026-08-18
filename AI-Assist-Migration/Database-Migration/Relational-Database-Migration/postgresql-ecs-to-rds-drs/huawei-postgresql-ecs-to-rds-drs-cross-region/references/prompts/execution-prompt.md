# Execution Prompt

You are executing a PostgreSQL ECS-to-RDS migration using DRS.

Given the following inputs:
- Task name: {{task_name}}
- Source: {{source_endpoint}}:{{source_port}}/{{source_database}} in {{source_region}}
- Target: RDS {{target_rds_id}}/{{target_database}} in {{target_region}}

Execute the DRS migration workflow:
1. Create DRS task (requires explicit_approval=true)
2. Capture DRS EIP
3. Run connection test
4. Run pre-check
5. Start task (requires explicit_approval=true)
6. Monitor progress

All write operations require explicit approval. Do NOT proceed without confirmation.
