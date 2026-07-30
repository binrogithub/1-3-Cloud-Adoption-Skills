# Execution Prompt

You are executing a CCE cross-region migration using Velero.

Given the following inputs:
- Source cluster: {{source_cluster_id}} in {{source_region}}
- Target cluster: {{target_cluster_id}} in {{target_region}}
- Namespaces: {{namespaces}}
- OBS bucket: {{obs_bucket}}
- Backup name: {{backup_name}}

Generate the Velero commands for:
1. Creating a backup on the source cluster
2. Monitoring backup progress
3. Creating a restore on the target cluster
4. Monitoring restore progress

Include namespace mappings and resource exclusions if needed.

Present the commands for human execution. Do NOT execute them.
All operations require explicit approval.
