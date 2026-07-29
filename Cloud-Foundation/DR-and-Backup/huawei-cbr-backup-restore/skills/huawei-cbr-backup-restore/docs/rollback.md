# Rollback Procedure

## Principles

1. A backup cannot be "rolled back" — it is a point-in-time capture that preserves data.
2. A restore should NOT be automatically deleted — it creates a new resource that may be needed.
3. Resource association can be removed from a vault (controlled removal).
4. Policies can be disabled before deletion to stop scheduled backups.
5. The original resource must always be preserved.

## Rollback by Phase

### Vault Creation Failure
- No data loss (vault was not created or is empty)
- Review error: quota, capacity, billing mode
- Retry with corrected parameters or different capacity
- Do NOT delete other vaults to free quota without explicit approval

### Association Failure
- Resource is unprotected (no backup taken)
- Verify vault type and resource type compatibility
- Verify region match
- Retry with correct vault

### Backup Failure
- No data loss (no backup created or backup in error state)
- Check vault capacity, resource state, agent status
- If backup in error state: document error, do NOT retry without investigation
- If backup stuck in protecting: wait for timeout, then report

### Restore Failure
- Original resource is intact (restore creates new resource)
- New resource may be partially created
- Assess new resource state
- Do NOT delete new resource automatically
- Do NOT delete original resource
- Report failure with full error details

### Policy Creation Failure
- No data loss (no scheduled backups started)
- Review schedule syntax and retention parameters
- Retry with corrected parameters

## Rollback Actions

### Disable Policy
```bash
hcloud CBR DisassociateVaultPolicy --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --policy_id=<POLICY_ID>
```

### Remove Resource from Vault
```bash
hcloud CBR RemoveVaultResource --cli-region=<SOURCE_REGION> \
  --vault_id=<VAULT_ID> \
  --resources='[{"id":"<RESOURCE_ID>","type":"<RESOURCE_TYPE>"}]'
```

### Delete Policy (requires explicit approval)
```bash
hcloud CBR DeletePolicy --cli-region=<SOURCE_REGION> --policy_id=<POLICY_ID>
```

### Delete Vault (requires explicit approval, vault must be empty)
```bash
hcloud CBR DeleteVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
```

## What NOT to Do

- Do NOT delete backups automatically
- Do NOT delete restored resources automatically
- Do NOT delete the original resource
- Do NOT overwrite the original resource during restore
- Do NOT remove vault resources without explicit approval
- Do NOT disable policies without documenting the reason
