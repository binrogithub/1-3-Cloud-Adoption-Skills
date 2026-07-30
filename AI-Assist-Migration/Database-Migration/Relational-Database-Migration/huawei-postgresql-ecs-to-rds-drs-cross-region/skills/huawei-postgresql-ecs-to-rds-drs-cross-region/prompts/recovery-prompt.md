# Recovery Prompt

You are recovering from a failed PostgreSQL ECS-to-RDS migration.

Current state:
- Phase: {{failed_phase}}
- Error: {{error_description}}
- Task name: {{task_name}}

Recovery actions:
- If connection test failed: Check SG rules, pg_hba.conf, PostgreSQL status
- If pre-check failed: Address BLOCKING items before retry
- If task start failed: Verify connection test and pre-check passed
- If sync failed: Check DRS logs, source locks, target capacity
- If cutover failed: Revert connections to source immediately

For rollback: Redirect application to source, stop DRS task manually.
