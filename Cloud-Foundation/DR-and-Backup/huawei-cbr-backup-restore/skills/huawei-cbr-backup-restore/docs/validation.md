# Validation

## Pre-backup validation

- hcloud CLI version confirmed (6.2.9)
- Authentication valid
- Region accessible
- CBR service available
- Source resource exists and is in compatible state
- Vault exists with sufficient capacity
- Resource associated with vault
- Agent status verified (for ECS application-consistent backup)
- Policy schedule valid (for scheduled backups)

## Post-backup validation

- Backup exists (ShowBackup)
- Backup status: available
- Protected resource matches source
- Vault matches
- Region matches
- Size recorded
- Creation time recorded
- Expiration time (if policy-based)
- Incremental or full relationship intact
- Checksum or consistency metadata (when available)

## Pre-restore validation

- Backup ID identified and status available
- Restore capability validated for resource type
- Destination AZ has capacity
- Network/subnet/SG available for ECS restore
- No IP conflicts for ECS restore
- Restore plan reviewed and approved

## Post-restore validation

### ECS
- New instance visible in ListServersDetails
- Status: ACTIVE
- Disks attached and match original
- Network configured
- Security groups applied
- Boot successful
- Application smoke tests pass

### EVS
- New volume visible in ListVolumes
- Status: available
- Size matches original
- AZ matches
- Attachment status correct
- Filesystem mountable (if applicable)
- Data integrity verified (if applicable)

### CCE-related
- Disks or nodes recovered per scope
- Kubernetes node status (if applicable)
- Do NOT assume deployments and runtime were restored automatically
