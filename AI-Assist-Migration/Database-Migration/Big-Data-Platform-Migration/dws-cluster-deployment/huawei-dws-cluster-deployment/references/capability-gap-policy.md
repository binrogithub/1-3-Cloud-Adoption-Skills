# DWS Cluster Deployment Capability Gap Policy

## Gap Summary

No dedicated DWS MCP exists and DWS is not in huaweicloud-deploy supported services.

## Decision

EXTEND_EXISTING_MCP

## Target

huaweicloud-deploy

## Core Workflow Blocker

NO — The core workflow operates via hcloud DWS CLI.

## Orchestration Blocker

YES — Automated infrastructure orchestration (Terraform) for DWS is not possible with the current MCP.

## Impact

DWS lifecycle operations use supervised hcloud CLI instead of MCP tools. This means:
- No structured error handling
- No built-in retry logic
- No type-safe parameter validation
- No automatic state management
- Manual polling for async operations

## Known Gaps

| Gap ID | Description | Decision |
|---|---|---|
| GAP-DWS-001 | No dedicated DWS MCP; all DWS operations via hcloud CLI | USE_HCLOUD_CLI |
| GAP-DWS-002 | DWS not in huaweicloud-deploy supported services | EXTEND_EXISTING_MCP |
| GAP-DWS-003 | hcloud CLI operations lack structured error handling and retry logic | USE_HCLOUD_CLI |
| GAP-DWS-004 | Node type availability varies by region | REGION_DEPENDENT |
| GAP-DWS-005 | Storage type availability varies by region | REGION_DEPENDENT |
| GAP-DWS-006 | Password handling in CLI is a security concern | SECURE_INPUT_REQUIRED |
| GAP-DWS-007 | Cluster creation time is variable and not SLA-guaranteed | POLLING_REQUIRED |

## Promotion Requirements

To promote DWS support in huaweicloud-deploy or a dedicated DWS MCP:

1. Verify official DWS API contracts
2. Add DWS to supported-services.json (if extending huaweicloud-deploy)
3. Implement read-only tools first:
   - list_dws_clusters
   - show_dws_cluster
   - list_dws_node_types
   - list_dws_versions
   - list_dws_snapshots
   - validate_dws_network_prerequisites
   - validate_dws_cluster_plan
   - estimate_dws_capacity
4. Add write tools with explicit approval:
   - create_dws_cluster
   - bind_dws_eip
   - create_dws_snapshot
   - restore_dws_cluster
   - configure_dws_snapshot_policy
   - resize_dws_cluster
   - restart_dws_cluster
   - delete_dws_cluster
5. Add mocks for all tools
6. Add unit tests
7. Run security review
8. Run isolated cloud test
9. Mark READY_FOR_REVIEW
10. Do NOT activate automatically

## MCP Extension Design

See [docs/dws-mcp-extension-request.md](dws-mcp-extension-request.md) for the detailed extension proposal.

## Alternative: Dedicated DWS MCP

Create a dedicated DWS MCP only if extending huaweicloud-deploy produces incorrect coupling or incompatible contracts. This is the secondary option.
