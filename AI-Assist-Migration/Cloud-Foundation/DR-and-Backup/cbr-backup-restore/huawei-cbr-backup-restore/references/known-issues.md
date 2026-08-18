# Known Issues

## CBR Service

1. **Vault type mismatch**: Using protect_type=replication for local backup or protect_type=backup for cross-region DR causes unexpected behavior. Validate protect_type matches intended use before vault creation.

2. **Resource type availability**: Not all resource types (server, disk, turbo, workspace, vmware, rds, file) are available in every region. Use ListProtectable to verify before creating vault.

3. **Agent requirement for ECS**: Application-consistent backup of ECS requires the CBR agent to be installed and registered. Without agent, backup is crash-consistent only.

4. **Backup consistency**: Crash-consistent vs application-consistent depends on agent presence and resource type. Databases should use application-consistent backup.

5. **Incremental chain dependency**: Deleting a base backup breaks the incremental chain. Always validate chain before deleting any backup.

6. **Cross-region copy limitations**: Not all regions support cross-region copy. Use ShowReplicationCapabilities to validate before CopyBackup.

7. **Vault capacity exhaustion**: If vault capacity is exceeded, new backups fail. Monitor capacity with ShowVault or ShowSummary.

## hcloud CLI

8. **CLI version compatibility**: Verified with hcloud 6.2.9. Version 7.2.12 may have parameter changes. Do NOT assume compatibility without validation.

9. **CLI authentication errors**: If hcloud auth fails, verify AK/SK configuration. Do NOT pass credentials in commands.

10. **Rate limiting**: hcloud CLI may hit API rate limits during rapid polling. Use --cli-retry-count for retry logic.

11. **Request timeout**: Long-running operations (backup, restore, copy) may exceed CLI timeout. Use --cli-waiter for polling.

## Restore

12. **Restore creates new resource**: RestoreBackup creates a new ECS or EVS resource. The original is NOT overwritten. Plan for new resource naming and network configuration.

13. **ECS restore network**: Restored ECS may require different network/subnet/SG configuration. Validate availability before restore.

14. **EVS restore attachment**: Restored EVS volume is created unattached. Manual attachment required after restore.

15. **CCE node restore scope**: CBR restores disks/nodes but does not restore Kubernetes deployments, ConfigMaps, or runtime state. Use Velero for Kubernetes state.

## Troubleshooting

| Symptom | Likely cause | Diagnostic command | Resolution | Retry safe |
|---|---|---|---|---|
| Source ECS in unsupported state | ECS is SHUTOFF or ERROR | `hcloud ECS ShowServer --server_id=<ID>` | Start ECS or use crash-consistent backup | No (state must change) |
| EVS volume state incompatible | Volume is error or in-use with constraints | `hcloud EVS ShowVolume --volume_id=<ID>` | Resolve volume state first | No (state must change) |
| Vault quota exceeded | Region vault limit reached | `hcloud CBR ListVault --cli-region=<REGION>` | Request quota increase or reuse existing vault | No (quota must change) |
| Vault capacity exhausted | Vault size too small for backup | `hcloud CBR ShowVault --vault_id=<ID>` | Expand vault capacity or create larger vault | Yes (after capacity increase) |
| Backup quota exceeded | Region backup limit reached | `hcloud CBR ListBackups --cli-region=<REGION>` | Delete old backups (with approval) or request quota increase | No (quota must change) |
| Resource already associated | Resource in another vault | `hcloud CBR ListProtectable --cli-region=<REGION>` | Remove from other vault first or use existing vault | Yes (after removal) |
| Policy schedule invalid | Schedule syntax error | `hcloud CBR ShowPolicy --policy_id=<ID>` | Fix schedule format per CBR documentation | Yes (after correction) |
| Backup remains pending | Resource state or vault issue | `hcloud CBR ShowBackup --backup_id=<ID>` | Wait, check resource state, check vault capacity | Yes (after investigation) |
| Backup enters failed state | Resource, vault, or agent issue | `hcloud CBR ShowBackup --backup_id=<ID>` | Review error details, check agent, check resource | No (root cause must resolve) |
| Incremental chain dependency | Base backup deleted or corrupted | `hcloud CBR ListBackups --vault_id=<ID>` | Create new full backup to reset chain | Yes (new full backup) |
| Restore target conflict | Target AZ or network unavailable | `hcloud ECS ListServersDetails --cli-region=<REGION>` | Choose different AZ or resolve network | Yes (after resolution) |
| Insufficient subnet IPs | Subnet has no available IPs | `hcloud VPC ShowSubnet --subnet_id=<ID>` | Use different subnet or expand CIDR | No (network must change) |
| Insufficient IAM permissions | CBR or ECS/EVS permissions missing | `hcloud CBR ListVault --cli-region=<REGION>` | Request IAM permissions from admin | No (permissions must change) |
| Region mismatch | Vault and resource in different regions | `hcloud CBR ShowVault --vault_id=<ID>` | Use vault in same region as resource | Yes (with correct region) |
| Enterprise project mismatch | Vault and resource in different projects | `hcloud CBR ShowVault --vault_id=<ID>` | Use matching enterprise project | Yes (with correct project) |
| Unsupported cross-region copy | Destination region lacks capability | `hcloud CBR ShowReplicationCapabilities --cli-region=<REGION>` | Use supported destination region | No (region must change) |
| CLI authentication error | Invalid or expired credentials | `hcloud CBR ListVault --cli-region=<REGION> --limit=1` | Reconfigure hcloud authentication | Yes (after reconfiguration) |
| CLI version incompatibility | Parameter format changed in newer version | `hcloud version` | Use verified version (6.2.9) or validate new version | No (version must match) |
| Rate limiting | Too many API calls in short time | Check CLI error output | Add delays between calls, use --cli-retry-count | Yes (after cooldown) |
| Request timeout | Long operation exceeds CLI timeout | Check CLI error output | Use --cli-waiter with appropriate timeout | Yes (with longer timeout) |
