---
name: mcp-capability-builder
version: 1.0.0
description: Analyze capability gaps from migration skills and prepare MCP extensions or new MCPs in a controlled, non-executing manner
category: shared
risk_level: low
status: READY_WITH_WARNINGS
requires_explicit_approval: false
---

# Purpose

Analyze capability gaps discovered by migration skills and prepare controlled solutions: either an extension of an existing MCP or a new specialized MCP. This skill NEVER executes cloud operations, publishes code, or activates MCPs.

# Supported scenario

- A migration skill identifies a capability gap that cannot be filled by existing MCP tools
- The gap affects a critical migration phase
- An MCP extension or new MCP is needed to close the gap

# When to use this skill

- When a migration skill reports a capability gap
- When evaluating whether to extend an existing MCP or create a new one
- When designing the contract for a new MCP tool

# When not to use this skill

- When an existing MCP tool can accomplish the task (use existing tool)
- When the gap can be resolved with a manual step (document as MANUAL_STEP)
- When the gap is not on a critical migration path (mark as NOT_REQUIRED)

# Required inputs

- gap_id: Identifier of the capability gap
- skill_name: Name of the requesting migration skill
- phase: Migration phase affected
- required_capability: Description of the required capability
- evaluated_mcps: List of MCPs already evaluated

# Optional inputs

- proposed_tool_contract: Suggested tool name, inputs, outputs
- priority: Critical, High, Medium, Low
- reuse_context: Whether this capability may be needed by other skills

# Required MCPs

None (this skill operates on local files only)

# Optional MCPs

None

# Tool selection policy

- This skill does not call any MCP tools
- All operations are local: analysis, design, code generation, documentation

# Safety and approval gates

1. Generated MCPs are marked as DRAFT or EXPERIMENTAL
2. Generated MCPs are NEVER activated automatically
3. Generated MCPs do NOT use real credentials
4. Generated MCPs do NOT call cloud services
5. Manual review is required before any promotion
6. This skill NEVER publishes code to any repository

# Workflow

## Phase 1 — Receive capability gap

1. Receive gap report from migration skill
2. Validate gap is real (not a naming mismatch)
3. Document gap with ID, skill, phase, capability description

## Phase 2 — Search existing tools

1. Search all available MCPs for equivalent or similar tools
2. Check if tool exists under different name
3. Check if tool can be composed from existing tools
4. If found: Recommend USE_EXISTING_TOOL

## Phase 3 — Evaluate MCP extension

1. Identify which MCP could be extended
2. Evaluate extension complexity and risk
3. Evaluate backward compatibility impact
4. If viable: Recommend EXTEND_EXISTING_MCP

## Phase 4 — Determine if new MCP needed

1. Only if no existing tool and no viable extension
2. Evaluate reusability across skills
3. Evaluate complexity and maintenance burden
4. If justified: Recommend CREATE_NEW_MCP
5. Otherwise: Recommend MANUAL_STEP

## Phase 5 — Design tool contract

1. Define tool name (exact, no ambiguity)
2. Define input schema (JSON Schema)
3. Define output schema (JSON Schema)
4. Classify as read-only or write
5. Define risk level
6. Define side effects
7. Define approval requirements
8. Define expected errors

## Phase 6 — Generate scaffold

1. Create MCP directory structure
2. Generate server.mjs scaffold
3. Generate tool implementation stub
4. Generate package.json
5. Generate .gitignore
6. Generate .env.example (sanitized)

## Phase 7 — Create tests

1. Generate unit test stubs
2. Generate mock data
3. Generate test configuration
4. All tests should be runnable without cloud access

## Phase 8 — Create documentation

1. Generate README.md
2. Generate architecture.md
3. Generate tools-reference.md
4. Generate security-model.md
5. Generate integration.md

## Phase 9 — Security review

1. Verify no hardcoded credentials
2. Verify no 0.0.0.0/0 access patterns
3. Verify write operations require approval
4. Verify secret redaction in outputs
5. Generate security review report

## Phase 10 — Mark for review

1. Mark MCP as DRAFT or EXPERIMENTAL
2. Generate integration instructions (for manual review)
3. Generate promotion checklist
4. Do NOT add to any configuration
5. Do NOT activate in OpenCode

# Capability gap handling

This skill IS the capability gap handler. It does not have its own gaps.

# Output artifacts

- gap-analysis.md — Analysis of the capability gap
- tool-contract.md — Designed tool contract
- mcp-scaffold/ — Generated MCP scaffold (if CREATE_NEW_MCP)
- tests/ — Generated test stubs
- security-review.md — Security review report
- integration-instructions.md — How to integrate (for manual review)
- promotion-checklist.md — Steps to promote to READY

# Failure handling

- Gap already covered by existing tool: Report USE_EXISTING_TOOL with tool name
- Extension not viable: Report reason, recommend MANUAL_STEP or CREATE_NEW_MCP
- New MCP not justified: Report reason, recommend MANUAL_STEP

# Recovery procedure

Not applicable (this skill does not execute operations)

# Evidence and traceability

- Gap analysis documented with evidence
- Decision rationale recorded
- Generated code reviewed for security
- All outputs marked with status (DRAFT/EXPERIMENTAL)

# Known limitations

- Does not execute or test generated MCPs against real services
- Security review is static (no dynamic analysis)
- Integration testing must be done manually
- Promotion requires human judgment

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- Skill operates on local files only (no cloud risk) [VERIFIED_FROM_DESIGN]
- Generated MCPs are never auto-activated [VERIFIED_FROM_DESIGN]
- Security review is included in workflow [VERIFIED_FROM_DESIGN]
- Manual review required for promotion [VERIFIED_FROM_DESIGN]
- Warning: Generated code is not tested against real services [INFERRED]
