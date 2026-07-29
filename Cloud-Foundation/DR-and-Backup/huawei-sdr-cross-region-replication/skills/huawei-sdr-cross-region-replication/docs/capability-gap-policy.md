# SDRS Capability Gap Policy

## Overview

This document defines how capability gaps are handled for the SDRS cross-region disaster recovery skill.

## Gap Handling Process

When a capability required for SDRS DR is not available:

1. Document the gap with Gap ID, phase, impact, and evidence classification
2. Classify the gap: critical path or optional
3. Evaluate alternatives:
   - USE_EXISTING_TOOL: An existing MCP tool can accomplish the task
   - EXTEND_EXISTING_MCP: An existing MCP can be extended to support the task
   - CREATE_NEW_MCP_CANDIDATE: A new MCP is needed (last resort)
   - MANUAL_CONSOLE: The step can be performed manually via console
   - FUTURE_MCP_CAPABILITY: The step is documented for future MCP implementation
   - REGION_DEPENDENT: The capability varies by region
4. Invoke mcp-capability-builder for gaps requiring CREATE_NEW_MCP_CANDIDATE
5. Update skill status if critical gaps remain unresolved
6. Never auto-activate generated MCPs

## Known Capability Gaps

| Gap ID | Description | Phase | Impact | Decision | Evidence |
|---|---|---|---|---|---|
| GAP-SDR-001 | No SDRS CLI support in hcloud 6.2.9 | All | Critical: all SDRS operations are manual | MANUAL_CONSOLE | NOT_AVAILABLE |
| GAP-SDR-002 | No SDRS MCP exists | All | Critical: no automation possible | CREATE_NEW_MCP_CANDIDATE | NOT_AVAILABLE |
| GAP-SDR-003 | Failover/reprotection/failback have no automation safeguard | Execution | Critical: human error risk | MANUAL_CONSOLE | NOT_AVAILABLE |
| GAP-SDR-004 | Replication monitoring requires manual console checks | Monitoring | High: delayed issue detection | MANUAL_CONSOLE | NOT_AVAILABLE |
| GAP-SDR-005 | SDRS not in huaweicloud-deploy supported services | Planning | Medium: no Terraform for SDRS | EXTEND_EXISTING_MCP | VERIFIED_FROM_CODE |
| GAP-SDR-006 | Region pair support must be verified manually | Readiness | Medium: may discover late | REGION_DEPENDENT | REGION_DEPENDENT |
| GAP-SDR-007 | DR gateway installation is manual | Execution | High: error-prone manual process | MANUAL_CONSOLE | NOT_AVAILABLE |

## Automation Impact

| Workflow | Core manual blocker | Automated workflow blocker |
|---|---|---|
| Discovery | No (hcloud CLI works for related resources) | No |
| Planning | No (logic-based) | No |
| Readiness | No (checklist) | No |
| Gateway setup | Yes (manual console) | Yes |
| Protection configuration | Yes (manual console) | Yes |
| Replication monitoring | Partial (manual console checks) | Yes |
| DR drill | Yes (manual console) | Yes |
| Failover | Yes (manual console, CRITICAL) | Yes |
| Reverse reprotection | Yes (manual console) | Yes |
| Failback | Yes (manual console, CRITICAL) | Yes |

## MCP Design Recommendation

When the user requests SDRS automation, invoke mcp-capability-builder to design a dedicated SDRS MCP. See docs/sdrs-mcp-capability-request.md for the proposed tool candidates.

## Decision: CREATE_NEW_MCP_CANDIDATE

A dedicated SDRS MCP is the recommended long-term solution. However:
- Do NOT generate functional MCP code in this skill
- Do NOT auto-activate any generated MCP
- Mark all candidate tools as NOT_IMPLEMENTED
- Require API contract validation before implementation
