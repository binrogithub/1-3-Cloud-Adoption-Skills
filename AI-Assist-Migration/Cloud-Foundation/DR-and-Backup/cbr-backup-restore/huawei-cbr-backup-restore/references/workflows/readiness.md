# Readiness Workflow

## Objective
Verify all prerequisites are met before backup execution.

## Inputs
- vault_id (from discovery or plan)
- source_resource_id
- resource_type

## Steps

1. Verify vault exists and is accessible
   ```bash
   hcloud CBR ShowVault --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
   ```

2. Verify vault has sufficient capacity
   - Check vault.billing.size vs current usage
   - Use ShowSummary for aggregate view:
   ```bash
   hcloud CBR ShowSummary --cli-region=<SOURCE_REGION>
   ```

3. Verify resource is associated with vault
   - Check vault resource list includes source_resource_id

4. Verify resource state is compatible
   - ECS: ACTIVE
   - EVS: available or in-use

5. Verify agent status (for ECS application-consistent backup)
   ```bash
   hcloud CBR ListAgent --cli-region=<SOURCE_REGION>
   ```

6. Verify backup quota
   ```bash
   hcloud CBR ListBackups --cli-region=<SOURCE_REGION> --vault_id=<VAULT_ID>
   ```

7. Verify policy association (for scheduled backups)
   ```bash
   hcloud CBR ShowPolicy --cli-region=<SOURCE_REGION> --policy_id=<POLICY_ID>
   ```

## Verification
- Vault accessible and has capacity
- Resource associated and in compatible state
- Agent present (for ECS app-consistent)
- Quota available

## Outputs
- Readiness report (pass/fail per check)

## Stop conditions
- Vault not found or no capacity
- Resource not associated
- Resource state incompatible
- Agent missing (for app-consistent requirement)
- Quota exceeded

## Approval requirements
None (all read-only)
