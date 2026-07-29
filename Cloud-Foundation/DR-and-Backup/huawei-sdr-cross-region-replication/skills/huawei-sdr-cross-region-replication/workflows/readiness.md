# SDRS Readiness Workflow

## Objective

Validate all prerequisites and readiness conditions before SDRS protection configuration.

## Prerequisites

- Discovery completed (artifacts/sdr-source-inventory.json and artifacts/sdr-target-inventory.json exist)
- Architecture plan generated (artifacts/sdr-architecture-plan.md exists)

## Checklist

### Regional Support

- [ ] SDRS available in production region
- [ ] SDRS available in DR region
- [ ] Region pair supported by SDRS
- [ ] AZ pair supported (if cross-AZ)

### Quotas

- [ ] Protection group quota sufficient in both regions
- [ ] Protected instance quota sufficient in DR region
- [ ] Replication pair quota sufficient in DR region
- [ ] ECS quota sufficient in DR region (for all protected instances)
- [ ] EVS quota sufficient in DR region (for all replication pairs)

### IAM

- [ ] SDRS permissions verified in production region
- [ ] SDRS permissions verified in DR region
- [ ] ECS read permissions verified in both regions
- [ ] EVS read permissions verified in both regions

### OS and Server Support

- [ ] All source ECS instances run supported OS
- [ ] All source ECS flavors are supported by SDRS
- [ ] All source EVS disk types are supported by SDRS

### Network

- [ ] DR site VPC exists and is configured
- [ ] DR site subnet exists and is configured
- [ ] DR site security groups exist and have required rules
- [ ] Cross-region connectivity established (for cross-region)
- [ ] Bandwidth sufficient for replication

### Application

- [ ] Application dependencies mapped
- [ ] Recovery order defined
- [ ] Consistency requirements documented

### DR Plan

- [ ] DNS cutover plan documented
- [ ] Failover plan documented
- [ ] Failback plan documented
- [ ] Approval owner identified and available

### Gateway (Cross-Region)

- [ ] Gateway prerequisites met (if required)
- [ ] Gateway server resources available
- [ ] Required ports identified and can be opened

## Result Classification

| Result | Condition | Action |
|---|---|---|
| READY | All checks pass | Proceed to execution |
| READY_WITH_WARNINGS | Non-critical warnings present | Proceed with documented warnings |
| NOT_READY | Critical prerequisites missing | Stop, report failures |
| BLOCKED | Fundamental blocker exists | Stop, report blocker |

## Output

- artifacts/sdr-readiness-report.md
