---
name: maas-spec-plan-build-test-skill
description: Use this skill when executing the Spec to Plan to Build to Test engineering workflow with gated phase transitions and human review between phases. TRIGGER when the user needs to implement a feature from requirements, validate a plan before coding, enforce build standards, generate tests from specifications, or run the full Spec-Plan-Build-Test cycle with evidence at each gate.
---

# MaaS Spec-Plan-Build-Test Skill

## Overview

The Spec-Plan-Build-Test workflow is the core engineering discipline. Each phase produces artifacts that the next phase consumes. Each phase transition requires a gate check. Human review is required between Plan and Build (the highest-risk transition). MaaS-backed agents assist at each phase but do not skip gates.

## When to Use

| Situation | Route |
|-----------|-------|
| New feature from requirements | Full workflow: Spec -> Plan -> Build -> Test |
| Validate existing plan | Run Plan phase gate only |
| Build from approved plan | Run Build phase (plan must be approved) |
| Generate tests for existing code | Run Test phase only |
| Spec refinement (grilling) | Run Spec phase with `--grill` flag |
| Requirements doc to code | Full workflow starting from Spec |

**When NOT to use:**
- One-line bug fixes (just fix and test)
- Documentation-only changes
- Configuration changes with no code impact
- Emergency hotfixes (fix first, spec later)

## Core Pattern

```
Requirements
  -> [Spec Phase] -> specification.md
  -> Gate: Spec complete? (clarity, no ambiguity, testable criteria)
  -> [Plan Phase] -> plan.md
  -> Gate: Plan approved? (HUMAN REVIEW MANDATORY)
  -> [Build Phase] -> code + implementation.md
  -> Gate: Build passes quality gates? (lint + compile)
  -> [Test Phase] -> test-results.md
  -> Gate: All tests pass + coverage met?
  -> Ship
```

## Phase Definitions

### Spec Phase

- **Input**: Requirements (user story, issue, document)
- **Process**: MaaS agent analyzes requirements, identifies ambiguities, states assumptions, produces specification
- **Output**: `specification.md` with: problem statement, success criteria (verifiable), assumptions, constraints, out-of-scope
- **Gate**: Every success criterion is testable. No ambiguous language ("should", "might", "if possible").
- **Grilling pattern**: Challenge the spec by asking "What if X fails?", "What happens at boundary Y?", "How do you verify Z?"

### Plan Phase

- **Input**: Approved specification
- **Process**: MaaS agent designs solution, identifies files to change, estimates complexity, produces plan
- **Output**: `plan.md` with: approach, files affected, change description per file, dependencies, risk assessment, rollback strategy
- **Gate**: Plan is reviewed and approved by human. **No auto-approval.**
- **Vertical slicing**: One test -> one implementation -> repeat. Not all tests then all implementation.

### Build Phase

- **Input**: Approved plan
- **Process**: MaaS agent implements changes following surgical discipline
- **Output**: Code changes + `implementation.md`
- **Gate**: Code passes lint and compiles. Quality gate from `maas-ai-coding-quality-skill` runs.
- **Surgical changes**: Touch only what you must. Match existing style. No speculative features.

### Test Phase

- **Input**: Built code + specification success criteria
- **Process**: MaaS agent generates tests, runs test suite, measures coverage
- **Output**: `test-results.md` with: pass/fail per test, coverage %, uncovered paths
- **Gate**: All tests pass. Coverage meets threshold. No skipped tests without documented reason.

## Anti-Rationalization Table

See [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md) for universal entries. Skill-specific:

| Excuse | Rebuttal |
|--------|----------|
| "The spec is clear enough, let's just start coding" | Unclear specs produce unclear code. Write the spec first. |
| "I don't need a plan for this small change" | Small changes in complex systems have large blast radius. Plan the change. |
| "The human can review after I build" | Post-hoc review is approval theater. Review the plan before building. |
| "I'll write tests after the implementation" | Test-after produces tests that verify the implementation, not the specification. Write tests from the spec. |
| "This feature might be needed later" | Speculative code is dead code. Implement only what the spec requires. |
| "The plan doesn't need a rollback strategy" | Every change can fail. If you can't roll back, you can't ship. |

## Quick Reference

| Phase | Command | Gate |
|-------|---------|------|
| Spec | `scripts/run-spec-phase.sh` | All criteria testable |
| Plan | `scripts/run-plan-phase.sh` | Human approval |
| Build | `scripts/run-build-phase.sh` | Lint + compile pass |
| Test | `scripts/run-test-phase.sh` | All pass + coverage met |
| Full | `scripts/run-full-workflow.sh` | All gates |

## Implementation

1. Gather requirements into a requirements document
2. Run Spec phase: `scripts/run-spec-phase.sh --input=requirements.md`
3. Review specification, resolve ambiguities, approve spec
4. Run Plan phase: `scripts/run-plan-phase.sh --spec=specification.md`
5. **Human reviews and approves plan (mandatory)**
6. Run Build phase: `scripts/run-build-phase.sh --plan=plan.md`
7. Quality gate runs automatically (lint + compile)
8. Run Test phase: `scripts/run-test-phase.sh --spec=specification.md`
9. All gates pass -> ship

## Verification Exit Criteria

- [ ] Specification exists with testable success criteria
- [ ] Specification has no ambiguous language
- [ ] Plan exists and has been approved by human
- [ ] Plan includes rollback strategy
- [ ] Code compiles and passes lint
- [ ] Quality gate from `maas-ai-coding-quality-skill` passes
- [ ] All tests pass
- [ ] Coverage meets threshold
- [ ] No skipped tests without documented reason
- [ ] Phase artifacts exist: specification.md, plan.md, implementation.md, test-results.md

## Common Mistakes

- Skipping the Plan phase human review ("the plan looks fine")
- Writing all implementation then all tests (vertical slice instead)
- Including speculative features "while we're here"
- Not documenting assumptions in the spec
- Auto-approving the plan gate
- Treating test failures as "test issues" rather than "specification issues"
- Not running the quality gate after build
- Running the full workflow without checking intermediate gate results

## Cross-Skill References

- Build phase gate delegates to [maas-ai-coding-quality-skill](../maas-ai-coding-quality-skill/) for lint + compile + coverage
- Pre-merge review delegates to [maas-code-review-and-security-skill](../maas-code-review-and-security-skill/) for security audit
- Legacy code changes delegate to [maas-legacy-code-migration-skill](../maas-legacy-code-migration-skill/) for behavior preservation
- Testing checklist: [../shared/references/testing-checklist.md](../shared/references/testing-checklist.md)
- Anti-rationalization table: [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md)
