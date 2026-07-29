# SDRS Validation Workflow

## Objective

Validate SDRS configuration, replication status, and recovery readiness at each stage.

## Validation Points

### After Protection Configuration

1. Protection group status: available
2. All protected instances: available
3. All replication pairs: available
4. Protection enabled: replicating
5. Replication lag: within threshold

### After DR Drill

1. Drill servers: booted and active
2. Application tests: pass
3. Data consistency: acceptable
4. RPO: within target
5. RTO: within target
6. Production: unaffected

### After Failover

1. DR site servers: running
2. Applications: functional
3. DNS: points to DR site
4. End-user access: verified
5. RPO: measured and documented
6. RTO: measured and documented
7. Production site: preserved

### After Reverse Reprotection

1. Reverse replication: active
2. Replication lag: within threshold
3. Original production site: accessible

### After Failback

1. Production site servers: running
2. Applications: functional
3. DNS: points to production
4. Replication: re-established in original direction
5. End-user access: verified

## Verification Commands (hcloud read-only)

```bash
hcloud ECS ListServersDetails --cli-region=<REGION>
hcloud EVS ListVolumes --cli-region=<REGION>
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSecurityGroups --cli-region=<REGION>
hcloud EIP ListPublicIps --cli-region=<REGION>
```

SDRS-specific validation is performed in the console.

## Output

- Validation results recorded in respective phase artifacts
- Final validation in artifacts/sdr-final-report.md
