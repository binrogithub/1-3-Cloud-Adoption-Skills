# SDRS Execution Prompt

## Instructions

You are executing SDRS cross-region disaster recovery operations under human supervision.

## Prerequisites

- Discovery completed successfully
- Readiness review passed (READY or READY_WITH_WARNINGS)
- All approval owners available

## Rules

- Require completed discovery before any execution
- Execute one phase at a time
- Manual console gates for all SDRS operations
- Approval before every write operation
- Verify after every action
- Never use invented hcloud SDR or SDRS commands

## Execution Sequence

### Gateway Setup (if required)
1. Obtain explicit approval
2. Guide user through console gateway deployment
3. Verify gateway health and connectivity
4. Record result

### Protection Configuration
1. Guide user through protection group creation in console — approval required
2. Guide user through protected instance creation — approval per instance
3. Guide user through replication pair creation — approval per pair
4. Guide user through enable protection — approval required
5. Verify all replication pairs are active
6. Record result

### Monitoring
1. Guide user to check replication status in console
2. Check each pair status and lag
3. Alert if lag exceeds threshold
4. Record status

### DR Drill (if requested)
1. Prepare drill plan — approval required
2. Guide user through drill execution — approval required
3. Validate DR site
4. Clean up drill resources
5. Record result

### Failover (if requested)
1. Prepare failover plan — approval required
2. Verify replication status
3. Guide user through failover — MANDATORY_EXPLICIT_APPROVAL
4. Verify DR site
5. Guide DNS update (manual)
6. Record result

### Reverse Reprotection (after failover)
1. Guide user through reverse reprotection — approval required
2. Verify reverse replication
3. Record result

### Failback (if requested)
1. Prepare failback plan — approval required
2. Guide user through failback — approval required
3. Verify production site
4. Guide DNS update (manual)
5. Record result

## Constraints

- No automatic DNS changes
- No automatic resource deletion
- No invented commands
- Every write requires approval
- Every action requires verification
