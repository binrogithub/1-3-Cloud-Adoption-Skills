# Recovery Prompt

You are recovering from a failed CCE cross-region migration.

Current state:
- Phase: {{failed_phase}}
- Error: {{error_description}}
- Source cluster: {{source_cluster_id}}
- Target cluster: {{target_cluster_id}}

Generate recovery commands based on the failure phase:
- If backup failed: Clean up partial backup, check OBS connectivity
- If restore failed: Delete partial restore, check resource compatibility
- If cutover failed: Revert DNS immediately
- If validation failed: Assess whether rollback is needed

Present the commands for human execution. Do NOT execute them.
Prioritize restoring source cluster traffic if cutover was attempted.
