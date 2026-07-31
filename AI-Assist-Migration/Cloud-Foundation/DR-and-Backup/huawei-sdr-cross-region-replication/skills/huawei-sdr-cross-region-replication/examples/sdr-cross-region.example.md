# SDRS Cross-Region DR Example

## Scenario

Cross-region disaster recovery for a web application with database backend.

## Parameters

| Parameter | Value |
|---|---|
| Scenario | cross-region |
| Production region | `<PRODUCTION_REGION>` |
| DR region | `<DR_REGION>` |
| Production AZ | `<PRODUCTION_AZ>` |
| DR AZ | `<DR_AZ>` |
| Source ECS | `<WEB_SERVER_NAME>`, `<APP_SERVER_NAME>`, `<DB_SERVER_NAME>` |
| Disks | `<WEB_VOLUME_NAMES>`, `<APP_VOLUME_NAMES>`, `<DB_VOLUME_NAMES>` |
| RPO target | `<RPO_TARGET>` (e.g., 5 minutes) |
| RTO target | `<RTO_TARGET>` (e.g., 30 minutes) |
| Protection group | `<PROTECTION_GROUP_NAME>` |
| Gateway | `<DR_GATEWAY_NAME>` |
| Target VPC | `<TARGET_VPC_NAME>` |
| Target subnet | `<TARGET_SUBNET_NAME>` |

## Step-by-Step Walkthrough

### Step 1: Parse Intent

```
Scenario: cross-region
Production region: <PRODUCTION_REGION>
DR region: <DR_REGION>
Source ECS: <WEB_SERVER_NAME>, <APP_SERVER_NAME>, <DB_SERVER_NAME>
RPO target: <RPO_TARGET>
RTO target: <RTO_TARGET>
Approval owner: <APPROVAL_OWNER>
```

Artifact: `artifacts/sdr-intent.json`

### Step 2: Validate Service and Topology

- SDRS available in both regions: Confirmed (console)
- Region pair supported: Confirmed (documentation)
- Cross-region topology supported: Confirmed
- Replication mode: Async (cross-region)
- Gateway required: Yes

Artifact: `artifacts/sdr-capability-assessment.md`

### Step 3: Discover Production Resources

```bash
hcloud ECS ListServersDetails --cli-region=<PRODUCTION_REGION>
hcloud EVS ListVolumes --cli-region=<PRODUCTION_REGION>
hcloud VPC ListVpcs --cli-region=<PRODUCTION_REGION>
hcloud VPC ListSubnets --cli-region=<PRODUCTION_REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<PRODUCTION_REGION>
```

Resolved:
- `<WEB_SERVER_NAME>` → ID resolved, status ACTIVE
- `<APP_SERVER_NAME>` → ID resolved, status ACTIVE
- `<DB_SERVER_NAME>` → ID resolved, status ACTIVE

Artifact: `artifacts/sdr-source-inventory.json`

### Step 4: Discover DR-Site Resources

```bash
hcloud VPC ListVpcs --cli-region=<DR_REGION>
hcloud VPC ListSubnets --cli-region=<DR_REGION> --vpc_id=<TARGET_VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<DR_REGION>
```

Artifact: `artifacts/sdr-target-inventory.json`

### Step 5: Application Dependency Analysis

Recovery order:
1. `<DB_SERVER_NAME>` (database, must start first)
2. `<APP_SERVER_NAME>` (application, depends on database)
3. `<WEB_SERVER_NAME>` (web server, depends on application)

Artifact: `artifacts/sdr-application-dependency-map.md`

### Step 6: RPO/RTO Plan

- Target RPO: `<RPO_TARGET>`
- Target RTO: `<RTO_TARGET>`
- Replication mode: Async
- Monitoring interval: Every 5 minutes

Artifact: `artifacts/sdr-rpo-rto-plan.md`

### Step 7: Architecture Plan

- Protection group: `<PROTECTION_GROUP_NAME>`
- Protected instances: 3 (web, app, db)
- Replication pairs: `<TOTAL_REPLICATION_PAIRS>`
- Gateway: `<DR_GATEWAY_NAME>` at both sites
- DR site VPC: `<TARGET_VPC_NAME>`
- DR site subnet: `<TARGET_SUBNET_NAME>`

Artifact: `artifacts/sdr-architecture-plan.md`

### Step 8: Readiness Review

Result: READY

Artifact: `artifacts/sdr-readiness-report.md`

### Step 9: Gateway Setup (Manual Console)

1. Deploy gateway at production site
2. Deploy gateway at DR site
3. Verify connectivity
4. Verify registration

Artifact: `artifacts/sdr-gateway-result.md`

### Step 10: Configure Protection (Manual Console)

1. Create protection group `<PROTECTION_GROUP_NAME>` — APPROVED
2. Create protected instance for `<DB_SERVER_NAME>` — APPROVED
3. Create protected instance for `<APP_SERVER_NAME>` — APPROVED
4. Create protected instance for `<WEB_SERVER_NAME>` — APPROVED
5. Create replication pairs for all volumes — APPROVED
6. Enable protection — APPROVED
7. Verify all pairs replicating

Artifact: `artifacts/sdr-protection-result.md`

### Step 11: Monitor Replication

- All pairs: Active
- Replication lag: Within threshold
- Gateway: Healthy

Artifact: `artifacts/sdr-replication-status-report.md`

### Step 12: DR Drill (Optional)

1. Create drill — APPROVED
2. Start drill servers at DR site
3. Validate applications
4. Measure RPO and RTO
5. Clean up drill

Artifact: `artifacts/sdr-drill-result.md`

### Step 13: Failover Plan

- Type: Planned
- Trigger: Scheduled maintenance
- DNS change: Update to DR site EIP
- Validation: Application tests

Artifact: `artifacts/sdr-failover-plan.md`

### Step 14: Execute Failover (Manual Console)

1. Verify replication status — all pairs active
2. Execute planned failover — MANDATORY_EXPLICIT_APPROVAL
3. Start DR site servers (db first, then app, then web)
4. Update DNS manually
5. Validate applications
6. Measure RPO and RTO

Artifact: `artifacts/sdr-failover-result.md`

### Step 15: Reverse Reprotection (Manual Console)

1. Verify DR site stable
2. Execute reverse reprotection — APPROVED
3. Verify reverse replication active

Artifact: `artifacts/sdr-reverse-reprotection-plan.md`

### Step 16: Failback (Manual Console)

1. Verify reverse replication synchronized
2. Create failback plan — APPROVED
3. Execute failback — APPROVED
4. Start production servers
5. Update DNS manually
6. Validate applications

Artifact: `artifacts/sdr-failback-plan.md`

### Step 17: Closure

Artifact: `artifacts/sdr-final-report.md`
