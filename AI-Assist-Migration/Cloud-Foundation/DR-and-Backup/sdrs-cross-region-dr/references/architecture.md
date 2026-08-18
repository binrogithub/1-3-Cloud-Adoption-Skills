# SDRS Cross-Region DR Architecture

## Overview

SDRS (Storage Disaster Recovery Service) provides cross-region and cross-AZ disaster recovery for Huawei Cloud ECS instances by replicating EVS volumes to a DR site.

## Core Concepts

| Concept | Description |
|---|---|
| Protection Group | Container for protected instances and replication pairs; defines source and target domains |
| Protected Instance | Mapping between a production ECS server and its DR-site counterpart |
| Replication Pair | Pair of EVS volumes (production + DR) with active data replication |
| DR Gateway | Server-side component required for cross-region replication channel |
| Replication Mode | Async (cross-region), sync or async (cross-AZ) |

## Architecture Components

### Production Site
- ECS instances running production workloads
- EVS volumes attached to ECS instances
- VPC, subnet, security groups, EIP, load balancers
- DR gateway (for cross-region)

### DR Site
- ECS instances (stopped, waiting for failover)
- EVS volumes (receiving replicated data)
- VPC, subnet, security groups, EIP, load balancers (must be pre-configured)
- DR gateway (for cross-region)

### Replication Flow
```
Production EVS → DR Gateway → Network → DR Gateway → DR EVS
```

## Topology: Cross-Region

- Requires DR gateway at both sites
- Asynchronous replication only
- RPO depends on data change rate, bandwidth, and latency
- Region pair must be supported by SDRS
- Network connectivity between regions required (VPC peering or cloud connection)

## Topology: Cross-AZ

- May or may not require DR gateway (version-dependent)
- May support synchronous or asynchronous replication
- Lower latency than cross-region
- Same region, different AZ

## Failover Sequence

1. Verify replication status
2. Execute failover (planned or unplanned)
3. Start DR-site servers
4. Verify DR-site application functionality
5. Update DNS to point to DR site (manual)
6. Verify end-user access

## Reverse Reprotection Sequence

1. Verify DR-site is stable and functional
2. Verify original production site is accessible
3. Execute reverse reprotection in console
4. Verify reverse replication is active
5. Monitor replication lag

## Failback Sequence

1. Verify reverse replication is synchronized
2. Plan failback (separate from failover plan)
3. Quiesce applications at DR site (if possible)
4. Execute failback
5. Start production-site servers
6. Verify production application functionality
7. Update DNS to point to production site (manual)
8. Verify end-user access
9. Re-establish original replication direction

## Network Requirements

- DR site VPC must mirror production VPC structure
- Security groups must allow required application traffic
- Route tables must be configured for DR site
- EIP or load balancer must be available at DR site
- Cross-region connectivity (VPC peering or cloud connection) for gateway communication

## Classification of Architecture Elements

| Element | Classification | Mechanism |
|---|---|---|
| Protection group | CREATE_MANUALLY | Console |
| Protected instance | CREATE_MANUALLY | Console |
| Replication pair | CREATE_MANUALLY | Console |
| DR gateway | CREATE_MANUALLY | Console or script |
| DR site VPC | CREATE_WITH_EXISTING_MCP or CREATE_MANUALLY | deploy MCP or console |
| DR site subnet | CREATE_WITH_EXISTING_MCP or CREATE_MANUALLY | deploy MCP or console |
| DR site security groups | CREATE_WITH_EXISTING_MCP or CREATE_MANUALLY | deploy MCP or console |
| DR site EIP | CREATE_MANUALLY | Console |
| DNS changes | MANUAL | Manual process |
| Monitoring | ASSISTED | Console periodic check |
