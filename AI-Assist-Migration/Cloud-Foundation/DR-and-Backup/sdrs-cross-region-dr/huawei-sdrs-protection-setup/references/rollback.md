# SDRS Rollback

## Rollback Principles

1. Failover rollback may require reprotection or failback — there is no simple "undo"
2. Never assume immediate reversal is possible
3. Preserve both sites (production and DR) at all times
4. Prevent simultaneous active writers on both sites (split-brain prevention)
5. DNS rollback is a separate manual operation
6. Data divergence must be assessed before any rollback
7. No automatic deletion of resources

## Rollback by Phase

### Gateway Setup Failure
- Clean up partially installed gateway resources manually
- Verify network configuration
- Retry with corrected configuration
- No data loss risk

### Protection Configuration Failure
- Remove partially created resources in console (protection group, instances, pairs)
- Verify no orphaned replication pairs exist
- Retry from the beginning of protection configuration
- No data loss risk (replication had not started)

### Replication Failure
- Replication may be degraded but data is not lost
- Assess replication pair status in console
- If a pair is failed, check source and target volume health
- Re-enable protection or recreate failed pairs
- Low data loss risk (existing data preserved)

### DR Drill Failure
- Clean up drill resources manually in console
- Verify production is unaffected
- No production impact
- Document drill failure for analysis

### Failover Failure
- **CRITICAL**: Both sites may be in an uncertain state
- DO NOT modify either site automatically
- Assess the state of both sites manually
- Determine which site has the most recent consistent data
- Decide next action based on data consistency assessment
- If DR site is functional: remain at DR site, proceed with validation
- If DR site is not functional: attempt to recover production site
- If neither site is functional: escalate immediately

### Reverse Reprotection Failure
- DR site is UNPROTECTED — this is a critical state
- Attempt to re-establish reverse reprotection
- If not possible, consider CBR backup as temporary protection
- Escalate immediately

### Failback Failure
- Remain at DR site (it is functional)
- Verify DR site is stable
- Re-attempt failback only after resolving the failure cause
- Do not force failback
- Document the failure and timeline

## DNS Rollback

DNS rollback is always manual:
1. Verify the target site is functional
2. Update DNS records to point to the target site
3. Verify end-user access
4. Document the DNS change with before/after state

## Data Divergence Assessment

After any failed operation that may have caused data divergence:
1. Compare data at both sites (application-level consistency check)
2. Determine which site has the authoritative data
3. Document the divergence
4. Decide on reconciliation strategy
5. Never assume automatic reconciliation
