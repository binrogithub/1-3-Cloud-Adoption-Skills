# Lessons Learned

## From Discovery (VERIFIED_FROM_LOCAL_HELP)

1. CBR service is available in hcloud CLI v6.2.9 with 68 operations — sufficient for full backup/restore lifecycle.
2. Key operations verified: ListVault, ShowVault, CreateVault, CreateCheckpoint, RestoreBackup, CopyBackup, ListBackups, ShowBackup, ListPolicies, CreatePolicy, AddVaultResource, ListProtectable, ShowReplicationCapabilities.
3. Backup statuses confirmed: available, protecting, deleting, restoring, error, waiting_protect, waiting_delete, waiting_restore.
4. Resource types confirmed: OS::Nova::Server, OS::Cinder::Volume, OS::Ironic::BareMetalServer, OS::Native::Server, OS::Sfs::Turbo.
5. Vault object types confirmed: server, disk, turbo, workspace, vmware, rds, file.
6. Protect types confirmed: backup, replication.

## From Documentation (VERIFIED_FROM_DOCUMENTATION)

7. CBR vault creation requires billing configuration (charging_mode, size).
8. CBR policy schedule uses specific format that must be validated.
9. RestoreBackup creates a new resource — original is preserved.
10. Cross-region copy requires ShowReplicationCapabilities validation first.

## From Risk Analysis (INFERRED)

11. Restore to original location is high risk — default to restore-to-new.
12. Vault capacity exhaustion is a common failure mode — validate before backup.
13. Incremental backup chain breaks if base backup is deleted — protect base backups.
14. Agent-based backup requires agent verification — check before ECS backup.

## Recommendations

1. Validate hcloud CLI 7.2.12 compatibility when available.
2. Consider building a dedicated CBR MCP for structured error handling and retry logic.
3. Implement vault capacity monitoring as a pre-check.
4. Add backup chain validation before any delete operation.
5. Document agent installation procedure for ECS application-consistent backup.
6. Add cross-region copy cost estimation using pricing MCP.
