# Architecture: CBR Backup and Restore

## Overview

Huawei Cloud CBR (Cloud Backup and Recovery) provides backup and restore capabilities for ECS instances, EVS volumes, and CCE node resources. This skill orchestrates the full lifecycle via hcloud CLI.

## Components

### Source Region
- ECS Instance / EVS Volume / CCE Node (resource to protect)
- CBR Vault (backup storage container)
- CBR Policy (optional, for scheduled backups)
- CBR Agent (optional, for application-consistent ECS backup)

### Restore Path
- CBR Backup/Checkpoint (point-in-time backup)
- Restored Resource (new ECS/EVS created from backup)

### Cross-Region (Optional)
- CBR Backup Copy (replicated backup in destination region)
- Destination Region Vault (for cross-region restore)

## Data Flow

```
Source Resource → AddVaultResource → CBR Vault → CreateCheckpoint → Backup
                                                                         │
                                                                    RestoreBackup
                                                                         │
                                                                  Restored Resource (new)
```

Cross-region copy flow:
```
Backup (Region A) → CopyBackup → Backup Copy (Region B) → RestoreBackup → Restored Resource (Region B)
```

## Key Design Decisions

1. **hcloud CLI as primary mechanism**: No dedicated CBR MCP exists. All operations via verified hcloud CLI commands.
2. **DISCOVER BEFORE CREATE**: Always list existing resources before creating new ones. Resolve names to IDs.
3. **VERIFY AFTER EVERY STEP**: Every write operation followed by a read verification.
4. **Restore to new by default**: RestoreBackup creates a new resource. In-place restore requires explicit double confirmation.
5. **Explicit approval for all writes**: No write operation executes without human approval.
6. **No CBR Terraform**: CBR is not in huaweicloud-deploy supported services. Vault/backup creation via CLI only.

## Resource Types

| CBR Resource Type | Huawei Cloud Type | Protectable |
|---|---|---|
| server | OS::Nova::Server | ECS instances |
| disk | OS::Cinder::Volume | EVS volumes |
| turbo | OS::Sfs::Turbo | SFS Turbo file systems |
| workspace | - | Workspace desktops |
| vmware | - | VMware VMs |
| rds | - | RDS instances |

## Vault Protect Types

| Type | Purpose |
|---|---|
| backup | Local backup (in-region) |
| replication | Cross-region replication |

## Backup Statuses

| Status | Meaning |
|---|---|
| available | Backup complete and usable |
| protecting | Backup in progress |
| deleting | Backup being deleted |
| restoring | Backup being restored |
| error | Backup failed |
| waiting_protect | Waiting to start protection |
| waiting_delete | Waiting to start deletion |
| waiting_restore | Waiting to start restore |

## Limitations

- CBR is NOT supported by huaweicloud-deploy MCP
- No dedicated CBR MCP exists
- Resource type availability varies by region
- CCE node backup protects disks but not Kubernetes logical state
- Agent required for application-consistent ECS backup
- Cross-region copy capability varies by region
