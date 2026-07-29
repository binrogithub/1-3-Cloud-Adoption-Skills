# Capability Analysis Methodology

## Gap Classification

| Level | Description | Action |
|---|---|---|
| Critical | Blocks migration progression | Must resolve before migration |
| High | Significant manual effort required | Should resolve if possible |
| Medium | Workaround available | Resolve when convenient |
| Low | Nice to have | Document for future |

## Decision Tree

1. Can an existing MCP tool accomplish the task?
   → YES: USE_EXISTING_TOOL
   → NO: Continue

2. Can existing tools be composed to accomplish the task?
   → YES: USE_EXISTING_TOOL (composition)
   → NO: Continue

3. Can an existing MCP be extended with a new tool?
   → YES and low risk: EXTEND_EXISTING_MCP
   → YES but high risk: Evaluate further
   → NO: Continue

4. Is the capability reusable across multiple skills?
   → YES: CREATE_NEW_MCP (shared-mcps/)
   → NO: Continue

5. Is the capability specific to one skill?
   → YES: CREATE_NEW_MCP (skills/<skill>/generated-mcps/)
   → NO: MANUAL_STEP

6. Can the step be performed manually with acceptable effort?
   → YES: MANUAL_STEP
   → NO: BLOCKED
