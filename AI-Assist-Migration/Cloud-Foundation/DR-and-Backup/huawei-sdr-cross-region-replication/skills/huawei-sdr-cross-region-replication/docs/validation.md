# SDRS Validation

## Validation Stages

### Pre-Protection Validation

| Check | Method | Pass Criteria |
|---|---|---|
| SDRS available in both regions | Console | Service accessible |
| Region pair supported | Documentation + console | Pair listed in supported pairs |
| ECS OS supported | Documentation | OS in supported list |
| EVS disk type supported | Documentation | Disk type in supported list |
| DR site capacity sufficient | Console quota check | Quota >= protected instance count |
| DR site VPC configured | hcloud CLI | VPC exists with required subnets |
| DR site security groups configured | hcloud CLI | SGs exist with required rules |
| Network connectivity verified | Console or network test | Gateway can reach both sites |
| IAM permissions verified | Discovery test | Discovery commands succeed |

### Post-Protection Validation

| Check | Method | Pass Criteria |
|---|---|---|
| Protection group created | Console | Status: available |
| Protected instances created | Console | Status: available |
| Replication pairs created | Console | Status: available |
| Protection enabled | Console | Replication status: replicating |
| Replication lag within threshold | Console | Lag < RPO target |
| Gateway healthy | Console | Status: running |

### Post-Drill Validation

| Check | Method | Pass Criteria |
|---|---|---|
| Drill servers boot | Console | Status: active |
| Application functional | Application test | Tests pass |
| Data consistent | Data validation | Within acceptable range |
| RPO within target | Measurement | RPO <= target |
| RTO within target | Measurement | RTO <= target |
| Production unaffected | Production monitoring | No impact detected |

### Post-Failover Validation

| Check | Method | Pass Criteria |
|---|---|---|
| DR site servers running | Console | Status: active |
| Applications functional | Application test | Tests pass |
| DNS points to DR site | DNS check | Resolves to DR site |
| End-user access verified | External test | Access successful |
| RPO measured | Measurement | Documented |
| RTO measured | Measurement | Documented |
| Production site preserved | Console | Resources intact |

### Post-Failback Validation

| Check | Method | Pass Criteria |
|---|---|---|
| Production site servers running | Console | Status: active |
| Applications functional | Application test | Tests pass |
| DNS points to production | DNS check | Resolves to production |
| Replication re-established | Console | Status: replicating |
| End-user access verified | External test | Access successful |

## Verification Commands (hcloud read-only)

```bash
hcloud ECS ListServersDetails --cli-region=<REGION>
hcloud EVS ListVolumes --cli-region=<REGION>
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSecurityGroups --cli-region=<REGION>
hcloud EIP ListPublicIps --cli-region=<REGION>
```

SDRS-specific validation must be performed in the console.
