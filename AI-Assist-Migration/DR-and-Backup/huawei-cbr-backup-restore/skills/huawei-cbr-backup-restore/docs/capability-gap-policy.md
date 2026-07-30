# Capability Gap Policy

## Gap: No dedicated CBR MCP

**Decision**: USE_HCLOUD_CLI

**Core blocker**: NO

**Impact**: All CBR operations require supervised CLI execution. Phases are ASSISTED rather than AUTOMATED. Error handling and retry logic must be implemented in the skill workflow rather than in an MCP.

## Gap Resolution Process

When a capability required for CBR backup/restore is not available in existing MCPs:

1. **Document the gap**: Record with Gap ID, phase, and impact
2. **Classify the gap**: Critical path or optional
3. **Evaluate alternatives**:
   - Can the step be performed via hcloud CLI? → USE_HCLOUD_CLI (preferred)
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL
   - Can an existing MCP be extended? → EXTEND_EXISTING_MCP
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort)
4. **Invoke mcp-capability-builder**: For gaps requiring EXTEND_EXISTING_MCP or CREATE_NEW_MCP
5. **Update skill status**: If critical gaps remain unresolved, status remains READY_WITH_WARNINGS
6. **Never auto-activate**: Generated MCPs require manual review and approval

## Known Gaps

| Gap ID | Description | Phase | Decision |
|---|---|---|---|
| GAP-CBR-001 | No dedicated CBR MCP; all operations via hcloud CLI | all | USE_HCLOUD_CLI |
| GAP-CBR-002 | CBR not in huaweicloud-deploy supported services | plan_generation | EXTEND_EXISTING_MCP |
| GAP-CBR-003 | hcloud CLI lacks structured error handling and retry logic | execution | USE_HCLOUD_CLI |
| GAP-CBR-004 | Cross-region copy capability varies by region | execution | REGION_DEPENDENT |
| GAP-CBR-005 | Agent-based backup requires agent verification via CLI | readiness | USE_HCLOUD_CLI |

## Future Options

- **EXTEND_EXISTING_MCP**: Add CBR support to huaweicloud-deploy MCP for Terraform generation (GAP-CBR-002).
- **CREATE_CBR_MCP**: Build a dedicated CBR MCP only if a reusable automation gap is confirmed through repeated manual operations. This is a future option and must NOT be initiated during this prompt.

## Constraints

- Do NOT generate a new MCP during this prompt.
- Do NOT declare CBR MCP support that does not exist.
- Do NOT block the workflow on optional MCP availability.
- All optional MCPs (pricing, ticket, deploy) are non-blocking.
