# mcp-capability-builder

## Summary

Shared skill that analyzes capability gaps found by migration skills and prepares extensions to existing MCPs or new MCPs in a controlled manner, without executing cloud operations or automatically activating results.

## Problem it solves

Migration skills may discover that current MCPs do not cover all required capabilities. This skill provides a controlled mechanism to close those gaps, either by extending an existing MCP or creating a new one, always with manual review before activation.

## Supported scenario

- A migration skill reports a capability gap
- Alternatives are evaluated: existing tool, extension, new MCP, manual step
- A scaffold is generated with tests and documentation
- It is marked for manual review (never activated automatically)

## Architecture

```
Migration Skill → Gap Report → mcp-capability-builder → Analysis → Decision
                                                        │
                                          ┌─────────────┼─────────────┐
                                          │             │             │
                                   USE_EXISTING   EXTEND_MCP    CREATE_NEW_MCP
                                          │             │             │
                                          │        Scaffold +    Scaffold +
                                          │        Tests +       Tests +
                                          │        Docs         Docs
                                          │             │             │
                                          └─────────────┼─────────────┘
                                                        │
                                                  DRAFT/EXPERIMENTAL
                                                        │
                                                  Manual Review
                                                        │
                                                  Promotion (if approved)
```

## MCPs used

| MCP | Required | Purpose | Read/Write | Risk |
|---|---|---|---|---|
| None | N/A | Local operation only | N/A | None |

## Capabilities

- Capability gap analysis
- Search for equivalent existing tools
- MCP extension evaluation
- Tool contract design
- MCP scaffold generation
- Test and mock generation
- Static security review
- Integration instructions

## General flow

1. Receive gap → 2. Search existing tools → 3. Evaluate extension → 4. Determine if new MCP → 5. Design contract → 6. Generate scaffold → 7. Create tests → 8. Create docs → 9. Security review → 10. Mark for review

## Automation level

| Phase | Status | Responsible |
|---|---|---|
| Receive gap | AUTOMATED | Agent |
| Search existing tools | AUTOMATED | Agent |
| Evaluate extension | ASSISTED | Agent + Human |
| Determine new MCP | ASSISTED | Agent + Human |
| Design contract | AUTOMATED | Agent |
| Generate scaffold | AUTOMATED | Agent |
| Create tests | AUTOMATED | Agent |
| Create docs | AUTOMATED | Agent |
| Security review | AUTOMATED | Agent |
| Mark for review | MANUAL | Human |

## Prerequisites

- None (local operation)

## Inputs

- gap_id: Gap ID
- skill_name: Requesting skill
- phase: Affected phase
- required_capability: Description of the required capability
- evaluated_mcps: MCPs already evaluated

## Outputs

- gap-analysis.md
- tool-contract.md
- mcp-scaffold/ (if CREATE_NEW_MCP)
- tests/
- security-review.md
- integration-instructions.md
- promotion-checklist.md

## Installation

No installation required. This is a local analysis skill.

## Configuration

```json
{
  "skills": {
    "mcp-capability-builder": {
      "path": "<INSTALLATION_ROOT>/shared-skills/mcp-capability-builder"
    }
  }
}
```

## Safe example

```
# Invoked by a migration skill
mcp-capability-builder({
  gap_id: "GAP-CCE-002",
  skill_name: "huawei-cce-cross-region-velero-migration",
  phase: "execution",
  required_capability: "Velero backup/restore operations",
  evaluated_mcps: ["huaweicloud-deploy", "huaweicloud-pricing"]
})

# Possible result:
# Decision: CREATE_NEW_MCP
# New MCP: huaweicloud-velero
# Status: DRAFT
# Requires manual review before activation
```

## Required approvals

- Promotion of generated MCP to READY (requires manual review)
- Integration into OpenCode configuration (requires manual action)

## Validation

- Verify no hardcoded credentials
- Verify no 0.0.0.0/0 patterns
- Verify write operations require approval
- Verify secret redaction in outputs

## Rollback

Not applicable (no operations are executed)

## Security

- Never uses real credentials
- Never calls cloud services
- Never creates resources
- Never modifies infrastructure
- Never auto-activates MCPs
- Security review included in workflow

## Limitations

- Does not test generated MCPs against real services
- Security review is static
- Integration testing must be done manually
- Promotion requires human judgment

## Maturity status

**READY_WITH_WARNINGS**

The skill operates locally without cloud risk. Generated MCPs require manual review.

## Evidence used

| Evidence | Type |
|---|---|
| Local operation without cloud access | VERIFIED_FROM_DESIGN |
| Generated MCPs never auto-activated | VERIFIED_FROM_DESIGN |
| Security review included | VERIFIED_FROM_DESIGN |
| Generated code not tested against real services | INFERRED |
