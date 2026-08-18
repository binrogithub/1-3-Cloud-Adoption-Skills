# SDRS Rollback Workflow

## Objective

Define rollback procedures for each execution phase when failures occur.

## Rollback Principles

1. Failover rollback may require reprotection or failback — no simple undo
2. Never assume immediate reversal
3. Preserve both sites at all times
4. Prevent simultaneous active writers (split-brain)
5. DNS rollback is separate and manual
6. Data divergence must be assessed
7. No automatic deletion

## Rollback Procedures

### Gateway Setup Failure

1. Clean up partially installed gateway resources manually
2. Verify network configuration
3. Document failure cause
4. Retry with corrected configuration

### Protection Configuration Failure

1. Remove partially created resources in console
2. Verify no orphaned replication pairs
3. Document failure cause
4. Retry from beginning of protection configuration

### Replication Degradation or Failure

1. Assess replication pair status in console
2. Check source and target volume health
3. Check network connectivity
4. If pair is recoverable: re-enable protection
5. If pair is irrecoverable: recreate pair (requires approval)
6. Document failure and recovery

### DR Drill Failure

1. Clean up drill resources manually
2. Verify production is unaffected
3. Document drill failure
4. No production impact

### Failover Failure

**CRITICAL**: Both sites may be in uncertain state.

1. DO NOT modify either site automatically
2. Assess state of both sites manually
3. Determine which site has most recent consistent data
4. If DR site is functional: remain at DR site
5. If DR site is not functional: attempt production recovery
6. If neither is functional: escalate immediately

### Reverse Reprotection Failure

1. DR site is UNPROTECTED — critical state
2. Attempt to re-establish reverse reprotection
3. If not possible: consider CBR backup as temporary protection
4. Escalate immediately

### Failback Failure

1. Remain at DR site
2. Verify DR site is stable
3. Document failure cause
4. Re-attempt only after resolving cause
5. Do not force failback

### DNS Rollback

1. Verify target site is functional
2. Update DNS records manually
3. Verify end-user access
4. Document before/after state
