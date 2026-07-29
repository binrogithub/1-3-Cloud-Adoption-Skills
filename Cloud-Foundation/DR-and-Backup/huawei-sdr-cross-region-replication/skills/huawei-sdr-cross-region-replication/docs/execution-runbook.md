# SDRS Execution Runbook

## Overview

This runbook provides step-by-step instructions for executing SDRS cross-region disaster recovery operations. All SDRS operations are performed manually via the Huawei Cloud console.

## Pre-Execution Checklist

- [ ] Intent parsed and validated (Step 1)
- [ ] SDRS service and topology validated (Step 2)
- [ ] Production resources discovered (Step 3)
- [ ] DR site resources discovered (Step 4)
- [ ] Application dependencies mapped (Step 5)
- [ ] RPO/RTO plan approved (Step 6)
- [ ] Architecture plan approved (Step 7)
- [ ] Readiness review passed (Step 8)

## Step 9: DR Gateway Setup (Cross-Region Only)

### Console Navigation
1. Log in to Huawei Cloud console (production region)
2. Navigate to Storage Disaster Recovery Service
3. Select the target protection group or create gateway first
4. Follow the gateway deployment wizard

### Verification
- Gateway status: Running
- Network connectivity: Verified
- Registration: Both sites registered
- Ports: Required ports open

### Security Notes
- Do NOT embed AK/SK in commands
- Use IAM agency or temporary credentials
- Warn about credential exposure in shell history
- Recommend secure credential delivery

## Step 10: Configure Protection

### Create Protection Group
1. Navigate to SDRS console
2. Click "Create Protection Group"
3. Enter name, select source domain (production AZ), target domain (DR AZ)
4. Submit and verify creation

### Create Protected Instances
For each ECS server:
1. Select protection group
2. Click "Create Protected Instance"
3. Select source server and target server configuration
4. Submit and verify creation

### Create Replication Pairs
For each EVS volume:
1. Select protection group
2. Click "Create Replication Pair"
3. Select source volume and target volume configuration
4. Submit and verify creation

### Enable Protection
1. Select protection group
2. Click "Enable Protection"
3. Confirm the action
4. Wait for all replication pairs to become active
5. Verify replication status

## Step 11: Monitor Replication

### Periodic Checks (Console)
1. Navigate to SDRS console
2. View protection group status
3. Check each protected instance status
4. Check each replication pair status and lag
5. Check gateway health
6. Record status in artifacts/sdr-replication-status-report.md

### Alert Thresholds
- Replication lag exceeds RPO target
- Replication pair status: degraded or failed
- Gateway status: unhealthy
- Protected instance status: error

## Step 12-13: DR Drill

### Prepare
1. Define drill scope
2. Define validation criteria
3. Define cleanup procedure
4. Obtain approval

### Execute
1. Navigate to SDRS console
2. Select protection group
3. Click "Create DR Drill"
4. Wait for drill resources to be created
5. Start drill servers
6. Validate applications
7. Measure RPO and RTO
8. Clean up drill resources

### Important
- A drill does NOT modify production
- A drill does NOT change DNS
- A drill is NOT a production failover

## Step 14-15: Failover

### Planned Failover
1. Verify replication status (all pairs active, lag within threshold)
2. Obtain MANDATORY_EXPLICIT_APPROVAL
3. Optionally quiesce applications at production site
4. Navigate to SDRS console
5. Select protection group
6. Click "Planned Failover"
7. Wait for failover to complete
8. Verify DR site servers are running
9. Update DNS manually (per DNS plan)
10. Validate applications at DR site
11. Measure RPO and RTO

### Unplanned Failover
1. Confirm primary site is unavailable (CRITICAL decision)
2. Obtain MANDATORY_EXPLICIT_APPROVAL
3. Navigate to SDRS console
4. Select protection group
5. Click "Unplanned Failover"
6. Wait for failover to complete
7. Start DR site servers
8. Update DNS manually
9. Validate applications at DR site
10. Assess data loss (compare last replication state)

## Step 16: Reverse Reprotection

1. Verify DR site is stable
2. Verify original production site is accessible
3. Obtain explicit approval
4. Navigate to SDRS console
5. Select protection group
6. Click "Reverse Reprotection"
7. Wait for reverse replication to activate
8. Monitor replication lag
9. Verify protection status

### Important
- Reverse reprotection is NOT failback
- It only re-establishes replication in the reverse direction
- Failback is a separate operation

## Step 17: Failback

1. Verify reverse replication is synchronized
2. Create failback plan (separate from failover plan)
3. Obtain explicit approval
4. Optionally quiesce applications at DR site
5. Execute failback in console
6. Start production site servers
7. Update DNS to point to production site
8. Validate applications at production site
9. Re-establish original replication direction
10. Measure RPO and RTO

## Post-Execution

- Document all actions with timestamps
- Record all approval decisions
- Preserve both sites until explicit cleanup approval
- Generate final report (Step 18)
