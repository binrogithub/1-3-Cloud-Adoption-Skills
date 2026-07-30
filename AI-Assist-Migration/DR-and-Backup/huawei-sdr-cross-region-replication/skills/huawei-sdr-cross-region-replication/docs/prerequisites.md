# SDRS Prerequisites

## Required Tools and Resources

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI 6.2.9 | Yes | Discovery of ECS, EVS, VPC, subnet, SG, EIP, AZ | `hcloud version` |
| Huawei Cloud authentication | Yes | API access for discovery | `hcloud ECS ListServersDetails --cli-region=<REGION>` |
| Production region | Yes | Source site region | Specified in intent |
| DR region | Yes | Target site region | Specified in intent |
| Production AZ | Yes | Source availability zone | Specified in intent |
| DR AZ | Yes | Target availability zone | Specified in intent |
| SDRS regional availability | Yes | Service enabled in both regions | Console verification |
| Source ECS instances | Yes | Servers to protect | `hcloud ECS ListServersDetails --cli-region=<REGION>` |
| Source EVS disks | Yes | Disks to replicate | `hcloud EVS ListVolumes --cli-region=<REGION>` |
| Source VPC and subnet | Yes | Production network | `hcloud VPC ListVpcs --cli-region=<REGION>` |
| Target VPC and subnet | Yes | DR site network | `hcloud VPC ListVpcs --cli-region=<DR_REGION>` |
| Security groups | Yes | Network access control | `hcloud VPC ListSecurityGroups --cli-region=<REGION>` |
| Route and DNS plan | Yes | Failover cutover strategy | Documented in intent |
| Source and target capacity | Yes | Sufficient compute for DR | Console quota verification |
| DR gateway | Conditional | Cross-region replication channel | Console verification |
| Required IAM permissions | Yes | SDRS read/write, ECS/EVS read | Verified by successful discovery |
| Bandwidth requirement | Yes | Replication throughput | Network assessment |
| RPO target | Yes | Maximum acceptable data loss | Specified in intent |
| RTO target | Yes | Maximum acceptable recovery time | Specified in intent |
| Maintenance window | Yes | Scheduled operations window | Specified in intent |
| Failover approval owner | Yes | Authority for critical operations | Specified in intent |

## Optional Tools and Resources

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| huaweicloud-pricing MCP | No | Cost estimation of DR infrastructure | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| huaweicloud-deploy MCP | No | VPC/subnet/SG prerequisites | MCP availability check |
| Playwright | No | Console exploration and form discovery | Integration availability check |
| mcp-capability-builder | Yes | Future SDRS MCP design | Path verification |

## SDRS-Specific Prerequisites

- SDRS service must be available in both the production and DR regions
- The region pair must be supported by SDRS (not all combinations are supported)
- ECS instances must run a supported operating system
- EVS disk types must be supported by SDRS replication
- DR site must have sufficient ECS quota to host all protected instances
- DR site must have sufficient EVS quota for all replication pairs
- Cross-region connectivity must be established before gateway deployment

## Gateway Prerequisites (Cross-Region)

- DR gateway software compatible with SDRS version
- Network connectivity between production and DR regions
- Required ports open in both directions
- Sufficient bandwidth for replication traffic
- Gateway server meets minimum resource requirements
- IAM permissions for gateway installation and registration

## IAM Permissions Required

- SDRS: read and write in both regions
- ECS: read in both regions
- EVS: read in both regions
- VPC: read in both regions
- IAM: context read (no secrets)

## Verification Commands (hcloud read-only)

```bash
hcloud version
hcloud ECS ListServersDetails --cli-region=<REGION>
hcloud EVS ListVolumes --cli-region=<REGION>
hcloud VPC ListVpcs --cli-region=<REGION>
hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>
hcloud VPC ListSecurityGroups --cli-region=<REGION>
hcloud EIP ListPublicIps --cli-region=<REGION>
```

Note: SDRS-specific verification must be performed in the console. No hcloud SDRS commands exist.
