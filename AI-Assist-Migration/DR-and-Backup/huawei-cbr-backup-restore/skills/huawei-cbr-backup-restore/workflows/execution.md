# Execution Workflow

## Objective
Execute backup and/or restore operations with explicit approval at each write step.

## Inputs
- vault_id
- source_resource_id
- backup_type (ad-hoc or scheduled)
- restore_requirement (boolean)

## Steps

### Backup Execution

1. **Ad-hoc backup** (requires explicit approval)
   ```bash
   hcloud CBR CreateCheckpoint --cli-region=<SOURCE_REGION> \
     --vault_id=<VAULT_ID>
   ```

2. **Verify backup started**
   ```bash
   hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID> --status=protecting
   ```

3. **Poll backup status** (use --cli-waiter or manual polling)
   ```bash
   hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
   ```
   - Handle: available (success), error (fail), timeout (report)

4. **Verify backup completed**
   ```bash
   hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
   ```
   Confirm: status=available, size, timestamps

### Restore Execution

5. **Plan restore** (generate artifacts/cbr-restore-plan.md)
   - Identify backup_id
   - Define restore target
   - Assess impact
   - Define rollback

6. **Execute restore** (requires explicit approval)
   ```bash
   hcloud CBR RestoreBackup --cli-region=<SOURCE_REGION> \
     --backup_id=<BACKUP_ID> \
     --restore='<RESTORE_SPEC>'
   ```

7. **Poll restore status**
   ```bash
   hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
   ```

8. **Verify restored resource**
   - ECS: `hcloud ECS ShowServer --server_id=<RESTORED_ID>`
   - EVS: `hcloud EVS ShowVolume --volume_id=<RESTORED_ID>`

### Cross-Region Copy (Optional)

9. **Validate cross-region capability**
   ```bash
   hcloud CBR ShowReplicationCapabilities --cli-region=<SOURCE_REGION>
   ```

10. **Execute copy** (requires explicit approval)
    ```bash
    hcloud CBR CopyBackup --cli-region=<SOURCE_REGION> \
      --backup_id=<BACKUP_ID> \
      --destination_region=<DEST_REGION> \
      --destination_project_id=<DEST_PROJECT_ID>
    ```

## Verification
After every write operation:
- Run corresponding Show or List command
- Confirm expected state
- Record evidence

## Outputs
- artifacts/cbr-backup-result.json
- artifacts/cbr-restore-result.json

## Stop conditions
- Backup fails (error state)
- Restore fails (error state)
- Approval denied
- Timeout exceeded

## Approval requirements
- CreateCheckpoint: EXPLICIT
- RestoreBackup: EXPLICIT
- CopyBackup: EXPLICIT

## Safety
- Never delete original resource
- Never restore in-place without double confirmation
- Never execute without approval
- Preserve all evidence artifacts
