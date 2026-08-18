# Capability Gap Policy

When a capability required for PostgreSQL ECS-to-RDS migration is not available:

1. **Document the gap**: Record in capability-gap-report.md with Gap ID, phase, and impact
2. **Classify the gap**: Determine if it affects a critical path or is optional
3. **Evaluate alternatives**:
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL
   - Can an existing MCP be extended? → EXTEND_EXISTING_MCP
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort)
   - Can the step be performed manually? → MANUAL_STEP
4. **Invoke mcp-capability-builder**: For gaps requiring EXTEND_EXISTING_MCP or CREATE_NEW_MCP
5. **Update skill status**: If critical gaps remain unresolved, status remains READY_WITH_WARNINGS
6. **Never auto-activate**: Generated MCPs require manual review and approval
