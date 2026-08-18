# DWS MCP Extension Request

## Date

2026-07-28

## Source Skill

huawei-dws-cluster-deployment

## Builder Skill

mcp-capability-builder

## Target

Extend huaweicloud-deploy MCP to support DWS service.

## Priority

1. **Extend huaweicloud-deploy** — Preferred if the model supports adding new services.
2. **Create dedicated DWS MCP** — Only if extension produces incorrect coupling.

## Candidate Read-Only Tools

| Tool | Purpose | Status |
|---|---|---|
| list_dws_clusters | List DWS clusters in region | NOT_IMPLEMENTED |
| show_dws_cluster | Show DWS cluster details | NOT_IMPLEMENTED |
| list_dws_node_types | List available node types | NOT_IMPLEMENTED |
| list_dws_versions | List available engine versions | NOT_IMPLEMENTED |
| list_dws_snapshots | List snapshots for a cluster | NOT_IMPLEMENTED |
| validate_dws_network_prerequisites | Validate VPC/subnet/SG for DWS | NOT_IMPLEMENTED |
| validate_dws_cluster_plan | Validate cluster creation parameters | NOT_IMPLEMENTED |
| estimate_dws_capacity | Estimate capacity for workload | NOT_IMPLEMENTED |

## Candidate Write Tools

| Tool | Purpose | Approval Required | Status |
|---|---|---|---|
| create_dws_cluster | Create DWS cluster | Yes | NOT_IMPLEMENTED |
| bind_dws_eip | Bind EIP to cluster | Yes | NOT_IMPLEMENTED |
| create_dws_snapshot | Create cluster snapshot | Yes | NOT_IMPLEMENTED |
| restore_dws_cluster | Restore from snapshot | Yes | NOT_IMPLEMENTED |
| configure_dws_snapshot_policy | Configure snapshot schedule | Yes | NOT_IMPLEMENTED |
| resize_dws_cluster | Resize cluster (add nodes) | Yes | NOT_IMPLEMENTED |
| restart_dws_cluster | Restart cluster | Yes | NOT_IMPLEMENTED |
| delete_dws_cluster | Delete cluster | Yes | NOT_IMPLEMENTED |

## API Contract Requirements

All tool names are candidates. API contracts require validation against:

1. Official DWS API documentation
2. hcloud CLI DWS operation parameters and responses
3. DWS API version compatibility
4. Region-specific behavior

## Implementation Order

1. Read-only tools (list_*, show_*, validate_*)
2. Write tools with explicit approval gates
3. Mocks for all tools
4. Unit tests
5. Security review
6. Isolated cloud test
7. READY_FOR_REVIEW (do not auto-activate)

## Constraints

- No tool is declared as available until implemented and tested.
- Every write tool requires explicit_approval parameter.
- No secrets in tool parameters or responses.
- All IDs must be validated, not assumed.
- Region-dependent behavior must be handled gracefully.
