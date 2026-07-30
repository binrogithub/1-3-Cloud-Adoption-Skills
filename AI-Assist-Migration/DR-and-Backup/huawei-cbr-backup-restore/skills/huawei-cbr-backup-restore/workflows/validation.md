# Validation Workflow

## Objective
Validate backup integrity and restored resource functionality.

## Inputs
- backup_id
- restored_resource_id (if restore was performed)
- resource_type

## Steps

### Backup Validation

1. Verify backup exists
   ```bash
   hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
   ```

2. Validate backup metadata:
   - status: available
   - protected_resource matches source
   - vault_id matches
   - region matches
   - size recorded
   - creation_time recorded
   - expiration_time (if policy-based)
   - incremental or full relationship

3. Validate backup consistency:
   - Crash-consistent: expected for resources without agent
   - Application-consistent: expected for ECS with agent

### Restored Resource Validation

4. For ECS:
   ```bash
   hcloud ECS ShowServer --cli-region=<SOURCE_REGION> --server_id=<RESTORED_SERVER_ID>
   ```
   - Status: ACTIVE
   - Disks attached
   - Network configured
   - Security groups applied
   - Boot successful

5. For EVS:
   ```bash
   hcloud EVS ShowVolume --cli-region=<SOURCE_REGION> --volume_id=<RESTORED_VOLUME_ID>
   ```
   - Status: available
   - Size matches original
   - AZ matches
   - Attachment status

6. For CCE-related:
   - Disks or nodes recovered per scope
   - Do NOT assume Kubernetes state was restored

7. Application smoke tests (if applicable)

## Verification
- All validation checks pass
- Evidence recorded in artifacts

## Outputs
- artifacts/cbr-backup-validation-report.md
- artifacts/cbr-restore-validation-report.md

## Stop conditions
- Backup not found
- Backup in error state
- Restored resource not found
- Restored resource in error state

## Approval requirements
None (all read-only)
