# Phase Gate Criteria

## Spec Phase Gate

**Auto-approve**: Yes (can be overridden with `--grill` flag)

**Pass criteria**:
- [ ] Specification document exists
- [ ] Problem statement is clear and unambiguous
- [ ] Every success criterion is testable (no "should", "might", "if possible")
- [ ] Assumptions are explicitly stated
- [ ] Constraints are documented
- [ ] Out-of-scope items are listed
- [ ] Test scenarios cover happy path, edge cases, and error paths

**Grilling questions** (when `--grill` flag is used):
- What if this dependency is unavailable?
- What happens at the boundary of this constraint?
- How do you verify this success criterion?
- What is the rollback if this fails?
- Are there regulatory/compliance requirements?

## Plan Phase Gate

**Auto-approve**: **No — human review is mandatory**

**Pass criteria**:
- [ ] Plan document exists
- [ ] Approach is clearly described
- [ ] All affected files are listed with actions (create/modify/delete)
- [ ] Change description per file is specific
- [ ] Dependencies are identified
- [ ] Risk assessment is complete (likelihood + impact + mitigation)
- [ ] Rollback strategy is documented
- [ ] Vertical slice order is defined
- [ ] **Human has reviewed and approved** (sign-off required)

**Why human review is mandatory**: The Plan phase is the highest-risk transition. An incorrect plan leads to wasted implementation effort. Human judgment is required to validate approach, assess risks, and approve the scope.

## Build Phase Gate

**Auto-approve**: Yes (quality gate is automated)

**Pass criteria**:
- [ ] Code compiles without errors
- [ ] Linter passes (0 warnings, 0 errors)
- [ ] All changed files are listed in the plan
- [ ] No speculative features added
- [ ] Commit messages follow convention
- [ ] Quality gate from `maas-ai-coding-quality-skill` passes

**Quality gate sequence**:
1. Lint (Gate 1)
2. Compile (implicit in lint for compiled languages)
3. Coverage (Gate 3 — may be partial; full coverage checked in Test phase)

## Test Phase Gate

**Auto-approve**: Yes (tests are automated)

**Pass criteria**:
- [ ] All tests pass (0 failures)
- [ ] Coverage meets language-specific threshold
- [ ] No skipped tests without documented reason and issue reference
- [ ] Test results document exists with pass/fail per test
- [ ] Coverage report exists with percentage and uncovered paths
- [ ] Edge cases are tested
- [ ] Error paths are tested

**Failure handling**:
- Test failure = specification failure (not "test issue")
- Investigate: is the test wrong, or is the implementation wrong?
- If the test is wrong: update the test AND the specification
- If the implementation is wrong: fix the implementation
- Never delete a failing test to make the suite pass
