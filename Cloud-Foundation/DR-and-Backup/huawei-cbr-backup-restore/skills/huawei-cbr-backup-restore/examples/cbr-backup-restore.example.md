# CBR Backup and Restore Example: ECS Ad-Hoc Backup and Restore

## Scenario

- Region: `<SOURCE_REGION>`
- ECS name: `<SOURCE_ECS_NAME>`
- Vault name: `<CBR_VAULT_NAME>`
- Policy: none (ad-hoc)
- Backup type: ad-hoc
- Restore target: `<RESTORED_ECS_NAME>`

---

## Step 1: Parse Intent

```json
{
  "resource_type": "ECS",
  "source_region": "<SOURCE_REGION>",
  "source_resource_name": "<SOURCE_ECS_NAME>",
  "vault_name": "<CBR_VAULT_NAME>",
  "backup_type": "ad-hoc",
  "restore_requirement": true,
  "restore_target_naming": "<RESTORED_ECS_NAME>",
  "approval_owner": "<APPROVAL_OWNER>"
}
```

Output: `artifacts/cbr-intent.json`

## Step 2: Discover Authentication and Region

```bash
hcloud version
hcloud CBR ListVault --cli-region=<SOURCE_REGION> --limit=1
```

Expected: Version 6.2.9, CBR accessible.

## Step 3: Discover Source Resource

```bash
hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>
hcloud CBR ListProtectable --cli-region=<SOURCE_REGION> --protectable_type=OS::Nova::Server
```

Resolve `<SOURCE_ECS_NAME>` to `<SOURCE_ECS_ID>`.
Validate ECS status is ACTIVE.

Output: `artifacts/cbr-source-discovery.json`

## Step 4: Discover Existing Vaults

```bash
hcloud CBR ListVault --cli-region=<SOURCE_REGION>
hcloud CBR ListPolicies --cli-region=<SOURCE_REGION>
hcloud CBR ListBackups --cli-region=<SOURCE_REGION>
```

No compatible vault found. Proceed to create.

Output: `artifacts/cbr-existing-resources.json`

## Step 5: Plan Vault

Vault plan:
- Name: `<CBR_VAULT_NAME>`
- Resource type: server
- Protect type: backup
- Capacity: 100 GB (example)
- Billing: post-paid
- Region: `<SOURCE_REGION>`

Output: `artifacts/cbr-vault-plan.md`

## Step 6: Approval Gate

**REQUIRE EXPLICIT APPROVAL** before vault creation.

Approval received from `<APPROVAL_OWNER>`.

## Step 7: Create Vault

```bash
hcloud CBR CreateVault --cli-region=<SOURCE_REGION> \
  --vault.name='<CBR_VAULT_NAME>' \
  --vault.billing.consistent_with_server=false \
  --vault.billing.charging_mode=2 \
  --vault.billing.size=100 \
  --vault.resource_type=server \
  --vault.prot_type=backup
```

Verify:
```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

Confirm: ID resolved, status available, capacity 100 GB, region matches.

Output: `artifacts/cbr-vault-result.json`

## Step 8: Associate Resource

**REQUIRE EXPLICIT APPROVAL** before association.

```bash
hcloud CBR AddVaultResource --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --resources='[{"id":"<SOURCE_ECS_ID>","type":"OS::Nova::Server"}]'
```

Verify:
```bash
hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

Confirm: `<SOURCE_ECS_ID>` appears in vault resources.

Output: `artifacts/cbr-association-result.json`

## Step 9: Trigger Backup

**REQUIRE EXPLICIT APPROVAL** before backup.

```bash
hcloud CBR CreateCheckpoint --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID>
```

Poll backup status:
```bash
hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

Wait for status: available.

Record `<BACKUP_ID>`.

Output: `artifacts/cbr-backup-result.json`

## Step 10: Verify Backup

```bash
hcloud CBR ShowBackup --cli-region=<SOURCE_REGION> --backup_id=<BACKUP_ID>
```

Validate:
- Status: available
- Protected resource: `<SOURCE_ECS_ID>`
- Vault: `<VAULT_ID>`
- Region: `<SOURCE_REGION>`
- Size recorded
- Creation time recorded

Output: `artifacts/cbr-backup-validation-report.md`

## Step 11: Plan Restore

Restore plan:
- Backup: `<BACKUP_ID>`
- Target: new ECS named `<RESTORED_ECS_NAME>`
- AZ: same as source
- Network: same VPC/subnet/SG as source
- Rollback: delete restored ECS if validation fails (requires approval)

**REQUIRE EXPLICIT APPROVAL** for restore plan.

Output: `artifacts/cbr-restore-plan.md`

## Step 12: Execute Restore

**REQUIRE EXPLICIT APPROVAL** before restore.

```bash
hcloud CBR RestoreBackup --cli-region=<SOURCE_REGION> \
  --backup_id=<BACKUP_ID> \
  --restore='<RESTORE_SPEC>'
```

Poll restore status. Record `<RESTORED_ECS_ID>`.

Output: `artifacts/cbr-restore-result.json`

## Step 13: Validate Restored ECS

```bash
hcloud ECS ShowServer --cli-region=<SOURCE_REGION> --server_id=<RESTORED_ECS_ID>
```

Validate:
- Status: ACTIVE
- Disks attached
- Network configured
- Security groups applied
- Boot successful

Output: `artifacts/cbr-restore-validation-report.md`

## Step 14: Closure

Generate final report:
- Backup: `<BACKUP_ID>` (status: available)
- Restored ECS: `<RESTORED_ECS_ID>` (status: ACTIVE)
- Original ECS: `<SOURCE_ECS_ID>` (preserved)
- Vault: `<VAULT_ID>`
- No automatic cleanup

Output: `artifacts/cbr-final-report.md`
