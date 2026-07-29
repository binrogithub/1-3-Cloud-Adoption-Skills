# SDRS Discovery Prompt

## Instructions

You are performing discovery for an SDRS cross-region disaster recovery scenario.

## Rules

- All operations are READ-ONLY
- No console write operations during discovery
- No Playwright write operations during discovery
- Produce inventories, not configurations

## Steps

1. Parse the user's intent to extract: scenario, production region, DR region, AZs, ECS names, disk scope, RPO, RTO, approval owner, and all optional parameters.

2. Validate SDRS service availability:
   - Check official documentation for SDRS availability in both regions
   - Verify region pair support
   - Confirm topology support (cross-region or cross-AZ)
   - Do NOT use hcloud SDR or SDRS commands (they do not exist)

3. Discover production resources using hcloud CLI (read-only):
   - ECS instances: `hcloud ECS ListServersDetails --cli-region=<PRODUCTION_REGION>`
   - EVS volumes: `hcloud EVS ListVolumes --cli-region=<PRODUCTION_REGION>`
   - VPC: `hcloud VPC ListVpcs --cli-region=<PRODUCTION_REGION>`
   - Subnets: `hcloud VPC ListSubnets --cli-region=<PRODUCTION_REGION> --vpc_id=<VPC_ID>`
   - Security groups: `hcloud VPC ListSecurityGroups --cli-region=<PRODUCTION_REGION>`
   - EIPs: `hcloud EIP ListPublicIps --cli-region=<PRODUCTION_REGION>`

4. Discover DR site resources using hcloud CLI (read-only):
   - Same commands with DR region
   - Check for existing SDRS resources via console exploration

5. Resolve names to IDs:
   - Exact match required
   - Reject zero matches
   - Reject ambiguous multiple matches
   - Record ID and state for each resource

6. Generate inventories:
   - artifacts/sdr-source-inventory.json
   - artifacts/sdr-target-inventory.json

## Output

Complete inventories of production and DR site resources with names resolved to IDs.
