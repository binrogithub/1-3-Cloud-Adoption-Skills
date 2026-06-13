# Batch Transform Pattern

## Overview

The reviewable batch pattern from awesome-codex-skills. Each migration is broken into small, reviewable batches. Each batch produces a separate PR that must pass CI and human review before the next batch begins.

## Batch Sizing Strategy

| Codebase Size | Batch Size | Rationale |
|---------------|:---:|-----------|
| < 50 files | 5 | Small codebase; small batches for precision |
| 50-200 files | 10 | Medium codebase; balance speed and reviewability |
| 200-500 files | 10 | Large codebase; keep batches small for risk control |
| > 500 files | 10 | Very large; never exceed 10 files per batch |

**Never** exceed 15 files per batch. Large batches hide failures.

## Batch Grouping Rules

1. **Dependency-respecting**: If file A depends on file B, they must be in the same batch or B's batch must come first
2. **Cohesion**: Files that change together should be in the same batch
3. **Risk-balanced**: Mix high-risk and low-risk files in each batch (don't put all risky files in one batch)
4. **Testable**: Each batch must be independently testable (characterization tests cover all changes)

## PR Template per Batch

```markdown
## Migration Batch N: [Description]

### Files Changed
- [file1] - [what changed]
- [file2] - [what changed]

### Characterization Tests
- [x] All characterization tests pass
- [ ] Behavior differences documented below

### Behavior Differences
(None / List any intentional behavior changes)

### Quality Gate
- [x] Lint passes
- [x] Tests pass
- [x] Coverage meets threshold
- [x] Security scan clean

### Rollback
Revert this commit to rollback batch N.
```

## CI Requirements per Batch

- Lint: must pass
- Unit tests: must pass
- Characterization tests: must pass
- Coverage: must not decrease from previous batch
- Security scan: no new critical/high findings

## Merge Criteria

1. CI is green (all checks pass)
2. At least one human review approval
3. No unresolved comments
4. Characterization tests pass (verified in CI)
5. No behavior differences without documentation

## Rollback Procedure

If a batch causes issues after merge:

1. `git revert <batch-commit>` — revert the specific batch
2. Run characterization tests against reverted codebase
3. If characterization tests pass: rollback successful
4. If characterization tests fail: investigate (may need to revert multiple batches)
5. Document the rollback reason and fix before re-attempting

## Done Tracking

The `done.list` file records completed files:

```
# Migration done.list
# Format: <file-path> <batch-number> <commit-hash>
src/auth/handler.py 1 abc1234
src/auth/token.py 1 abc1234
src/api/router.py 2 def5678
```

On re-run after failure, `run-batch-transform.sh` skips files already in `done.list`.

## Stop-on-Failure

When a batch fails:
- **Do NOT** continue to the next batch
- **Do NOT** mark the batch as done
- Fix the failure in the current batch
- Re-run the batch (skipping already-done files)
- Only proceed to the next batch after the current one succeeds

This is non-negotiable. Continue-on-error is forbidden in legacy migration.
