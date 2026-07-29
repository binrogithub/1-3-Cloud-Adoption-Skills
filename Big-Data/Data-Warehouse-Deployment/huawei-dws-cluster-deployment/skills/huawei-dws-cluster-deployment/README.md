# Huawei DWS Cluster Deployment

## Purpose

Discover, plan, deploy, validate and configure a Huawei Cloud DWS (GaussDB(DWS)) data warehouse cluster using verified hcloud CLI operations and controlled approval gates.

## Supported scenario

- Deploy a new DWS cluster for data warehousing workloads
- Discover available DWS node types, versions, and capabilities
- Plan capacity and cost before deployment
- Validate prerequisites (VPC, subnet, security group)
- Configure snapshot policies
- Verify cluster health and connectivity

## Architecture

DWS cluster deployment follows a 20-step workflow from intent parsing to closure, using hcloud DWS CLI as the primary mechanism with optional MCP support for prerequisites and cost estimation.

## Rules summary

1. PostgreSQL compatibility is partial — do not assume full compatibility
2. Engine version must be discovered per region — never hardcode
3. Node types must be discovered via ListNodeTypes — never hardcode flavors
4. Cluster requires pre-existing VPC, subnet, security group
5. Never open DWS port to 0.0.0.0/0
6. Never store or log the database administrator password
7. DISCOVER BEFORE CREATE — always
8. VERIFY AFTER EVERY STEP — always
9. All write operations require explicit approval
10. No automatic delete or restore

## Prerequisites

| Tool or resource | Required | Purpose |
|---|---:|---|
| hcloud CLI 6.2.9 | Yes | DWS lifecycle operations |
| Huawei Cloud authentication | Yes | API access |
| Target region | Yes | DWS service availability |
| Project context | Yes | Resource scoping |
| VPC, subnet, security group | Yes | Network prerequisites |
| Secure password source | Yes | Database administrator |
| mcp-capability-builder | Yes (shared) | Future MCP design |

## Workflow summary

20 steps: Parse intent → Verify auth → Discover existing → Discover capabilities → Discover network → Capacity/cost plan → Architecture plan → Readiness → Prepare network → Prepare credentials → Create cluster → Poll creation → Verify cluster → Configure public access → Verify connectivity → Create database/schemas → OBS data load → Configure snapshots → Operational validation → Closure

## Automation classification

| Phase | Classification | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Existing discovery | ASSISTED | hcloud DWS ListClusters |
| Capability discovery | ASSISTED | hcloud DWS ListNodeTypes |
| Network discovery | ASSISTED | hcloud VPC commands |
| Capacity planning | AUTOMATED | Logic + pricing MCP |
| Architecture planning | AUTOMATED | Logic |
| Readiness | ASSISTED | Validation checks |
| Network preparation | ASSISTED | huaweicloud-deploy MCP |
| Credential preparation | MANUAL | Secure input |
| Cluster creation | ASSISTED | hcloud DWS CreateCluster (approval required) |
| Polling | AUTOMATED | hcloud DWS ShowClusters |
| Cluster validation | ASSISTED | hcloud DWS ShowClusters |
| EIP binding | ASSISTED | hcloud VPC (approval required) |
| Connectivity | MANUAL | psql/JDBC verification |
| Database/schema | MANUAL | SQL DDL |
| OBS load | MANUAL | External table + INSERT |
| Snapshot policy | ASSISTED | hcloud DWS CreateSnapshot |
| Operational validation | ASSISTED | hcloud DWS Show* |
| Closure | AUTOMATED | Logic |

## hcloud compatibility

- VERIFIED_WITH_HCLOUD_VERSION: 6.2.9
- NEWER_VERSION_VALIDATION_PENDING: 7.2.12
- No compatibility claimed for 7.2.12
- 28+ DWS operations verified from local help

## MCP dependencies

- Required MCPs: None
- Optional: huaweicloud-pricing, huaweicloud-ticket, huaweicloud-deploy
- Required shared skill: mcp-capability-builder

## Capability gap

No dedicated DWS MCP exists. DWS is not in huaweicloud-deploy supported services.

Decision: EXTEND_EXISTING_MCP (target: huaweicloud-deploy)

Core workflow blocker: NO
Orchestration blocker: YES

## Password security

- Never in command line, shell history, logs, or versioned files
- Prefer `--cli-jsonInput` for file-based input
- Temporary file: 0600 permissions, outside repository, secure deletion
- Never include in examples or artifacts

## Approval gates

CreateCluster, DeleteCluster, ResizeCluster, RestartCluster, CreateSnapshot, RestoreCluster, BindEIP, ResetPassword, ChangeSecurityGroup, network creation, database creation, OBS data load

## Outputs

18 artifacts from intent to final report (see [SKILL.md](SKILL.md))

## Known limitations

- No DWS MCP; all operations via hcloud CLI
- DWS not in huaweicloud-deploy; no Terraform generation for DWS
- Node type and storage availability are region-dependent
- PostgreSQL compatibility is partial
- Cluster creation time is variable (10-15 min reference, not SLA)
- hcloud 7.2.12 compatibility not validated

## Troubleshooting

See [docs/known-issues.md](docs/known-issues.md) for the troubleshooting table.

## Maturity status

READY_WITH_WARNINGS — DWS CLI verified, no cloud tests, region-dependent capabilities

## Evidence

- 28+ DWS operations verified from hcloud 6.2.9 local help [VERIFIED_FROM_LOCAL_HELP]
- CreateCluster parameters verified [VERIFIED_FROM_LOCAL_HELP]
- Cluster name, node count, port, username constraints verified [VERIFIED_FROM_LOCAL_HELP]
- No dedicated DWS MCP [VERIFIED_FROM_LOCAL_HELP]
- No cloud-side tests [NOT_VERIFIED]
- Region-dependent capabilities [REGION_DEPENDENT]
