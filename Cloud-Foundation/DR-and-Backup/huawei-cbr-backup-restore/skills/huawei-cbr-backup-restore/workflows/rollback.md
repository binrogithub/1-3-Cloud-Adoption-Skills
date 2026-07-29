# Rollback Workflow

## Objective
Revert operations if validation fails or issues are discovered, while preserving data and evidence.

## Inputs
- failed_phase
- error_description
- vault_id
- backup_id
- restored_resource_id

## Steps

### Principles

1. A backup cannot be "rolled back" — it is a point-in-time capture.
2. A restore should NOT be automatically deleted — it creates a new resource.
3. The original resource must always be preserved.
4. Policies can be disabled before deletion.
5. Resource association can be removed from a vault (controlled).

### Rollback by Phase

**Vault creation failure**:
- No data loss (vault empty or not created)
- Review error, retry with corrected parameters
- Do NOT delete other vaults without explicit approval

**Association failure**:
- Resource is unprotected
- Verify vault/resource compatibility, retry

**Backup failure**:
- No data loss (no backup created)
- Check vault capacity, resource state, agent
- Do NOT retry without investigating root cause

**Restore failure**:
- Original resource intact
- New resource may be partially created
- Do NOT delete new resource automatically
- Do NOT delete original resource
- Report failure with full details

**Policy creation failure**:
- No data loss
- Review schedule syntax, retry with correction

### Controlled Rollback Actions

1. **Disable policy** (stop scheduled backups)
   ```bash
   hcloud CBR DisassociateVaultPolicy --cli-region=<SOURCE_REGION> \
     --vault_id=<VAULT_ID> \
     --policy_id=<POLICY_ID>
   ```

2. **Remove resource from vault** (requires explicit approval)
   ```bash
   hcloud CBR RemoveVaultResource --cli-region=<SOURCE_REGION> \
     --vault_id=<VAULT_ID> \
     --resources='[{"id":"<RESOURCE_ID>","type":"<RESOURCE_TYPE>"}]'
   ```

3. **Delete policy** (requires explicit approval)
   ```bash
   hcloud CBR DeletePolicy --cli-region=<SOURCE_REGION> --policy_id=<POLICY_ID>
   ```

4. **Delete vault** (requires explicit approval, vault must be empty)
   ```bash
   hcloud CBR DeleteVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
   ```

## Verification
After each rollback action:
- Verify state with Show or List command
- Record evidence

## Outputs
- Rollback report with actions taken and results

## Stop conditions
- Rollback action fails
- Approval denied for rollback

## Approval requirements
- RemoveVaultResource: EXPLICIT
- DeletePolicy: EXPLICIT
- DeleteVault: EXPLICIT

## Safety
- Never delete backups automatically
- Never delete restored resources automatically
- Never delete the original resource
- Never overwrite original resource during restore
- Document all rollback actions with reason
