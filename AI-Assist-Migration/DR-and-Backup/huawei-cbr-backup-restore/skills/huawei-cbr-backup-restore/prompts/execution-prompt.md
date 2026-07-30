# Execution Prompt

You are executing a Huawei Cloud CBR backup and/or restore operation.

Prerequisites:
- Discovery must be completed (artifacts/cbr-source-discovery.json exists)
- Vault plan must be approved (artifacts/cbr-vault-plan.md reviewed)
- All required IDs must be resolved from discovery

Given the following inputs:
- Vault ID: {{vault_id}}
- Source resource ID: {{source_resource_id}}
- Resource type: {{resource_type}}
- Backup type: {{backup_type}} (ad-hoc or scheduled)
- Restore requirement: {{restore_requirement}}

Execute ONE phase at a time:

1. **Vault**: Create or reuse vault (requires approval)
2. **Association**: Add resource to vault (requires approval)
3. **Policy**: Create policy if scheduled (requires approval)
4. **Backup**: Create checkpoint (requires approval)
5. **Verify backup**: Confirm backup status available
6. **Restore**: Execute restore if required (requires approval + impact plan)
7. **Verify restore**: Confirm restored resource functional

After every write operation, run the corresponding verification command.

Rules:
- Require discovery artifacts before execution
- Require plan review before execution
- Require explicit approval for every write operation
- Verify after every write operation
- Never execute multiple write operations without verification between them
- Never include secrets in commands
- Never hardcode IDs
- Stop on any error; do not continue
