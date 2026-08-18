# SDRS Execution Workflow

## Objective

Execute SDRS protection configuration, monitoring, drill, failover, reverse reprotection, and failback operations under human supervision.

## Prerequisites

- Readiness review passed (READY or READY_WITH_WARNINGS)
- All approval owners available

## Execution Phases

### Phase 1: Gateway Setup (Cross-Region Only)

**Mechanism**: MANUAL_CONSOLE

1. Obtain explicit approval
2. Deploy DR gateway at production site (console)
3. Deploy DR gateway at DR site (console)
4. Verify gateway health and connectivity
5. Record result in artifacts/sdr-gateway-result.md

### Phase 2: Protection Configuration

**Mechanism**: MANUAL_CONSOLE

1. Create protection group (console) — requires approval
2. Create protected instances (console) — requires approval per instance
3. Create replication pairs (console) — requires approval per pair
4. Enable protection (console) — requires approval
5. Verify all replication pairs are active
6. Record result in artifacts/sdr-protection-result.md

### Phase 3: Replication Monitoring

**Mechanism**: ASSISTED (periodic console checks)

1. Check protection group status
2. Check each protected instance status
3. Check each replication pair status and lag
4. Check gateway health
5. Record status in artifacts/sdr-replication-status-report.md
6. Alert if lag exceeds threshold or status is degraded

### Phase 4: DR Drill (Optional)

**Mechanism**: MANUAL_CONSOLE

1. Prepare drill plan — requires approval
2. Execute drill in console — requires approval
3. Validate DR site applications
4. Measure RPO and RTO
5. Clean up drill resources
6. Record result in artifacts/sdr-drill-result.md

### Phase 5: Failover

**Mechanism**: MANUAL_CONSOLE (CRITICAL)

1. Prepare failover plan — requires approval
2. Verify replication status
3. Execute failover in console — MANDATORY_EXPLICIT_APPROVAL
4. Verify DR site servers running
5. Update DNS manually
6. Validate applications at DR site
7. Measure RPO and RTO
8. Record result in artifacts/sdr-failover-result.md

### Phase 6: Reverse Reprotection

**Mechanism**: MANUAL_CONSOLE

1. Verify DR site is stable
2. Execute reverse reprotection in console — requires approval
3. Verify reverse replication active
4. Record plan in artifacts/sdr-reverse-reprotection-plan.md

### Phase 7: Failback

**Mechanism**: MANUAL_CONSOLE (CRITICAL)

1. Verify reverse replication synchronized
2. Create failback plan — requires approval
3. Execute failback in console — requires approval
4. Verify production site functional
5. Update DNS manually
6. Record plan in artifacts/sdr-failback-plan.md

## Constraints

- Every write operation requires explicit approval
- Every operation is followed by verification
- No automatic DNS changes
- No automatic resource deletion
- No invented hcloud SDRS commands
