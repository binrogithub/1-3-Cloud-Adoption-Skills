# SDRS Discovery Workflow

## Objective

Discover all resources relevant to the SDRS cross-region DR scenario in both production and DR regions.

## Prerequisites

- hcloud CLI 6.2.9 installed and authenticated
- Production region specified
- DR region specified

## Steps

### 1. Verify hcloud and Authentication

```bash
hcloud version
hcloud ECS ListServersDetails --cli-region=<PRODUCTION_REGION> --limit=1
hcloud ECS ListServersDetails --cli-region=<DR_REGION> --limit=1
```

### 2. Discover Production Resources

```bash
hcloud ECS ListServersDetails --cli-region=<PRODUCTION_REGION>
hcloud EVS ListVolumes --cli-region=<PRODUCTION_REGION>
hcloud VPC ListVpcs --cli-region=<PRODUCTION_REGION>
hcloud VPC ListSubnets --cli-region=<PRODUCTION_REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<PRODUCTION_REGION>
hcloud EIP ListPublicIps --cli-region=<PRODUCTION_REGION>
```

### 3. Discover DR Site Resources

```bash
hcloud ECS ListServersDetails --cli-region=<DR_REGION>
hcloud EVS ListVolumes --cli-region=<DR_REGION>
hcloud VPC ListVpcs --cli-region=<DR_REGION>
hcloud VPC ListSubnets --cli-region=<DR_REGION> --vpc_id=<TARGET_VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<DR_REGION>
hcloud EIP ListPublicIps --cli-region=<DR_REGION>
```

### 4. Discover SDRS Resources (Manual Console)

Navigate to SDRS console in both regions:
- List existing protection groups
- List existing protected instances
- List existing replication pairs
- Check DR gateway status

### 5. Resolve Names to IDs

For each source ECS name:
- Find exact match in ECS list
- Reject zero matches
- Reject ambiguous multiple matches
- Record ID and state

### 6. Generate Inventories

- artifacts/sdr-source-inventory.json
- artifacts/sdr-target-inventory.json

## Constraints

- All commands are read-only
- No SDRS CLI commands exist (do not invent them)
- No console write operations during discovery
- No Playwright write operations during discovery
