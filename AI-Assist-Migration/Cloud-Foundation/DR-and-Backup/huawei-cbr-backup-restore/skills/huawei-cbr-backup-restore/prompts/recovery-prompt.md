# Recovery Prompt

You are recovering from a failed CBR backup or restore operation.

Current state:
- Failed phase: {{failed_phase}}
- Error: {{error_description}}
- Vault ID: {{vault_id}}
- Backup ID: {{backup_id}} (if backup was attempted)
- Restored resource ID: {{restored_resource_id}} (if restore was attempted)

Recovery rules:

1. **Detect last checkpoint**: Check what operations completed successfully by examining artifacts and CBR state.
   ```bash
   hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
   hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
   ```

2. **Do not duplicate backups**: If a backup already exists and is available, do not create another checkpoint.

3. **Do not recreate vaults without discovering**: Always list existing vaults before creating.
   ```bash
   hcloud CBR ListVault --cli-region=<SOURCE_REGION>
   ```

4. **Do not repeat restores**: If a restore was already attempted, check the restored resource state before retrying.
   ```bash
   hcloud ECS ShowServer --server_id=<RESTORED_ID>
   hcloud EVS ShowVolume --volume_id=<RESTORED_ID>
   ```

5. **Preserve IDs and evidence**: Do not delete artifacts. Record all recovery actions.

6. **Continue from real state**: Do not assume state; verify current state before proceeding.

Recovery by phase:
- **Vault creation failed**: Check quota, retry with corrected parameters
- **Association failed**: Check vault/resource compatibility, retry
- **Backup failed**: Check vault capacity, resource state, agent; do NOT retry without investigation
- **Restore failed**: Original resource intact; check error, assess new resource state
- **Validation failed**: Assess which resource is functional; do NOT delete either

Present the recovery commands for human execution. Do NOT execute them.
Prioritize preserving the original resource and existing data.
