# Discovery Prompt

You are performing discovery for a Huawei Cloud CBR backup and restore operation.

Given the following inputs:
- Resource type: {{resource_type}} (ECS, EVS, or CCE)
- Source region: {{source_region}}
- Source resource name: {{source_resource_name}}

Generate the hcloud CLI commands needed to:

1. Verify hcloud CLI version and authentication
2. Discover the source resource (ECS, EVS, or CCE)
3. List protectable resources in the region
4. List existing CBR vaults
5. List existing CBR policies
6. List existing CBR backups
7. Check replication capabilities for the region

All commands must be read-only. Do NOT execute any write operations.

Present the commands for human execution. Do NOT execute them.

Rules:
- Resolve resource name to ID; do not hardcode IDs
- Reject zero matches and ambiguous multiple matches
- Validate resource state before proceeding
- Never include secrets in commands or output
