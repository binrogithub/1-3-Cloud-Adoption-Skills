# SDRS Lessons Learned

## Capability Gap Lessons

1. **No CLI support is a fundamental blocker for automation**: SDRS absence from hcloud CLI means all operations are manual. This cannot be worked around without building a dedicated MCP.

2. **Manual console operations require disciplined documentation**: Every console action must be recorded with timestamps, results, and identifiers. Without this, traceability is lost.

3. **Failover is irreversible in practice**: While SDRS supports failback, the process is complex and time-consuming. Treat failover as a one-way door that requires a separate failback plan.

4. **Reverse reprotection is commonly misunderstood**: Teams often assume that reverse reprotection automatically means failback. These are distinct operations with different prerequisites.

5. **DR drills are essential but not sufficient**: A successful drill does not guarantee a successful production failover. Drills should be conducted regularly but with realistic expectations.

6. **Network configuration at DR site is often overlooked**: SDRS replicates disks but does not configure network infrastructure. VPC, subnet, security groups, routes, and DNS must be pre-configured.

7. **RPO targets may not be achievable under load**: Asynchronous replication lag depends on data change rate and bandwidth. Under peak load, actual RPO may exceed the target.

## Process Lessons

1. **Discover before create applies even to manual operations**: Check for existing protection groups, instances, and pairs before creating new ones.

2. **Approval gates prevent catastrophic mistakes**: Every critical operation (failover, failback, reverse reprotection) must require explicit approval from a designated authority.

3. **DNS is the most error-prone part of failover**: DNS cutover is manual and often forgotten or misconfigured. Include DNS verification in every failover plan.

4. **Both sites must be preserved after failover**: Never delete the original production site after failover. It may be needed for failback or data recovery.

5. **Split-brain prevention is critical**: After failover, ensure the original production site cannot accept writes. This prevents data divergence.

## Technical Lessons

1. **Gateway health is a prerequisite for all operations**: If the DR gateway is unhealthy, no SDRS operations will succeed. Monitor gateway health continuously.

2. **Region pair support is not universal**: Not all region combinations are supported. Verify the specific pair before designing the architecture.

3. **EVS disk type matters**: Not all disk types are supported for SDRS replication. Verify disk type compatibility before attempting protection.

4. **OS support varies**: Not all operating systems are supported. Check the supported OS list for the SDRS version.

5. **Quota at DR site is a common blocker**: The DR site must have sufficient ECS and EVS quota to host all protected instances. Request quota increases proactively.
