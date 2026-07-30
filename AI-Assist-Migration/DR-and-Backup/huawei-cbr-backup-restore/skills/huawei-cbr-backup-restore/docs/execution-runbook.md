# Execution Runbook: CBR Backup and Restore

## Step 1: Parse Intent

Extract all required and optional inputs. Generate `artifacts/cbr-intent.json`.

If critical information is missing: STOP and request clarification.

## Step 2: Discover Authentication and Region

```bash
hcloud version
hcloud CBR ListVault --cli-region=<SOURCE_REGION> --limit=1
```

Verify: version, region, CBR availability.

## Step 3: Discover Source Resources

For ECS:
```bash
hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>
hcloud CBR ListProtectable --cli-region=<SOURCE_REGION> --protectable_type=OS::Nova::Server
```

For EVS:
```bash
hcloud EVS ListVolumes --cli-region=<SOURCE_REGION>
hcloud CBR ListProtectable --cli-region=<SOURCE_REGION> --protectable_type=OS::Cinder::Volume
```

For CCE:
```bash
hcloud CCE ListClusters --cli-region=<SOURCE_REGION>
```

Resolve name to ID. Reject zero or ambiguous matches. Validate resource state.

## Step 4: Discover Existing Vaults and Policies

```bash
hcloud CBR ListVault --cli-region=<SOURCE_REGION>
hcloud CBR ListPolicies --cli-region=<SOURCE_REGION>
hcloud CBR ListBackups --cli-region=<SOURCE_REGION>
hcloud CBR ShowReplicationCapabilities --cli-region=<SOURCE_REGION>
```

Apply DISCOVER BEFORE CREATE. Present reuse option if compatible vault exists.

## Step 5: Plan Vault

Generate vault plan: name, type, capacity, billing, region, project, tags, reuse decision, quota impact, estimated cost.

Output: `artifacts/cbr-vault-plan.md`

## Step 6: Create or Reuse Vault

If creating (requires explicit approval):
```bash
hcloud CBR CreateVault --cli-region=<SOURCE_REGION> \
  --vault.name='<VAULT_NAME>' \
  --vault.billing.consistent_with_server=false \
  --vault.billing.charging_mode=<CHARGING_MODE> \
  --vault.billing.size=<CAPACITY_GB> \
  --vault.resource_type=<RESOURCE_TYPE> \
  --vault.prot_type=<PROTECT_TYPE>
```

Verify:
```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

## Step 7: Associate Resource

Requires explicit approval.
```bash
hcloud CBR AddVaultResource --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --resources='[{"id":"<RESOURCE_ID>","type":"<RESOURCE_TYPE>"}]'
```

Verify:
```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

## Step 8: Create or Reuse Policy

For ad-hoc: skip.

For scheduled (requires explicit approval):
```bash
hcloud CBR CreatePolicy --cli-region=<SOURCE_REGION> \
  --policy.name='<POLICY_NAME>' \
  --policy.enabled=<ENABLED> \
  --policy.trigger.properties.schedule='<SCHEDULE>' \
  --policy.trigger.type=time \
  --policy.operation_definition.retention_duration_days=<RETENTION_DAYS>
```

Associate:
```bash
hcloud CBR AssociateVaultPolicy --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --policy_id=<POLICY_ID>
```

Verify:
```bash
hcloud CBR ShowPolicy --cli-region=<SOURCE_REGION> --policy_id=<POLICY_ID>
```

## Step 9: Trigger Backup

For ad-hoc (requires explicit approval):
```bash
hcloud CBR CreateCheckpoint --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID>
```

Poll backup status:
```bash
hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
```

## Step 10: Verify Backup

```bash
hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
```

Validate: status=available, resource, vault, region, size, timestamps.

## Step 11: Plan Restore

Generate restore plan with impact analysis and rollback strategy.
Output: `artifacts/cbr-restore-plan.md`

## Step 12: Execute Restore

Requires explicit approval.
```bash
hcloud CBR RestoreBackup --cli-region=<SOURCE_REGION> \
  --backup_id=<BACKUP_ID> \
  --restore='<RESTORE_SPEC>'
```

Poll restore status.

## Step 13: Verify Restored Resource

For ECS:
```bash
hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>
hcloud ECS ShowServer --cli-region=<SOURCE_REGION> --server_id=<RESTORED_SERVER_ID>
```

For EVS:
```bash
hcloud EVS ListVolumes --cli-region=<SOURCE_REGION>
hcloud EVS ShowVolume --cli-region=<SOURCE_REGION> --volume_id=<RESTORED_VOLUME_ID>
```

## Step 14: Closure

Generate final report. Do NOT delete backups, vaults, or restored resources automatically.
