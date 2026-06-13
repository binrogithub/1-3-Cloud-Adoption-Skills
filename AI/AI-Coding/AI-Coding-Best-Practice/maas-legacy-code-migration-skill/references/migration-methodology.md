# Migration Methodology

## Phase 1: Understand

**Goal**: Produce a complete understanding document for the legacy codebase.

**Steps**:
1. Run `scripts/analyze-legacy.sh --language=<lang> --path=<dir>`
2. MaaS agent reads each source file and produces:
   - Purpose and responsibility of the file
   - Dependencies (imports, calls, data access)
   - Business logic encoded in the file
   - Complexity estimate (lines, branches, dependencies)
3. Aggregate into understanding document
4. Human reviews understanding document for accuracy

**Entry criteria**: Access to legacy source code
**Exit criteria**: Understanding document exists and has been reviewed by human

## Phase 2: Characterize

**Goal**: Pin current behavior with characterization tests.

**Steps**:
1. Identify critical paths (from understanding document)
2. For each critical path:
   - Identify inputs and outputs
   - Generate characterization test: call code with known inputs, assert outputs
   - Run test against original code (must pass)
3. Document paths that cannot be characterized (and why)
4. Get human sign-off on uncharacterized paths

**Entry criteria**: Understanding document exists
**Exit criteria**: Characterization tests pass on original code; uncharacterized paths documented and signed off

## Phase 3: Plan

**Goal**: Identify migration targets and group into batches.

**Steps**:
1. Run `scripts/plan-migration.sh --analysis=<understanding-doc>`
2. MaaS agent identifies:
   - Migration targets (files/modules that need to change)
   - Dependencies between targets (must migrate together)
   - Batch groupings (5-10 files per batch, respecting dependencies)
   - Migration order (leaf modules first, core modules last)
   - Risk per batch (high/medium/low based on complexity and test coverage)
3. Human reviews and approves migration plan

**Entry criteria**: Characterization tests exist
**Exit criteria**: Migration plan exists with batch groupings and has been approved by human

## Phase 4: Transform

**Goal**: Execute migration in reviewable batches.

**Steps** (for each batch):
1. Run `scripts/run-batch-transform.sh --batch-number=N`
2. MaaS agent transforms files in the batch
3. Run characterization tests against transformed code
4. If characterization tests fail:
   - Investigate: is the behavior change intentional?
   - If intentional: update characterization test and document
   - If unintentional: revert the change and fix
5. Run quality gate from `maas-ai-coding-quality-skill`
6. Run code review from `maas-code-review-and-security-skill`
7. Create PR for batch
8. Wait for CI to pass
9. Wait for human review
10. Merge or fix
11. Record in `done.list`

**Entry criteria**: Migration plan approved; previous batch merged
**Exit criteria**: Batch merged; `done.list` updated; characterization tests pass

## Phase 5: Verify

**Goal**: Confirm all behavior is preserved after full migration.

**Steps**:
1. Run all characterization tests against fully migrated codebase
2. Compare before/after behavior for any differences
3. Run full test suite (unit + integration + e2e)
4. Run security audit
5. Performance benchmark against original

**Entry criteria**: All batches merged
**Exit criteria**: All characterization tests pass; no unexpected behavior differences; full test suite green

## Phase 6: Document

**Goal**: Record migration decisions, gaps, and remaining tech debt.

**Steps**:
1. Document all migration decisions made during transform phase
2. Document behavior differences (intentional changes)
3. Document remaining tech debt (things not migrated)
4. Document rollback points (which commit to revert to for each batch)
5. Update README and architecture docs

**Entry criteria**: Verification phase complete
**Exit criteria**: Migration documentation complete and reviewed
