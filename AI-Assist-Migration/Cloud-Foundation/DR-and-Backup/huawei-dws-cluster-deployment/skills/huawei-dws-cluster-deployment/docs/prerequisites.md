# DWS Cluster Deployment Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI 6.2.9 | Yes | DWS cluster lifecycle operations | `hcloud DWS --help` returns operations |
| Huawei Cloud authentication | Yes | API access | Configured profile with AK/SK or token |
| Target region | Yes | DWS service availability | `hcloud DWS ListClusters --cli-region=<REGION>` succeeds |
| Project context | Yes | Resource scoping | Project ID in hcloud profile |
| DWS service availability | Yes | Service enabled in region | `hcloud DWS ListNodeTypes --cli-region=<REGION>` returns types |
| Supported AZ | Yes | Cluster placement | Discovered from region query |
| Supported engine version | Yes | Cluster version | Discovered from ListNodeTypes or ListUpdatableVersion |
| Supported node type | Yes | Cluster sizing | `hcloud DWS ListNodeTypes --cli-region=<REGION>` |
| Supported storage type | Yes | Cluster storage | Discovered from ListNodeTypes response |
| VPC | Yes | Network isolation | `hcloud VPC ListVpcs --cli-region=<REGION>` |
| Subnet | Yes | Cluster network | `hcloud VPC ListSubnets --cli-region=<REGION> --vpc_id=<VPC_ID>` |
| Security group | Yes | Access control | `hcloud VPC ListSecurityGroups --cli-region=<REGION>` |
| Sufficient subnet IP capacity | Yes | Node addressing | Calculated: available IPs >= node_count + buffer |
| IAM permissions | Yes | DWS create/manage | DWS Administrator or equivalent role |
| DWS quota | Yes | Cluster limit | Quota API or console check |
| Compute or node quota | Yes | Node limit | Quota API or console check |
| Storage quota | Yes | Storage limit | Quota API or console check |
| Database administrator password source | Yes | Secure credential | Never plain text; use --cli-jsonInput or env var |
| Private DNS or endpoint plan | Yes | Post-deployment connectivity | DNS configuration or direct endpoint |
| Optional EIP | No | Public access | `hcloud VPC ListPublicIps --cli-region=<REGION>` |
| Optional OBS bucket | No | Data loading | OBS bucket in same region as cluster |
| Optional huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| Optional huaweicloud-ticket MCP | No | Support tickets | MCP availability check |
| Optional huaweicloud-deploy MCP | No | VPC/subnet/SG prerequisites | MCP availability check |
| mcp-capability-builder shared skill | Yes (shared) | Future MCP extension design | Skill directory exists |

## Cluster Name Constraints

- 4 to 64 characters
- Must start with a letter
- Only letters, digits, hyphens (-), and underscores (_) allowed
- Must be unique within the project/region scope

[VERIFIED_FROM_LOCAL_HELP]

## Administrator Username Constraints

- Lowercase letters, digits, or underscores
- Start with a lowercase letter or underscore
- 1 to 63 characters
- Cannot be a DWS database keyword

[VERIFIED_FROM_LOCAL_HELP]

## Password Constraints

- 8 to 32 characters
- Cannot be the same as the username or username reversed
- At least three of: lowercase, uppercase, digits, special characters (~!?,.:;-_'"(){}[]/<>@#%^&*+|\=)
- Cannot be the same as previous passwords
- Cannot be a weak password

[VERIFIED_FROM_LOCAL_HELP]

## Node Count Constraints

- Cluster mode: 3 to 256 nodes
- Standalone (hybrid) mode: 1 node
- CN count: 2 to min(node_count, 20), default 3

[VERIFIED_FROM_LOCAL_HELP]

## Port Range

- 8000 to 30000
- Default: 8000

[VERIFIED_FROM_LOCAL_HELP]
